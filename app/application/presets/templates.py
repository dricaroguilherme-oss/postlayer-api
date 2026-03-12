from __future__ import annotations

from typing import Any, TypedDict


class TemplateSeed(TypedDict):
    id: str
    name: str
    channel: str
    format_type: str
    page_role: str
    schema_json: dict[str, Any]
    constraints_json: dict[str, Any]
    tags: list[str]
    is_system_template: bool


SYSTEM_LAYOUT_TEMPLATES: list[TemplateSeed] = [
    {
        "id": "3bbfacb2-0f09-4cf8-b8d1-b2be0d176e0d",
        "name": "Editorial Split Cover",
        "channel": "instagram",
        "format_type": "instagram_post_square",
        "page_role": "cover",
        "schema_json": {
            "canvas": {"padding": 72, "background_style": "gradient"},
            "regions": [
                {"slot": "heading", "x": 72, "y": 104, "width": 560, "height": 220},
                {"slot": "body", "x": 72, "y": 350, "width": 460, "height": 220},
                {"slot": "cta", "x": 72, "y": 900, "width": 260, "height": 84},
                {"slot": "media", "x": 640, "y": 120, "width": 320, "height": 760},
            ],
        },
        "constraints_json": {"safe_zone": "strict", "max_heading_chars": 64, "max_body_chars": 180},
        "tags": ["cover", "editorial", "split", "system"],
        "is_system_template": True,
    },
    {
        "id": "66c54b1a-74e6-4b54-9084-d757450dd091",
        "name": "Story Hero Stack",
        "channel": "instagram",
        "format_type": "instagram_story",
        "page_role": "cover",
        "schema_json": {
            "canvas": {"padding": 84, "background_style": "photo_overlay"},
            "regions": [
                {"slot": "eyebrow", "x": 84, "y": 220, "width": 480, "height": 60},
                {"slot": "heading", "x": 84, "y": 320, "width": 720, "height": 320},
                {"slot": "body", "x": 84, "y": 680, "width": 520, "height": 260},
                {"slot": "cta", "x": 84, "y": 1540, "width": 340, "height": 92},
            ],
        },
        "constraints_json": {"safe_zone": "story_strict", "max_heading_chars": 52, "max_body_chars": 140},
        "tags": ["story", "hero", "stacked", "system"],
        "is_system_template": True,
    },
    {
        "id": "5c5c7c11-3c13-42f5-a8de-8250fd8c2014",
        "name": "Carousel Insight Card",
        "channel": "linkedin",
        "format_type": "linkedin_carousel",
        "page_role": "body",
        "schema_json": {
            "canvas": {"padding": 72, "background_style": "solid"},
            "regions": [
                {"slot": "badge", "x": 72, "y": 90, "width": 240, "height": 56},
                {"slot": "heading", "x": 72, "y": 180, "width": 720, "height": 220},
                {"slot": "body", "x": 72, "y": 460, "width": 620, "height": 360},
                {"slot": "stat_card", "x": 760, "y": 280, "width": 248, "height": 320},
                {"slot": "progression_marker", "x": 72, "y": 1234, "width": 180, "height": 42},
            ],
        },
        "constraints_json": {"safe_zone": "strict", "max_heading_chars": 70, "max_body_chars": 220},
        "tags": ["carousel", "insight", "data", "system"],
        "is_system_template": True,
    },
]
