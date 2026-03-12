from __future__ import annotations

from app.infra.db.base import Base
from app.infra.db import session


def test_session_bootstrap_registers_domain_tables() -> None:
    expected_tables = {
        "organizations",
        "brands",
        "brand_assets",
        "layout_templates",
        "design_components",
        "creative_projects",
        "creative_pages",
        "project_versions",
        "export_jobs",
        "ai_jobs",
    }
    assert expected_tables.issubset(Base.metadata.tables.keys())


def test_uses_pooler_for_supabase_pooler_host() -> None:
    database_url = "postgresql+psycopg://postgres.project-ref:secret@aws-1-us-east-1.pooler.supabase.com:5432/postgres"
    assert session._uses_pooler(database_url) is True


def test_does_not_treat_direct_supabase_host_as_pooler() -> None:
    database_url = "postgresql+psycopg://postgres:secret@db.project-ref.supabase.co:5432/postgres"
    assert session._uses_pooler(database_url) is False
