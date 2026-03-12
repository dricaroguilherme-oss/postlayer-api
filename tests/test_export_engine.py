from __future__ import annotations

from uuid import UUID

from app.export_engine.manifest import build_export_manifest
from app.infra.providers.local_ai import LocalImageGenerationProvider
from app.rendering.svg_renderer import SvgLayoutRenderer


def _page(asset_ref: str | None = None) -> dict:
    return {
        "page_index": 0,
        "page_role": "cover",
        "width": 320,
        "height": 320,
        "nodes": [
            {
                "id": "background-0",
                "type": "background",
                "x": 0,
                "y": 0,
                "width": 320,
                "height": 320,
                "z_index": 0,
                "style": {"backgroundColor": "#111827", "opacity": 1},
                "asset_ref": asset_ref,
                "children": [],
            },
            {
                "id": "heading-0",
                "type": "heading",
                "x": 24,
                "y": 32,
                "width": 240,
                "height": 120,
                "z_index": 10,
                "style": {"color": "#F8FAFC", "fontSize": 30, "fontWeight": 700},
                "content": {"text": "Export bitmap real"},
                "children": [],
            },
        ],
    }


def test_local_image_provider_generates_png_data_url() -> None:
    provider = LocalImageGenerationProvider()
    asset = provider.generate_asset(
        {
            "prompt": "gradient background",
            "width": 320,
            "height": 320,
            "category": "background",
            "usage": "hero_background",
        }
    )

    assert asset["file_url"].startswith("data:image/png;base64,")


def test_renderer_exports_png_and_jpg_bytes() -> None:
    provider = LocalImageGenerationProvider()
    asset = provider.generate_asset(
        {
            "prompt": "gradient background",
            "width": 320,
            "height": 320,
            "category": "background",
            "usage": "hero_background",
        }
    )
    renderer = SvgLayoutRenderer()

    png_export = renderer.export_bitmap({"pages": [_page(asset["preview_url"])], "file_type": "png", "dpi": 144})
    jpg_export = renderer.export_bitmap({"pages": [_page(asset["preview_url"])], "file_type": "jpg", "dpi": 144})

    assert png_export["pages"][0]["bytes"].startswith(b"\x89PNG")
    assert jpg_export["pages"][0]["bytes"].startswith(b"\xff\xd8")
    assert png_export["pages"][0]["width"] == 640
    assert jpg_export["pages"][0]["height"] == 640


def test_build_export_manifest_includes_batch_and_page_urls() -> None:
    manifest = build_export_manifest(
        base_url="https://postlayer-api.example.com",
        project_id=UUID("f2a4f167-f2d7-4eb5-8ec9-fc11ab5d1c00"),
        export_job_id=UUID("2fe8ebbe-f88c-44f7-884e-0f1603c72a61"),
        page_indices=[0, 1],
        file_type="png",
    )

    assert manifest["batch_output_url"].endswith("/download")
    assert manifest["pages"][0]["output_url"].endswith("/pages/0")
    assert manifest["pages"][1]["file_type"] == "png"
