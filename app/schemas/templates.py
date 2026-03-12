from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import APIModel, ORMModel


class LayoutTemplatePayload(APIModel):
    brand_id: UUID | None = None
    name: str
    channel: str
    format_type: str
    page_role: str
    schema_definition: dict[str, object] = Field(default_factory=dict, alias="schema_json", serialization_alias="schema_json")
    constraints_json: dict[str, object] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    is_system_template: bool = False


class LayoutTemplateRead(ORMModel):
    id: UUID
    tenant_id: UUID | None = None
    brand_id: UUID | None = None
    name: str
    channel: str
    format_type: str
    page_role: str
    schema_definition: dict[str, object] = Field(alias="schema_json", serialization_alias="schema_json")
    constraints_json: dict[str, object]
    tags: list[str]
    is_system_template: bool
    created_at: datetime
    updated_at: datetime


class LayoutTemplateListResponse(BaseModel):
    items: list[LayoutTemplateRead] = Field(default_factory=list)
