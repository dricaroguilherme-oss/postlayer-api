from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.dependencies.auth import get_current_user, slugify
from app.infra.providers.supabase import request as supabase_request, require_ok
from app.schemas.creative import OrganizationPayload

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("")
def list_organizations(user: dict = Depends(get_current_user)) -> list[dict]:
    response = supabase_request(
        "GET",
        "/rest/v1/organization_members",
        params={
            "select": "role,organizations(id,name,slug,logo_url)",
            "user_id": f"eq.{user['id']}",
            "order": "created_at.asc",
        },
    )
    rows = require_ok(response)
    organizations = []
    for row in rows:
        org = row.get("organizations")
        if org:
          organizations.append({**org, "role": row["role"]})
    return organizations


@router.post("", status_code=status.HTTP_201_CREATED)
def create_organization(payload: OrganizationPayload, user: dict = Depends(get_current_user)) -> dict:
    org_id = str(uuid.uuid4())
    member_id = str(uuid.uuid4())
    brand_id = str(uuid.uuid4())
    slug = slugify(payload.name)
    existing_response = supabase_request(
        "GET",
        "/rest/v1/organizations",
        params={"select": "id", "slug": f"eq.{slug}", "limit": "1"},
    )
    if require_ok(existing_response):
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    org_response = supabase_request(
        "POST",
        "/rest/v1/organizations",
        headers={"Prefer": "return=representation"},
        json={"id": org_id, "name": payload.name, "slug": slug},
    )
    created_org = require_ok(org_response)[0]
    supabase_request(
        "POST",
        "/rest/v1/organization_members",
        headers={"Prefer": "return=minimal"},
        json={"id": member_id, "organization_id": org_id, "user_id": user["id"], "role": "admin"},
    ).raise_for_status()
    supabase_request(
        "POST",
        "/rest/v1/brand_settings",
        headers={"Prefer": "return=minimal"},
        json={"id": brand_id, "organization_id": org_id},
    ).raise_for_status()

    return {**created_org, "role": "admin"}
