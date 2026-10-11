"""persist actionable automation tasks

Revision ID: 20261008_0007
Revises: 20261008_0006
Create Date: 2026-10-08 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261008_0007"
down_revision: str | Sequence[str] | None = "20261008_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_tasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("dedupe_key", sa.String(180), nullable=False),
        sa.Column("entity_id", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("reference", sa.String(120), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("suggested_action", sa.String(500), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("assignee", sa.String(80), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("organization_id", "dedupe_key", name="uq_automation_tasks_org_dedupe"),
    )
    op.create_index(
        "ix_automation_tasks_org_status_created",
        "automation_tasks",
        ["organization_id", "status", "created_at"],
    )
    op.create_index("ix_automation_tasks_run_id", "automation_tasks", ["run_id"])


def downgrade() -> None:
    op.drop_table("automation_tasks")
