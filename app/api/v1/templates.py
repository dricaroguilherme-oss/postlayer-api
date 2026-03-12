from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user, get_membership
from app.infra.providers.supabase import request as supabase_request, require_ok

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("")
def list_templates(organization_id: str, user: dict = Depends(get_current_user)) -> list[dict]:
    get_membership(user["id"], organization_id)
    response = supabase_request(
        "GET",
        "/rest/v1/templates",
        params={
            "select": "id,name,category,format,is_public",
            "or": f"(organization_id.eq.{organization_id},is_public.eq.true)",
            "order": "created_at.desc",
        },
    )
    return require_ok(response)
