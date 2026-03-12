from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.common.types import ExportFileType, JobStatus, PieceType, ProjectStatus, ProjectVersionSourceType
from app.infra.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CreativeProject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "creative_projects"

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
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    format_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    piece_type: Mapped[str] = mapped_column(String(32), default=PieceType.SINGLE_POST.value, nullable=False)
    dimensions_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    objective: Mapped[str] = mapped_column(String(255), nullable=False)
    audience: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    cta: Mapped[str | None] = mapped_column(String(255))
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=ProjectStatus.DRAFT.value, nullable=False, index=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "project_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_creative_projects_current_version_id_project_versions",
        ),
    )
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)

    pages: Mapped[list["CreativePage"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    versions: Mapped[list["ProjectVersion"]] = relationship(
        back_populates="project",
        foreign_keys="ProjectVersion.project_id",
        cascade="all, delete-orphan",
    )
    export_jobs: Mapped[list["ExportJob"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    ai_jobs: Mapped[list["AIJob"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    current_version: Mapped["ProjectVersion | None"] = relationship(
        foreign_keys=[current_version_id],
        post_update=True,
    )


class CreativePage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "creative_pages"
    __table_args__ = (UniqueConstraint("project_id", "page_index", name="uq_creative_pages_project_page"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creative_projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    page_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_role: Mapped[str] = mapped_column(String(64), nullable=False)
    content_plan_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    layout_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    review_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    project: Mapped[CreativeProject] = relationship(back_populates="pages")


class ProjectVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "project_versions"
    __table_args__ = (UniqueConstraint("project_id", "version_number", name="uq_project_versions_project_version"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creative_projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default=ProjectVersionSourceType.SYSTEM_GENERATION.value, nullable=False)
    strategy_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    art_direction_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    render_tree_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    exported_assets_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project: Mapped[CreativeProject] = relationship(back_populates="versions", foreign_keys=[project_id])
    export_jobs: Mapped[list["ExportJob"]] = relationship(back_populates="version", cascade="all, delete-orphan")


class ExportJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "export_jobs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creative_projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    file_type: Mapped[str] = mapped_column(String(16), default=ExportFileType.PNG.value, nullable=False)
    dimensions_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    dpi: Mapped[int] = mapped_column(Integer, default=144, nullable=False)
    output_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.PENDING.value, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[CreativeProject] = relationship(back_populates="export_jobs")
    version: Mapped[ProjectVersion] = relationship(back_populates="export_jobs")


class AIJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_jobs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creative_projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.PENDING.value, nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text)

    project: Mapped[CreativeProject] = relationship(back_populates="ai_jobs")
