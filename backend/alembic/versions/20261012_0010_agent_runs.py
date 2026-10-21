"""agentic review layer (agent runs, steps, competitor library, diagnoses)

Revision ID: 20261012_0010
Revises: 20261010_0009
Create Date: 2026-10-12 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261012_0010"
down_revision: str | Sequence[str] | None = "20261010_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("shop_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Index("ix_agent_runs_org_created", "organization_id", "created_at"),
    )
    op.create_table(
        "agent_steps",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("wave", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(48), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Index("ix_agent_steps_run_sequence", "run_id", "sequence"),
    )
    op.create_table(
        "competitors",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("platform_label", sa.String(32), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("sales_7d", sa.Integer(), nullable=False),
        sa.Column("conversion_rate", sa.Float(), nullable=False),
        sa.Column("selling_points", sa.JSON(), nullable=False),
        sa.Column("review_pain_points", sa.JSON(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Index("ix_competitors_org_category", "organization_id", "category"),
        sa.Index("ix_competitors_org_updated", "organization_id", "updated_at"),
    )
    op.create_table(
        "diagnoses",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("shop_id", sa.String(64), nullable=False),
        sa.Column("shop_name", sa.String(200), nullable=False),
        sa.Column("product_id", sa.String(64), nullable=True),
        sa.Column("kind", sa.String(48), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("detail", sa.String(500), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("recommendation", sa.String(500), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("decided_by", sa.String(80), nullable=True),
        sa.Column("decision_note", sa.String(500), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Index("ix_diagnoses_run_created", "run_id", "created_at"),
        sa.Index(
            "ix_diagnoses_org_status_created",
            "organization_id",
            "status",
            "created_at",
        ),
    )


def downgrade() -> None:
    op.drop_table("diagnoses")
    op.drop_table("competitors")
    op.drop_table("agent_steps")
    op.drop_table("agent_runs")
