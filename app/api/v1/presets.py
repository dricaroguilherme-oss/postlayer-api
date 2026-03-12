from __future__ import annotations

from fastapi import APIRouter

from app.application.presets.social import SOCIAL_FORMAT_PRESETS

router = APIRouter(prefix="/presets", tags=["presets"])


@router.get("/formats")
def get_format_presets() -> dict:
    return {"items": list(SOCIAL_FORMAT_PRESETS.values())}
