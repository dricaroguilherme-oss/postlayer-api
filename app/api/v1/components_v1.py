from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, get_membership
from app.api.dependencies.db import get_session
from app.domain.brand.models import DesignComponent
from app.schemas.brand import DesignComponentListResponse, DesignComponentPayload, DesignComponentRead

router = APIRouter(prefix="/v1/components", tags=["v1-components"])


@router.post("", response_model=DesignComponentRead, status_code=status.HTTP_201_CREATED)
def create_component(
    tenant_id: UUID,
    payload: DesignComponentPayload,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DesignComponentRead:
    get_membership(user["id"], str(tenant_id))
    component = DesignComponent(tenant_id=tenant_id, **payload.model_dump(by_alias=True))
    session.add(component)
    session.commit()
    session.refresh(component)
    return DesignComponentRead.model_validate(component)


@router.get("", response_model=DesignComponentListResponse)
def list_components(
    tenant_id: UUID,
    brand_id: UUID | None = None,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DesignComponentListResponse:
    get_membership(user["id"], str(tenant_id))
    statement = select(DesignComponent).where(DesignComponent.tenant_id == tenant_id)
    if brand_id:
        statement = statement.where(DesignComponent.brand_id == brand_id)
    components = session.scalars(statement.order_by(DesignComponent.created_at.desc())).all()
    return DesignComponentListResponse(items=[DesignComponentRead.model_validate(component) for component in components])
