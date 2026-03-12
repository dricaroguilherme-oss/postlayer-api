from __future__ import annotations

from typing import Any
from uuid import UUID


def build_export_manifest(
    *,
    base_url: str,
    project_id: UUID,
    export_job_id: UUID,
    page_indices: list[int],
    file_type: str,
) -> dict[str, Any]:
    root = base_url.rstrip("/")
    download_root = f"{root}/api/v1/projects/{project_id}/exports/{export_job_id}"
    page_entries = [
        {
            "page_index": page_index,
            "output_url": f"{download_root}/pages/{page_index}",
            "file_type": file_type,
        }
        for page_index in page_indices
    ]
    return {
        "page_count": len(page_entries),
        "batch_output_url": f"{download_root}/download",
        "pages": page_entries,
    }
