"""add object storage metadata to asset versions

Revision ID: 20260913_0004
Revises: 20260913_0003
Create Date: 2026-09-13 14:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_0004"
down_revision: str | Sequence[str] | None = "20260913_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("asset_versions", sa.Column("object_key", sa.String(length=500), nullable=True))
    op.add_column("asset_versions", sa.Column("content_type", sa.String(length=120), nullable=True))
    op.add_column("asset_versions", sa.Column("file_size", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("asset_versions", "file_size")
    op.drop_column("asset_versions", "content_type")
    op.drop_column("asset_versions", "object_key")
