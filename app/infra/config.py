from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    postlayer_allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080,http://localhost:5173"
    )
    database_url: str | None = None
    openai_api_key: str | None = None
    openai_text_model: str = "gpt-5-mini"
    openai_image_model: str = "gpt-image-1"
    openai_enable_live_calls: bool = False

    @property
    def sqlalchemy_database_url(self) -> str | None:
        if not self.database_url:
            return None
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
