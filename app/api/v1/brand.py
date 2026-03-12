from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.auth import get_current_user, get_membership
from app.infra.providers.supabase import request as supabase_request, require_ok
from app.schemas.brand import BrandPayload

router = APIRouter(prefix="/brand", tags=["brand"])


@router.get("/{organization_id}")
def get_brand(organization_id: str, user: dict = Depends(get_current_user)) -> dict:
    get_membership(user["id"], organization_id)
    response = supabase_request(
        "GET",
        "/rest/v1/brand_settings",
        params={"select": "*", "organization_id": f"eq.{organization_id}", "limit": "1"},
    )
    rows = require_ok(response)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand settings not found")
    return rows[0]


@router.put("/{organization_id}")
def update_brand(organization_id: str, payload: BrandPayload, user: dict = Depends(get_current_user)) -> dict:
    membership = get_membership(user["id"], organization_id)
    if membership["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    response = supabase_request(
        "PATCH",
        "/rest/v1/brand_settings",
        headers={"Prefer": "return=representation"},
        params={"organization_id": f"eq.{organization_id}"},
        json=payload.model_dump(),
    )
    rows = require_ok(response)
    return rows[0]
