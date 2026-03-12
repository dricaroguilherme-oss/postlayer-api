from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user
from app.schemas.auth import LoginPayload, RegisterPayload
from app.infra.providers.supabase import request as supabase_request, require_ok

router = APIRouter(prefix="/auth", tags=["auth"])


def auth_response(payload: dict) -> dict:
    user = payload["user"]
    metadata = user.get("user_metadata") or {}
    return {
        "access_token": payload["access_token"],
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": metadata.get("full_name"),
            "created_at": user["created_at"],
            "updated_at": user.get("updated_at") or user["created_at"],
        },
    }


@router.post("/register")
def register(payload: RegisterPayload) -> dict:
    create_response = supabase_request(
        "POST",
        "/auth/v1/admin/users",
        json={
            "email": payload.email.lower(),
            "password": payload.password,
            "email_confirm": True,
            "user_metadata": {"full_name": payload.full_name},
        },
    )
    require_ok(create_response)
    return login(LoginPayload(email=payload.email, password=payload.password))


@router.post("/login")
def login(payload: LoginPayload) -> dict:
    response = supabase_request(
        "POST",
        "/auth/v1/token",
        use_service_role=False,
        params={"grant_type": "password"},
        json={"email": payload.email.lower(), "password": payload.password},
    )
    payload_data = require_ok(response)
    return auth_response(payload_data)


@router.get("/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    return {key: user[key] for key in ("id", "email", "full_name", "created_at", "updated_at")}
