from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.auth import get_current_user, get_membership
from app.infra.providers.supabase import content_range_total, request as supabase_request, require_ok
from app.schemas.creative import CreatePostPayload

router = APIRouter(tags=["creative"])


@router.get("/dashboard/stats")
def dashboard_stats(organization_id: str, user: dict = Depends(get_current_user)) -> dict:
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


@router.get("/posts")
def list_posts(organization_id: str, user: dict = Depends(get_current_user)) -> list[dict]:
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


@router.post("/posts", status_code=status.HTTP_201_CREATED)
def create_post(payload: CreatePostPayload, user: dict = Depends(get_current_user)) -> dict:
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


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: str, user: dict = Depends(get_current_user)) -> None:
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
