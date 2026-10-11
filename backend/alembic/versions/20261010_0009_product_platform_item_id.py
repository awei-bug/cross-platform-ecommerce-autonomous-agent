"""add platform_item_id to products

Revision ID: 20261010_0009
Revises: 20261010_0008
Create Date: 2026-10-10
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261010_0009"
down_revision: str | None = "20261010_0008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> Sequence:
    op.add_column(
        "products",
        sa.Column("platform_item_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_products_platform_item_id", "products", ["platform_item_id"], unique=False
    )


def downgrade() -> Sequence:
    op.drop_index("ix_products_platform_item_id", table_name="products")
    op.drop_column("products", "platform_item_id")
