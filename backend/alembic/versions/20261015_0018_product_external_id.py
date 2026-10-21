"""add external_id to products

Revision ID: 20261015_0018
Revises: 20261015_0017
Create Date: 2026-12

把商品记忆库（data-hub）的外部身份接入本项目商品表。

背景与取舍：
- data-hub 是商品内容知识的唯一权威源，本项目只作为**只读消费者**，不在本地
  复制知识字段，避免出现第二份真相。
- 因此只需一个 `external_id` 把本地商品与 data-hub 记录对账，而不是加一堆
  JSON 字段。
- 抖店同步来的商品记 `dy-{platform_item_id}`，data-hub 来的商品沿用原值；
  幂等优先级为 external_id > (shop_id, sku) > platform_item_id。

该列可空：历史种子商品没有对应记忆库记录，填 NULL 而不是伪造一个 ID。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261015_0018"
down_revision: str | None = "20261015_0017"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> Sequence:
    op.add_column(
        "products",
        sa.Column("external_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_products_external_id", "products", ["external_id"], unique=False
    )


def downgrade() -> Sequence:
    op.drop_index("ix_products_external_id", table_name="products")
    op.drop_column("products", "external_id")
