from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.common.types import AssetSourceType
from app.infra.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Brand(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "brands"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_brands_tenant_name"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_colors: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    secondary_colors: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    neutral_colors: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    typography_heading: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    typography_body: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    font_weights: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False)
    default_title_sizes: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False)
    default_body_sizes: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False)
    border_radius_preset: Mapped[str | None] = mapped_column(String(64))
    shadow_preset: Mapped[str | None] = mapped_column(String(64))
    logo_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brand_assets.id", ondelete="SET NULL", use_alter=True, name="fk_brands_logo_asset_id_brand_assets"),
    )
    visual_style_keywords: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    composition_rules_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    approved_reference_assets: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    rejected_reference_assets: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    assets: Mapped[list["BrandAsset"]] = relationship(
        back_populates="brand",
        foreign_keys="BrandAsset.brand_id",
        cascade="all, delete-orphan",
    )
    logo_asset: Mapped["BrandAsset | None"] = relationship(foreign_keys=[logo_asset_id], post_update=True)
    components: Mapped[list["DesignComponent"]] = relationship(back_populates="brand", cascade="all, delete-orphan")


class BrandAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "brand_assets"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(80))
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    source_type: Mapped[AssetSourceType] = mapped_column(String(32), nullable=False, default=AssetSourceType.UPLOAD.value)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    preview_url: Mapped[str | None] = mapped_column(Text)
    dominant_color: Mapped[str | None] = mapped_column(String(32))
    is_recolorable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_decorative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    usage_context: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    brand: Mapped[Brand] = relationship(back_populates="assets", foreign_keys=[brand_id])


class DesignComponent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "design_components"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="SET NULL"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    component_type: Mapped[str] = mapped_column(String(80), nullable=False)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    style_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    brand: Mapped[Brand | None] = relationship(back_populates="components")
