from __future__ import annotations

import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.application.contracts.providers import ImageGenerationProvider, Renderer, ReviewRuleSet, TextReasoningProvider
from app.application.services.versioning import next_project_version_number
from app.domain.brand.models import Brand, BrandAsset
from app.domain.common.types import JobStatus, ProjectStatus, ProjectVersionSourceType
from app.domain.creative.models import AIJob, CreativePage, CreativeProject, ExportJob, ProjectVersion
from app.domain.template.models import LayoutTemplate
from app.export_engine.service import ExportEngine
from app.infra.providers.local_ai import LocalImageGenerationProvider, LocalTextReasoningProvider
from app.infra.providers.openai_ai import OpenAIImageGenerationProvider, OpenAITextReasoningProvider
from app.orchestration.langgraph.agents import (
    ArtDirectorAgent,
    ComposerAgent,
    MemoryCuratorAgent,
    ReviewerAgent,
    StrategistAgent,
    VisualGeneratorAgent,
    apply_autofixes,
)
from app.rendering.svg_renderer import SvgLayoutRenderer
from app.review_engine.rules import RuleBasedReviewRuleSet
from app.schemas.brand import BrandRead
from app.schemas.creative import CreativeProjectRead
from app.schemas.orchestration import WorkflowRunResponse
from app.schemas.templates import LayoutTemplateRead


class WorkflowState(TypedDict, total=False):
    project_id: str
    tenant_id: str
    brand_id: str | None
    ai_job_id: str
    version_id: str | None
    export_job_id: str | None
    project_context: dict[str, Any]
    brand_context: dict[str, Any]
    asset_context: dict[str, Any]
    template_context: dict[str, Any]
    content_plan: dict[str, Any] | None
    art_direction_plan: dict[str, Any] | None
    generated_assets: list[dict[str, Any]]
    composition_result: dict[str, Any] | None
    review_result: dict[str, Any] | None
    user_edits: dict[str, Any] | None
    export_context: dict[str, Any] | None
    execution_log: list[dict[str, Any]]
    asset_suggestions: list[dict[str, Any]]


class LangGraphOrchestrationService:
    def __init__(
        self,
        session: Session,
        text_provider: TextReasoningProvider,
        image_provider: ImageGenerationProvider,
        renderer: Renderer,
        review_rules: ReviewRuleSet,
    ) -> None:
        self.session = session
        self.text_provider = text_provider
        self.image_provider = image_provider
        self.renderer = renderer
        self.review_rules = review_rules
        self.export_engine = ExportEngine(renderer)
        self.strategist = StrategistAgent(text_provider)
        self.art_director = ArtDirectorAgent(text_provider)
        self.visual_generator = VisualGeneratorAgent(image_provider)
        self.composer = ComposerAgent(text_provider)
        self.reviewer = ReviewerAgent(review_rules)
        self.memory_curator = MemoryCuratorAgent()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(WorkflowState)
        graph.add_node("load_project_context", self.load_project_context)
        graph.add_node("load_brand_context", self.load_brand_context)
        graph.add_node("load_asset_library", self.load_asset_library)
        graph.add_node("retrieve_existing_templates", self.retrieve_existing_templates)
        graph.add_node("retrieve_existing_assets", self.retrieve_existing_assets)
        graph.add_node("generate_content_plan", self.generate_content_plan)
        graph.add_node("generate_art_direction", self.generate_art_direction)
        graph.add_node("generate_visual_assets", self.generate_visual_assets)
        graph.add_node("compose_layout", self.compose_layout)
        graph.add_node("review_layout", self.review_layout)
        graph.add_node("apply_autofixes", self.apply_autofixes)
        graph.add_node("persist_version", self.persist_version)
        graph.add_node("suggest_asset_saving", self.suggest_asset_saving)
        graph.add_node("wait_for_user_edits", self.wait_for_user_edits)
        graph.add_node("export_final_assets", self.export_final_assets)

        graph.add_edge(START, "load_project_context")
        graph.add_edge("load_project_context", "load_brand_context")
        graph.add_edge("load_brand_context", "load_asset_library")
        graph.add_edge("load_asset_library", "retrieve_existing_templates")
        graph.add_edge("retrieve_existing_templates", "retrieve_existing_assets")
        graph.add_edge("retrieve_existing_assets", "generate_content_plan")
        graph.add_edge("generate_content_plan", "generate_art_direction")
        graph.add_conditional_edges(
            "generate_art_direction",
            self.decide_if_generate_assets,
            {
                "generate_assets": "generate_visual_assets",
                "skip_generation": "compose_layout",
            },
        )
        graph.add_edge("generate_visual_assets", "compose_layout")
        graph.add_edge("compose_layout", "review_layout")
        graph.add_conditional_edges(
            "review_layout",
            self.decide_if_apply_autofix,
            {
                "apply_autofix": "apply_autofixes",
                "persist_version": "persist_version",
            },
        )
        graph.add_edge("apply_autofixes", "persist_version")
        graph.add_edge("persist_version", "suggest_asset_saving")
        graph.add_edge("suggest_asset_saving", "wait_for_user_edits")
        graph.add_conditional_edges(
            "wait_for_user_edits",
            self.decide_if_export,
            {
                "export": "export_final_assets",
                "end": END,
            },
        )
        graph.add_edge("export_final_assets", END)
        return graph.compile()

    def load_project_context(self, state: WorkflowState) -> WorkflowState:
        execution_log = list(state.get("execution_log", []))
        execution_log.append({"step": "load_project_context", "detail": "Project context loaded"})
        return {"execution_log": execution_log}

    def load_brand_context(self, state: WorkflowState) -> WorkflowState:
        execution_log = list(state.get("execution_log", []))
        execution_log.append({"step": "load_brand_context", "detail": "Brand context loaded"})
        return {"execution_log": execution_log}

    def load_asset_library(self, state: WorkflowState) -> WorkflowState:
        execution_log = list(state.get("execution_log", []))
        assets = state.get("asset_context", {}).get("assets", [])
        execution_log.append({"step": "load_asset_library", "detail": f"{len(assets)} assets available"})
        return {"execution_log": execution_log}

    def retrieve_existing_templates(self, state: WorkflowState) -> WorkflowState:
        project_context = state["project_context"]
        templates = state.get("template_context", {}).get("templates", [])
        filtered = [
            template
            for template in templates
            if template["format_type"] == project_context["format_type"]
        ]
        execution_log = list(state.get("execution_log", []))
        execution_log.append({"step": "retrieve_existing_templates", "detail": f"{len(filtered)} matching templates"})
        return {"template_context": {"templates": filtered}, "execution_log": execution_log}

    def retrieve_existing_assets(self, state: WorkflowState) -> WorkflowState:
        assets = state.get("asset_context", {}).get("assets", [])
        reusable = [asset for asset in assets if asset.get("category") in {"background", "texture", "graphic"}]
        execution_log = list(state.get("execution_log", []))
        execution_log.append({"step": "retrieve_existing_assets", "detail": f"{len(reusable)} reusable assets"})
        return {"asset_context": {"assets": reusable}, "execution_log": execution_log}

    def generate_content_plan(self, state: WorkflowState) -> WorkflowState:
        return self.strategist.run(state)

    def generate_art_direction(self, state: WorkflowState) -> WorkflowState:
        return self.art_director.run(state)

    def decide_if_generate_assets(self, state: WorkflowState) -> str:
        if state.get("art_direction_plan", {}).get("generation_instructions"):
            return "generate_assets"
        if not state.get("asset_context", {}).get("assets"):
            return "generate_assets"
        return "skip_generation"

    def generate_visual_assets(self, state: WorkflowState) -> WorkflowState:
        return self.visual_generator.run(state)

    def compose_layout(self, state: WorkflowState) -> WorkflowState:
        return self.composer.run(state)

    def review_layout(self, state: WorkflowState) -> WorkflowState:
        return self.reviewer.run(state)

    def decide_if_apply_autofix(self, state: WorkflowState) -> str:
        review = state["review_result"]
        if review["contrast_score"] < 0.72 or review["text_density_score"] < 0.72:
            return "apply_autofix"
        return "persist_version"

    def apply_autofixes(self, state: WorkflowState) -> WorkflowState:
        return apply_autofixes(state, self.text_provider, self.review_rules)

    def persist_version(self, state: WorkflowState) -> WorkflowState:
        project = self.session.get(CreativeProject, uuid.UUID(state["project_id"]))
        if project is None:
            raise ValueError("Project not found for orchestration persistence")

        version_number = next_project_version_number(self.session, project.id)
        version = ProjectVersion(
            project_id=project.id,
            version_number=version_number,
            source_type=(
                ProjectVersionSourceType.AUTOFIX.value
                if state.get("review_result", {}).get("autofixes_applied")
                else ProjectVersionSourceType.SYSTEM_GENERATION.value
            ),
            strategy_json=state.get("content_plan") or {},
            art_direction_json=state.get("art_direction_plan") or {},
            render_tree_json=state.get("composition_result") or {},
            exported_assets_json={"generated_assets": state.get("generated_assets", [])},
        )
        self.session.add(version)
        self.session.flush()

        slides_by_index = {
            slide["page_index"]: slide for slide in (state.get("content_plan") or {}).get("slides", [])
        }
        existing_pages = {
            page.page_index: page
            for page in self.session.scalars(
                select(CreativePage).where(CreativePage.project_id == project.id)
            )
        }
        for page_payload in (state.get("composition_result") or {}).get("pages", []):
            page = existing_pages.get(page_payload["page_index"])
            if page is None:
                page = CreativePage(
                    project_id=project.id,
                    page_index=page_payload["page_index"],
                    page_role=page_payload["page_role"],
                )
                self.session.add(page)
            page.page_role = page_payload["page_role"]
            page.content_plan_json = slides_by_index.get(page_payload["page_index"], {})
            page.layout_json = page_payload
            page.review_json = state.get("review_result") or {}

        project.current_version_id = version.id
        project.status = ProjectStatus.IN_REVIEW.value if state.get("review_result", {}).get("warnings") else ProjectStatus.READY.value

        ai_job = self.session.get(AIJob, uuid.UUID(state["ai_job_id"]))
        if ai_job is not None:
            ai_job.output_json = {
                "content_plan": state.get("content_plan"),
                "art_direction_plan": state.get("art_direction_plan"),
                "review_result": state.get("review_result"),
                "version_id": str(version.id),
            }
            ai_job.status = JobStatus.COMPLETED.value

        self.session.commit()

        execution_log = list(state.get("execution_log", []))
        execution_log.append({"step": "persist_version", "detail": f"Version {version_number} persisted"})
        return {"version_id": str(version.id), "execution_log": execution_log}

    def suggest_asset_saving(self, state: WorkflowState) -> WorkflowState:
        return self.memory_curator.run(state)

    def wait_for_user_edits(self, state: WorkflowState) -> WorkflowState:
        execution_log = list(state.get("execution_log", []))
        execution_log.append({"step": "wait_for_user_edits", "detail": "Pipeline paused for user edits"})
        return {"execution_log": execution_log}

    def decide_if_export(self, state: WorkflowState) -> str:
        return "export" if state.get("export_context") else "end"

    def export_final_assets(self, state: WorkflowState) -> WorkflowState:
        export_context = state["export_context"]
        export_result = self.export_engine.export(
            {
                "pages": state["composition_result"]["pages"],
                "file_type": export_context["file_type"],
            }
        )

        export_job = ExportJob(
            project_id=uuid.UUID(state["project_id"]),
            version_id=uuid.UUID(state["version_id"]),
            file_type=export_context["file_type"],
            dimensions_json=state["project_context"]["dimensions"],
            dpi=export_context.get("dpi", 144),
            output_url=export_result["pages"][0]["data_url"] if export_result["pages"] else None,
            status=JobStatus.COMPLETED.value,
        )
        self.session.add(export_job)
        self.session.commit()

        execution_log = list(state.get("execution_log", []))
        execution_log.append({"step": "export_final_assets", "detail": export_context["file_type"]})
        return {
            "export_job_id": str(export_job.id),
            "export_context": {
                **export_context,
                "pages": export_result["pages"],
            },
            "execution_log": execution_log,
        }

    def run(
        self,
        project: CreativeProject,
        brand: Brand | None,
        *,
        user_id: str,
        export_context: dict[str, Any] | None = None,
        user_edits: dict[str, Any] | None = None,
    ) -> WorkflowRunResponse:
        brand_assets = (
            list(self.session.scalars(select(BrandAsset).where(BrandAsset.brand_id == project.brand_id)))
            if project.brand_id
            else []
        )
        templates = list(
            self.session.scalars(
                select(LayoutTemplate).where(
                    LayoutTemplate.format_type == project.format_type,
                    or_(LayoutTemplate.tenant_id == project.tenant_id, LayoutTemplate.is_system_template.is_(True)),
                )
            )
        )
        ai_job = AIJob(
            project_id=project.id,
            job_type="creative_orchestration",
            provider="langgraph",
            model="deterministic-v1",
            input_json={
                "project_id": str(project.id),
                "tenant_id": str(project.tenant_id),
                "user_id": user_id,
            },
            output_json={},
            status=JobStatus.RUNNING.value,
        )
        self.session.add(ai_job)
        project.status = ProjectStatus.GENERATING.value
        self.session.commit()

        initial_state: WorkflowState = {
            "project_id": str(project.id),
            "tenant_id": str(project.tenant_id),
            "brand_id": str(project.brand_id) if project.brand_id else None,
            "ai_job_id": str(ai_job.id),
            "project_context": self._build_project_context(project),
            "brand_context": self._build_brand_context(brand),
            "template_context": {
                "templates": [
                    LayoutTemplateRead.model_validate(template).model_dump(mode="json", by_alias=True)
                    for template in templates
                ]
            },
            "generated_assets": [],
            "user_edits": user_edits,
            "export_context": export_context,
            "execution_log": [],
            "asset_suggestions": [],
        }
        initial_state["asset_context"] = {
            "assets": [
                {
                    "id": str(asset.id),
                    "category": asset.category,
                    "is_decorative": asset.is_decorative,
                    "preview_url": asset.preview_url,
                }
                for asset in brand_assets
            ]
        }

        try:
            result = self.graph.invoke(initial_state)
        except Exception as exc:
            failed_job = self.session.get(AIJob, ai_job.id)
            if failed_job is not None:
                failed_job.status = JobStatus.FAILED.value
                failed_job.error_message = str(exc)
            project.status = ProjectStatus.FAILED.value
            self.session.commit()
            raise

        return WorkflowRunResponse.model_validate(
            {
                "project_id": str(project.id),
                "version_id": result.get("version_id"),
                "ai_job_id": str(ai_job.id),
                "content_plan": result.get("content_plan"),
                "art_direction_plan": result.get("art_direction_plan"),
                "generated_assets": result.get("generated_assets", []),
                "composition_result": result.get("composition_result"),
                "review_result": result.get("review_result"),
                "asset_suggestions": result.get("asset_suggestions", []),
                "export_job_id": result.get("export_job_id"),
                "export_context": result.get("export_context"),
                "execution_log": result.get("execution_log", []),
            }
        )

    def _build_project_context(self, project: CreativeProject) -> dict[str, Any]:
        project_schema = CreativeProjectRead.model_validate(project).model_dump(mode="json")
        return {
            "channel": project_schema["channel"],
            "format_type": project_schema["format_type"],
            "piece_type": project_schema["piece_type"],
            "page_count": project_schema["page_count"],
            "dimensions": project_schema["dimensions_json"],
            "objective": project_schema["objective"],
            "audience": project_schema["audience"],
            "language": project_schema["language"],
            "cta": project_schema["cta"],
            "user_prompt": project_schema["user_prompt"],
        }

    def _build_brand_context(self, brand: Brand | None) -> dict[str, Any]:
        if brand is None:
            return {
                "color_tokens": {
                    "primary": ["#111827"],
                    "secondary": ["#7C3AED"],
                    "neutral": ["#F9FAFB"],
                },
                "typography": {
                    "heading_family": "Space Grotesk",
                    "body_family": "DM Sans",
                },
                "visual_style_keywords": ["clean", "editorial"],
            }

        brand_schema = BrandRead.model_validate(brand).model_dump(mode="json")
        return {
            "color_tokens": {
                "primary": brand_schema["primary_colors"],
                "secondary": brand_schema["secondary_colors"],
                "neutral": brand_schema["neutral_colors"],
            },
            "typography": {
                "heading_family": brand_schema["typography_heading"].get("family", "Space Grotesk"),
                "body_family": brand_schema["typography_body"].get("family", "DM Sans"),
                "font_weights": brand_schema["font_weights"],
                "default_title_sizes": brand_schema["default_title_sizes"],
                "default_body_sizes": brand_schema["default_body_sizes"],
            },
            "visual_style_keywords": brand_schema["visual_style_keywords"],
            "composition_rules": brand_schema["composition_rules_json"],
        }


def build_orchestration_service(session: Session) -> LangGraphOrchestrationService:
    text_provider: TextReasoningProvider = OpenAITextReasoningProvider()
    image_provider: ImageGenerationProvider = OpenAIImageGenerationProvider()
    renderer: Renderer = SvgLayoutRenderer()
    review_rules: ReviewRuleSet = RuleBasedReviewRuleSet()

    return LangGraphOrchestrationService(
        session=session,
        text_provider=text_provider,
        image_provider=image_provider,
        renderer=renderer,
        review_rules=review_rules,
    )
