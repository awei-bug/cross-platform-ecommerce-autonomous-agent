"""Align pre-existing ORM indexes with the migration history."""

from alembic import op

revision = "20261015_0017"
down_revision = "20261015_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"])
    op.create_index("ix_diagnostic_exports_report_id", "diagnostic_exports", ["report_id"])
    op.create_index("ix_products_shop_id", "products", ["shop_id"])


def downgrade() -> None:
    op.drop_index("ix_products_shop_id", table_name="products")
    op.drop_index("ix_diagnostic_exports_report_id", table_name="diagnostic_exports")
    op.drop_index("ix_agent_steps_run_id", table_name="agent_steps")
