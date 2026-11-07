"""Add explicit merchant tenant to organization mappings; no data is migrated."""

import sqlalchemy as sa

from alembic import op

revision = "20261029_0020"
down_revision = "20261029_0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "merchant_organization_mappings",
        sa.Column("tenant_id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("organization_id", name="uq_merchant_mapping_organization"),
        sa.CheckConstraint("tenant_id > 0", name="ck_merchant_mapping_tenant_positive"),
        sa.CheckConstraint(
            "length(trim(organization_id)) > 0", name="ck_merchant_mapping_org_nonempty"
        ),
    )


def downgrade():
    op.drop_table("merchant_organization_mappings")
