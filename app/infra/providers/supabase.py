from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException, status

from app.infra.config import get_settings

settings = get_settings()


def supabase_url() -> str:
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is required")
    return settings.supabase_url.strip().rstrip("/")


def anon_key() -> str:
    if not settings.supabase_anon_key:
        raise RuntimeError("SUPABASE_ANON_KEY is required")
    return settings.supabase_anon_key.strip()


def service_role_key() -> str:
    if not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required")
    return settings.supabase_service_role_key.strip()


def request(
    method: str,
    path: str,
    *,
    use_service_role: bool = True,
    access_token: str | None = None,
    params: dict[str, Any] | None = None,
    json: Any | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    key = service_role_key() if use_service_role else anon_key()
    merged_headers = {
        "apikey": key,
        "Authorization": f"Bearer {access_token or key}",
    }
    if headers:
        merged_headers.update(headers)

    return httpx.request(
        method,
        f"{supabase_url()}{path}",
        params=params,
        json=json,
        headers=merged_headers,
        timeout=20.0,
    )


def require_ok(response: httpx.Response) -> Any:
    if response.is_success:
        if not response.content:
            return None
        return response.json()

    try:
        payload = response.json()
        detail = payload.get("msg") or payload.get("message") or payload.get("error_description") or payload.get("error")
    except Exception:
        detail = response.text or "Supabase request failed"

    raise HTTPException(status_code=response.status_code or status.HTTP_502_BAD_GATEWAY, detail=detail)


def content_range_total(response: httpx.Response) -> int:
    content_range = response.headers.get("content-range", "")
    if "/" not in content_range:
        return 0
    total = content_range.rsplit("/", 1)[-1]
    return int(total) if total.isdigit() else 0
