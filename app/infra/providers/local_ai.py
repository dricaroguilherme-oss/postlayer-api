from __future__ import annotations

import re
import textwrap
import urllib.parse
from typing import Any

from app.application.contracts.providers import ImageGenerationProvider, TextReasoningProvider


def _normalize_text(value: str) -> str:
    return " ".join((value or "").split())


def _clip_text(value: str, limit: int) -> str:
    normalized = _normalize_text(value)
    if len(normalized) <= limit:
        return normalized
    clipped = normalized[: limit - 1].rsplit(" ", 1)[0]
    return f"{clipped}…"


def _split_sentences(value: str) -> list[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    return [part.strip() for part in parts if part.strip()]


def _extract_keywords(value: str, limit: int = 4) -> list[str]:
    words = re.findall(r"[A-Za-zÀ-ÿ0-9-]{4,}", value.lower())
    stopwords = {
        "para",
        "com",
        "como",
        "sobre",
        "esse",
        "essa",
        "isso",
        "mais",
        "muito",
        "foco",
        "post",
        "criar",
        "peça",
        "peças",
        "times",
        "time",
        "social",
    }
    keywords: list[str] = []
    for word in words:
        if word in stopwords or word in keywords:
            continue
        keywords.append(word)
        if len(keywords) >= limit:
            break
    return keywords


def _page_roles(page_count: int, piece_type: str) -> list[str]:
    if page_count <= 1:
        return ["cover"]
    roles = ["cover"]
    if piece_type == "carousel" and page_count > 2:
        roles.extend(["body"] * (page_count - 2))
    else:
        roles.extend(["body"] * max(page_count - 2, 0))
    roles.append("cta")
    return roles


def _suggest_cta(project_context: dict[str, Any]) -> str:
    if project_context.get("cta"):
        return str(project_context["cta"])
    objective = str(project_context.get("objective", "")).lower()
    suggestions = {
        "conversion": "Teste agora",
        "captacao": "Fale com o time",
        "education": "Salve este post",
        "awareness": "Conheça a proposta",
        "engagement": "Comente sua opinião",
    }
    return suggestions.get(objective, "Saiba mais")


def _title_case_snippet(value: str, limit: int) -> str:
    clipped = _clip_text(value, limit)
    return clipped[:1].upper() + clipped[1:] if clipped else clipped


def _intent_for_role(role: str, index: int, page_count: int, objective: str) -> str:
    if role == "cover":
        return "Hook and framing"
    if role == "cta":
        return f"Conversion close for {objective or 'campaign goal'}"
    return f"Progressive explanation step {index + 1} of {page_count}"


class LocalTextReasoningProvider(TextReasoningProvider):
    def generate_content_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_context = payload["project_context"]
        brand_context = payload.get("brand_context", {})
        prompt = _normalize_text(project_context["user_prompt"])
        page_count = max(int(project_context["page_count"]), 1)
        cta = _suggest_cta(project_context)
        style_words = ", ".join(brand_context.get("visual_style_keywords", [])[:3]) or "brand-first"
        audience = _normalize_text(str(project_context.get("audience", "")))
        objective = _normalize_text(str(project_context.get("objective", "")))
        global_message = _clip_text(prompt, 220)
        sentences = _split_sentences(prompt) or [global_message]
        keywords = _extract_keywords(prompt)
        segments = sentences if len(sentences) >= page_count else textwrap.wrap(global_message, width=72) or [global_message]
        roles = _page_roles(page_count, str(project_context.get("piece_type", "single_post")))

        slides: list[dict[str, Any]] = []
        for page_index in range(page_count):
            role = roles[page_index] if page_index < len(roles) else "body"
            segment = segments[min(page_index, len(segments) - 1)]
            keyword = keywords[min(page_index, len(keywords) - 1)] if keywords else ""

            if role == "cover":
                headline = _title_case_snippet(segment, 58)
                body = _clip_text(
                    f"{global_message} Direção: {style_words}. Público: {audience or 'generalista'}.",
                    140 if page_count > 1 else 170,
                )
                slide_cta = cta if page_count == 1 else None
            elif role == "cta":
                headline = _title_case_snippet(cta, 42)
                body = _clip_text(
                    f"Feche a narrativa reforçando {objective or 'o benefício principal'} com linguagem clara e memorável.",
                    120,
                )
                slide_cta = cta
            else:
                headline_seed = f"{keyword}: {segment}" if keyword else segment
                headline = _title_case_snippet(headline_seed, 54)
                body = _clip_text(
                    f"{segment} Conecte este ponto ao objetivo {objective or 'principal'} e preserve o tom {style_words}.",
                    165,
                )
                slide_cta = None

            slides.append(
                {
                    "page_index": page_index,
                    "page_role": role,
                    "headline": headline,
                    "body": body,
                    "cta": slide_cta,
                    "narrative_intent": _intent_for_role(role, page_index, page_count, objective),
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
        reusable_assets = asset_context.get("assets", [])
        primary_assets = [asset["id"] for asset in reusable_assets if asset.get("category") == "background"][:1]
        support_assets = [
            asset["id"]
            for asset in reusable_assets
            if asset.get("category") in {"texture", "graphic", "badge"}
        ][:2]
        matching_template = next(
            (
                template
                for template in templates
                if template.get("format_type") == project_context["format_type"]
                and template.get("page_role") in {"cover", "body"}
            ),
            None,
        )
        heading_family = typography.get("heading_family") or typography.get("family") or "Space Grotesk"
        objective = str(project_context.get("objective", "")).lower()
        piece_type = str(project_context.get("piece_type", "single_post"))
        palette_mode = (
            "high_contrast_brand"
            if objective in {"conversion", "captacao"}
            else "editorial_neutral"
            if objective == "education"
            else "balanced_brand"
        )

        generation_plan: list[dict[str, Any]] = []
        has_media_slot = any(
            region.get("slot") == "media"
            for region in (matching_template or {}).get("schema_json", {}).get("regions", [])
        )
        if not primary_assets:
            generation_plan.append(
                {
                    "prompt": (
                        f"Branded background for {project_context['channel']} {project_context['format_type']} "
                        f"with {', '.join(visual_keywords[:3]) or 'clean editorial'} direction"
                    ),
                    "category": "background",
                    "usage": "hero_background",
                }
            )
        if piece_type == "carousel" and not support_assets:
            generation_plan.append(
                {
                    "prompt": (
                        f"Recurring progression marker for carousel about {project_context['objective']} "
                        f"using {heading_family} inspired geometry"
                    ),
                    "category": "graphic",
                    "usage": "progression_marker",
                }
            )
        if piece_type == "single_post" and not support_assets and has_media_slot:
            generation_plan.append(
                {
                    "prompt": (
                        f"Decorative branded accent object for {project_context['format_type']} "
                        f"to support {project_context['objective']}"
                    ),
                    "category": "graphic",
                    "usage": "decorative_anchor",
                }
            )

        return {
            "visual_direction": f"{heading_family} / {', '.join(visual_keywords[:3]) or 'clean editorial'}",
            "palette_mode": palette_mode,
            "template_id": matching_template.get("id") if matching_template else None,
            "component_refs": ["cta_card", "progression_badge"] if piece_type == "carousel" else ["cta_card"],
            "asset_refs": primary_assets + support_assets,
            "generation_instructions": [item["prompt"] for item in generation_plan],
            "asset_generation_plan": generation_plan,
        }

    def summarize(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = _normalize_text(str(payload["text"]))
        limit = int(payload.get("max_chars", 160))
        if len(text) <= limit:
            return {"text": text}
        sentences = _split_sentences(text)
        if sentences:
            summary = sentences[0]
            if len(summary) <= limit:
                return {"text": summary}
        return {"text": _clip_text(text, limit)}


class LocalImageGenerationProvider(ImageGenerationProvider):
    def generate_asset(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = str(payload["prompt"])
        width = int(payload["width"])
        height = int(payload["height"])
        category = str(payload.get("category", "background"))
        usage = str(payload.get("usage", "decorative"))
        tone = abs(hash(f"{category}:{prompt}")) % 360
        secondary = (tone + 48) % 360
        tertiary = (tone + 112) % 360

        if category == "graphic":
            svg = f"""
            <svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>
              <rect width='100%' height='100%' fill='transparent' />
              <path d='M {width * 0.14} {height * 0.78} C {width * 0.22} {height * 0.26}, {width * 0.62} {height * 0.26}, {width * 0.84} {height * 0.72}' fill='none' stroke='hsl({tone},72%,58%)' stroke-width='{max(width, height) * 0.028}' stroke-linecap='round' />
              <circle cx='{width * 0.72}' cy='{height * 0.24}' r='{max(width, height) * 0.08}' fill='hsl({secondary},74%,55%)' opacity='0.92' />
              <circle cx='{width * 0.24}' cy='{height * 0.36}' r='{max(width, height) * 0.05}' fill='hsl({tertiary},70%,64%)' opacity='0.8' />
            </svg>
            """.strip()
        else:
            svg = f"""
            <svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>
              <defs>
                <linearGradient id='bg' x1='0%' y1='0%' x2='100%' y2='100%'>
                  <stop offset='0%' stop-color='hsl({tone}, 70%, 58%)' />
                  <stop offset='100%' stop-color='hsl({secondary}, 72%, 42%)' />
                </linearGradient>
                <radialGradient id='orb' cx='50%' cy='50%' r='50%'>
                  <stop offset='0%' stop-color='rgba(255,255,255,0.45)' />
                  <stop offset='100%' stop-color='rgba(255,255,255,0)' />
                </radialGradient>
              </defs>
              <rect width='100%' height='100%' fill='url(#bg)' />
              <circle cx='{width * 0.24}' cy='{height * 0.18}' r='{max(width, height) * 0.12}' fill='url(#orb)' />
              <circle cx='{width * 0.76}' cy='{height * 0.72}' r='{max(width, height) * 0.18}' fill='rgba(0,0,0,0.16)' />
              <path d='M {width * 0.1} {height * 0.92} L {width * 0.42} {height * 0.6} L {width * 0.7} {height * 0.76} L {width * 0.92} {height * 0.26}' stroke='rgba(255,255,255,0.18)' stroke-width='{max(width, height) * 0.018}' fill='none' />
            </svg>
            """.strip()

        data_url = "data:image/svg+xml;utf8," + urllib.parse.quote(svg)
        return {
            "name": _clip_text(prompt, 42),
            "category": category,
            "source_type": "ai_generated",
            "file_url": data_url,
            "preview_url": data_url,
            "dominant_color": f"hsl({tone}, 70%, 58%)",
            "metadata_json": {
                "prompt": prompt,
                "provider": "local-gradient",
                "usage": usage,
            },
        }
