from __future__ import annotations

from uuid import uuid4

from app.api.v1.projects_v1 import _extract_template_regions, _template_preview_layout
from app.domain.creative.models import CreativePage, CreativeProject
from app.domain.template.models import LayoutTemplate


def _project() -> CreativeProject:
    return CreativeProject(
        id=uuid4(),
        tenant_id=uuid4(),
        brand_id=None,
        title="Template Source",
        channel="instagram",
        format_type="instagram_post_square",
        piece_type="single_post",
        dimensions_json={"width": 1080, "height": 1080},
        objective="conversion",
        audience="founders",
        language="pt-BR",
        cta="Saiba mais",
        page_count=1,
        user_prompt="Crie um post editorial",
        status="draft",
        created_by="user-1",
    )


def _page(project: CreativeProject) -> CreativePage:
    return CreativePage(
        id=uuid4(),
        project_id=project.id,
        page_index=0,
        page_role="cover",
        content_plan_json={},
        layout_json={
            "page_index": 0,
            "page_role": "cover",
            "width": 1080,
            "height": 1080,
            "nodes": [
                {"id": "heading-0", "type": "heading", "x": 72, "y": 96, "width": 720, "height": 220},
                {"id": "body-0", "type": "paragraph", "x": 72, "y": 340, "width": 720, "height": 240},
                {"id": "cta-bg-0", "type": "shape", "x": 72, "y": 910, "width": 260, "height": 80},
            ],
        },
        review_json={},
    )


def _template(project: CreativeProject) -> LayoutTemplate:
    return LayoutTemplate(
        id=uuid4(),
        tenant_id=project.tenant_id,
        brand_id=None,
        name="Editorial Cover",
        channel=project.channel,
        format_type=project.format_type,
        page_role="cover",
        schema_json={
            "regions": [
                {"slot": "heading", "x": 72, "y": 96, "width": 720, "height": 220},
                {"slot": "body", "x": 72, "y": 340, "width": 720, "height": 240},
            ]
        },
        constraints_json={},
        tags=["editorial"],
        is_system_template=False,
    )


def test_extract_template_regions_from_page_layout() -> None:
    project = _project()
    page = _page(project)

    regions = _extract_template_regions(page)

    assert [region["slot"] for region in regions] == ["heading", "body", "cta"]


def test_template_preview_layout_marks_selected_template() -> None:
    project = _project()
    page = _page(project)
    template = _template(project)

    layout = _template_preview_layout(project, page, template)

    assert layout["template_id"] == str(template.id)
    assert len(layout["nodes"]) == 5
