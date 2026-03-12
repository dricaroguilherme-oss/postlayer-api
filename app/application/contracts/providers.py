from __future__ import annotations

from typing import Any, Protocol


class TextReasoningProvider(Protocol):
    def generate_content_plan(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def generate_art_direction(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def summarize(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class ImageGenerationProvider(Protocol):
    def generate_asset(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class AssetStorageProvider(Protocol):
    def save_asset(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class Renderer(Protocol):
    def render_preview(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def export_bitmap(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class ReviewRuleSet(Protocol):
    def run(self, payload: dict[str, Any]) -> dict[str, Any]: ...
