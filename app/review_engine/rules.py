from __future__ import annotations

from typing import Any

from app.application.contracts.providers import ReviewRuleSet


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    if len(value) != 6:
        return (1.0, 1.0, 1.0)
    return tuple(int(value[index : index + 2], 16) / 255 for index in (0, 2, 4))


def _linearize(channel: float) -> float:
    return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4


def _contrast_ratio(foreground: str, background: str) -> float:
    fg = _hex_to_rgb(foreground)
    bg = _hex_to_rgb(background)
    fg_luminance = 0.2126 * _linearize(fg[0]) + 0.7152 * _linearize(fg[1]) + 0.0722 * _linearize(fg[2])
    bg_luminance = 0.2126 * _linearize(bg[0]) + 0.7152 * _linearize(bg[1]) + 0.0722 * _linearize(bg[2])
    lighter, darker = max(fg_luminance, bg_luminance), min(fg_luminance, bg_luminance)
    return (lighter + 0.05) / (darker + 0.05)


class RuleBasedReviewRuleSet(ReviewRuleSet):
    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        warnings: list[dict[str, Any]] = []
        pages = payload["composition_result"]["pages"]
        brand_colors = payload.get("brand_context", {}).get("color_tokens", {})
        allowed_palette = set(
            brand_colors.get("primary", []) + brand_colors.get("secondary", []) + brand_colors.get("neutral", [])
        )

        contrast_scores: list[float] = []
        density_scores: list[float] = []
        adherence_scores: list[float] = []

        for page in pages:
            background_node = next((node for node in page["nodes"] if node["type"] == "background"), None)
            background_color = (background_node or {}).get("style", {}).get("backgroundColor", "#F9FAFB")
            text_nodes = [node for node in page["nodes"] if node["type"] in {"heading", "paragraph", "cta", "text"}]
            page_contrast = []
            page_chars = 0
            off_brand_nodes = 0

            for node in text_nodes:
                color = node.get("style", {}).get("color", "#111827")
                ratio = _contrast_ratio(color, background_color)
                page_contrast.append(min(ratio / 7.0, 1.0))
                if ratio < 4.5:
                    warnings.append(
                        {
                            "code": "low_contrast",
                            "severity": "warning",
                            "message": f"Contraste insuficiente no nó {node['id']} (ratio {ratio:.2f})",
                            "target_node_id": node["id"],
                        }
                    )
                if allowed_palette and color not in allowed_palette and color not in {"#FFFFFF", "#111827"}:
                    off_brand_nodes += 1

                text = str(node.get("content", {}).get("text", ""))
                page_chars += len(text)

            contrast_scores.append(sum(page_contrast) / len(page_contrast) if page_contrast else 1.0)
            density_budget = max((page["width"] * page["height"]) / 12000, 90)
            density_ratio = page_chars / density_budget if density_budget else 0
            density_score = max(0.0, min(1.0, 1.15 - density_ratio))
            density_scores.append(density_score)
            if density_score < 0.65:
                warnings.append(
                    {
                        "code": "text_density_high",
                        "severity": "warning",
                        "message": f"Excesso de texto na página {page['page_index'] + 1}",
                        "target_node_id": None,
                    }
                )

            adherence_scores.append(1.0 if not text_nodes else max(0.0, 1 - (off_brand_nodes / len(text_nodes))))

        contrast_score = sum(contrast_scores) / len(contrast_scores) if contrast_scores else 1.0
        text_density_score = sum(density_scores) / len(density_scores) if density_scores else 1.0
        brand_adherence_score = sum(adherence_scores) / len(adherence_scores) if adherence_scores else 1.0
        legibility_score = (contrast_score + text_density_score) / 2

        return {
            "warnings": warnings,
            "legibility_score": round(legibility_score, 3),
            "brand_adherence_score": round(brand_adherence_score, 3),
            "contrast_score": round(contrast_score, 3),
            "text_density_score": round(text_density_score, 3),
            "autofixes_applied": [],
        }
