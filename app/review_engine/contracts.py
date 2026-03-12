from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewSignal(BaseModel):
    code: str
    severity: str
    message: str
    target_node_id: str | None = None


class ReviewSummary(BaseModel):
    warnings: list[ReviewSignal] = Field(default_factory=list)
    legibility_score: float = 0.0
    brand_adherence_score: float = 0.0
    contrast_score: float = 0.0
    text_density_score: float = 0.0
