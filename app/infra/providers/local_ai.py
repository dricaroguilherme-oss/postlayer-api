from __future__ import annotations

import base64
import io
import re
import textwrap
from typing import Any

from PIL import Image, ImageDraw

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
        preferred_template_id = project_context.get("preferred_template_id")
        matching_template = next(
            (
                template
                for template in templates
                if preferred_template_id and template.get("id") == preferred_template_id
            ),
            None,
        )
        if matching_template is None:
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

        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image, "RGBA")
        base_hue = tone / 360
        accent_hue = secondary / 360
        tertiary_hue = tertiary / 360

        def to_rgba(hue: float, saturation: float, lightness: float, alpha: float = 1) -> tuple[int, int, int, int]:
            import colorsys

            red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
            return (int(red * 255), int(green * 255), int(blue * 255), int(alpha * 255))

        if category == "graphic":
            draw.ellipse(
                (
                    width * 0.62,
                    height * 0.14,
                    width * 0.82,
                    height * 0.34,
                ),
                fill=to_rgba(accent_hue, 0.74, 0.55, 0.92),
            )
            draw.ellipse(
                (
                    width * 0.18,
                    height * 0.30,
                    width * 0.30,
                    height * 0.42,
                ),
                fill=to_rgba(tertiary_hue, 0.7, 0.64, 0.8),
            )
            draw.line(
                (
                    width * 0.14,
                    height * 0.78,
                    width * 0.30,
                    height * 0.30,
                    width * 0.62,
                    height * 0.30,
                    width * 0.84,
                    height * 0.72,
                ),
                fill=to_rgba(base_hue, 0.72, 0.58),
                width=max(4, int(max(width, height) * 0.028)),
            )
        else:
            top_color = to_rgba(base_hue, 0.7, 0.58)
            bottom_color = to_rgba(accent_hue, 0.72, 0.42)
            gradient = Image.new("RGBA", (width, height))
            gradient_pixels = gradient.load()
            for y in range(height):
                ratio = y / max(height - 1, 1)
                for x in range(width):
                    mix = min(1, max(0, (x / max(width - 1, 1) + ratio) / 2))
                    gradient_pixels[x, y] = (
                        int(top_color[0] + (bottom_color[0] - top_color[0]) * mix),
                        int(top_color[1] + (bottom_color[1] - top_color[1]) * mix),
                        int(top_color[2] + (bottom_color[2] - top_color[2]) * mix),
                        255,
                    )
            image.alpha_composite(gradient)
            draw = ImageDraw.Draw(image, "RGBA")
            draw.ellipse(
                (
                    width * 0.12,
                    height * 0.06,
                    width * 0.36,
                    height * 0.30,
                ),
                fill=(255, 255, 255, 105),
            )
            draw.ellipse(
                (
                    width * 0.58,
                    height * 0.54,
                    width * 0.94,
                    height * 0.90,
                ),
                fill=(12, 18, 28, 42),
            )
            draw.line(
                (
                    width * 0.1,
                    height * 0.92,
                    width * 0.42,
                    height * 0.6,
                    width * 0.7,
                    height * 0.76,
                    width * 0.92,
                    height * 0.26,
                ),
                fill=(255, 255, 255, 48),
                width=max(3, int(max(width, height) * 0.018)),
            )

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
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
