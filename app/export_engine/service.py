from __future__ import annotations

from typing import Any

from app.application.contracts.providers import Renderer


class ExportEngine:
    def __init__(self, renderer: Renderer) -> None:
        self.renderer = renderer

    def export(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.renderer.export_bitmap(payload)
