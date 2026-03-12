from __future__ import annotations

from typing import TypedDict


class SafeZone(TypedDict):
    top: int
    right: int
    bottom: int
    left: int


class FormatPreset(TypedDict):
    channel: str
    format_type: str
    label: str
    width: int
    height: int
    safe_zone: SafeZone


SOCIAL_FORMAT_PRESETS: dict[str, FormatPreset] = {
    "instagram_post_portrait": {
        "channel": "instagram",
        "format_type": "instagram_post_portrait",
        "label": "Instagram Post Retrato",
        "width": 1080,
        "height": 1350,
        "safe_zone": {"top": 96, "right": 72, "bottom": 96, "left": 72},
    },
    "instagram_post_square": {
        "channel": "instagram",
        "format_type": "instagram_post_square",
        "label": "Instagram Post Quadrado",
        "width": 1080,
        "height": 1080,
        "safe_zone": {"top": 72, "right": 72, "bottom": 72, "left": 72},
    },
    "instagram_story": {
        "channel": "instagram",
        "format_type": "instagram_story",
        "label": "Instagram Story",
        "width": 1080,
        "height": 1920,
        "safe_zone": {"top": 180, "right": 84, "bottom": 220, "left": 84},
    },
    "linkedin_post": {
        "channel": "linkedin",
        "format_type": "linkedin_post",
        "label": "LinkedIn Post",
        "width": 1080,
        "height": 1080,
        "safe_zone": {"top": 72, "right": 72, "bottom": 72, "left": 72},
    },
    "linkedin_carousel": {
        "channel": "linkedin",
        "format_type": "linkedin_carousel",
        "label": "LinkedIn Carrossel",
        "width": 1080,
        "height": 1350,
        "safe_zone": {"top": 96, "right": 72, "bottom": 96, "left": 72},
    },
    "tiktok_vertical": {
        "channel": "tiktok",
        "format_type": "tiktok_vertical",
        "label": "TikTok Vertical",
        "width": 1080,
        "height": 1920,
        "safe_zone": {"top": 180, "right": 84, "bottom": 220, "left": 84},
    },
    "youtube_thumbnail": {
        "channel": "youtube",
        "format_type": "youtube_thumbnail",
        "label": "YouTube Thumbnail",
        "width": 1280,
        "height": 720,
        "safe_zone": {"top": 56, "right": 56, "bottom": 56, "left": 56},
    },
}
