"""create product domain tables

Revision ID: 20260312_0001
Revises:
Create Date: 2026-03-12 02:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260312_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("primary_colors", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("secondary_colors", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("neutral_colors", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("typography_heading", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("typography_body", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("font_weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("default_title_sizes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("default_body_sizes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("border_radius_preset", sa.String(length=64), nullable=True),
        sa.Column("shadow_preset", sa.String(length=64), nullable=True),
        sa.Column("logo_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "visual_style_keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "composition_rules_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "approved_reference_assets",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "rejected_reference_assets",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brands")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_brands_tenant_name"),
    )
    op.create_index(op.f("ix_brands_tenant_id"), "brands", ["tenant_id"], unique=False)

    op.create_table(
        "brand_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("subcategory", sa.String(length=80), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="upload"),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("preview_url", sa.Text(), nullable=True),
        sa.Column("dominant_color", sa.String(length=32), nullable=True),
        sa.Column("is_recolorable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_decorative", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "usage_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("ai_generated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brand_assets")),
    )
    op.create_index(op.f("ix_brand_assets_brand_id"), "brand_assets", ["brand_id"], unique=False)
    op.create_index(op.f("ix_brand_assets_category"), "brand_assets", ["category"], unique=False)
    op.create_index(op.f("ix_brand_assets_tenant_id"), "brand_assets", ["tenant_id"], unique=False)

    op.create_foreign_key(
        "fk_brands_logo_asset_id_brand_assets",
        "brands",
        "brand_assets",
        ["logo_asset_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "layout_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("format_type", sa.String(length=64), nullable=False),
        sa.Column("page_role", sa.String(length=64), nullable=False),
        sa.Column("schema_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "constraints_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_system_template", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("tenant_id IS NOT NULL OR is_system_template = true", name="layout_templates_scope"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_layout_templates")),
    )
    op.create_index(op.f("ix_layout_templates_brand_id"), "layout_templates", ["brand_id"], unique=False)
    op.create_index(op.f("ix_layout_templates_channel"), "layout_templates", ["channel"], unique=False)
    op.create_index(op.f("ix_layout_templates_format_type"), "layout_templates", ["format_type"], unique=False)
    op.create_index(op.f("ix_layout_templates_is_system_template"), "layout_templates", ["is_system_template"], unique=False)
    op.create_index(op.f("ix_layout_templates_tenant_id"), "layout_templates", ["tenant_id"], unique=False)

    op.create_table(
        "design_components",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("component_type", sa.String(length=80), nullable=False),
        sa.Column("schema_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("style_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_design_components")),
    )
    op.create_index(op.f("ix_design_components_brand_id"), "design_components", ["brand_id"], unique=False)
    op.create_index(op.f("ix_design_components_tenant_id"), "design_components", ["tenant_id"], unique=False)

    op.create_table(
        "creative_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("format_type", sa.String(length=64), nullable=False),
        sa.Column("piece_type", sa.String(length=32), nullable=False, server_default="single_post"),
        sa.Column("dimensions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("objective", sa.String(length=255), nullable=False),
        sa.Column("audience", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("cta", sa.String(length=255), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_creative_projects")),
    )
    op.create_index(op.f("ix_creative_projects_brand_id"), "creative_projects", ["brand_id"], unique=False)
    op.create_index(op.f("ix_creative_projects_channel"), "creative_projects", ["channel"], unique=False)
    op.create_index(op.f("ix_creative_projects_format_type"), "creative_projects", ["format_type"], unique=False)
    op.create_index(op.f("ix_creative_projects_status"), "creative_projects", ["status"], unique=False)
    op.create_index(op.f("ix_creative_projects_tenant_id"), "creative_projects", ["tenant_id"], unique=False)

    op.create_table(
        "creative_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("page_role", sa.String(length=64), nullable=False),
        sa.Column("content_plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("layout_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("review_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["project_id"], ["creative_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_creative_pages")),
        sa.UniqueConstraint("project_id", "page_index", name="uq_creative_pages_project_page"),
    )
    op.create_index(op.f("ix_creative_pages_project_id"), "creative_pages", ["project_id"], unique=False)

    op.create_table(
        "project_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="system_generation"),
        sa.Column("strategy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "art_direction_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("render_tree_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "exported_assets_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["project_id"], ["creative_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_versions")),
        sa.UniqueConstraint("project_id", "version_number", name="uq_project_versions_project_version"),
    )
    op.create_index(op.f("ix_project_versions_project_id"), "project_versions", ["project_id"], unique=False)

    op.create_foreign_key(
        "fk_creative_projects_current_version_id_project_versions",
        "creative_projects",
        "project_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "export_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=False, server_default="png"),
        sa.Column("dimensions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("dpi", sa.Integer(), nullable=False, server_default="144"),
        sa.Column("output_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["creative_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["project_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_export_jobs")),
    )
    op.create_index(op.f("ix_export_jobs_project_id"), "export_jobs", ["project_id"], unique=False)
    op.create_index(op.f("ix_export_jobs_status"), "export_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_export_jobs_version_id"), "export_jobs", ["version_id"], unique=False)

    op.create_table(
        "ai_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["project_id"], ["creative_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_jobs")),
    )
    op.create_index(op.f("ix_ai_jobs_project_id"), "ai_jobs", ["project_id"], unique=False)
    op.create_index(op.f("ix_ai_jobs_status"), "ai_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_jobs_status"), table_name="ai_jobs")
    op.drop_index(op.f("ix_ai_jobs_project_id"), table_name="ai_jobs")
    op.drop_table("ai_jobs")

    op.drop_index(op.f("ix_export_jobs_version_id"), table_name="export_jobs")
    op.drop_index(op.f("ix_export_jobs_status"), table_name="export_jobs")
    op.drop_index(op.f("ix_export_jobs_project_id"), table_name="export_jobs")
    op.drop_table("export_jobs")

    op.drop_constraint("fk_creative_projects_current_version_id_project_versions", "creative_projects", type_="foreignkey")
    op.drop_index(op.f("ix_project_versions_project_id"), table_name="project_versions")
    op.drop_table("project_versions")

    op.drop_index(op.f("ix_creative_pages_project_id"), table_name="creative_pages")
    op.drop_table("creative_pages")

    op.drop_index(op.f("ix_creative_projects_tenant_id"), table_name="creative_projects")
    op.drop_index(op.f("ix_creative_projects_status"), table_name="creative_projects")
    op.drop_index(op.f("ix_creative_projects_format_type"), table_name="creative_projects")
    op.drop_index(op.f("ix_creative_projects_channel"), table_name="creative_projects")
    op.drop_index(op.f("ix_creative_projects_brand_id"), table_name="creative_projects")
    op.drop_table("creative_projects")

    op.drop_index(op.f("ix_design_components_tenant_id"), table_name="design_components")
    op.drop_index(op.f("ix_design_components_brand_id"), table_name="design_components")
    op.drop_table("design_components")

    op.drop_index(op.f("ix_layout_templates_tenant_id"), table_name="layout_templates")
    op.drop_index(op.f("ix_layout_templates_is_system_template"), table_name="layout_templates")
    op.drop_index(op.f("ix_layout_templates_format_type"), table_name="layout_templates")
    op.drop_index(op.f("ix_layout_templates_channel"), table_name="layout_templates")
    op.drop_index(op.f("ix_layout_templates_brand_id"), table_name="layout_templates")
    op.drop_table("layout_templates")

    op.drop_constraint("fk_brands_logo_asset_id_brand_assets", "brands", type_="foreignkey")
    op.drop_index(op.f("ix_brand_assets_tenant_id"), table_name="brand_assets")
    op.drop_index(op.f("ix_brand_assets_category"), table_name="brand_assets")
    op.drop_index(op.f("ix_brand_assets_brand_id"), table_name="brand_assets")
    op.drop_table("brand_assets")

    op.drop_index(op.f("ix_brands_tenant_id"), table_name="brands")
    op.drop_table("brands")
