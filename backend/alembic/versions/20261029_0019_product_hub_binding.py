"""Store explicit knowledge bindings separately from platform identity."""

import sqlalchemy as sa

from alembic import op

revision = "20261029_0019"
down_revision = "20261015_0018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("hub_product_id", sa.String(128), nullable=True))


def downgrade():
    op.drop_column("products", "hub_product_id")
