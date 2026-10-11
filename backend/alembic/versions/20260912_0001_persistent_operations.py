"""create persistent operation, audit, and alert state tables

Revision ID: 20260912_0001
Revises:
Create Date: 2026-09-12 15:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260912_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operation_jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("succeeded", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("entity_ids", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "kind", "idempotency_key", name="uq_operation_jobs_kind_idempotency"
        ),
    )
    op.create_index(
        "ix_operation_jobs_kind_created_at",
        "operation_jobs",
        ["kind", "created_at"],
        unique=False,
    )
    op.create_index("ix_operation_jobs_status", "operation_jobs", ["status"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("entity_reference", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("action_label", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=80), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_job_id", "audit_logs", ["job_id"], unique=False)
    op.create_index(
        "ix_audit_logs_domain_entity_created",
        "audit_logs",
        ["domain", "entity_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "alert_states",
        sa.Column("alert_id", sa.String(length=80), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("alert_id"),
    )


def downgrade() -> None:
    op.drop_table("alert_states")
    op.drop_index("ix_audit_logs_domain_entity_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_job_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_operation_jobs_status", table_name="operation_jobs")
    op.drop_index("ix_operation_jobs_kind_created_at", table_name="operation_jobs")
    op.drop_table("operation_jobs")
