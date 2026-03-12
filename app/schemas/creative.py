from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.common.types import LayoutNodeType, PieceType
from app.schemas.common import ORMModel


class OrganizationPayload(BaseModel):
    name: str


class LayerPayload(BaseModel):
    type: str
    visible: bool = True
    properties: dict[str, Any] = Field(default_factory=dict)


class CreatePostPayload(BaseModel):
    organization_id: str
    title: str
    format: str
    width: int
    height: int
    layers: list[LayerPayload]


class BackgroundPayload(BaseModel):
    prompt: str
    width: int
    height: int


class LayoutNodeConstraints(BaseModel):
    align: str | None = None
    max_chars: int | None = None
    min_font_size: int | None = None
    max_font_size: int | None = None
    padding: int | None = None
    safe_zone_behavior: str | None = None
    truncate_behavior: str | None = None
    priority: int | None = None


class LayoutNode(BaseModel):
    id: str
    type: LayoutNodeType
    x: float
    y: float
    width: float
    height: float
    z_index: int
    rotation: float | None = None
    style: dict[str, Any] = Field(default_factory=dict)
    content: dict[str, Any] | None = None
    asset_ref: str | None = None
    constraints: LayoutNodeConstraints | None = None
    children: list["LayoutNode"] = Field(default_factory=list)


class ProjectContext(BaseModel):
    channel: str
    format_type: str
    piece_type: PieceType
    page_count: int
    dimensions: dict[str, int]
    objective: str
    audience: str
    language: str
    cta: str | None = None
    user_prompt: str


class ContentPlanSlide(BaseModel):
    page_index: int
    page_role: str
    headline: str
    body: str
    cta: str | None = None
    narrative_intent: str


class ContentPlan(BaseModel):
    project_id: str
    global_message: str
    slides: list[ContentPlanSlide]


class ArtDirectionPlan(BaseModel):
    visual_direction: str
    palette_mode: str
    template_id: str | None = None
    component_refs: list[str] = Field(default_factory=list)
    asset_refs: list[str] = Field(default_factory=list)
    generation_instructions: list[str] = Field(default_factory=list)


class ReviewWarning(BaseModel):
    code: str
    severity: str
    message: str
    target_node_id: str | None = None


class ReviewResult(BaseModel):
    warnings: list[ReviewWarning] = Field(default_factory=list)
    legibility_score: float
    brand_adherence_score: float
    contrast_score: float
    text_density_score: float
    autofixes_applied: list[str] = Field(default_factory=list)


class CreativeProjectPayload(BaseModel):
    brand_id: UUID | None = None
    title: str
    channel: str
    format_type: str
    piece_type: PieceType = PieceType.SINGLE_POST
    dimensions_json: dict[str, int]
    objective: str
    audience: str
    language: str
    cta: str | None = None
    page_count: int
    user_prompt: str
    status: str = "draft"
    created_by: str | None = None


class CreativePagePayload(BaseModel):
    page_index: int
    page_role: str
    content_plan_json: dict[str, Any] = Field(default_factory=dict)
    layout_json: dict[str, Any] = Field(default_factory=dict)
    review_json: dict[str, Any] = Field(default_factory=dict)


class ProjectVersionPayload(BaseModel):
    source_type: str = "system_generation"
    strategy_json: dict[str, Any] = Field(default_factory=dict)
    art_direction_json: dict[str, Any] = Field(default_factory=dict)
    render_tree_json: dict[str, Any] = Field(default_factory=dict)
    exported_assets_json: dict[str, Any] = Field(default_factory=dict)


class ExportJobPayload(BaseModel):
    version_id: UUID
    file_type: str = "png"
    dimensions_json: dict[str, int]
    dpi: int = 144


class AIJobPayload(BaseModel):
    job_type: str
    provider: str
    model: str
    input_json: dict[str, Any] = Field(default_factory=dict)
    output_json: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    error_message: str | None = None


class CreativePageRead(ORMModel):
    id: UUID
    project_id: UUID
    page_index: int
    page_role: str
    content_plan_json: dict[str, Any]
    layout_json: dict[str, Any]
    review_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProjectVersionRead(ORMModel):
    id: UUID
    project_id: UUID
    version_number: int
    source_type: str
    strategy_json: dict[str, Any]
    art_direction_json: dict[str, Any]
    render_tree_json: dict[str, Any]
    exported_assets_json: dict[str, Any]
    created_at: datetime


class ExportJobRead(ORMModel):
    id: UUID
    project_id: UUID
    version_id: UUID
    file_type: str
    dimensions_json: dict[str, Any]
    dpi: int
    output_url: str | None = None
    status: str
    created_at: datetime
    completed_at: datetime | None = None


class AIJobRead(ORMModel):
    id: UUID
    project_id: UUID
    job_type: str
    provider: str
    model: str
    input_json: dict[str, Any]
    output_json: dict[str, Any]
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class CreativeProjectRead(ORMModel):
    id: UUID
    tenant_id: UUID
    brand_id: UUID | None = None
    title: str
    channel: str
    format_type: str
    piece_type: str
    dimensions_json: dict[str, Any]
    objective: str
    audience: str
    language: str
    cta: str | None = None
    page_count: int
    user_prompt: str
    status: str
    current_version_id: UUID | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class CreativeProjectBundle(ORMModel):
    project: CreativeProjectRead
    pages: list[CreativePageRead] = Field(default_factory=list)
    versions: list[ProjectVersionRead] = Field(default_factory=list)


class CreativeProjectListResponse(BaseModel):
    items: list[CreativeProjectRead] = Field(default_factory=list)
