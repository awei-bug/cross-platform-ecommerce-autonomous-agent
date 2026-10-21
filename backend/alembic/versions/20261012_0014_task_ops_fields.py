"""task ops fields (attempts / started_at / dead letter)

Revision ID: 20261012_0014
Revises: 20261012_0013
Create Date: 2026-10-12 17:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261012_0014"
down_revision: str | Sequence[str] | None = "20261012_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("operation_jobs", "generation_jobs", "agent_runs")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        )
        op.add_column(
            table,
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        )
        op.add_column(table, sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(
            table, sa.Column("dead_letter_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "dead_letter_at")
        op.drop_column(table, "started_at")
        op.drop_column(table, "max_attempts")
        op.drop_column(table, "attempts")
