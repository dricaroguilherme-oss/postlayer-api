from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.infra.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    allowed_origins = [
        origin.strip()
        for origin in settings.postlayer_allowed_origins.split(",")
        if origin.strip()
    ]
    allow_all_origins = allowed_origins == ["*"]

    app = FastAPI(
        title="PostLayer API",
        version="0.2.0",
        description="API modular para orquestração criativa, brand system e composição programática.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all_origins else allowed_origins,
        allow_credentials=not allow_all_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", tags=["system"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)
    return app


app = create_app()
