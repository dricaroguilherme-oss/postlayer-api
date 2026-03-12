from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.brand import BrandAssetRead, DesignComponentRead
from app.schemas.common import APIModel


class MemorySuggestionPayload(BaseModel):
    name: str
    category: str
    component_type: str | None = None
    tags: list[str] = Field(default_factory=list)
    origin: str | None = None
    usage_context: list[str] = Field(default_factory=list)
    file_url: str | None = None
    preview_url: str | None = None
    dominant_color: str | None = None
    ai_generated: bool = False
    is_decorative: bool = False
    schema_definition: dict[str, Any] = Field(default_factory=dict, alias="schema_json", serialization_alias="schema_json")
    style_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = None


class AcceptMemorySuggestionPayload(APIModel):
    suggestion: MemorySuggestionPayload
    save_as: Literal["asset", "component"] | None = None
    brand_id: UUID | None = None
    name: str | None = None
    tags: list[str] | None = None
    category: str | None = None
    component_type: str | None = None


class AcceptMemorySuggestionResponse(BaseModel):
    kind: Literal["asset", "component"]
    asset: BrandAssetRead | None = None
    component: DesignComponentRead | None = None
