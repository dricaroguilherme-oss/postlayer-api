from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.application.contracts.providers import ImageGenerationProvider, ReviewRuleSet, TextReasoningProvider


def _append_log(state: dict[str, Any], step: str, detail: str) -> list[dict[str, Any]]:
    log = list(state.get("execution_log", []))
    log.append({"step": step, "detail": detail})
    return log


def _first_color(brand_context: dict[str, Any], bucket: str, fallback: str) -> str:
    return brand_context.get("color_tokens", {}).get(bucket, [fallback])[0]


class StrategistAgent:
    def __init__(self, provider: TextReasoningProvider) -> None:
        self.provider = provider

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        content_plan = self.provider.generate_content_plan(
            {
                "project_id": state["project_id"],
                "project_context": state["project_context"],
                "brand_context": state.get("brand_context", {}),
            }
        )
        return {
            "content_plan": content_plan,
            "execution_log": _append_log(state, "generate_content_plan", f"{len(content_plan['slides'])} slides planned"),
        }


class ArtDirectorAgent:
    def __init__(self, provider: TextReasoningProvider) -> None:
        self.provider = provider

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        art_direction = self.provider.generate_art_direction(
            {
                "project_context": state["project_context"],
                "brand_context": state.get("brand_context", {}),
                "asset_context": state.get("asset_context", {}),
                "template_context": state.get("template_context", {}),
            }
        )
        return {
            "art_direction_plan": art_direction,
            "execution_log": _append_log(state, "generate_art_direction", art_direction["visual_direction"]),
        }


class VisualGeneratorAgent:
    def __init__(self, provider: ImageGenerationProvider) -> None:
        self.provider = provider

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        instructions = state.get("art_direction_plan", {}).get("generation_instructions", [])
        dimensions = state["project_context"]["dimensions"]
        assets = list(state.get("generated_assets", []))

        for instruction in instructions:
            generated = self.provider.generate_asset(
                {
                    "prompt": instruction,
                    "width": dimensions["width"],
                    "height": dimensions["height"],
                }
            )
            assets.append(generated)

        return {
            "generated_assets": assets,
            "execution_log": _append_log(state, "generate_visual_assets", f"{len(assets)} assets available"),
        }


class ComposerAgent:
    def __init__(self, provider: TextReasoningProvider) -> None:
        self.provider = provider

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        project_context = state["project_context"]
        brand_context = state.get("brand_context", {})
        content_plan = state["content_plan"]
        template_by_role = {
            template["page_role"]: template
            for template in state.get("template_context", {}).get("templates", [])
            if template.get("format_type") == project_context["format_type"]
        }
        generated_assets = state.get("generated_assets", [])
        width = project_context["dimensions"]["width"]
        height = project_context["dimensions"]["height"]

        background_color = _first_color(brand_context, "primary", "#111827")
        body_color = _first_color(brand_context, "neutral", "#F9FAFB")
        accent_color = _first_color(brand_context, "secondary", "#7C3AED")

        pages = []
        for slide in content_plan["slides"]:
            template = template_by_role.get(slide["page_role"]) or next(iter(template_by_role.values()), None)
            schema_regions = (template or {}).get("schema_json", {}).get("regions", [])
            heading_region = next((region for region in schema_regions if region.get("slot") == "heading"), None)
            body_region = next((region for region in schema_regions if region.get("slot") == "body"), None)
            cta_region = next((region for region in schema_regions if region.get("slot") == "cta"), None)

            page_background = generated_assets[slide["page_index"] % len(generated_assets)] if generated_assets else None
            nodes = [
                {
                    "id": f"background-{slide['page_index']}",
                    "type": "background",
                    "x": 0,
                    "y": 0,
                    "width": width,
                    "height": height,
                    "z_index": 0,
                    "style": {
                        "backgroundColor": background_color if slide["page_role"] != "body" else "#F9FAFB",
                        "opacity": 1,
                    },
                    "asset_ref": page_background.get("preview_url") if page_background else None,
                    "children": [],
                },
                {
                    "id": f"heading-{slide['page_index']}",
                    "type": "heading",
                    "x": (heading_region or {}).get("x", 72),
                    "y": (heading_region or {}).get("y", 108),
                    "width": (heading_region or {}).get("width", width - 144),
                    "height": (heading_region or {}).get("height", 220),
                    "z_index": 10,
                    "style": {
                        "color": "#FFFFFF" if slide["page_role"] != "body" else background_color,
                        "fontSize": 54 if slide["page_role"] == "cover" else 42,
                        "fontWeight": 700,
                        "fontFamily": brand_context.get("typography", {}).get("heading_family", "Space Grotesk"),
                    },
                    "content": {"text": slide["headline"]},
                    "children": [],
                },
                {
                    "id": f"body-{slide['page_index']}",
                    "type": "paragraph",
                    "x": (body_region or {}).get("x", 72),
                    "y": (body_region or {}).get("y", 360),
                    "width": (body_region or {}).get("width", width - 180),
                    "height": (body_region or {}).get("height", 260),
                    "z_index": 20,
                    "style": {
                        "color": body_color if slide["page_role"] != "body" else "#111827",
                        "fontSize": 24,
                        "fontWeight": 500,
                        "fontFamily": brand_context.get("typography", {}).get("body_family", "DM Sans"),
                    },
                    "content": {"text": slide["body"]},
                    "children": [],
                },
            ]

            if slide.get("cta"):
                nodes.append(
                    {
                        "id": f"cta-{slide['page_index']}",
                        "type": "cta",
                        "x": (cta_region or {}).get("x", 72),
                        "y": (cta_region or {}).get("y", height - 140),
                        "width": (cta_region or {}).get("width", 280),
                        "height": (cta_region or {}).get("height", 76),
                        "z_index": 30,
                        "style": {
                            "backgroundColor": accent_color,
                            "color": "#FFFFFF",
                            "fontSize": 24,
                            "fontWeight": 700,
                            "borderRadius": 18,
                            "fontFamily": brand_context.get("typography", {}).get("body_family", "DM Sans"),
                        },
                        "content": {"text": slide["cta"]},
                        "children": [],
                    }
                )

            pages.append(
                {
                    "page_index": slide["page_index"],
                    "page_role": slide["page_role"],
                    "width": width,
                    "height": height,
                    "template_id": (template or {}).get("id"),
                    "nodes": nodes,
                }
            )

        return {
            "composition_result": {"pages": pages},
            "execution_log": _append_log(state, "compose_layout", f"{len(pages)} page layouts composed"),
        }


class ReviewerAgent:
    def __init__(self, rules: ReviewRuleSet) -> None:
        self.rules = rules

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        review = self.rules.run(
            {
                "composition_result": state["composition_result"],
                "brand_context": state.get("brand_context", {}),
            }
        )
        return {
            "review_result": review,
            "execution_log": _append_log(state, "review_layout", f"{len(review['warnings'])} warnings"),
        }


class MemoryCuratorAgent:
    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        suggestions = []
        for asset in state.get("generated_assets", []):
            suggestions.append(
                {
                    "name": asset["name"],
                    "category": asset["category"],
                    "tags": ["generated", "background", state["project_context"]["format_type"]],
                    "rationale": "Generated asset was used in final composition and can be reused as a memory primitive.",
                }
            )

        return {
            "asset_suggestions": suggestions,
            "execution_log": _append_log(state, "suggest_asset_saving", f"{len(suggestions)} reusable suggestions"),
        }


def apply_autofixes(state: dict[str, Any], provider: TextReasoningProvider) -> dict[str, Any]:
    review = deepcopy(state["review_result"])
    composition = deepcopy(state["composition_result"])
    applied = list(review.get("autofixes_applied", []))

    if review["contrast_score"] < 0.72:
        for page in composition["pages"]:
            for node in page["nodes"]:
                if node["type"] == "background":
                    node["style"]["backgroundColor"] = "#111827"
                if node["type"] in {"heading", "paragraph", "cta"}:
                    node["style"]["color"] = "#FFFFFF" if node["type"] != "cta" else "#FFFFFF"
        applied.append("contrast_overlay")

    if review["text_density_score"] < 0.72:
        for page in composition["pages"]:
            for node in page["nodes"]:
                if node["type"] == "paragraph":
                    summary = provider.summarize({"text": node.get("content", {}).get("text", ""), "max_chars": 120})
                    node["content"]["text"] = summary["text"]
        applied.append("body_summarization")

    review["autofixes_applied"] = applied
    return {
        "composition_result": composition,
        "review_result": review,
        "execution_log": _append_log(state, "apply_autofixes", ", ".join(applied) or "no-op"),
    }
