from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LayoutTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "layout_templates"
    __table_args__ = (
        CheckConstraint(
            "tenant_id IS NOT NULL OR is_system_template = true",
            name="layout_templates_scope",
        ),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="SET NULL"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    format_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    page_role: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    constraints_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    is_system_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
