from __future__ import annotations

from pydantic import BaseModel


class RenderRequest(BaseModel):
    render_tree: dict
    dimensions: dict
    format: str = "svg"
