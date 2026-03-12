from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import APIModel


class LangGraphState(BaseModel):
    project_context: dict[str, Any]
    brand_context: dict[str, Any]
    asset_context: dict[str, Any]
    template_context: dict[str, Any]
    content_plan: dict[str, Any] | None = None
    art_direction_plan: dict[str, Any] | None = None
    generated_assets: list[dict[str, Any]] = Field(default_factory=list)
    composition_result: dict[str, Any] | None = None
    review_result: dict[str, Any] | None = None
    user_edits: dict[str, Any] | None = None
    export_context: dict[str, Any] | None = None
    execution_log: list[dict[str, Any]] = Field(default_factory=list)
    asset_suggestions: list[dict[str, Any]] = Field(default_factory=list)
    version_id: str | None = None
    ai_job_id: str | None = None
    export_job_id: str | None = None


class OrchestrateProjectPayload(APIModel):
    export_after_run: bool = False
    export_file_type: str = "png"
    dpi: int = 144
    user_edits: dict[str, Any] | None = None


class PageEditPayload(APIModel):
    layout_json: dict[str, Any] | None = None
    content_plan_json: dict[str, Any] | None = None
    review_json: dict[str, Any] | None = None


class ReorderProjectPagesPayload(APIModel):
    page_ids: list[UUID] = Field(min_length=1)


class WorkflowRunResponse(BaseModel):
    project_id: UUID
    version_id: UUID | None = None
    ai_job_id: UUID | None = None
    content_plan: dict[str, Any] | None = None
    art_direction_plan: dict[str, Any] | None = None
    generated_assets: list[dict[str, Any]] = Field(default_factory=list)
    composition_result: dict[str, Any] | None = None
    review_result: dict[str, Any] | None = None
    asset_suggestions: list[dict[str, Any]] = Field(default_factory=list)
    export_job_id: UUID | None = None
    export_context: dict[str, Any] | None = None
    execution_log: list[dict[str, Any]] = Field(default_factory=list)
