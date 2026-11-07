"""Add explicit employee/shop grants without granting existing accounts access."""

import sqlalchemy as sa

from alembic import op

revision = "20261029_0021"
down_revision = "20261029_0020"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "merchant_shop_grants",
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("merchant_organization_mappings.tenant_id"),
            primary_key=True,
        ),
        sa.Column("staff_id", sa.Integer(), primary_key=True),
        sa.Column("shop_id", sa.String(64), sa.ForeignKey("shops.id"), primary_key=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("staff_id > 0", name="ck_merchant_shop_grant_staff_positive"),
    )


def downgrade():
    op.drop_table("merchant_shop_grants")
