from app.schemas.brand import BrandCreatePayload, BrandSystem
from app.schemas.creative import (
    AIJobPayload,
    ArtDirectionPlan,
    ContentPlan,
    CreativeProjectPayload,
    ExportJobPayload,
    LayoutNode,
    ProjectContext,
    ProjectVersionPayload,
    ReviewResult,
)
from app.schemas.orchestration import LangGraphState
from app.schemas.templates import LayoutTemplatePayload


def test_shared_schemas_validate() -> None:
    project = ProjectContext.model_validate(
        {
            "channel": "instagram",
            "format_type": "instagram_post_square",
            "piece_type": "single_post",
            "page_count": 1,
            "dimensions": {"width": 1080, "height": 1080},
            "objective": "captacao",
            "audience": "founders",
            "language": "pt-BR",
            "cta": "Saiba mais",
            "user_prompt": "Crie um post editorial sobre automação",
        }
    )
    assert project.page_count == 1

    brand = BrandSystem.model_validate(
        {
            "color_tokens": {"primary": ["#111827"], "secondary": ["#7C3AED"], "neutral": ["#F9FAFB"]},
            "typography": {"heading_family": "Space Grotesk", "body_family": "DM Sans"},
            "radius_preset": "soft",
            "shadow_preset": "subtle",
            "visual_style_keywords": ["editorial"],
            "composition_rules": {"safe_zone": "strict"},
            "approved_refs": [],
            "rejected_refs": [],
        }
    )
    assert brand.radius_preset == "soft"

    node = LayoutNode.model_validate(
        {
            "id": "canvas-1",
            "type": "canvas",
            "x": 0,
            "y": 0,
            "width": 1080,
            "height": 1080,
            "z_index": 0,
            "style": {},
            "children": [],
        }
    )
    assert node.type == "canvas"

    content_plan = ContentPlan.model_validate(
        {
            "project_id": "project-1",
            "global_message": "Mensagem principal",
            "slides": [
                {
                    "page_index": 0,
                    "page_role": "cover",
                    "headline": "Headline",
                    "body": "Body",
                    "cta": "Saiba mais",
                    "narrative_intent": "Hook",
                }
            ],
        }
    )
    assert len(content_plan.slides) == 1

    art_direction = ArtDirectionPlan.model_validate(
        {
            "visual_direction": "clean editorial",
            "palette_mode": "brand_primary",
            "component_refs": [],
            "asset_refs": [],
            "generation_instructions": ["soft gradient background"],
        }
    )
    assert art_direction.palette_mode == "brand_primary"

    review = ReviewResult.model_validate(
        {
            "warnings": [],
            "legibility_score": 0.91,
            "brand_adherence_score": 0.88,
            "contrast_score": 0.79,
            "text_density_score": 0.7,
            "autofixes_applied": ["added_overlay"],
        }
    )
    assert review.autofixes_applied == ["added_overlay"]

    persisted_brand = BrandCreatePayload.model_validate(
        {
            "name": "PostLayer Studio",
            "primary_colors": ["#111827"],
            "secondary_colors": ["#7C3AED"],
            "neutral_colors": ["#F9FAFB"],
            "typography_heading": {"family": "Space Grotesk"},
            "typography_body": {"family": "DM Sans"},
            "font_weights": [400, 500, 700],
            "default_title_sizes": [32, 48],
            "default_body_sizes": [16, 20],
            "visual_style_keywords": ["editorial"],
        }
    )
    assert persisted_brand.name == "PostLayer Studio"

    template = LayoutTemplatePayload.model_validate(
        {
            "name": "Editorial Split Cover",
            "channel": "instagram",
            "format_type": "instagram_post_square",
            "page_role": "cover",
            "schema_json": {"canvas": {"padding": 72}},
            "constraints_json": {"safe_zone": "strict"},
            "tags": ["system"],
            "is_system_template": True,
        }
    )
    assert template.is_system_template is True

    project_payload = CreativeProjectPayload.model_validate(
        {
            "title": "Campanha de produto",
            "channel": "instagram",
            "format_type": "instagram_post_square",
            "piece_type": "single_post",
            "dimensions_json": {"width": 1080, "height": 1080},
            "objective": "conversion",
            "audience": "founders",
            "language": "pt-BR",
            "page_count": 1,
            "user_prompt": "Criar campanha de lançamento",
            "created_by": "user-1",
        }
    )
    assert project_payload.status == "draft"

    version_payload = ProjectVersionPayload.model_validate({"render_tree_json": {"root": "canvas"}})
    assert version_payload.source_type == "system_generation"

    export_payload = ExportJobPayload.model_validate(
        {
            "version_id": "ca0b93dd-24a4-4d70-97fd-b631ca90b6ce",
            "dimensions_json": {"width": 1080, "height": 1080},
        }
    )
    assert export_payload.file_type == "png"

    ai_job = AIJobPayload.model_validate(
        {
            "job_type": "content_plan",
            "provider": "openai",
            "model": "gpt-5",
        }
    )
    assert ai_job.status == "pending"

    state = LangGraphState.model_validate(
        {
            "project_context": project.model_dump(),
            "brand_context": brand.model_dump(),
            "asset_context": {},
            "template_context": {},
        }
    )
    assert state.project_context["channel"] == "instagram"
