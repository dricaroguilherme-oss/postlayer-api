from __future__ import annotations

import textwrap
import urllib.parse
from typing import Any

from app.application.contracts.providers import ImageGenerationProvider, TextReasoningProvider


def _clip_text(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    clipped = normalized[: limit - 1].rsplit(" ", 1)[0]
    return f"{clipped}…"


class LocalTextReasoningProvider(TextReasoningProvider):
    def generate_content_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_context = payload["project_context"]
        brand_context = payload.get("brand_context", {})
        prompt = project_context["user_prompt"]
        page_count = max(project_context["page_count"], 1)
        cta = project_context.get("cta") or "Saiba mais"
        style_words = ", ".join(brand_context.get("visual_style_keywords", [])[:3]) or "brand-first"
        global_message = _clip_text(prompt, 220)
        slides: list[dict[str, Any]] = []

        if page_count == 1:
            slides.append(
                {
                    "page_index": 0,
                    "page_role": "cover",
                    "headline": _clip_text(prompt, 58),
                    "body": _clip_text(f"{global_message} Direção visual: {style_words}.", 180),
                    "cta": cta,
                    "narrative_intent": "Single-message conversion post",
                }
            )
        else:
            page_roles = ["cover"] + ["body"] * max(page_count - 2, 0) + ["cta"]
            segments = textwrap.wrap(global_message, width=max(48, len(global_message) // page_count or 48))
            for page_index in range(page_count):
                role = page_roles[page_index] if page_index < len(page_roles) else "body"
                body_segment = segments[page_index] if page_index < len(segments) else global_message
                headline = (
                    _clip_text(prompt, 54)
                    if role == "cover"
                    else _clip_text(f"Passo {page_index + 1}: {body_segment}", 54)
                    if role == "body"
                    else _clip_text(cta, 40)
                )
                slides.append(
                    {
                        "page_index": page_index,
                        "page_role": role,
                        "headline": headline,
                        "body": _clip_text(body_segment, 170 if role == "body" else 130),
                        "cta": cta if role in {"cover", "cta"} else None,
                        "narrative_intent": {
                            "cover": "Hook and framing",
                            "body": "Progressive explanation",
                            "cta": "Conversion close",
                        }[role],
                    }
                )

        return {
            "project_id": payload["project_id"],
            "global_message": global_message,
            "slides": slides,
        }

    def generate_art_direction(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_context = payload["project_context"]
        brand_context = payload.get("brand_context", {})
        template_context = payload.get("template_context", {})
        asset_context = payload.get("asset_context", {})
        visual_keywords = brand_context.get("visual_style_keywords", [])
        typography = brand_context.get("typography", {})
        templates = template_context.get("templates", [])
        matching_template = next(
            (
                template
                for template in templates
                if template.get("format_type") == project_context["format_type"]
            ),
            None,
        )
        reusable_assets = [asset["id"] for asset in asset_context.get("assets", [])[:3] if asset.get("is_decorative")]
        palette_mode = "brand_primary" if brand_context.get("color_tokens", {}).get("primary") else "neutral_editorial"
        heading_family = typography.get("heading_family") or typography.get("family") or "Space Grotesk"

        generation_instructions = []
        if not reusable_assets:
            generation_instructions.append(
                f"Generate branded background for {project_context['channel']} / {project_context['format_type']}"
            )
        if project_context["piece_type"] == "carousel":
            generation_instructions.append("Generate recurring visual cue for carousel progression")

        return {
            "visual_direction": f"{heading_family} / {', '.join(visual_keywords[:3]) or 'clean editorial'}",
            "palette_mode": palette_mode,
            "template_id": matching_template.get("id") if matching_template else None,
            "component_refs": [],
            "asset_refs": reusable_assets,
            "generation_instructions": generation_instructions,
        }

    def summarize(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = payload["text"]
        limit = payload.get("max_chars", 160)
        return {"text": _clip_text(text, limit)}


class LocalImageGenerationProvider(ImageGenerationProvider):
    def generate_asset(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = payload["prompt"]
        width = payload["width"]
        height = payload["height"]
        tone = abs(hash(prompt)) % 360
        secondary = (tone + 48) % 360
        svg = f"""
        <svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>
          <defs>
            <linearGradient id='bg' x1='0%' y1='0%' x2='100%' y2='100%'>
              <stop offset='0%' stop-color='hsl({tone}, 70%, 58%)' />
              <stop offset='100%' stop-color='hsl({secondary}, 72%, 42%)' />
            </linearGradient>
          </defs>
          <rect width='100%' height='100%' fill='url(#bg)' />
          <circle cx='{width * 0.25}' cy='{height * 0.2}' r='{max(width, height) * 0.12}' fill='rgba(255,255,255,0.15)' />
          <circle cx='{width * 0.78}' cy='{height * 0.68}' r='{max(width, height) * 0.18}' fill='rgba(0,0,0,0.14)' />
        </svg>
        """.strip()
        data_url = "data:image/svg+xml;utf8," + urllib.parse.quote(svg)
        return {
            "name": _clip_text(prompt, 42),
            "category": "background",
            "source_type": "ai_generated",
            "file_url": data_url,
            "preview_url": data_url,
            "dominant_color": f"hsl({tone}, 70%, 58%)",
            "metadata_json": {"prompt": prompt, "provider": "local-gradient"},
        }
