"""diagnostic report snapshots

Revision ID: 20261012_0011
Revises: 20261012_0010
Create Date: 2026-10-12 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261012_0011"
down_revision: str | Sequence[str] | None = "20261012_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_reports",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("shop_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Index("ix_diagnostic_reports_org_created", "organization_id", "created_at"),
    )


def downgrade() -> None:
    op.drop_table("diagnostic_reports")
