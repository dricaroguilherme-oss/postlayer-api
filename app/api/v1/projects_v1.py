from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, get_membership
from app.api.dependencies.db import get_session
from app.application.services.versioning import next_project_version_number
from app.domain.brand.models import Brand
from app.domain.common.types import JobStatus, ProjectVersionSourceType
from app.domain.creative.models import CreativePage, CreativeProject, ExportJob, ProjectVersion
from app.export_engine.service import ExportEngine
from app.orchestration.langgraph.service import build_orchestration_service
from app.rendering.svg_renderer import SvgLayoutRenderer
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
from app.schemas.orchestration import OrchestrateProjectPayload, PageEditPayload, WorkflowRunResponse

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


def _serialize_project_bundle(session: Session, project: CreativeProject) -> CreativeProjectBundle:
    pages = session.scalars(
        select(CreativePage).where(CreativePage.project_id == project.id).order_by(CreativePage.page_index.asc())
    ).all()
    versions = session.scalars(
        select(ProjectVersion).where(ProjectVersion.project_id == project.id).order_by(ProjectVersion.version_number.desc())
    ).all()
    return CreativeProjectBundle(
        project=CreativeProjectRead.model_validate(project),
        pages=[CreativePageRead.model_validate(page) for page in pages],
        versions=[ProjectVersionRead.model_validate(version) for version in versions],
    )


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
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WorkflowRunResponse:
    project = _project_or_404(session, project_id)
    get_membership(user["id"], str(project.tenant_id))
    brand = session.get(Brand, project.brand_id) if project.brand_id else None
    service = build_orchestration_service(session)
    export_context = None
    if payload.export_after_run:
        export_context = {"file_type": payload.export_file_type, "dpi": payload.dpi}
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

    pages = session.scalars(
        select(CreativePage).where(CreativePage.project_id == project.id).order_by(CreativePage.page_index.asc())
    ).all()
    version = ProjectVersion(
        project_id=project.id,
        version_number=next_project_version_number(session, project.id),
        source_type=ProjectVersionSourceType.USER_EDIT.value,
        strategy_json={"edited_page_id": str(page.id)},
        art_direction_json={},
        render_tree_json={
            "pages": [
                {
                    "page_index": current_page.page_index,
                    "page_role": current_page.page_role,
                    **current_page.layout_json,
                }
                for current_page in pages
            ]
        },
        exported_assets_json={},
    )
    session.add(version)
    session.flush()
    project.current_version_id = version.id
    session.commit()
    session.refresh(version)
    return ProjectVersionRead.model_validate(version)


@router.post("/{project_id}/exports", response_model=ExportJobRead, status_code=status.HTTP_201_CREATED)
def export_project(
    project_id: UUID,
    payload: ExportJobPayload,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ExportJobRead:
    project = _project_or_404(session, project_id)
    get_membership(user["id"], str(project.tenant_id))
    version = session.get(ProjectVersion, payload.version_id)
    if version is None or version.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    renderer = SvgLayoutRenderer()
    engine = ExportEngine(renderer)
    export_result = engine.export(
        {
            "pages": version.render_tree_json.get("pages", []),
            "file_type": payload.file_type,
        }
    )
    export_job = ExportJob(
        project_id=project.id,
        version_id=version.id,
        file_type=payload.file_type,
        dimensions_json=payload.dimensions_json,
        dpi=payload.dpi,
        output_url=export_result["pages"][0]["data_url"] if export_result["pages"] else None,
        status=JobStatus.COMPLETED.value,
    )
    session.add(export_job)
    session.commit()
    session.refresh(export_job)
    return ExportJobRead.model_validate(export_job)


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
