"""Audit explicit merchant access changes."""

import sqlalchemy as sa

from alembic import op

revision = "20261029_0022"
down_revision = "20261029_0021"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "merchant_access_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("target_staff_id", sa.Integer(), nullable=True),
        sa.Column("target_shop_id", sa.String(64), nullable=True),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_merchant_access_audit_tenant_id", "merchant_access_audit", ["tenant_id"])


def downgrade():
    op.drop_index("ix_merchant_access_audit_tenant_id", table_name="merchant_access_audit")
    op.drop_table("merchant_access_audit")
