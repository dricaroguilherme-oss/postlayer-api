from __future__ import annotations

from pydantic import BaseModel


class ExportRequest(BaseModel):
    project_id: str
    version_id: str
    file_type: str
    dimensions: dict
    dpi: int = 144
