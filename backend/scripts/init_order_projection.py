"""显式创建订单投影表与水位表。

本机 .env 关闭了 DATABASE_AUTO_CREATE，启动不会自动建表。新环境部署时
执行本脚本，或运行 alembic upgrade head（版本 20261107_0024）。
create_all 带 checkfirst，只补缺失表，不改动既有结构与数据。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect  # noqa: E402

from app.db.models import Base  # noqa: E402
from app.db.session import get_engine  # noqa: E402


def main() -> None:
    engine = get_engine()
    before = set(inspect(engine).get_table_names())
    Base.metadata.create_all(bind=engine, checkfirst=True)
    after = set(inspect(engine).get_table_names())
    print("engine:", engine.url)
    for name in ("order_projections", "event_watermarks"):
        if name in before:
            state = "already present"
        elif name in after:
            state = "created"
        else:
            state = "MISSING"
        print(f"{name}: {state}")
    engine.dispose()


if __name__ == "__main__":
    main()
