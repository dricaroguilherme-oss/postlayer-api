from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import APIModel, ORMModel


class BrandPayload(BaseModel):
    primary_color: str
    secondary_color: str
    accent_color: str
    font_heading: str
    font_body: str


class BrandSystem(BaseModel):
    color_tokens: dict[str, list[str]]
    typography: dict[str, object]
    radius_preset: str
    shadow_preset: str
    visual_style_keywords: list[str] = Field(default_factory=list)
    composition_rules: dict[str, object] = Field(default_factory=dict)
    approved_refs: list[str] = Field(default_factory=list)
    rejected_refs: list[str] = Field(default_factory=list)


class BrandAssetPayload(APIModel):
    brand_id: UUID
    name: str
    category: str
    subcategory: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_type: str = "upload"
    file_url: str
    preview_url: str | None = None
    dominant_color: str | None = None
    is_recolorable: bool = False
    is_decorative: bool = False
    usage_context: list[str] = Field(default_factory=list)
    ai_generated: bool = False
    metadata_json: dict[str, object] = Field(default_factory=dict)


class BrandAssetRead(ORMModel):
    id: UUID
    tenant_id: UUID
    brand_id: UUID
    name: str
    category: str
    subcategory: str | None = None
    tags: list[str]
    source_type: str
    file_url: str
    preview_url: str | None = None
    dominant_color: str | None = None
    is_recolorable: bool
    is_decorative: bool
    usage_context: list[str]
    ai_generated: bool
    metadata_json: dict[str, object]
    created_at: datetime
    updated_at: datetime


class DesignComponentPayload(APIModel):
    brand_id: UUID | None = None
    name: str
    component_type: str
    schema_definition: dict[str, object] = Field(default_factory=dict, alias="schema_json", serialization_alias="schema_json")
    style_json: dict[str, object] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class DesignComponentRead(ORMModel):
    id: UUID
    tenant_id: UUID
    brand_id: UUID | None = None
    name: str
    component_type: str
    schema_definition: dict[str, object] = Field(alias="schema_json", serialization_alias="schema_json")
    style_json: dict[str, object]
    tags: list[str]
    usage_count: int
    created_at: datetime
    updated_at: datetime


class BrandCreatePayload(BaseModel):
    name: str
    primary_colors: list[str] = Field(default_factory=list)
    secondary_colors: list[str] = Field(default_factory=list)
    neutral_colors: list[str] = Field(default_factory=list)
    typography_heading: dict[str, object] = Field(default_factory=dict)
    typography_body: dict[str, object] = Field(default_factory=dict)
    font_weights: list[int] = Field(default_factory=list)
    default_title_sizes: list[int] = Field(default_factory=list)
    default_body_sizes: list[int] = Field(default_factory=list)
    border_radius_preset: str | None = None
    shadow_preset: str | None = None
    logo_asset_id: UUID | None = None
    visual_style_keywords: list[str] = Field(default_factory=list)
    composition_rules_json: dict[str, object] = Field(default_factory=dict)
    approved_reference_assets: list[str] = Field(default_factory=list)
    rejected_reference_assets: list[str] = Field(default_factory=list)


class BrandRead(ORMModel):
    id: UUID
    tenant_id: UUID
    name: str
    primary_colors: list[str]
    secondary_colors: list[str]
    neutral_colors: list[str]
    typography_heading: dict[str, object]
    typography_body: dict[str, object]
    font_weights: list[int]
    default_title_sizes: list[int]
    default_body_sizes: list[int]
    border_radius_preset: str | None = None
    shadow_preset: str | None = None
    logo_asset_id: UUID | None = None
    visual_style_keywords: list[str]
    composition_rules_json: dict[str, object]
    approved_reference_assets: list[str]
    rejected_reference_assets: list[str]
    created_at: datetime
    updated_at: datetime


class BrandListResponse(BaseModel):
    items: list[BrandRead] = Field(default_factory=list)
