from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.presets.templates import SYSTEM_LAYOUT_TEMPLATES
from app.domain.template.models import LayoutTemplate
from app.infra.db import models as _models  # noqa: F401


def seed_system_layout_templates(session: Session) -> int:
    existing_ids = {
        value
        for value in session.scalars(
            select(LayoutTemplate.id).where(LayoutTemplate.id.in_([uuid.UUID(item["id"]) for item in SYSTEM_LAYOUT_TEMPLATES]))
        )
    }
    created = 0

    for item in SYSTEM_LAYOUT_TEMPLATES:
        template_id = uuid.UUID(item["id"])
        if template_id in existing_ids:
            continue

        session.add(
            LayoutTemplate(
                id=template_id,
                tenant_id=None,
                brand_id=None,
                name=item["name"],
                channel=item["channel"],
                format_type=item["format_type"],
                page_role=item["page_role"],
                schema_json=item["schema_json"],
                constraints_json=item["constraints_json"],
                tags=item["tags"],
                is_system_template=item["is_system_template"],
            )
        )
        created += 1

    return created
