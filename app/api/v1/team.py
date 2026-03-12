from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user, get_membership
from app.infra.providers.supabase import request as supabase_request, require_ok

router = APIRouter(prefix="/team", tags=["team"])


@router.get("/{organization_id}")
def list_team(organization_id: str, user: dict = Depends(get_current_user)) -> list[dict]:
    get_membership(user["id"], organization_id)
    members_response = supabase_request(
        "GET",
        "/rest/v1/organization_members",
        params={"select": "id,role,user_id", "organization_id": f"eq.{organization_id}", "order": "created_at.asc"},
    )
    members = require_ok(members_response)
    user_ids = [member["user_id"] for member in members]
    if not user_ids:
        return []

    profiles_response = supabase_request(
        "GET",
        "/rest/v1/profiles",
        params={"select": "user_id,full_name", "user_id": f"in.({','.join(user_ids)})"},
    )
    profiles = require_ok(profiles_response)
    profile_by_user_id = {profile["user_id"]: profile for profile in profiles}

    return [{**member, "full_name": profile_by_user_id.get(member["user_id"], {}).get("full_name")} for member in members]
