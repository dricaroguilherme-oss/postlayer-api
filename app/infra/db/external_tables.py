from __future__ import annotations

from sqlalchemy import Column, Table
from sqlalchemy.dialects.postgresql import UUID

from app.infra.db.base import Base


# Legacy tenancy tables are managed outside of the product-domain migrations.
# We register lightweight metadata stubs so SQLAlchemy can resolve foreign keys
# from the new owned domain without trying to persist these tables itself.
organizations = Table(
    "organizations",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    info={"managed_externally": True},
    extend_existing=True,
)
