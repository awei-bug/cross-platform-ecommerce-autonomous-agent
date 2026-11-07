"""Explicit product-read permission, disabled for all existing shop grants."""

import sqlalchemy as sa

from alembic import op

revision = "20261029_0023"
down_revision = "20261029_0022"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "merchant_shop_grants",
        sa.Column("can_read_products", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("merchant_shop_grants", "can_read_products")
