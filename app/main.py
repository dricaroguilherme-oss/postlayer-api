from __future__ import annotations

import os
import re
import uuid
import urllib.parse
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.supabase import content_range_total, request as supabase_request, require_ok


allowed_origins = [
    origin.strip()
    for origin in os.getenv("POSTLAYER_ALLOWED_ORIGINS", "http://localhost:8080,http://localhost:5173").split(",")
    if origin.strip()
]
allow_all_origins = allowed_origins == ["*"]


app = FastAPI(title="PostLayer API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else allowed_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RegisterPayload(BaseModel):
    email: str
    password: str = Field(min_length=6)
    full_name: str | None = None


class LoginPayload(BaseModel):
    email: str
    password: str


class OrganizationPayload(BaseModel):
    name: str


class BrandPayload(BaseModel):
    primary_color: str
    secondary_color: str
    accent_color: str
    font_heading: str
    font_body: str


class LayerPayload(BaseModel):
    type: str
    visible: bool = True
    properties: dict[str, Any] = Field(default_factory=dict)


class CreatePostPayload(BaseModel):
    organization_id: str
    title: str
    format: str
    width: int
    height: int
    layers: list[LayerPayload]


class BackgroundPayload(BaseModel):
    prompt: str
    width: int
    height: int


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


def auth_response(payload: dict[str, Any]) -> dict[str, Any]:
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


@app.get("/api/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/register")
def register(payload: RegisterPayload) -> dict[str, Any]:
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


@app.post("/api/auth/login")
def login(payload: LoginPayload) -> dict[str, Any]:
    response = supabase_request(
        "POST",
        "/auth/v1/token",
        use_service_role=False,
        params={"grant_type": "password"},
        json={"email": payload.email.lower(), "password": payload.password},
    )
    payload_data = require_ok(response)
    return auth_response(payload_data)


@app.get("/api/auth/me")
def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {k: user[k] for k in ("id", "email", "full_name", "created_at", "updated_at")}


@app.get("/api/organizations")
def list_organizations(user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
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
        if not org:
            continue
        organizations.append({**org, "role": row["role"]})
    return organizations


@app.post("/api/organizations", status_code=status.HTTP_201_CREATED)
def create_organization(payload: OrganizationPayload, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
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


@app.get("/api/dashboard/stats")
def dashboard_stats(organization_id: str, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, int]:
    get_membership(user["id"], organization_id)
    posts_response = supabase_request(
        "HEAD",
        "/rest/v1/posts",
        headers={"Prefer": "count=exact"},
        params={"select": "id", "organization_id": f"eq.{organization_id}"},
    )
    templates_response = supabase_request(
        "HEAD",
        "/rest/v1/templates",
        headers={"Prefer": "count=exact"},
        params={"select": "id", "or": f"(organization_id.eq.{organization_id},is_public.eq.true)"},
    )
    return {"posts": content_range_total(posts_response), "templates": content_range_total(templates_response)}


@app.get("/api/brand/{organization_id}")
def get_brand(organization_id: str, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
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


@app.put("/api/brand/{organization_id}")
def update_brand(organization_id: str, payload: BrandPayload, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
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


@app.get("/api/team/{organization_id}")
def list_team(organization_id: str, user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
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


@app.get("/api/posts")
def list_posts(organization_id: str, user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    get_membership(user["id"], organization_id)
    response = supabase_request(
        "GET",
        "/rest/v1/posts",
        params={
            "select": "id,title,format,created_at",
            "organization_id": f"eq.{organization_id}",
            "order": "created_at.desc",
        },
    )
    return require_ok(response)


@app.post("/api/posts", status_code=status.HTTP_201_CREATED)
def create_post(payload: CreatePostPayload, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    get_membership(user["id"], payload.organization_id)
    post_id = str(uuid.uuid4())
    post_response = supabase_request(
        "POST",
        "/rest/v1/posts",
        headers={"Prefer": "return=representation"},
        json={
            "id": post_id,
            "organization_id": payload.organization_id,
            "title": payload.title,
            "format": payload.format,
            "width": payload.width,
            "height": payload.height,
            "created_by": user["id"],
        },
    )
    created = require_ok(post_response)[0]

    layer_rows = [
        {
            "id": str(uuid.uuid4()),
            "post_id": post_id,
            "type": layer.type,
            "z_index": index,
            "properties": layer.properties,
            "visible": layer.visible,
        }
        for index, layer in enumerate(payload.layers)
    ]
    if layer_rows:
        require_ok(
            supabase_request(
                "POST",
                "/rest/v1/post_layers",
                headers={"Prefer": "return=minimal"},
                json=layer_rows,
            )
        )
    return created


@app.delete("/api/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: str, user: dict[str, Any] = Depends(get_current_user)) -> None:
    post_response = supabase_request(
        "GET",
        "/rest/v1/posts",
        params={"select": "id,organization_id", "id": f"eq.{post_id}", "limit": "1"},
    )
    posts = require_ok(post_response)
    if not posts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    get_membership(user["id"], posts[0]["organization_id"])
    delete_response = supabase_request("DELETE", "/rest/v1/posts", params={"id": f"eq.{post_id}"})
    require_ok(delete_response)


@app.get("/api/templates")
def list_templates(organization_id: str, user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
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


@app.post("/api/ai/generate-background")
def generate_background(payload: BackgroundPayload, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    tone = abs(hash(payload.prompt)) % 360
    secondary = (tone + 45) % 360
    svg = f"""
    <svg xmlns='http://www.w3.org/2000/svg' width='{payload.width}' height='{payload.height}' viewBox='0 0 {payload.width} {payload.height}'>
      <defs>
        <linearGradient id='g' x1='0%' y1='0%' x2='100%' y2='100%'>
          <stop offset='0%' stop-color='hsl({tone}, 75%, 55%)' />
          <stop offset='100%' stop-color='hsl({secondary}, 72%, 45%)' />
        </linearGradient>
      </defs>
      <rect width='100%' height='100%' fill='url(#g)' />
      <circle cx='{payload.width * 0.18}' cy='{payload.height * 0.22}' r='{max(payload.width, payload.height) * 0.12}' fill='rgba(255,255,255,0.16)' />
      <circle cx='{payload.width * 0.82}' cy='{payload.height * 0.18}' r='{max(payload.width, payload.height) * 0.08}' fill='rgba(255,255,255,0.1)' />
      <circle cx='{payload.width * 0.72}' cy='{payload.height * 0.78}' r='{max(payload.width, payload.height) * 0.18}' fill='rgba(0,0,0,0.14)' />
    </svg>
    """.strip()
    image_url = "data:image/svg+xml;utf8," + urllib.parse.quote(svg)
    return {"imageUrl": image_url, "provider": "local-gradient", "prompt": payload.prompt}
