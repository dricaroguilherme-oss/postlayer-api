from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, get_membership
from app.api.dependencies.db import get_session
from app.application.presets.social import SOCIAL_FORMAT_PRESETS
from app.application.services.versioning import next_project_version_number
from app.domain.brand.models import Brand, BrandAsset, DesignComponent
from app.domain.common.types import JobStatus, ProjectStatus, ProjectVersionSourceType
from app.domain.creative.models import CreativePage, CreativeProject, ExportJob, ProjectVersion
from app.domain.template.models import LayoutTemplate
from app.export_engine.manifest import build_export_manifest
from app.export_engine.service import ExportEngine
from app.orchestration.langgraph.service import build_orchestration_service
from app.rendering.svg_renderer import SvgLayoutRenderer
from app.schemas.brand import BrandAssetRead, DesignComponentRead
from app.schemas.creative import (
    CreativePagePayload,
    CreativePageRead,
    CreativeProjectBundle,
    CreativeProjectListResponse,
    CreativeProjectPayload,
    CreativeProjectRead,
    ExportJobPayload,
    ExportJobRead,
    ProjectVersionRead,
)
from app.schemas.memory import AcceptMemorySuggestionPayload, AcceptMemorySuggestionResponse
from app.schemas.orchestration import (
    OrchestrateProjectPayload,
    PageEditPayload,
    ReorderProjectPagesPayload,
    WorkflowRunResponse,
)
from app.schemas.templates import ApplyProjectTemplatePayload, LayoutTemplateRead, SaveProjectTemplatePayload

router = APIRouter(prefix="/v1/projects", tags=["v1-projects"])


def _page_roles(page_count: int, piece_type: str) -> list[str]:
    if page_count <= 1:
        return ["cover"]
    roles = ["cover"]
    if piece_type == "carousel" and page_count > 2:
        roles.extend(["body"] * (page_count - 2))
    elif page_count > 2:
        roles.extend(["body"] * (page_count - 2))
    roles.append("cta")
    return roles


def _project_or_404(session: Session, project_id: UUID) -> CreativeProject:
    project = session.get(CreativeProject, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _project_pages(session: Session, project_id: UUID) -> list[CreativePage]:
    return list(
        session.scalars(
            select(CreativePage).where(CreativePage.project_id == project_id).order_by(CreativePage.page_index.asc())
        )
    )


def _render_tree_from_pages(pages: list[CreativePage]) -> dict:
    return {
        "pages": [
            {
                "page_index": page.page_index,
                "page_role": page.page_role,
                **page.layout_json,
            }
            for page in pages
        ]
    }


def _persist_user_version(
    session: Session,
    project: CreativeProject,
    *,
    source_type: str,
    strategy_json: dict,
    pages: list[CreativePage],
) -> ProjectVersion:
    version = ProjectVersion(
        project_id=project.id,
        version_number=next_project_version_number(session, project.id),
        source_type=source_type,
        strategy_json=strategy_json,
        art_direction_json={},
        render_tree_json=_render_tree_from_pages(pages),
        exported_assets_json={},
    )
    session.add(version)
    session.flush()
    project.current_version_id = version.id
    return version


def _reindex_pages(session: Session, ordered_pages: list[CreativePage]) -> list[CreativePage]:
    offset = len(ordered_pages) + 1
    for index, page in enumerate(ordered_pages):
        page.page_index = index + offset
        if page.layout_json:
            page.layout_json = {**page.layout_json, "page_index": index + offset}
    session.flush()

    for index, page in enumerate(ordered_pages):
        page.page_index = index
        if page.layout_json:
            page.layout_json = {**page.layout_json, "page_index": index}
    session.flush()
    return ordered_pages


def _serialize_project_bundle(session: Session, project: CreativeProject) -> CreativeProjectBundle:
    pages = _project_pages(session, project.id)
    versions = session.scalars(
        select(ProjectVersion).where(ProjectVersion.project_id == project.id).order_by(ProjectVersion.version_number.desc())
    ).all()
    return CreativeProjectBundle(
        project=CreativeProjectRead.model_validate(project),
        pages=[CreativePageRead.model_validate(page) for page in pages],
        versions=[ProjectVersionRead.model_validate(version) for version in versions],
    )


def _export_job_or_404(session: Session, project_id: UUID, export_job_id: UUID) -> ExportJob:
    export_job = session.get(ExportJob, export_job_id)
    if export_job is None or export_job.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found")
    return export_job


def _project_slug(project: CreativeProject) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", project.title.lower()).strip("-")
    return slug or "postlayer-project"


def _page_file_name(project: CreativeProject, version_number: int, page_index: int, extension: str) -> str:
    return f"{_project_slug(project)}-v{version_number:02d}-page-{page_index + 1}.{extension}"


def _archive_file_name(project: CreativeProject, version_number: int, extension: str) -> str:
    return f"{_project_slug(project)}-v{version_number:02d}-{extension}-batch.zip"


def _render_export_pages(
    *,
    version: ProjectVersion,
    file_type: str,
    dpi: int,
    page_index: int | None = None,
) -> dict:
    pages = sorted(list(version.render_tree_json.get("pages", [])), key=lambda page: int(page.get("page_index", 0)))
    if page_index is not None:
        pages = [page for page in pages if int(page.get("page_index", -1)) == page_index]
        if not pages:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export page not found")
    if not pages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project version has no renderable pages")
    renderer = SvgLayoutRenderer()
    engine = ExportEngine(renderer)
    return engine.export({"pages": pages, "file_type": file_type, "dpi": dpi})


def _project_safe_zone(project: CreativeProject) -> dict[str, int]:
    return dict(SOCIAL_FORMAT_PRESETS.get(project.format_type, {}).get("safe_zone", {"top": 72, "right": 72, "bottom": 72, "left": 72}))


def _extract_template_regions(page: CreativePage) -> list[dict[str, int | str]]:
    layout = page.layout_json if isinstance(page.layout_json, dict) else {}
    nodes = list(layout.get("nodes", []))

    def first_node(predicate):
        for node in nodes:
            if predicate(node):
                return node
        return None

    slot_candidates = {
        "heading": first_node(lambda node: node.get("type") == "heading"),
        "body": first_node(lambda node: node.get("id", "").startswith("body-") or node.get("type") == "paragraph"),
        "cta": first_node(lambda node: node.get("id", "").startswith(("cta-bg", "cta-label")) or node.get("type") == "cta"),
        "media": first_node(lambda node: node.get("id", "").startswith(("media-", "decorative-graphic")) or node.get("type") == "image"),
        "progression": first_node(lambda node: node.get("id", "").startswith(("slide-index-bg", "slide-index"))),
    }

    regions: list[dict[str, int | str]] = []
    for slot, node in slot_candidates.items():
        if not node:
            continue
        regions.append(
            {
                "slot": slot,
                "x": int(node.get("x", 0)),
                "y": int(node.get("y", 0)),
                "width": int(node.get("width", 0)),
                "height": int(node.get("height", 0)),
            }
        )
    return regions


def _template_preview_layout(project: CreativeProject, page: CreativePage, template: LayoutTemplate) -> dict:
    dimensions = project.dimensions_json or {}
    width = int(dimensions.get("width", 1080))
    height = int(dimensions.get("height", 1080))
    safe_zone = _project_safe_zone(project)
    regions = list((template.schema_json or {}).get("regions", []))
    nodes: list[dict] = [
        {
            "id": f"template-background-{page.page_index}",
            "type": "background",
            "x": 0,
            "y": 0,
            "width": width,
            "height": height,
            "z_index": 0,
            "style": {"backgroundColor": "#F8FAFC", "opacity": 1},
            "children": [],
        }
    ]

    for index, region in enumerate(regions):
        slot = str(region.get("slot", f"region-{index}"))
        x = int(region.get("x", safe_zone["left"]))
        y = int(region.get("y", safe_zone["top"]))
        region_width = int(region.get("width", width - safe_zone["left"] - safe_zone["right"]))
        region_height = int(region.get("height", 120))
        nodes.extend(
            [
                {
                    "id": f"template-slot-{page.page_index}-{slot}",
                    "type": "shape",
                    "x": x,
                    "y": y,
                    "width": region_width,
                    "height": region_height,
                    "z_index": 10 + index * 2,
                    "style": {"backgroundColor": "#2563EB", "borderRadius": 24, "opacity": 0.12},
                    "children": [],
                },
                {
                    "id": f"template-label-{page.page_index}-{slot}",
                    "type": "paragraph",
                    "x": x + 20,
                    "y": y + 16,
                    "width": max(80, region_width - 40),
                    "height": min(48, region_height - 24),
                    "z_index": 11 + index * 2,
                    "style": {"color": "#1D4ED8", "fontSize": 22, "fontWeight": 700, "fontFamily": "DM Sans"},
                    "content": {"text": slot.replace("_", " ").title()},
                    "children": [],
                },
            ]
        )

    return {
        "page_index": page.page_index,
        "page_role": page.page_role,
        "width": width,
        "height": height,
        "safe_zone": safe_zone,
        "template_id": str(template.id),
        "template_schema": template.schema_json,
        "nodes": nodes,
    }


def _template_or_404(session: Session, tenant_id: UUID, template_id: UUID) -> LayoutTemplate:
    template = session.get(LayoutTemplate, template_id)
    if template is None or (template.tenant_id not in {None, tenant_id} and not template.is_system_template):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return template


@router.post("", response_model=CreativeProjectBundle, status_code=status.HTTP_201_CREATED)
def create_project(
    tenant_id: UUID,
    payload: CreativeProjectPayload,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CreativeProjectBundle:
    get_membership(user["id"], str(tenant_id))
    project = CreativeProject(
        tenant_id=tenant_id,
        brand_id=payload.brand_id,
        title=payload.title,
        channel=payload.channel,
        format_type=payload.format_type,
        piece_type=payload.piece_type.value if hasattr(payload.piece_type, "value") else str(payload.piece_type),
        dimensions_json=payload.dimensions_json,
        objective=payload.objective,
        audience=payload.audience,
        language=payload.language,
        cta=payload.cta,
        page_count=payload.page_count,
        user_prompt=payload.user_prompt,
        status=payload.status,
        created_by=user["id"],
    )
    session.add(project)
    session.flush()

    for index, role in enumerate(_page_roles(payload.page_count, project.piece_type)):
        session.add(
            CreativePage(
                project_id=project.id,
                page_index=index,
                page_role=role,
                content_plan_json=CreativePagePayload(page_index=index, page_role=role).content_plan_json,
                layout_json=CreativePagePayload(page_index=index, page_role=role).layout_json,
                review_json=CreativePagePayload(page_index=index, page_role=role).review_json,
            )
        )

    session.commit()
    session.refresh(project)
    return _serialize_project_bundle(session, project)


@router.get("", response_model=CreativeProjectListResponse)
def list_projects(
    tenant_id: UUID,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CreativeProjectListResponse:
    get_membership(user["id"], str(tenant_id))
    projects = session.scalars(
        select(CreativeProject).where(CreativeProject.tenant_id == tenant_id).order_by(CreativeProject.updated_at.desc())
    ).all()
    return CreativeProjectListResponse(items=[CreativeProjectRead.model_validate(project) for project in projects])


@router.get("/{project_id}", response_model=CreativeProjectBundle)
def get_project(
    project_id: UUID,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CreativeProjectBundle:
    project = _project_or_404(session, project_id)
    get_membership(user["id"], str(project.tenant_id))
    return _serialize_project_bundle(session, project)


@router.post("/{project_id}/orchestrate", response_model=WorkflowRunResponse)
def orchestrate_project(
    project_id: UUID,
    payload: OrchestrateProjectPayload,
    request: Request,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WorkflowRunResponse:
    project = _project_or_404(session, project_id)
    get_membership(user["id"], str(project.tenant_id))
    brand = session.get(Brand, project.brand_id) if project.brand_id else None
    service = build_orchestration_service(session)
    export_context = None
    if payload.export_after_run:
        export_context = {
            "file_type": payload.export_file_type,
            "dpi": payload.dpi,
            "public_base_url": str(request.base_url).rstrip("/"),
        }
    return service.run(project, brand, user_id=user["id"], export_context=export_context, user_edits=payload.user_edits)


@router.post("/{project_id}/pages/{page_id}/edits", response_model=ProjectVersionRead)
def apply_page_edit(
    project_id: UUID,
    page_id: UUID,
    payload: PageEditPayload,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProjectVersionRead:
    project = _project_or_404(session, project_id)
    get_membership(user["id"], str(project.tenant_id))
    page = session.get(CreativePage, page_id)
    if page is None or page.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    if payload.layout_json is not None:
        page.layout_json = payload.layout_json
    if payload.content_plan_json is not None:
        page.content_plan_json = payload.content_plan_json
    if payload.review_json is not None:
        page.review_json = payload.review_json

    pages = _project_pages(session, project.id)
    version = _persist_user_version(
        session,
        project,
        source_type=ProjectVersionSourceType.USER_EDIT.value,
        strategy_json={"edited_page_id": str(page.id)},
        pages=pages,
    )
    session.commit()
    session.refresh(version)
    return ProjectVersionRead.model_validate(version)


@router.post("/{project_id}/pages/{page_id}/duplicate", response_model=CreativeProjectBundle)
def duplicate_project_page(
    project_id: UUID,
    page_id: UUID,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CreativeProjectBundle:
    project = _project_or_404(session, project_id)
    get_membership(user["id"], str(project.tenant_id))
    page = session.get(CreativePage, page_id)
    if page is None or page.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    pages = _project_pages(session, project.id)
    insert_index = page.page_index + 1
    duplicated_page = CreativePage(
        project_id=project.id,
        page_index=insert_index,
        page_role=page.page_role,
        content_plan_json=dict(page.content_plan_json),
        layout_json={**page.layout_json, "page_index": insert_index},
        review_json=dict(page.review_json),
    )
    session.add(duplicated_page)
    session.flush()
    project.page_count += 1
    pages = _project_pages(session, project.id)
    pages.insert(insert_index, pages.pop(next(index for index, current_page in enumerate(pages) if current_page.id == duplicated_page.id)))
    _reindex_pages(session, pages)
    _persist_user_version(
        session,
        project,
        source_type=ProjectVersionSourceType.USER_EDIT.value,
        strategy_json={"duplicated_page_id": str(page.id)},
        pages=pages,
    )
    session.commit()
    session.refresh(project)
    return _serialize_project_bundle(session, project)


@router.post("/{project_id}/pages/reorder", response_model=CreativeProjectBundle)
def reorder_project_pages(
    project_id: UUID,
    payload: ReorderProjectPagesPayload,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CreativeProjectBundle:
    project = _project_or_404(session, project_id)
    get_membership(user["id"], str(project.tenant_id))

    pages = _project_pages(session, project.id)
    pages_by_id = {page.id: page for page in pages}
    if set(pages_by_id.keys()) != set(payload.page_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page order must include all project pages")

    reordered_pages = [pages_by_id[page_id] for page_id in payload.page_ids]
    _reindex_pages(session, reordered_pages)
    _persist_user_version(
        session,
        project,
        source_type=ProjectVersionSourceType.USER_EDIT.value,
        strategy_json={"reordered_page_ids": [str(page_id) for page_id in payload.page_ids]},
        pages=reordered_pages,
    )
    session.commit()
    session.refresh(project)
    return _serialize_project_bundle(session, project)


@router.post("/{project_id}/memory/accept", response_model=AcceptMemorySuggestionResponse, status_code=status.HTTP_201_CREATED)
def accept_memory_suggestion(
    project_id: UUID,
    payload: AcceptMemorySuggestionPayload,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AcceptMemorySuggestionResponse:
    project = _project_or_404(session, project_id)
    get_membership(user["id"], str(project.tenant_id))

    suggestion = payload.suggestion
    save_as = payload.save_as or ("component" if suggestion.category == "component" else "asset")
    brand_id = payload.brand_id or project.brand_id
    tags = payload.tags or suggestion.tags
    name = payload.name or suggestion.name

    if save_as == "asset":
        if brand_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Asset suggestions require a brand")
        file_url = suggestion.file_url or suggestion.preview_url
        if not file_url:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Asset suggestion does not include a file URL")
        source_type = "ai_generated" if suggestion.ai_generated or suggestion.origin == "ai_generated" else "imported"
        asset = BrandAsset(
            tenant_id=project.tenant_id,
            brand_id=brand_id,
            name=name,
            category=payload.category or suggestion.category,
            subcategory=None,
            tags=tags,
            source_type=source_type,
            file_url=file_url,
            preview_url=suggestion.preview_url or file_url,
            dominant_color=suggestion.dominant_color,
            is_recolorable=False,
            is_decorative=suggestion.is_decorative,
            usage_context=suggestion.usage_context,
            ai_generated=suggestion.ai_generated or suggestion.origin == "ai_generated",
            metadata_json={
                **suggestion.metadata_json,
                "origin": suggestion.origin,
                "rationale": suggestion.rationale,
            },
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
        return AcceptMemorySuggestionResponse(kind="asset", asset=BrandAssetRead.model_validate(asset))

    component = DesignComponent(
        tenant_id=project.tenant_id,
        brand_id=brand_id,
        name=name,
        component_type=payload.component_type or suggestion.component_type or "layout_pattern",
        schema_json={
            **suggestion.schema_definition,
            "usage_context": suggestion.usage_context,
            "metadata": suggestion.metadata_json,
        },
        style_json=suggestion.style_json or {"variant": "default"},
        tags=tags,
        usage_count=1,
    )
    session.add(component)
    session.commit()
    session.refresh(component)
    return AcceptMemorySuggestionResponse(kind="component", component=DesignComponentRead.model_validate(component))


@router.post("/{project_id}/templates", response_model=LayoutTemplateRead, status_code=status.HTTP_201_CREATED)
def save_project_template(
    project_id: UUID,
    payload: SaveProjectTemplatePayload,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LayoutTemplateRead:
    project = _project_or_404(session, project_id)
    get_membership(user["id"], str(project.tenant_id))
    project_pages = _project_pages(session, project.id)
    if not project_pages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project has no pages to convert into template")
    page = session.get(CreativePage, payload.page_id) if payload.page_id else project_pages[0]
    if page is None or page.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    regions = _extract_template_regions(page)
    if not regions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected page has no reusable regions yet")

    template = LayoutTemplate(
        tenant_id=project.tenant_id,
        brand_id=payload.brand_id if payload.brand_id is not None else project.brand_id,
        name=payload.name,
        channel=project.channel,
        format_type=project.format_type,
        page_role=page.page_role,
        schema_json={"regions": regions, "source_page_id": str(page.id)},
        constraints_json={"safe_zone": _project_safe_zone(project)},
        tags=payload.tags or [project.format_type, page.page_role, "project-derived"],
        is_system_template=False,
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return LayoutTemplateRead.model_validate(template)


@router.post("/{project_id}/templates/{template_id}/apply", response_model=CreativeProjectBundle)
def apply_project_template(
    project_id: UUID,
    template_id: UUID,
    payload: ApplyProjectTemplatePayload,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CreativeProjectBundle:
    project = _project_or_404(session, project_id)
    get_membership(user["id"], str(project.tenant_id))
    template = _template_or_404(session, project.tenant_id, template_id)

    pages = _project_pages(session, project.id)
    if payload.page_id:
        page = session.get(CreativePage, payload.page_id)
        if page is None or page.project_id != project.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
        target_pages = [page]
    else:
        target_pages = [page for page in pages if page.page_role == template.page_role]
        if not target_pages and pages:
            target_pages = [pages[0]]

    for page in target_pages:
        page.layout_json = _template_preview_layout(project, page, template)
        page.review_json = {**(page.review_json or {}), "template_applied": True}

    pages = _project_pages(session, project.id)
    _persist_user_version(
        session,
        project,
        source_type=ProjectVersionSourceType.USER_EDIT.value,
        strategy_json={"applied_template_id": str(template.id), "page_ids": [str(page.id) for page in target_pages]},
        pages=pages,
    )
    session.commit()
    session.refresh(project)
    return _serialize_project_bundle(session, project)


@router.post("/{project_id}/exports", response_model=ExportJobRead, status_code=status.HTTP_201_CREATED)
def export_project(
    project_id: UUID,
    payload: ExportJobPayload,
    request: Request,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ExportJobRead:
    project = _project_or_404(session, project_id)
    get_membership(user["id"], str(project.tenant_id))
    version = session.get(ProjectVersion, payload.version_id)
    if version is None or version.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    export_result = _render_export_pages(
        version=version,
        file_type=payload.file_type,
        dpi=payload.dpi,
    )
    export_job = ExportJob(
        project_id=project.id,
        version_id=version.id,
        file_type=payload.file_type,
        dimensions_json=payload.dimensions_json,
        dpi=payload.dpi,
        output_url="",
        output_manifest_json={},
        status=JobStatus.COMPLETED.value,
        completed_at=datetime.now(timezone.utc),
    )
    session.add(export_job)
    session.flush()
    manifest = build_export_manifest(
        base_url=str(request.base_url).rstrip("/"),
        project_id=project.id,
        export_job_id=export_job.id,
        page_indices=[page["page_index"] for page in export_result["pages"]],
        file_type=payload.file_type,
    )
    export_job.output_url = manifest["batch_output_url"]
    export_job.output_manifest_json = manifest
    version.exported_assets_json = {
        **(version.exported_assets_json or {}),
        "latest_export": {
            "export_job_id": str(export_job.id),
            "file_type": payload.file_type,
            "output_url": export_job.output_url,
            "output_manifest_json": manifest,
        },
    }
    project.status = ProjectStatus.EXPORTED.value
    session.commit()
    session.refresh(export_job)
    return ExportJobRead.model_validate(export_job)


@router.get("/{project_id}/exports/{export_job_id}/download")
def download_export_batch(
    project_id: UUID,
    export_job_id: UUID,
    session: Session = Depends(get_session),
) -> Response:
    project = _project_or_404(session, project_id)
    export_job = _export_job_or_404(session, project_id, export_job_id)
    version = session.get(ProjectVersion, export_job.version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    export_result = _render_export_pages(
        version=version,
        file_type=export_job.file_type,
        dpi=export_job.dpi,
    )
    if len(export_result["pages"]) == 1:
        page = export_result["pages"][0]
        return Response(
            content=page["bytes"],
            media_type=page["mime_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{_page_file_name(project, version.version_number, page["page_index"], page["extension"])}"'
            },
        )

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for page in export_result["pages"]:
            archive.writestr(
                _page_file_name(project, version.version_number, page["page_index"], page["extension"]),
                page["bytes"],
            )

    return Response(
        content=archive_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{_archive_file_name(project, version.version_number, export_job.file_type)}"'
        },
    )


@router.get("/{project_id}/exports/{export_job_id}/pages/{page_index}")
def download_export_page(
    project_id: UUID,
    export_job_id: UUID,
    page_index: int,
    session: Session = Depends(get_session),
) -> Response:
    project = _project_or_404(session, project_id)
    export_job = _export_job_or_404(session, project_id, export_job_id)
    version = session.get(ProjectVersion, export_job.version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    export_result = _render_export_pages(
        version=version,
        file_type=export_job.file_type,
        dpi=export_job.dpi,
        page_index=page_index,
    )
    page = export_result["pages"][0]
    return Response(
        content=page["bytes"],
        media_type=page["mime_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{_page_file_name(project, version.version_number, page_index, page["extension"])}"'
        },
    )


@router.get("/{project_id}/versions/{version_id}", response_model=ProjectVersionRead)
def get_project_version(
    project_id: UUID,
    version_id: UUID,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProjectVersionRead:
    project = _project_or_404(session, project_id)
    get_membership(user["id"], str(project.tenant_id))
    version = session.get(ProjectVersion, version_id)
    if version is None or version.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    return ProjectVersionRead.model_validate(version)
