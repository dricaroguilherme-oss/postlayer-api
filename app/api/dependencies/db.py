from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.infra.db.session import get_db_session


def get_session() -> Generator[Session, None, None]:
    yield from get_db_session()
