"""report export records (excel / pdf)

Revision ID: 20261012_0013
Revises: 20261012_0012
Create Date: 2026-10-12 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261012_0013"
down_revision: str | Sequence[str] | None = "20261012_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_exports",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("template_id", sa.String(32), nullable=False),
        sa.Column("template_name", sa.String(80), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("shop_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("file_name", sa.String(200), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Index("ix_report_exports_org_created", "organization_id", "created_at"),
    )


def downgrade() -> None:
    op.drop_table("report_exports")
