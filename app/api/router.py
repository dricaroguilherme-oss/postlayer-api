from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    ai,
    assets_v1,
    auth,
    brand,
    brands_v1,
    components_v1,
    creative,
    organizations,
    presets,
    projects_v1,
    team,
    templates,
    templates_v1,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(brand.router)
api_router.include_router(team.router)
api_router.include_router(templates.router)
api_router.include_router(creative.router)
api_router.include_router(ai.router)
api_router.include_router(presets.router)
api_router.include_router(brands_v1.router)
api_router.include_router(assets_v1.router)
api_router.include_router(components_v1.router)
api_router.include_router(templates_v1.router)
api_router.include_router(projects_v1.router)
