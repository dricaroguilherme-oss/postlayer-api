from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.infra.config import get_settings
from app.infra.db import models as _models  # noqa: F401

settings = get_settings()
DATABASE_URL = settings.sqlalchemy_database_url

engine_kwargs: dict = {"pool_pre_ping": True}


def _uses_pooler(database_url: str | None) -> bool:
    if not database_url:
        return False
    try:
        parsed = make_url(database_url)
    except Exception:
        return False

    host = (parsed.host or "").lower()
    return "pooler.supabase.com" in host or parsed.port in {6432, 6543}


if _uses_pooler(DATABASE_URL):
    # Serverless functions should not hold open pools against Supabase poolers.
    engine_kwargs["poolclass"] = NullPool
    # Supavisor/PgBouncer can reject prepared statements in transaction mode.
    engine_kwargs["connect_args"] = {"prepare_threshold": None}


engine = create_engine(DATABASE_URL, **engine_kwargs) if DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False) if engine else None


def get_db_session() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is required to use the ORM-backed domain modules.")

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
