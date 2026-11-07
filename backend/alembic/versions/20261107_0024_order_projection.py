"""Order projection and event watermark for cross-system order events."""

import sqlalchemy as sa

from alembic import op

revision = "20261107_0024"
down_revision = "20261029_0023"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "order_projections",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("order_no", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_order_projections_event_id"),
    )
    op.create_index("ix_order_projections_org", "order_projections", ["organization_id"])
    op.create_index(
        op.f("ix_order_projections_order_no"), "order_projections", ["order_no"]
    )

    op.create_table(
        "event_watermarks",
        sa.Column("consumer", sa.String(length=64), nullable=False),
        sa.Column("last_event_id", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("consumer"),
    )


def downgrade():
    op.drop_table("event_watermarks")
    op.drop_index(op.f("ix_order_projections_order_no"), table_name="order_projections")
    op.drop_index("ix_order_projections_org", table_name="order_projections")
    op.drop_table("order_projections")
