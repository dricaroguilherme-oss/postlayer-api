from __future__ import annotations

from app.infra.db.base import Base
from app.infra.db import session  # noqa: F401


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
