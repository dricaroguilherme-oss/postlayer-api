from __future__ import annotations

import base64
import colorsys
import html
import io
import re
import urllib.parse
from functools import lru_cache
from typing import Any

import httpx
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from app.application.contracts.providers import Renderer

_FONT_FILES = {
    "regular": [
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
    "bold": [
        "DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
}


def _attrs(mapping: dict[str, Any]) -> str:
    return " ".join(f'{key}="{html.escape(str(value), quote=True)}"' for key, value in mapping.items() if value is not None)


def _render_node(node: dict[str, Any]) -> str:
    node_type = node["type"]
    style = node.get("style", {})
    children = "".join(_render_node(child) for child in sorted(node.get("children", []), key=lambda item: item.get("z_index", 0)))
    frame = {
        "x": node.get("x", 0),
        "y": node.get("y", 0),
        "width": node.get("width", 0),
        "height": node.get("height", 0),
    }

    if node_type in {"canvas", "group"}:
        return children

    if node_type in {"background", "shape", "card", "badge", "divider"}:
        return (
            f"<rect {_attrs({'x': frame['x'], 'y': frame['y'], 'width': frame['width'], 'height': frame['height'], 'rx': style.get('borderRadius', 0), 'fill': style.get('backgroundColor') or style.get('fill', 'transparent'), 'opacity': style.get('opacity', 1)})} />"
            + children
        )

    if node_type in {"image", "icon"} and node.get("asset_ref"):
        href = html.escape(str(node["asset_ref"]), quote=True)
        return f"<image {_attrs({'href': href, 'x': frame['x'], 'y': frame['y'], 'width': frame['width'], 'height': frame['height'], 'preserveAspectRatio': 'xMidYMid slice'})} />"

    content = node.get("content", {})
    text = html.escape(str(content.get("text", "")))
    font_size = style.get("fontSize", 42)
    baseline = frame["y"] + font_size
    return (
        f"<text {_attrs({'x': frame['x'], 'y': baseline, 'fill': style.get('color', '#111827'), 'font-size': font_size, 'font-weight': style.get('fontWeight', 600), 'font-family': style.get('fontFamily', 'DM Sans')})}>{text}</text>"
        + children
    )


def _node_opacity(style: dict[str, Any]) -> float:
    value = style.get("opacity", 1)
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return 1.0


def _parse_color(value: str | None, default: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    if not value:
        return default

    raw = value.strip()
    try:
        if raw.startswith("rgba(") and raw.endswith(")"):
            red, green, blue, alpha = [item.strip() for item in raw[5:-1].split(",")]
            return (int(float(red)), int(float(green)), int(float(blue)), int(float(alpha) * 255))
        if raw.startswith("rgb(") and raw.endswith(")"):
            red, green, blue = [item.strip() for item in raw[4:-1].split(",")]
            return (int(float(red)), int(float(green)), int(float(blue)), 255)
        if raw.startswith("hsla(") and raw.endswith(")"):
            hue, saturation, lightness, alpha = [item.strip().rstrip("%") for item in raw[5:-1].split(",")]
            rgb = colorsys.hls_to_rgb(float(hue) / 360, float(lightness) / 100, float(saturation) / 100)
            return (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255), int(float(alpha) * 255))
        if raw.startswith("hsl(") and raw.endswith(")"):
            hue, saturation, lightness = [item.strip().rstrip("%") for item in raw[4:-1].split(",")]
            rgb = colorsys.hls_to_rgb(float(hue) / 360, float(lightness) / 100, float(saturation) / 100)
            return (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255), 255)
        red, green, blue = ImageColor.getrgb(raw)
        return (red, green, blue, 255)
    except (ValueError, TypeError):
        return default


def _font(size: int, weight: int | str | None) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    font_size = max(10, int(size))
    weight_value = 400
    try:
        weight_value = int(weight or 400)
    except (TypeError, ValueError):
        weight_value = 700 if str(weight).lower() in {"bold", "semibold"} else 400
    bucket = "bold" if weight_value >= 600 else "regular"
    for candidate in _FONT_FILES[bucket]:
        try:
            return ImageFont.truetype(candidate, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_length(draw: ImageDraw.ImageDraw, value: str, font: ImageFont.ImageFont | ImageFont.FreeTypeFont) -> float:
    return float(draw.textlength(value, font=font))


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    max_width: int,
    max_height: int,
) -> str:
    words = text.split()
    if not words:
        return ""

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or _text_length(draw, candidate, font) <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = word
    if current:
        lines.append(current)

    line_height = max(12, int(getattr(font, "size", 18) * 1.2))
    max_lines = max(1, max_height // line_height)
    if len(lines) <= max_lines:
        return "\n".join(lines)

    truncated = lines[:max_lines]
    while truncated and _text_length(draw, truncated[-1] + "…", font) > max_width:
        parts = truncated[-1].split(" ")
        if len(parts) <= 1:
            truncated[-1] = parts[0][: max(1, len(parts[0]) - 1)]
            break
        truncated[-1] = " ".join(parts[:-1])
    truncated[-1] = f"{truncated[-1].rstrip()}…"
    return "\n".join(truncated)


def _apply_opacity(image: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 1:
        return image
    alpha = image.getchannel("A")
    alpha = alpha.point(lambda value: int(value * opacity))
    image.putalpha(alpha)
    return image


def _decode_data_url(asset_ref: str) -> tuple[str, bytes] | None:
    if not asset_ref.startswith("data:"):
        return None
    header, _, payload = asset_ref.partition(",")
    mime_type = header[5:].split(";")[0] or "application/octet-stream"
    if ";base64" in header:
        return mime_type, base64.b64decode(payload)
    return mime_type, urllib.parse.unquote_to_bytes(payload)


@lru_cache(maxsize=128)
def _fetch_asset_bytes(asset_ref: str) -> tuple[str, bytes] | None:
    decoded = _decode_data_url(asset_ref)
    if decoded is not None:
        return decoded
    if not asset_ref.startswith(("http://", "https://")):
        return None
    response = httpx.get(asset_ref, timeout=20.0)
    response.raise_for_status()
    return response.headers.get("content-type", "application/octet-stream"), response.content


def _load_asset_image(asset_ref: str) -> Image.Image | None:
    if not asset_ref:
        return None
    try:
        payload = _fetch_asset_bytes(asset_ref)
    except httpx.HTTPError:
        return None
    if payload is None:
        return None
    mime_type, data = payload
    if "svg" in mime_type:
        return None
    try:
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except (UnidentifiedImageError, OSError):
        return None


def _fit_image(asset: Image.Image, width: int, height: int) -> Image.Image:
    return ImageOps.fit(asset, (max(1, width), max(1, height)), method=Image.Resampling.LANCZOS)


def _rounded_mask(width: int, height: int, radius: int) -> Image.Image:
    mask = Image.new("L", (max(1, width), max(1, height)), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width, height), radius=max(0, radius), fill=255)
    return mask


def _draw_rect_node(page_image: Image.Image, node: dict[str, Any], scale: float) -> None:
    style = node.get("style", {})
    width = max(1, int(node.get("width", 0) * scale))
    height = max(1, int(node.get("height", 0) * scale))
    x = int(node.get("x", 0) * scale)
    y = int(node.get("y", 0) * scale)
    radius = int(float(style.get("borderRadius", 0) or 0) * scale)
    fill = _parse_color(style.get("backgroundColor") or style.get("fill"), (0, 0, 0, 0))
    layer = Image.new("RGBA", page_image.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer, "RGBA")
    layer_draw.rounded_rectangle((x, y, x + width, y + height), radius=radius, fill=fill)

    asset_ref = node.get("asset_ref")
    if asset_ref:
        asset = _load_asset_image(str(asset_ref))
        if asset is not None:
            fitted = _fit_image(asset, width, height)
            mask = _rounded_mask(width, height, radius)
            layer.paste(fitted, (x, y), mask)

    _apply_opacity(layer, _node_opacity(style))
    page_image.alpha_composite(layer)


def _draw_image_node(page_image: Image.Image, node: dict[str, Any], scale: float) -> None:
    asset = _load_asset_image(str(node.get("asset_ref") or ""))
    if asset is None:
        return
    style = node.get("style", {})
    width = max(1, int(node.get("width", 0) * scale))
    height = max(1, int(node.get("height", 0) * scale))
    x = int(node.get("x", 0) * scale)
    y = int(node.get("y", 0) * scale)
    fitted = _fit_image(asset, width, height)
    layer = Image.new("RGBA", page_image.size, (0, 0, 0, 0))
    layer.paste(fitted, (x, y), fitted)
    _apply_opacity(layer, _node_opacity(style))
    page_image.alpha_composite(layer)


def _draw_text_node(page_image: Image.Image, node: dict[str, Any], scale: float) -> None:
    style = node.get("style", {})
    text = str((node.get("content") or {}).get("text", "")).strip()
    if not text:
        return
    x = int(node.get("x", 0) * scale)
    y = int(node.get("y", 0) * scale)
    width = max(1, int(node.get("width", 0) * scale))
    height = max(1, int(node.get("height", 0) * scale))
    font_size = max(12, int(float(style.get("fontSize", 18) or 18) * scale))
    font = _font(font_size, style.get("fontWeight"))
    layer = Image.new("RGBA", page_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    wrapped = _wrap_text(draw, re.sub(r"\s+", " ", text), font, width, height)
    fill = _parse_color(style.get("color"), (17, 24, 39, 255))
    shadow_color = _parse_color(style.get("shadowColor"), (0, 0, 0, 0))
    if shadow_color[3] > 0:
        draw.multiline_text((x + 2, y + 2), wrapped, font=font, fill=shadow_color, spacing=max(4, int(font_size * 0.16)))
    draw.multiline_text((x, y), wrapped, font=font, fill=fill, spacing=max(4, int(font_size * 0.16)))
    _apply_opacity(layer, _node_opacity(style))
    page_image.alpha_composite(layer)


def _draw_nodes(page_image: Image.Image, nodes: list[dict[str, Any]], scale: float) -> None:
    for node in sorted(nodes, key=lambda item: item.get("z_index", 0)):
        node_type = node.get("type")
        if node_type == "group":
            _draw_nodes(page_image, node.get("children", []), scale)
            continue
        if node_type in {"background", "shape", "card", "badge", "divider"}:
            _draw_rect_node(page_image, node, scale)
        elif node_type in {"image", "icon"}:
            _draw_image_node(page_image, node, scale)
        elif node_type in {"text", "heading", "subheading", "paragraph", "cta"}:
            _draw_text_node(page_image, node, scale)
        if node.get("children"):
            _draw_nodes(page_image, node["children"], scale)


class SvgLayoutRenderer(Renderer):
    def render_preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        pages = []
        for page in payload["pages"]:
            width = page["width"]
            height = page["height"]
            content = "".join(
                _render_node(node)
                for node in sorted(page.get("nodes", []), key=lambda item: item.get("z_index", 0))
            )
            svg = (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
                + content
                + "</svg>"
            )
            pages.append(
                {
                    "page_index": page["page_index"],
                    "svg": svg,
                    "data_url": "data:image/svg+xml;utf8," + urllib.parse.quote(svg),
                }
            )

        return {"pages": pages}

    def export_bitmap(self, payload: dict[str, Any]) -> dict[str, Any]:
        file_type = str(payload.get("file_type", "png")).lower()
        dpi = max(72, int(payload.get("dpi", 144)))
        scale = dpi / 72
        pages: list[dict[str, Any]] = []

        for page in payload["pages"]:
            width = int(page["width"])
            height = int(page["height"])
            image = Image.new("RGBA", (max(1, int(width * scale)), max(1, int(height * scale))), (255, 255, 255, 0))
            _draw_nodes(image, page.get("nodes", []), scale)
            output = io.BytesIO()
            if file_type == "jpg":
                flattened = Image.new("RGB", image.size, (255, 255, 255))
                flattened.paste(image, mask=image.getchannel("A"))
                flattened.save(output, format="JPEG", quality=95, optimize=True)
                mime_type = "image/jpeg"
                extension = "jpg"
            else:
                image.save(output, format="PNG", optimize=True)
                mime_type = "image/png"
                extension = "png"
            pages.append(
                {
                    "page_index": page["page_index"],
                    "width": image.width,
                    "height": image.height,
                    "bytes": output.getvalue(),
                    "mime_type": mime_type,
                    "extension": extension,
                }
            )

        return {
            "format": file_type,
            "dpi": dpi,
            "pages": pages,
        }
