"""diagnostic exports (pdf / xlsx)

Revision ID: 20261012_0012
Revises: 20261012_0011
Create Date: 2026-10-12 15:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261012_0012"
down_revision: str | Sequence[str] | None = "20261012_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_exports",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("report_id", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("format", sa.String(8), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(200), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Index("ix_diagnostic_exports_org_created", "organization_id", "created_at"),
    )


def downgrade() -> None:
    op.drop_table("diagnostic_exports")
