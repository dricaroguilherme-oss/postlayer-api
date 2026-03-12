from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user
from app.schemas.creative import BackgroundPayload

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/generate-background")
def generate_background(payload: BackgroundPayload, _: dict = Depends(get_current_user)) -> dict:
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
