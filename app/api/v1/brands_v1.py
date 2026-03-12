from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, get_membership
from app.api.dependencies.db import get_session
from app.domain.brand.models import Brand
from app.schemas.brand import BrandCreatePayload, BrandListResponse, BrandRead

router = APIRouter(prefix="/v1/brands", tags=["v1-brands"])


@router.post("", response_model=BrandRead, status_code=status.HTTP_201_CREATED)
def create_brand(
    tenant_id: UUID,
    payload: BrandCreatePayload,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BrandRead:
    get_membership(user["id"], str(tenant_id))
    brand = Brand(tenant_id=tenant_id, **payload.model_dump())
    session.add(brand)
    session.commit()
    session.refresh(brand)
    return BrandRead.model_validate(brand)


@router.get("", response_model=BrandListResponse)
def list_brands(
    tenant_id: UUID,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BrandListResponse:
    get_membership(user["id"], str(tenant_id))
    brands = session.scalars(select(Brand).where(Brand.tenant_id == tenant_id).order_by(Brand.created_at.desc())).all()
    return BrandListResponse(items=[BrandRead.model_validate(brand) for brand in brands])


@router.get("/{brand_id}", response_model=BrandRead)
def get_brand_v1(
    brand_id: UUID,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BrandRead:
    brand = session.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    get_membership(user["id"], str(brand.tenant_id))
    return BrandRead.model_validate(brand)
