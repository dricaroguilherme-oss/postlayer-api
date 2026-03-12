from __future__ import annotations

from app.infra.providers.local_ai import LocalImageGenerationProvider, LocalTextReasoningProvider
from app.orchestration.langgraph.service import LangGraphOrchestrationService
from app.rendering.svg_renderer import SvgLayoutRenderer
from app.review_engine.rules import RuleBasedReviewRuleSet


class DummySession:
    pass


class OrchestrationServiceStub(LangGraphOrchestrationService):
    def persist_version(self, state):  # type: ignore[override]
        execution_log = list(state.get("execution_log", []))
        execution_log.append({"step": "persist_version", "detail": "Version 1 persisted (test stub)"})
        return {"version_id": "9342bf7f-b93f-4e6b-9628-a7ec6f668a97", "execution_log": execution_log}

    def export_final_assets(self, state):  # type: ignore[override]
        execution_log = list(state.get("execution_log", []))
        execution_log.append({"step": "export_final_assets", "detail": "png"})
        return {
            "export_job_id": "1d636211-3f26-4b8c-b0b7-71dd874df0f9",
            "export_context": {"file_type": "png", "pages": [{"page_index": 0}]},
            "execution_log": execution_log,
        }


def _service() -> OrchestrationServiceStub:
    return OrchestrationServiceStub(
        session=DummySession(),  # type: ignore[arg-type]
        text_provider=LocalTextReasoningProvider(),
        image_provider=LocalImageGenerationProvider(),
        renderer=SvgLayoutRenderer(),
        review_rules=RuleBasedReviewRuleSet(),
    )


def test_graph_single_post_happy_path() -> None:
    service = _service()
    result = service.graph.invoke(
        {
            "project_id": "614848c1-5b36-4277-a23d-cb03f56d855d",
            "tenant_id": "078e523c-be43-45de-b8d8-4b0fb005459a",
            "brand_id": None,
            "ai_job_id": "3ec35f36-6e52-4edc-94dc-9ca47f68e0eb",
            "project_context": {
                "channel": "instagram",
                "format_type": "instagram_post_square",
                "piece_type": "single_post",
                "page_count": 1,
                "dimensions": {"width": 1080, "height": 1080},
                "objective": "conversion",
                "audience": "founders",
                "language": "pt-BR",
                "cta": "Teste agora",
                "user_prompt": "Crie um post sobre automação criativa com foco em velocidade e branding.",
            },
            "brand_context": {
                "color_tokens": {
                    "primary": ["#111827"],
                    "secondary": ["#7C3AED"],
                    "neutral": ["#F9FAFB"],
                },
                "typography": {"heading_family": "Space Grotesk", "body_family": "DM Sans"},
                "visual_style_keywords": ["editorial", "high contrast"],
            },
            "asset_context": {
                "assets": [
                    {
                        "id": "asset-1",
                        "category": "background",
                        "is_decorative": True,
                        "preview_url": "https://example.com/background.png",
                    }
                ]
            },
            "template_context": {
                "templates": [
                    {
                        "id": "template-1",
                        "format_type": "instagram_post_square",
                        "page_role": "cover",
                        "schema_json": {
                            "regions": [
                                {"slot": "heading", "x": 72, "y": 96, "width": 720, "height": 220},
                                {"slot": "body", "x": 72, "y": 340, "width": 720, "height": 240},
                                {"slot": "cta", "x": 72, "y": 910, "width": 260, "height": 80},
                            ]
                        },
                    }
                ]
            },
            "generated_assets": [],
            "execution_log": [],
            "asset_suggestions": [],
        }
    )

    assert result["content_plan"]["slides"][0]["headline"]
    assert result["art_direction_plan"]["template_id"] == "template-1"
    assert result["art_direction_plan"]["page_styles"]["cover"]["background_mode"] == "hero"
    assert result["composition_result"]["pages"][0]["nodes"]
    assert result["review_result"]["legibility_score"] > 0
    assert result["version_id"] == "9342bf7f-b93f-4e6b-9628-a7ec6f668a97"


def test_graph_carousel_triggers_generation_autofix_and_export() -> None:
    service = _service()
    result = service.graph.invoke(
        {
            "project_id": "d58d15ea-a958-4dba-9a78-64e85c03c589",
            "tenant_id": "078e523c-be43-45de-b8d8-4b0fb005459a",
            "brand_id": None,
            "ai_job_id": "08e4ca60-1e7e-4590-8a56-79ed6de31317",
            "project_context": {
                "channel": "linkedin",
                "format_type": "linkedin_carousel",
                "piece_type": "carousel",
                "page_count": 3,
                "dimensions": {"width": 1080, "height": 1350},
                "objective": "education",
                "audience": "marketing leads",
                "language": "pt-BR",
                "cta": "Baixe o guia",
                "user_prompt": "Crie um carrossel detalhado explicando como combinar IA visual, composição estruturada, regras de branding e revisão automática para peças estáticas de alta consistência com exemplos e benefícios práticos para times de marketing.",
            },
            "brand_context": {
                "color_tokens": {
                    "primary": ["#F8FAFC"],
                    "secondary": ["#38BDF8"],
                    "neutral": ["#FFFFFF"],
                },
                "typography": {"heading_family": "Space Grotesk", "body_family": "DM Sans"},
                "visual_style_keywords": ["clean", "airy"],
            },
            "asset_context": {"assets": []},
            "template_context": {"templates": []},
            "generated_assets": [],
            "execution_log": [],
            "asset_suggestions": [],
            "export_context": {"file_type": "png", "dpi": 144},
        }
    )

    assert result["generated_assets"]
    assert result["review_result"]["autofixes_applied"]
    assert any(
        node["id"].startswith("slide-index")
        for page in result["composition_result"]["pages"]
        for node in page["nodes"]
    )
    assert any(suggestion["category"] == "component" for suggestion in result["asset_suggestions"])
    assert result["export_job_id"] == "1d636211-3f26-4b8c-b0b7-71dd874df0f9"
    assert any(entry["step"] == "export_final_assets" for entry in result["execution_log"])


def test_graph_reuses_existing_background_before_generating() -> None:
    service = _service()
    result = service.graph.invoke(
        {
            "project_id": "84515b56-1c16-4b5a-9d3e-2efe30cbe1a6",
            "tenant_id": "078e523c-be43-45de-b8d8-4b0fb005459a",
            "brand_id": None,
            "ai_job_id": "d9a6fd30-ccfc-4777-9dda-d719f28f374d",
            "project_context": {
                "channel": "instagram",
                "format_type": "instagram_post_square",
                "piece_type": "single_post",
                "page_count": 1,
                "dimensions": {"width": 1080, "height": 1080},
                "objective": "awareness",
                "audience": "design leads",
                "language": "pt-BR",
                "cta": "Conheça o sistema",
                "user_prompt": "Apresente o sistema visual da plataforma com clareza e sofisticação.",
            },
            "brand_context": {
                "color_tokens": {
                    "primary": ["#0F172A"],
                    "secondary": ["#E11D48"],
                    "neutral": ["#F8FAFC"],
                },
                "typography": {"heading_family": "Space Grotesk", "body_family": "DM Sans"},
                "visual_style_keywords": ["editorial", "bold"],
            },
            "asset_context": {
                "assets": [
                    {
                        "id": "asset-bg-1",
                        "category": "background",
                        "is_decorative": True,
                        "preview_url": "https://example.com/hero-bg.png",
                    }
                ]
            },
            "template_context": {"templates": []},
            "generated_assets": [],
            "execution_log": [],
            "asset_suggestions": [],
        }
    )

    assert result["art_direction_plan"]["asset_refs"] == ["asset-bg-1"]
    assert result["generated_assets"] == []
