from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.application.contracts.providers import ImageGenerationProvider, ReviewRuleSet, TextReasoningProvider
from app.application.presets.social import SOCIAL_FORMAT_PRESETS


TEXT_NODE_TYPES = {"heading", "paragraph", "cta", "text", "subheading"}


def _append_log(state: dict[str, Any], step: str, detail: str) -> list[dict[str, Any]]:
    log = list(state.get("execution_log", []))
    log.append({"step": step, "detail": detail})
    return log


def _first_color(brand_context: dict[str, Any], bucket: str, fallback: str) -> str:
    return brand_context.get("color_tokens", {}).get(bucket, [fallback])[0]


def _page_roles(page_count: int, piece_type: str) -> list[str]:
    if page_count <= 1:
        return ["cover"]
    roles = ["cover"]
    roles.extend(["body"] * max(page_count - 2, 0))
    roles.append("cta")
    return roles if piece_type == "carousel" else roles


def _safe_zone(project_context: dict[str, Any]) -> dict[str, int]:
    preset = SOCIAL_FORMAT_PRESETS.get(project_context["format_type"])
    if preset:
        return preset["safe_zone"]
    return {"top": 72, "right": 72, "bottom": 72, "left": 72}


def _find_region(regions: list[dict[str, Any]], slot: str, fallback: dict[str, Any]) -> dict[str, Any]:
    return next((region for region in regions if region.get("slot") == slot), fallback)


def _max_chars_for_role(role: str, node_type: str) -> int:
    if node_type == "heading":
        return 60 if role == "cover" else 54
    if node_type == "paragraph":
        return 110 if role == "cover" else 150 if role == "body" else 90
    return 36


def _font_size_for_text(text: str, *, role: str, kind: str, typography: dict[str, Any]) -> int:
    length = len(text.strip())
    title_sizes = typography.get("default_title_sizes") or [56, 48, 40]
    body_sizes = typography.get("default_body_sizes") or [24, 20, 18]
    if kind == "heading":
        if role == "cover":
            return title_sizes[0] if length <= 34 else title_sizes[min(1, len(title_sizes) - 1)] if length <= 54 else title_sizes[min(2, len(title_sizes) - 1)]
        return title_sizes[min(1, len(title_sizes) - 1)] if length <= 46 else title_sizes[min(2, len(title_sizes) - 1)]
    return body_sizes[0] if length <= 90 else body_sizes[min(1, len(body_sizes) - 1)] if length <= 130 else body_sizes[min(2, len(body_sizes) - 1)]


def _pick_asset(asset_pool: list[dict[str, Any]], *, categories: set[str], usage: str | None = None, fallback_index: int = 0) -> dict[str, Any] | None:
    matching = [asset for asset in asset_pool if asset.get("category") in categories]
    if usage:
        usage_matches = [
            asset
            for asset in matching
            if asset.get("metadata_json", {}).get("usage") == usage or asset.get("usage") == usage
        ]
        if usage_matches:
            matching = usage_matches
    if not matching:
        return None
    return matching[fallback_index % len(matching)]


def _carousel_accent(index: int, primary: str, secondary: str, neutral: str) -> tuple[str, str, str]:
    if index == 0:
        return primary, "#FFFFFF", secondary
    if index % 2 == 1:
        return neutral, primary, secondary
    return "#FFFFFF", primary, secondary


def _node_outside_safe_zone(node: dict[str, Any], page: dict[str, Any], safe_zone: dict[str, int]) -> bool:
    if node.get("type") not in TEXT_NODE_TYPES | {"shape", "image"}:
        return False
    x = float(node.get("x", 0))
    y = float(node.get("y", 0))
    width = float(node.get("width", 0))
    height = float(node.get("height", 0))
    return (
        x < safe_zone["left"]
        or y < safe_zone["top"]
        or x + width > page["width"] - safe_zone["right"]
        or y + height > page["height"] - safe_zone["bottom"]
    )


def _agent_review_checks(
    composition_result: dict[str, Any],
    project_context: dict[str, Any],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    safe_zone = _safe_zone(project_context)
    pages = composition_result.get("pages", [])
    carousel = project_context.get("piece_type") == "carousel" and len(pages) > 1

    for page in pages:
        for node in page.get("nodes", []):
            if _node_outside_safe_zone(node, page, safe_zone):
                warnings.append(
                    {
                        "code": "safe_zone_violation",
                        "severity": "warning",
                        "message": f"Nó {node['id']} ultrapassa a área segura da página {page['page_index'] + 1}",
                        "target_node_id": node["id"],
                    }
                )

        if carousel and page["page_role"] in {"body", "cta"}:
            has_progression = any(
                node["id"].startswith("slide-index") or node["id"].startswith("progress-track") for node in page.get("nodes", [])
            )
            if not has_progression:
                warnings.append(
                    {
                        "code": "carousel_progression_missing",
                        "severity": "warning",
                        "message": f"Página {page['page_index'] + 1} sem marcador de progressão do carrossel",
                        "target_node_id": None,
                    }
                )

        if page["page_role"] == "cta":
            has_cta = any(node["id"].startswith("cta-label") for node in page.get("nodes", []))
            if not has_cta:
                warnings.append(
                    {
                        "code": "cta_missing",
                        "severity": "warning",
                        "message": f"Página {page['page_index'] + 1} deveria reforçar CTA final",
                        "target_node_id": None,
                    }
                )

    return warnings


def _evaluate_review(
    composition_result: dict[str, Any],
    brand_context: dict[str, Any],
    project_context: dict[str, Any],
    review_rules: ReviewRuleSet,
) -> dict[str, Any]:
    review = review_rules.run(
        {
            "composition_result": composition_result,
            "brand_context": brand_context,
        }
    )
    agent_warnings = _agent_review_checks(composition_result, project_context)
    all_warnings = list(review.get("warnings", [])) + agent_warnings
    severe_penalty = min(0.24, len(agent_warnings) * 0.04)
    review["warnings"] = all_warnings
    review["legibility_score"] = round(max(0.0, review["legibility_score"] - severe_penalty), 3)
    review["brand_adherence_score"] = round(max(0.0, review["brand_adherence_score"] - severe_penalty / 2), 3)
    return review


class StrategistAgent:
    def __init__(self, provider: TextReasoningProvider) -> None:
        self.provider = provider

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        project_context = state["project_context"]
        page_count = max(int(project_context["page_count"]), 1)
        roles = _page_roles(page_count, str(project_context.get("piece_type", "single_post")))
        suggested_cta = project_context.get("cta") or "Saiba mais"

        raw_content_plan = self.provider.generate_content_plan(
            {
                "project_id": state["project_id"],
                "project_context": project_context,
                "brand_context": state.get("brand_context", {}),
            }
        )

        slides = list(raw_content_plan.get("slides", []))
        normalized_slides = []
        for index in range(page_count):
            role = roles[index] if index < len(roles) else "body"
            slide = slides[index] if index < len(slides) else {}
            headline_limit = _max_chars_for_role(role, "heading")
            body_limit = _max_chars_for_role(role, "paragraph")
            headline = self.provider.summarize(
                {"text": slide.get("headline") or slide.get("body") or project_context["user_prompt"], "max_chars": headline_limit}
            )["text"]
            body = self.provider.summarize(
                {"text": slide.get("body") or raw_content_plan.get("global_message") or project_context["user_prompt"], "max_chars": body_limit}
            )["text"]
            cta = suggested_cta if page_count == 1 or role == "cta" else None
            normalized_slides.append(
                {
                    "page_index": index,
                    "page_role": role,
                    "headline": headline,
                    "body": body,
                    "cta": cta,
                    "narrative_intent": slide.get("narrative_intent") or f"{role} narrative block",
                }
            )

        return {
            "content_plan": {
                "project_id": state["project_id"],
                "global_message": raw_content_plan.get("global_message") or project_context["user_prompt"],
                "slides": normalized_slides,
            },
            "execution_log": _append_log(state, "generate_content_plan", f"{len(normalized_slides)} slides planned"),
        }


class ArtDirectorAgent:
    def __init__(self, provider: TextReasoningProvider) -> None:
        self.provider = provider

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        project_context = state["project_context"]
        brand_context = state.get("brand_context", {})
        asset_context = state.get("asset_context", {})
        templates = state.get("template_context", {}).get("templates", [])
        generated = self.provider.generate_art_direction(
            {
                "project_context": project_context,
                "brand_context": brand_context,
                "asset_context": asset_context,
                "template_context": state.get("template_context", {}),
            }
        )

        def template_score(template: dict[str, Any]) -> tuple[int, int]:
            role = template.get("page_role")
            is_system = 1 if template.get("is_system_template") else 0
            if project_context.get("piece_type") == "single_post":
                preferred = 3 if role == "cover" else 1
            else:
                preferred = 3 if role == "body" else 2 if role == "cover" else 1
            return preferred, is_system

        primary_template = max(templates, key=template_score) if templates else None
        reusable_assets = list(asset_context.get("assets", []))
        asset_refs = list(dict.fromkeys(list(generated.get("asset_refs", []))))
        if not asset_refs:
            asset_refs.extend([asset["id"] for asset in reusable_assets if asset.get("category") == "background"][:1])
        if project_context.get("piece_type") == "carousel":
            asset_refs.extend(
                [asset["id"] for asset in reusable_assets if asset.get("category") in {"graphic", "badge"}][:1]
            )
        asset_refs = list(dict.fromkeys(asset_refs))

        generation_plan = list(generated.get("asset_generation_plan", []))
        if not generation_plan and generated.get("generation_instructions"):
            generation_plan = [{"prompt": prompt, "category": "background"} for prompt in generated["generation_instructions"]]

        if project_context.get("piece_type") == "carousel":
            primary_background = any(asset.get("category") == "background" for asset in reusable_assets)
            progression_anchor = any(asset.get("category") in {"graphic", "badge"} for asset in reusable_assets)
            if not primary_background:
                generation_plan.insert(
                    0,
                    {
                        "prompt": f"Hero background for {project_context['format_type']} with {_first_color(brand_context, 'primary', '#111827')} palette",
                        "category": "background",
                        "usage": "hero_background",
                    },
                )
            if not progression_anchor:
                generation_plan.append(
                    {
                        "prompt": f"Recurring badge/progression marker for {project_context['format_type']}",
                        "category": "graphic",
                        "usage": "progression_marker",
                    }
                )

        component_refs = list(dict.fromkeys(list(generated.get("component_refs", []))))
        if primary_template:
            regions = primary_template.get("schema_json", {}).get("regions", [])
            for region in regions:
                slot = region.get("slot")
                if slot in {"cta", "stat_card", "badge", "progression_marker", "media"}:
                    component_refs.append(str(slot))
        component_refs = list(dict.fromkeys(component_refs))

        page_styles = {
            "cover": {"background_mode": "hero", "layout_tension": "high"},
            "body": {"background_mode": "surface", "layout_tension": "balanced"},
            "cta": {"background_mode": "accent", "layout_tension": "focused"},
        }

        art_direction = {
            **generated,
            "template_id": generated.get("template_id") or (primary_template.get("id") if primary_template else None),
            "asset_refs": asset_refs,
            "component_refs": component_refs,
            "generation_instructions": [item["prompt"] for item in generation_plan],
            "asset_generation_plan": generation_plan,
            "page_styles": page_styles,
        }
        return {
            "art_direction_plan": art_direction,
            "execution_log": _append_log(state, "generate_art_direction", art_direction["visual_direction"]),
        }


class VisualGeneratorAgent:
    def __init__(self, provider: ImageGenerationProvider) -> None:
        self.provider = provider

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        dimensions = state["project_context"]["dimensions"]
        assets = list(state.get("generated_assets", []))
        generation_plan = list(state.get("art_direction_plan", {}).get("asset_generation_plan", []))
        if not generation_plan:
            generation_plan = [
                {"prompt": instruction, "category": "background"}
                for instruction in state.get("art_direction_plan", {}).get("generation_instructions", [])
            ]

        seen_prompts: set[str] = set()
        for index, item in enumerate(generation_plan):
            prompt = str(item.get("prompt", "")).strip()
            if not prompt or prompt in seen_prompts:
                continue
            seen_prompts.add(prompt)
            generated = self.provider.generate_asset(
                {
                    "prompt": prompt,
                    "width": dimensions["width"],
                    "height": dimensions["height"],
                    "category": item.get("category", "background"),
                    "usage": item.get("usage"),
                    "page_index": index,
                }
            )
            generated["usage"] = item.get("usage")
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
        templates = state.get("template_context", {}).get("templates", [])
        asset_pool = list(state.get("asset_context", {}).get("assets", [])) + list(state.get("generated_assets", []))
        typography = brand_context.get("typography", {})
        safe_zone = _safe_zone(project_context)
        width = project_context["dimensions"]["width"]
        height = project_context["dimensions"]["height"]

        template_by_role = {
            template["page_role"]: template
            for template in templates
            if template.get("format_type") == project_context["format_type"]
        }

        pages = []
        for slide in content_plan["slides"]:
            page_index = slide["page_index"]
            role = slide["page_role"]
            template = template_by_role.get(role) or template_by_role.get("cover") or next(iter(template_by_role.values()), None)
            schema_regions = (template or {}).get("schema_json", {}).get("regions", [])

            default_heading = {
                "x": safe_zone["left"],
                "y": safe_zone["top"] + 24,
                "width": width - safe_zone["left"] - safe_zone["right"],
                "height": 220,
            }
            default_body = {
                "x": safe_zone["left"],
                "y": safe_zone["top"] + 280,
                "width": width - safe_zone["left"] - safe_zone["right"],
                "height": 280,
            }
            default_cta = {
                "x": safe_zone["left"],
                "y": height - safe_zone["bottom"] - 92,
                "width": 320,
                "height": 76,
            }
            heading_region = _find_region(schema_regions, "heading", default_heading)
            body_region = _find_region(schema_regions, "body", default_body)
            cta_region = _find_region(schema_regions, "cta", default_cta)
            media_region = next((region for region in schema_regions if region.get("slot") in {"media", "stat_card"}), None)
            progression_region = next((region for region in schema_regions if region.get("slot") in {"badge", "progression_marker"}), None)
            if progression_region is None and project_context.get("piece_type") == "carousel":
                progression_region = {
                    "x": safe_zone["left"],
                    "y": safe_zone["top"],
                    "width": 184,
                    "height": 48,
                }

            background_color, text_color, accent_color = _carousel_accent(
                page_index,
                _first_color(brand_context, "primary", "#111827"),
                _first_color(brand_context, "secondary", "#7C3AED"),
                _first_color(brand_context, "neutral", "#F8FAFC"),
            )
            background_asset = _pick_asset(asset_pool, categories={"background"}, usage="hero_background", fallback_index=page_index)
            graphic_asset = _pick_asset(asset_pool, categories={"graphic", "badge"}, usage="progression_marker", fallback_index=page_index)
            media_asset = graphic_asset if media_region else None

            heading_text = self.provider.summarize(
                {"text": slide["headline"], "max_chars": _max_chars_for_role(role, "heading")}
            )["text"]
            body_text = self.provider.summarize(
                {"text": slide["body"], "max_chars": _max_chars_for_role(role, "paragraph")}
            )["text"]

            nodes: list[dict[str, Any]] = [
                {
                    "id": f"background-{page_index}",
                    "type": "background",
                    "x": 0,
                    "y": 0,
                    "width": width,
                    "height": height,
                    "z_index": 0,
                    "style": {
                        "backgroundColor": background_color,
                        "opacity": 1,
                    },
                    "asset_ref": background_asset.get("preview_url") if role != "body" and background_asset else None,
                    "children": [],
                }
            ]

            if role != "body" and background_asset:
                nodes.append(
                    {
                        "id": f"overlay-{page_index}",
                        "type": "shape",
                        "x": 0,
                        "y": 0,
                        "width": width,
                        "height": height,
                        "z_index": 2,
                        "style": {"backgroundColor": "#0F172A", "opacity": 0.36 if role == "cover" else 0.28},
                        "children": [],
                    }
                )

            if role == "body":
                nodes.append(
                    {
                        "id": f"surface-{page_index}",
                        "type": "card",
                        "x": safe_zone["left"] - 12,
                        "y": safe_zone["top"] - 12,
                        "width": width - safe_zone["left"] - safe_zone["right"] + 24,
                        "height": height - safe_zone["top"] - safe_zone["bottom"] + 24,
                        "z_index": 1,
                        "style": {"backgroundColor": "#FFFFFF", "borderRadius": 28, "opacity": 0.96},
                        "children": [],
                    }
                )

            if progression_region and project_context.get("piece_type") == "carousel":
                nodes.extend(
                    [
                        {
                            "id": f"slide-index-bg-{page_index}",
                            "type": "shape",
                            "x": progression_region.get("x", safe_zone["left"]),
                            "y": progression_region.get("y", safe_zone["top"]),
                            "width": progression_region.get("width", 184),
                            "height": progression_region.get("height", 48),
                            "z_index": 10,
                            "style": {"backgroundColor": accent_color, "borderRadius": 999, "opacity": 0.95},
                            "children": [],
                        },
                        {
                            "id": f"slide-index-{page_index}",
                            "type": "paragraph",
                            "x": progression_region.get("x", safe_zone["left"]) + 24,
                            "y": progression_region.get("y", safe_zone["top"]) + 10,
                            "width": progression_region.get("width", 184) - 48,
                            "height": progression_region.get("height", 48) - 20,
                            "z_index": 11,
                            "style": {
                                "color": "#FFFFFF",
                                "fontSize": 18,
                                "fontWeight": 700,
                                "fontFamily": typography.get("body_family", "DM Sans"),
                            },
                            "content": {"text": f"Slide {page_index + 1}/{len(content_plan['slides'])}"},
                            "constraints": {"safe_zone_behavior": "strict", "priority": 1},
                            "children": [],
                        },
                    ]
                )

            if media_region:
                if media_asset and media_asset.get("preview_url"):
                    nodes.append(
                        {
                            "id": f"media-{page_index}",
                            "type": "image",
                            "x": media_region.get("x", width - safe_zone["right"] - 260),
                            "y": media_region.get("y", safe_zone["top"] + 160),
                            "width": media_region.get("width", 260),
                            "height": media_region.get("height", 260),
                            "z_index": 12,
                            "asset_ref": media_asset.get("preview_url"),
                            "children": [],
                        }
                    )
                else:
                    nodes.append(
                        {
                            "id": f"media-shape-{page_index}",
                            "type": "shape",
                            "x": media_region.get("x", width - safe_zone["right"] - 260),
                            "y": media_region.get("y", safe_zone["top"] + 160),
                            "width": media_region.get("width", 260),
                            "height": media_region.get("height", 260),
                            "z_index": 12,
                            "style": {"backgroundColor": accent_color, "borderRadius": 24, "opacity": 0.18},
                            "children": [],
                        }
                    )

            if role == "body" and graphic_asset and graphic_asset.get("preview_url"):
                nodes.append(
                    {
                        "id": f"decorative-graphic-{page_index}",
                        "type": "image",
                        "x": width - safe_zone["right"] - 220,
                        "y": safe_zone["top"] + 120,
                        "width": 180,
                        "height": 180,
                        "z_index": 8,
                        "asset_ref": graphic_asset.get("preview_url"),
                        "children": [],
                    }
                )

            nodes.append(
                {
                    "id": f"heading-{page_index}",
                    "type": "heading",
                    "x": heading_region.get("x", default_heading["x"]),
                    "y": heading_region.get("y", default_heading["y"]),
                    "width": heading_region.get("width", default_heading["width"]),
                    "height": heading_region.get("height", default_heading["height"]),
                    "z_index": 20,
                    "style": {
                        "color": "#FFFFFF" if role != "body" else text_color,
                        "fontSize": _font_size_for_text(heading_text, role=role, kind="heading", typography=typography),
                        "fontWeight": 700,
                        "fontFamily": typography.get("heading_family", "Space Grotesk"),
                    },
                    "content": {"text": heading_text},
                    "constraints": {
                        "max_chars": _max_chars_for_role(role, "heading"),
                        "min_font_size": 28,
                        "max_font_size": 64,
                        "safe_zone_behavior": "strict",
                        "priority": 1,
                    },
                    "children": [],
                }
            )

            if role == "body":
                nodes.append(
                    {
                        "id": f"body-card-{page_index}",
                        "type": "card",
                        "x": body_region.get("x", default_body["x"]) - 24,
                        "y": body_region.get("y", default_body["y"]) - 18,
                        "width": body_region.get("width", default_body["width"]) + 48,
                        "height": body_region.get("height", default_body["height"]) + 36,
                        "z_index": 18,
                        "style": {"backgroundColor": "#F8FAFC", "borderRadius": 24, "opacity": 1},
                        "children": [],
                    }
                )

            nodes.append(
                {
                    "id": f"body-{page_index}",
                    "type": "paragraph",
                    "x": body_region.get("x", default_body["x"]),
                    "y": body_region.get("y", default_body["y"]),
                    "width": body_region.get("width", default_body["width"]),
                    "height": body_region.get("height", default_body["height"]),
                    "z_index": 22,
                    "style": {
                        "color": "#F8FAFC" if role != "body" else "#0F172A",
                        "fontSize": _font_size_for_text(body_text, role=role, kind="paragraph", typography=typography),
                        "fontWeight": 500,
                        "fontFamily": typography.get("body_family", "DM Sans"),
                    },
                    "content": {"text": body_text},
                    "constraints": {
                        "max_chars": _max_chars_for_role(role, "paragraph"),
                        "min_font_size": 16,
                        "max_font_size": 28,
                        "safe_zone_behavior": "strict",
                        "priority": 2,
                    },
                    "children": [],
                }
            )

            if role == "body":
                nodes.append(
                    {
                        "id": f"progress-track-{page_index}",
                        "type": "divider",
                        "x": safe_zone["left"],
                        "y": height - safe_zone["bottom"] - 24,
                        "width": min(width * 0.58, 320 + page_index * 32),
                        "height": 8,
                        "z_index": 24,
                        "style": {"backgroundColor": accent_color, "borderRadius": 999, "opacity": 0.95},
                        "children": [],
                    }
                )

            if slide.get("cta"):
                nodes.extend(
                    [
                        {
                            "id": f"cta-bg-{page_index}",
                            "type": "shape",
                            "x": cta_region.get("x", default_cta["x"]),
                            "y": cta_region.get("y", default_cta["y"]),
                            "width": cta_region.get("width", default_cta["width"]),
                            "height": cta_region.get("height", default_cta["height"]),
                            "z_index": 26,
                            "style": {"backgroundColor": accent_color, "borderRadius": 18, "opacity": 1},
                            "children": [],
                        },
                        {
                            "id": f"cta-label-{page_index}",
                            "type": "cta",
                            "x": cta_region.get("x", default_cta["x"]) + 24,
                            "y": cta_region.get("y", default_cta["y"]) + 18,
                            "width": cta_region.get("width", default_cta["width"]) - 48,
                            "height": cta_region.get("height", default_cta["height"]) - 36,
                            "z_index": 27,
                            "style": {
                                "color": "#FFFFFF",
                                "fontSize": 22,
                                "fontWeight": 700,
                                "fontFamily": typography.get("body_family", "DM Sans"),
                            },
                            "content": {"text": slide["cta"]},
                            "constraints": {"max_chars": 32, "safe_zone_behavior": "strict", "priority": 1},
                            "children": [],
                        },
                    ]
                )

            pages.append(
                {
                    "page_index": page_index,
                    "page_role": role,
                    "width": width,
                    "height": height,
                    "template_id": (template or {}).get("id"),
                    "safe_zone": safe_zone,
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
        review = _evaluate_review(
            state["composition_result"],
            state.get("brand_context", {}),
            state["project_context"],
            self.rules,
        )
        return {
            "review_result": review,
            "execution_log": _append_log(state, "review_layout", f"{len(review['warnings'])} warnings"),
        }


class MemoryCuratorAgent:
    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        suggestions = []
        pages = state.get("composition_result", {}).get("pages", [])
        project_context = state["project_context"]

        for asset in state.get("generated_assets", []):
            used_on_pages = [
                page["page_index"]
                for page in pages
                if any(node.get("asset_ref") == asset.get("preview_url") for node in page.get("nodes", []))
            ]
            if not used_on_pages:
                continue
            suggestions.append(
                {
                    "name": asset["name"],
                    "category": asset["category"],
                    "tags": ["generated", project_context["format_type"], project_context["channel"]],
                    "origin": "ai_generated",
                    "usage_context": [f"page_{index + 1}" for index in used_on_pages],
                    "metadata_json": asset.get("metadata_json", {}),
                    "rationale": "Generated asset was used in the final layout and can become a reusable memory asset.",
                }
            )

        cta_pages = [page["page_index"] for page in pages if any(node["id"].startswith("cta-bg") for node in page.get("nodes", []))]
        if cta_pages:
            suggestions.append(
                {
                    "name": "CTA Card",
                    "category": "component",
                    "component_type": "cta_block",
                    "tags": ["cta", project_context["format_type"], "reusable"],
                    "usage_context": [f"page_{index + 1}" for index in cta_pages],
                    "metadata_json": {"source": "layout_pattern"},
                    "rationale": "CTA block appears as a consistent callout and should be saved as a reusable design component.",
                }
            )

        progression_pages = [
            page["page_index"]
            for page in pages
            if any(node["id"].startswith("slide-index") for node in page.get("nodes", []))
        ]
        if progression_pages:
            suggestions.append(
                {
                    "name": "Carousel Progression Badge",
                    "category": "component",
                    "component_type": "progression_badge",
                    "tags": ["carousel", "badge", "navigation"],
                    "usage_context": [f"page_{index + 1}" for index in progression_pages],
                    "metadata_json": {"source": "layout_pattern"},
                    "rationale": "Progression badge repeats across carousel pages and should be promoted to reusable memory.",
                }
            )

        return {
            "asset_suggestions": suggestions,
            "execution_log": _append_log(state, "suggest_asset_saving", f"{len(suggestions)} reusable suggestions"),
        }


def apply_autofixes(
    state: dict[str, Any],
    provider: TextReasoningProvider,
    review_rules: ReviewRuleSet,
) -> dict[str, Any]:
    review = deepcopy(state["review_result"])
    composition = deepcopy(state["composition_result"])
    applied = list(review.get("autofixes_applied", []))
    brand_context = state.get("brand_context", {})
    primary = _first_color(brand_context, "primary", "#111827")
    neutral = _first_color(brand_context, "neutral", "#FFFFFF")

    if review["contrast_score"] < 0.72:
        for page in composition["pages"]:
            has_overlay = any(node["id"].startswith("overlay-") for node in page["nodes"])
            background = next((node for node in page["nodes"] if node["id"].startswith("background-")), None)
            if background and background.get("asset_ref") and not has_overlay:
                page["nodes"].append(
                    {
                        "id": f"overlay-{page['page_index']}-autofix",
                        "type": "shape",
                        "x": 0,
                        "y": 0,
                        "width": page["width"],
                        "height": page["height"],
                        "z_index": 3,
                        "style": {"backgroundColor": primary, "opacity": 0.44},
                        "children": [],
                    }
                )
            elif background:
                background["style"]["backgroundColor"] = primary

            for node in page["nodes"]:
                if node["type"] in TEXT_NODE_TYPES:
                    node.setdefault("style", {})
                    node["style"]["color"] = neutral if page["page_role"] != "body" else primary
                    node["style"]["textShadow"] = "0 2px 16px rgba(15,23,42,0.28)"
        applied.append("contrast_overlay")

    if review["text_density_score"] < 0.72:
        for page in composition["pages"]:
            for node in page["nodes"]:
                if node["type"] == "paragraph":
                    node["content"]["text"] = provider.summarize(
                        {
                            "text": node.get("content", {}).get("text", ""),
                            "max_chars": 110 if page["page_role"] == "body" else 90,
                        }
                    )["text"]
                if node["type"] == "heading":
                    node["content"]["text"] = provider.summarize(
                        {"text": node.get("content", {}).get("text", ""), "max_chars": 52}
                    )["text"]
        applied.append("body_summarization")

    recalculated = _evaluate_review(composition, brand_context, state["project_context"], review_rules)
    recalculated["autofixes_applied"] = applied
    return {
        "composition_result": composition,
        "review_result": recalculated,
        "execution_log": _append_log(state, "apply_autofixes", ", ".join(applied) or "no-op"),
    }
