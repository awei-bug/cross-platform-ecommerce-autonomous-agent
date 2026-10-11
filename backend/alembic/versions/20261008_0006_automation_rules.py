"""add policy-driven automation rules and run history

Revision ID: 20261008_0006
Revises: 20260918_0005
Create Date: 2026-10-08 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261008_0006"
down_revision: str | Sequence[str] | None = "20260918_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_rules",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("rule_type", sa.String(48), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("organization_id", "rule_type", name="uq_automation_rules_org_type"),
    )
    op.create_index(
        "ix_automation_rules_organization_enabled",
        "automation_rules",
        ["organization_id", "is_enabled"],
    )
    op.create_table(
        "automation_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("matched_count", sa.Integer(), nullable=False),
        sa.Column("task_count", sa.Integer(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_automation_runs_rule_id", "automation_runs", ["rule_id"])
    op.create_index(
        "ix_automation_runs_rule_created", "automation_runs", ["rule_id", "created_at"]
    )
    op.create_index(
        "ix_automation_runs_organization_created",
        "automation_runs",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("automation_runs")
    op.drop_table("automation_rules")
