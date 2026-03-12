from __future__ import annotations

import html
import urllib.parse
from typing import Any

from app.application.contracts.providers import Renderer


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
        preview = self.render_preview(payload)
        return {
            "format": payload.get("file_type", "png"),
            "pages": preview["pages"],
        }
