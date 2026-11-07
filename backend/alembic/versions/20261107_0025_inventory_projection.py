"""Inventory projection for cross-system stock events."""

import sqlalchemy as sa

from alembic import op

revision = "20261107_0025"
down_revision = "20261107_0024"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inventory_projections",
        sa.Column("id", sa.String(length=96), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("sku_id", sa.String(length=64), nullable=True),
        sa.Column("item_title", sa.String(length=255), nullable=False),
        sa.Column("stock_after", sa.Integer(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_inventory_projections_event_id"),
    )
    op.create_index("ix_inventory_projections_org", "inventory_projections", ["organization_id"])
    op.create_index(
        op.f("ix_inventory_projections_product_id"),
        "inventory_projections",
        ["product_id"],
    )


def downgrade():
    op.drop_index(
        op.f("ix_inventory_projections_product_id"), table_name="inventory_projections"
    )
    op.drop_index("ix_inventory_projections_org", table_name="inventory_projections")
    op.drop_table("inventory_projections")
