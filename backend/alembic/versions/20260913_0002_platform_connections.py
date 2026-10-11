"""create platform connection and oauth state tables

Revision ID: 20260913_0002
Revises: 20260912_0001
Create Date: 2026-09-13 01:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_0002"
down_revision: str | Sequence[str] | None = "20260912_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_connections",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("app_key_reference", sa.String(length=32), nullable=True),
        sa.Column("encrypted_access_token", sa.Text(), nullable=True),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("platform_user_id", sa.String(length=128), nullable=True),
        sa.Column("platform_user_name", sa.String(length=200), nullable=True),
        sa.Column("platform_shop_id", sa.String(length=128), nullable=True),
        sa.Column("platform_shop_name", sa.String(length=200), nullable=True),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "platform", name="uq_platform_connections_org_platform"
        ),
    )
    op.create_index(
        "ix_platform_connections_organization_id",
        "platform_connections",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_platform_connections_platform_state",
        "platform_connections",
        ["platform", "state"],
        unique=False,
    )

    op.create_table(
        "oauth_states",
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("redirect_uri", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("state_hash"),
    )
    op.create_index(
        "ix_oauth_states_organization_id",
        "oauth_states",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_oauth_states_platform_expires",
        "oauth_states",
        ["platform", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_oauth_states_platform_expires", table_name="oauth_states")
    op.drop_index("ix_oauth_states_organization_id", table_name="oauth_states")
    op.drop_table("oauth_states")
    op.drop_index("ix_platform_connections_platform_state", table_name="platform_connections")
    op.drop_index("ix_platform_connections_organization_id", table_name="platform_connections")
    op.drop_table("platform_connections")
