from __future__ import annotations

from uuid import UUID

from app.application.presets.templates import SYSTEM_LAYOUT_TEMPLATES


def test_system_layout_templates_have_unique_ids() -> None:
    identifiers = [UUID(template["id"]) for template in SYSTEM_LAYOUT_TEMPLATES]
    assert len(identifiers) == len(set(identifiers))


def test_system_layout_templates_cover_multiple_formats() -> None:
    formats = {template["format_type"] for template in SYSTEM_LAYOUT_TEMPLATES}
    assert {"instagram_post_square", "instagram_story", "linkedin_carousel"}.issubset(formats)


def test_seed_templates_include_structural_schema() -> None:
    first_template = SYSTEM_LAYOUT_TEMPLATES[0]
    assert "canvas" in first_template["schema_json"]
    assert first_template["constraints_json"]["safe_zone"]
