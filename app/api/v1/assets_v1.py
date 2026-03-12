from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, get_membership
from app.api.dependencies.db import get_session
from app.domain.brand.models import BrandAsset
from app.schemas.brand import BrandAssetPayload, BrandAssetRead

router = APIRouter(prefix="/v1/assets", tags=["v1-assets"])


@router.post("", response_model=BrandAssetRead, status_code=status.HTTP_201_CREATED)
def create_asset(
    tenant_id: UUID,
    payload: BrandAssetPayload,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BrandAssetRead:
    get_membership(user["id"], str(tenant_id))
    asset = BrandAsset(tenant_id=tenant_id, **payload.model_dump())
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return BrandAssetRead.model_validate(asset)


@router.get("", response_model=list[BrandAssetRead])
def list_assets(
    tenant_id: UUID,
    brand_id: UUID | None = None,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[BrandAssetRead]:
    get_membership(user["id"], str(tenant_id))
    statement = select(BrandAsset).where(BrandAsset.tenant_id == tenant_id)
    if brand_id:
        statement = statement.where(BrandAsset.brand_id == brand_id)
    assets = session.scalars(statement.order_by(BrandAsset.created_at.desc())).all()
    return [BrandAssetRead.model_validate(asset) for asset in assets]
