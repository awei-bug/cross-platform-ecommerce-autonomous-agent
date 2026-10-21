"""content publish (douyin content studio)

Revision ID: 20261012_0015
Revises: 20261012_0014
Create Date: 2026-10-12 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261012_0015"
down_revision: str | Sequence[str] | None = "20261012_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_publishes",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="douyin"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("video_url", sa.String(length=1000), nullable=True),
        sa.Column("cover_url", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("external_url", sa.String(length=1000), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_content_publishes_org_created",
        "content_publishes",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_content_publishes_org_created", table_name="content_publishes")
    op.drop_table("content_publishes")
