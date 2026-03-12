from __future__ import annotations

from app.infra.db.base import Base
from app.infra.db import models  # noqa: F401


def test_domain_tables_are_registered() -> None:
    expected_tables = {
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


def test_project_versioning_constraints_exist() -> None:
    creative_projects = Base.metadata.tables["creative_projects"]
    project_versions = Base.metadata.tables["project_versions"]
    creative_pages = Base.metadata.tables["creative_pages"]

    assert "current_version_id" in creative_projects.c
    assert any(constraint.name == "uq_project_versions_project_version" for constraint in project_versions.constraints)
    assert any(constraint.name == "uq_creative_pages_project_page" for constraint in creative_pages.constraints)
