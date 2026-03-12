from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.creative.models import ProjectVersion


def next_project_version_number(session: Session, project_id: str) -> int:
    statement = select(func.coalesce(func.max(ProjectVersion.version_number), 0)).where(
        ProjectVersion.project_id == project_id
    )
    current = session.scalar(statement) or 0
    return int(current) + 1
