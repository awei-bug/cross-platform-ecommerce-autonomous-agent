"""add ai configuration and asset workbench tables

Revision ID: 20260913_0003
Revises: 20260913_0002
Create Date: 2026-09-13 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_0003"
down_revision: str | Sequence[str] | None = "20260913_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_configurations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("provider_id", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("selected_model", sa.String(200), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "provider_id", name="uq_ai_configurations_org_provider"
        ),
    )
    op.create_index(
        "ix_ai_configurations_organization_id", "ai_configurations", ["organization_id"]
    )
    op.create_table(
        "ai_discovered_models",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("configuration_id", sa.String(64), nullable=False),
        sa.Column("provider_id", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "configuration_id", "model_id", name="uq_ai_discovered_models_config_model"
        ),
    )
    op.create_index(
        "ix_ai_discovered_models_configuration_id", "ai_discovered_models", ["configuration_id"]
    )
    op.create_table(
        "assets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("product_id", sa.String(64), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_version_id", sa.String(64), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assets_product_id", "assets", ["product_id"])
    op.create_index("ix_assets_organization_updated", "assets", ["organization_id", "updated_at"])
    op.create_index("ix_assets_organization_type", "assets", ["organization_id", "asset_type"])
    op.create_table(
        "asset_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("asset_id", sa.String(64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("preview_url", sa.String(1000), nullable=True),
        sa.Column("quality_status", sa.String(32), nullable=False),
        sa.Column("quality_issues", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_asset_versions_asset_id", "asset_versions", ["asset_id"])
    op.create_index("ix_asset_versions_asset_created", "asset_versions", ["asset_id", "created_at"])
    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("asset_id", sa.String(64), nullable=True),
        sa.Column("configuration_id", sa.String(64), nullable=True),
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("result_version_id", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_generation_jobs_organization_created",
        "generation_jobs",
        ["organization_id", "created_at"],
    )
    op.create_table(
        "asset_quality_checks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("version_id", sa.String(64), nullable=False),
        sa.Column("check_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_asset_quality_checks_version_id", "asset_quality_checks", ["version_id"])
    op.create_index(
        "ix_asset_quality_checks_version_created",
        "asset_quality_checks",
        ["version_id", "created_at"],
    )
    op.create_table(
        "distribution_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("version_id", sa.String(64), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_distribution_jobs_organization_created",
        "distribution_jobs",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    for table in (
        "distribution_jobs",
        "asset_quality_checks",
        "generation_jobs",
        "asset_versions",
        "assets",
        "ai_discovered_models",
        "ai_configurations",
    ):
        op.drop_table(table)
