from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, get_membership
from app.api.dependencies.db import get_session
from app.domain.template.models import LayoutTemplate
from app.schemas.templates import LayoutTemplateListResponse, LayoutTemplatePayload, LayoutTemplateRead

router = APIRouter(prefix="/v1/templates", tags=["v1-templates"])


@router.post("", response_model=LayoutTemplateRead, status_code=status.HTTP_201_CREATED)
def create_template(
    tenant_id: UUID,
    payload: LayoutTemplatePayload,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LayoutTemplateRead:
    get_membership(user["id"], str(tenant_id))
    template = LayoutTemplate(tenant_id=tenant_id, **payload.model_dump(by_alias=True))
    session.add(template)
    session.commit()
    session.refresh(template)
    return LayoutTemplateRead.model_validate(template)


@router.get("", response_model=LayoutTemplateListResponse)
def list_templates_v1(
    tenant_id: UUID,
    brand_id: UUID | None = None,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LayoutTemplateListResponse:
    get_membership(user["id"], str(tenant_id))
    statement = select(LayoutTemplate).where(
        or_(LayoutTemplate.tenant_id == tenant_id, LayoutTemplate.is_system_template.is_(True))
    )
    if brand_id:
        statement = statement.where(or_(LayoutTemplate.brand_id == brand_id, LayoutTemplate.brand_id.is_(None)))
    templates = session.scalars(statement.order_by(LayoutTemplate.created_at.desc())).all()
    return LayoutTemplateListResponse(items=[LayoutTemplateRead.model_validate(template) for template in templates])
