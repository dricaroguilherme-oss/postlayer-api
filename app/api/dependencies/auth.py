from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import Depends, Header, HTTPException, status

from app.infra.providers.supabase import request as supabase_request, require_ok


def get_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return authorization.removeprefix("Bearer ").strip()


def get_current_user(token: str = Depends(get_token)) -> dict[str, Any]:
    response = supabase_request("GET", "/auth/v1/user", use_service_role=False, access_token=token)
    payload = require_ok(response)
    metadata = payload.get("user_metadata") or {}
    return {
        "id": payload["id"],
        "email": payload["email"],
        "full_name": metadata.get("full_name"),
        "created_at": payload["created_at"],
        "updated_at": payload.get("updated_at") or payload["created_at"],
        "access_token": token,
    }


def get_membership(user_id: str, organization_id: str) -> dict[str, Any]:
    response = supabase_request(
        "GET",
        "/rest/v1/organization_members",
        params={
            "select": "id,role,organizations(id,name,slug,logo_url)",
            "user_id": f"eq.{user_id}",
            "organization_id": f"eq.{organization_id}",
            "limit": "1",
        },
    )
    rows = require_ok(response)
    if not rows:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this organization")

    membership = rows[0]
    org = membership.get("organizations") or {}
    return {
        "id": membership["id"],
        "role": membership["role"],
        "organization_id": org.get("id", organization_id),
        "name": org.get("name"),
        "slug": org.get("slug"),
        "logo_url": org.get("logo_url"),
    }


def slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return base or f"org-{uuid.uuid4().hex[:8]}"
