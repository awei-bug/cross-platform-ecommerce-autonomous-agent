"""seed operational data layer (shops, products, alerts, workspace stats)

Revision ID: 20261010_0008
Revises: 20261008_0007
Create Date: 2026-10-10 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261010_0008"
down_revision: str | Sequence[str] | None = "20261008_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shops",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("platform_label", sa.String(32), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_source", sa.String(32), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Index("ix_shops_organization_id", "organization_id"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("shop_id", sa.String(64), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("platform_label", sa.String(32), nullable=False),
        sa.Column("shop_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("risk", sa.String(32), nullable=False),
        sa.Column("risk_labels", sa.JSON(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("cost", sa.Float(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("sales_7d", sa.Integer(), nullable=False),
        sa.Column("revenue_7d", sa.Float(), nullable=False),
        sa.Column("conversion_rate", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Index("ix_products_organization_id", "organization_id"),
        sa.Index("ix_products_organization_shop", "organization_id", "shop_id"),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("shop_id", sa.String(64), nullable=False),
        sa.Column("shop_name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Index("ix_alerts_organization_id", "organization_id"),
    )
    op.create_table(
        "workspace_stats",
        sa.Column("organization_id", sa.String(64), primary_key=True),
        sa.Column("today_sales", sa.Integer(), nullable=False),
        sa.Column("paid_orders", sa.Integer(), nullable=False),
        sa.Column("active_alerts", sa.Integer(), nullable=False),
        sa.Column("pending_tasks", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workspace_stats")
    op.drop_table("alerts")
    op.drop_table("products")
    op.drop_table("shops")
