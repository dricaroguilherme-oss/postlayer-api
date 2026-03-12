from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infra.config import get_settings
from app.infra.db import models as _models  # noqa: F401

settings = get_settings()
DATABASE_URL = settings.sqlalchemy_database_url

engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False) if engine else None


def get_db_session() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is required to use the ORM-backed domain modules.")

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
