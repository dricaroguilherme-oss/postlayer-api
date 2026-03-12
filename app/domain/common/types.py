from __future__ import annotations

from enum import StrEnum


class PieceType(StrEnum):
    SINGLE_POST = "single_post"
    CAROUSEL = "carousel"


class LayoutNodeType(StrEnum):
    CANVAS = "canvas"
    BACKGROUND = "background"
    IMAGE = "image"
    TEXT = "text"
    HEADING = "heading"
    SUBHEADING = "subheading"
    PARAGRAPH = "paragraph"
    BADGE = "badge"
    ICON = "icon"
    SHAPE = "shape"
    CARD = "card"
    DIVIDER = "divider"
    CTA = "cta"
    GROUP = "group"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    GENERATING = "generating"
    IN_REVIEW = "in_review"
    READY = "ready"
    EXPORTED = "exported"
    FAILED = "failed"


class ProjectVersionSourceType(StrEnum):
    SYSTEM_GENERATION = "system_generation"
    USER_EDIT = "user_edit"
    AUTOFIX = "autofix"
    EXPORT_SNAPSHOT = "export_snapshot"


class ExportFileType(StrEnum):
    PNG = "png"
    JPG = "jpg"


class AssetSourceType(StrEnum):
    UPLOAD = "upload"
    AI_GENERATED = "ai_generated"
    SYSTEM = "system"
    IMPORTED = "imported"
