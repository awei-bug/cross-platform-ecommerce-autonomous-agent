"""add is_free flag to discovered AI models

Revision ID: 20260918_0005
Revises: 20260913_0004
Create Date: 2026-09-18 23:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260918_0005"
down_revision: str | Sequence[str] | None = "20260913_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_discovered_models", sa.Column("is_free", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_discovered_models", "is_free")
