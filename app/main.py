from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.db import get_cursor, init_db, utcnow
from app.security import create_access_token, decode_access_token, hash_password, verify_password


app = FastAPI(title="PostLayer API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in __import__("os").getenv(
            "POSTLAYER_ALLOWED_ORIGINS", "http://localhost:8080,http://localhost:5173"
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


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
    try:
        user_id = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    with get_cursor() as cur:
        user = cur.execute(
            "SELECT id, email, full_name, created_at, updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_membership(user_id: str, organization_id: str) -> dict[str, Any]:
    with get_cursor() as cur:
        membership = cur.execute(
            """
            SELECT om.id, om.role, o.id AS organization_id, o.name, o.slug, o.logo_url
            FROM organization_members om
            JOIN organizations o ON o.id = om.organization_id
            WHERE om.user_id = ? AND om.organization_id = ?
            """,
            (user_id, organization_id),
        ).fetchone()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this organization")
    return membership


def slugify(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return base or f"org-{uuid.uuid4().hex[:8]}"


def auth_response(user: dict[str, Any]) -> dict[str, Any]:
    token = create_access_token(user["id"])
    return {"access_token": token, "user": user}


@app.get("/api/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/register")
def register(payload: RegisterPayload) -> dict[str, Any]:
    now = utcnow()
    user_id = str(uuid.uuid4())
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO users (id, email, password_hash, full_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, payload.email.lower(), hash_password(payload.password), payload.full_name, now, now),
            )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from exc

    user = {"id": user_id, "email": payload.email.lower(), "full_name": payload.full_name, "created_at": now, "updated_at": now}
    return auth_response(user)


@app.post("/api/auth/login")
def login(payload: LoginPayload) -> dict[str, Any]:
    with get_cursor() as cur:
        user = cur.execute("SELECT * FROM users WHERE email = ?", (payload.email.lower(),)).fetchone()
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return auth_response(
        {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "created_at": user["created_at"],
            "updated_at": user["updated_at"],
        }
    )


@app.get("/api/auth/me")
def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return user


@app.get("/api/organizations")
def list_organizations(user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    with get_cursor() as cur:
        rows = cur.execute(
            """
            SELECT o.id, o.name, o.slug, o.logo_url, om.role
            FROM organization_members om
            JOIN organizations o ON o.id = om.organization_id
            WHERE om.user_id = ?
            ORDER BY o.created_at ASC
            """,
            (user["id"],),
        ).fetchall()
    return rows


@app.post("/api/organizations", status_code=status.HTTP_201_CREATED)
def create_organization(payload: OrganizationPayload, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    now = utcnow()
    org_id = str(uuid.uuid4())
    member_id = str(uuid.uuid4())
    brand_id = str(uuid.uuid4())
    slug = slugify(payload.name)

    with get_cursor(commit=True) as cur:
        existing = cur.execute("SELECT id FROM organizations WHERE slug = ?", (slug,)).fetchone()
        if existing:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"

        cur.execute(
            "INSERT INTO organizations (id, name, slug, logo_url, created_at, updated_at) VALUES (?, ?, ?, NULL, ?, ?)",
            (org_id, payload.name, slug, now, now),
        )
        cur.execute(
            "INSERT INTO organization_members (id, organization_id, user_id, role, created_at) VALUES (?, ?, ?, 'admin', ?)",
            (member_id, org_id, user["id"], now),
        )
        cur.execute(
            """
            INSERT INTO brand_settings (
              id, organization_id, primary_color, secondary_color, accent_color, font_heading, font_body, created_at, updated_at
            ) VALUES (?, ?, '#3B82F6', '#8B5CF6', '#F59E0B', 'Inter', 'Inter', ?, ?)
            """,
            (brand_id, org_id, now, now),
        )

    return {"id": org_id, "name": payload.name, "slug": slug, "logo_url": None, "role": "admin"}


@app.get("/api/dashboard/stats")
def dashboard_stats(organization_id: str, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, int]:
    get_membership(user["id"], organization_id)
    with get_cursor() as cur:
        posts = cur.execute("SELECT COUNT(*) AS total FROM posts WHERE organization_id = ?", (organization_id,)).fetchone()
        templates = cur.execute(
            "SELECT COUNT(*) AS total FROM templates WHERE organization_id = ? OR is_public = 1",
            (organization_id,),
        ).fetchone()
    return {"posts": posts["total"], "templates": templates["total"]}


@app.get("/api/brand/{organization_id}")
def get_brand(organization_id: str, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    get_membership(user["id"], organization_id)
    with get_cursor() as cur:
        row = cur.execute("SELECT * FROM brand_settings WHERE organization_id = ?", (organization_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand settings not found")
    return row


@app.put("/api/brand/{organization_id}")
def update_brand(organization_id: str, payload: BrandPayload, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    membership = get_membership(user["id"], organization_id)
    if membership["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    now = utcnow()
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            UPDATE brand_settings
            SET primary_color = ?, secondary_color = ?, accent_color = ?, font_heading = ?, font_body = ?, updated_at = ?
            WHERE organization_id = ?
            """,
            (
                payload.primary_color,
                payload.secondary_color,
                payload.accent_color,
                payload.font_heading,
                payload.font_body,
                now,
                organization_id,
            ),
        )
        row = cur.execute("SELECT * FROM brand_settings WHERE organization_id = ?", (organization_id,)).fetchone()
    return row


@app.get("/api/team/{organization_id}")
def list_team(organization_id: str, user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    get_membership(user["id"], organization_id)
    with get_cursor() as cur:
        rows = cur.execute(
            """
            SELECT om.id, om.role, om.user_id, u.full_name
            FROM organization_members om
            JOIN users u ON u.id = om.user_id
            WHERE om.organization_id = ?
            ORDER BY om.created_at ASC
            """,
            (organization_id,),
        ).fetchall()
    return rows


@app.get("/api/posts")
def list_posts(organization_id: str, user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    get_membership(user["id"], organization_id)
    with get_cursor() as cur:
        rows = cur.execute(
            """
            SELECT id, title, format, created_at
            FROM posts
            WHERE organization_id = ?
            ORDER BY created_at DESC
            """,
            (organization_id,),
        ).fetchall()
    return rows


@app.post("/api/posts", status_code=status.HTTP_201_CREATED)
def create_post(payload: CreatePostPayload, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    get_membership(user["id"], payload.organization_id)
    now = utcnow()
    post_id = str(uuid.uuid4())

    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO posts (id, organization_id, title, format, width, height, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post_id,
                payload.organization_id,
                payload.title,
                payload.format,
                payload.width,
                payload.height,
                user["id"],
                now,
                now,
            ),
        )

        for index, layer in enumerate(payload.layers):
            cur.execute(
                """
                INSERT INTO post_layers (id, post_id, type, z_index, properties, visible, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    post_id,
                    layer.type,
                    index,
                    __import__("json").dumps(layer.properties),
                    1 if layer.visible else 0,
                    now,
                    now,
                ),
            )

        created = cur.execute("SELECT id, title, format, created_at FROM posts WHERE id = ?", (post_id,)).fetchone()
    return created


@app.delete("/api/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: str, user: dict[str, Any] = Depends(get_current_user)) -> None:
    with get_cursor(commit=True) as cur:
        post = cur.execute("SELECT id, organization_id FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
        get_membership(user["id"], post["organization_id"])
        cur.execute("DELETE FROM posts WHERE id = ?", (post_id,))


@app.get("/api/templates")
def list_templates(organization_id: str, user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    get_membership(user["id"], organization_id)
    with get_cursor() as cur:
        rows = cur.execute(
            """
            SELECT id, name, category, format, is_public
            FROM templates
            WHERE organization_id = ? OR is_public = 1
            ORDER BY created_at DESC
            """,
            (organization_id,),
        ).fetchall()
    return [{**row, "is_public": bool(row["is_public"])} for row in rows]


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
    image_url = "data:image/svg+xml;utf8," + __import__("urllib.parse").parse.quote(svg)
    return {"imageUrl": image_url, "provider": "local-gradient", "prompt": payload.prompt}
