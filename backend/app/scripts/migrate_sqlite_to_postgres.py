"""Idempotent SQLite -> PostgreSQL data migration with per-table reconciliation.

Design rules
------------
* The source SQLite file is opened READ-ONLY (``mode=ro`` URI); it is never
  written, vacuumed or migrated.
* The target PostgreSQL database must be migrated to Alembic head first
  (``alembic upgrade head``). This script only copies rows; it never creates
  or drops tables.
* Re-running is safe: rows are upserted by primary key. A second run over the
  same source produces identical row counts and identical content.
* The target must be EMPTY (all migrated tables at 0 rows) unless
  ``--replace`` is passed explicitly. Silently merging into a populated
  database is refused, not attempted.
* Only columns present in BOTH source and target are copied. Columns that
  exist only in the target keep their server/ORM defaults (e.g. ``external_id``
  and ``hub_product_id`` on ``products``), and missing source tables simply
  contribute zero rows.
* After copying, every table's source and target row count is reconciled and a
  non-zero exit status is returned on any mismatch.

Usage
-----
    python -m app.scripts.migrate_sqlite_to_postgres \
        --source data/ops_workbench.db \
        --target postgresql+psycopg://user@host:port/dbname \
        [--replace] [--dry-run]

Exit codes: 0 success, 1 reconciliation mismatch, 2 refused/unsafe condition.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, Table, create_engine, inspect, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from app.db.models import Base

# SQLite stores JSON columns as text and timestamps as ISO strings; PostgreSQL
# typed columns need real values, so these are converted on the way through.
_JSON_HINTS = {"JSON"}
_DATETIME_HINTS = {"DATETIME", "TIMESTAMP"}
_INT_HINTS = {"INTEGER", "BIGINT", "SMALLINT"}
_FLOAT_HINTS = {"FLOAT", "REAL", "DOUBLE", "NUMERIC", "DECIMAL"}
_BOOL_HINTS = {"BOOLEAN", "BOOL"}

# Copied in foreign-key-safe order; parents before children.
TABLE_ORDER = [
    "merchant_organization_mappings",
    "shops",
    "merchant_shop_grant",
    "merchant_shop_grants",
    "merchant_access_audit",
    "workspace_stats",
    "products",
    "alerts",
    "alert_states",
    "operation_jobs",
    "audit_logs",
    "automation_rules",
    "automation_runs",
    "automation_tasks",
    "platform_connections",
    "oauth_states",
    "ai_configurations",
    "ai_discovered_models",
    "assets",
    "asset_versions",
    "generation_jobs",
    "asset_quality_checks",
    "distribution_jobs",
    "diagnostic_reports",
    "report_exports",
    "diagnostic_exports",
    "agent_runs",
    "agent_steps",
    "competitors",
    "diagnoses",
    "content_publishes",
    "ecom_configurations",
    "ecom_records",
    "ecom_runs",
    "ecom_tasks",
    "ecom_events",
    "ecom_audits",
    "ecom_schedules",
]


class MigrationRefused(Exception):
    """An unsafe precondition: never proceed, never partially merge."""


@dataclass(frozen=True)
class TableReport:
    table: str
    source_rows: int | None  # None: table absent from the source database
    target_rows: int
    copied: int
    missing_columns: tuple[str, ...]

    @property
    def matches(self) -> bool:
        # 源库没有该表时，目标库也应保持为空（无数据可迁移）。
        if self.source_rows is None:
            return self.target_rows == 0
        return self.target_rows == self.source_rows


def _source_tables(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _source_columns(conn: sqlite3.Connection, table: str) -> list[tuple[str, str]]:
    return [
        (row[1], (row[2] or "").upper())
        for row in conn.execute(f'PRAGMA table_info("{table}")')
    ]


def _target_columns(engine: Engine, table: str) -> dict[str, str]:
    """Column name -> SQLAlchemy type class name for the target table."""
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return {}
    return {
        column["name"]: type(column["type"]).__name__.upper()
        for column in inspector.get_columns(table)
    }


def _coerce(value: Any, target_type: str) -> Any:
    """Convert a SQLite text/blob value into the target column's Python type."""
    if value is None:
        return None
    if target_type in _JSON_HINTS:
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return stripped
        return value
    if target_type in _DATETIME_HINTS:
        if isinstance(value, str):
            text_value = value.strip()
            if not text_value:
                return None
            normalised = text_value.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(normalised)
            except ValueError:
                return None
            # SQLite rows are naive; treat them as UTC so PostgreSQL's
            # timestamptz column stores an unambiguous instant.
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
        return value
    if target_type in _BOOL_HINTS:
        if isinstance(value, (int, bool)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "t", "yes"}
        return bool(value)
    if target_type in _INT_HINTS:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if target_type in _FLOAT_HINTS:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return value


def _quote(engine: Engine, name: str) -> str:
    return engine.dialect.identifier_preparer.quote(name)


def _primary_key(engine: Engine, table: str) -> list[str]:
    inspector = inspect(engine)
    pk = inspector.get_pk_constraint(table)
    return list(pk.get("constrained_columns") or [])


def _ensure_target_empty(engine: Engine, tables: list[str]) -> None:
    """Refuse to merge into a non-empty target unless --replace was explicit."""
    with engine.connect() as connection:
        populated = []
        for table in tables:
            count = connection.execute(
                text(f"SELECT count(*) FROM {_quote(engine, table)}")
            ).scalar_one()
            if count:
                populated.append(f"{table}={count}")
    if populated:
        raise MigrationRefused(
            "目标库非空，拒绝覆盖：" + ", ".join(populated) + "；如确需覆盖请显式传入 --replace"
        )


def _reflect(engine: Engine, table: str) -> Table:
    """Reflect the target table so column types bind correctly (esp. JSON)."""
    return Table(table, MetaData(), autoload_with=engine)


def _upsert(engine: Engine, table: str, rows: list[dict[str, Any]], pk: list[str]) -> int:
    """Insert-or-update by primary key; returns the number of rows written.

    Re-running over the same source converges on the same content, which is what
    makes the migration idempotent: an existing row is overwritten with the
    source value rather than appended or silently skipped.
    """
    if not rows:
        return 0
    target = _reflect(engine, table)
    update_columns = [c for c in rows[0] if c not in pk]
    with engine.begin() as connection:
        if update_columns:
            statement = pg_insert(target).values(rows)
            statement = statement.on_conflict_do_update(
                index_elements=pk,
                set_={c: statement.excluded[c] for c in update_columns},
            )
        else:
            statement = pg_insert(target).values(rows).on_conflict_do_nothing(
                index_elements=pk
            )
        connection.execute(statement)
    return len(rows)


def migrate(
    source_path: Path,
    target_url: str,
    *,
    replace: bool = False,
    dry_run: bool = False,
) -> list[TableReport]:
    if not source_path.is_file():
        raise MigrationRefused(f"源库不存在：{source_path}")
    # Read-only URI: the source file cannot be modified by this process.
    source_uri = f"file:{source_path.as_posix()}?mode=ro"
    engine = create_engine(target_url, future=True)
    if engine.dialect.name != "postgresql":
        raise MigrationRefused("目标必须是 PostgreSQL；SQLite 之间无需迁移")

    reports: list[TableReport] = []
    conn = sqlite3.connect(source_uri, uri=True)
    try:
        present_source = _source_tables(conn)
        target_tables = set(inspect(engine).get_table_names())
        if "alembic_version" not in target_tables:
            raise MigrationRefused(
                "目标库未执行 Alembic 迁移；请先运行 alembic upgrade head"
            )

        candidates = [
            table
            for table in TABLE_ORDER
            if table in target_tables or table in present_source
        ]
        # Anything the ORM knows about but not listed above is appended so the
        # reconciliation covers every mapped table.
        for table in Base.metadata.tables:
            if table not in candidates and table in target_tables:
                candidates.append(table)
        candidates = [t for t in candidates if t in target_tables]

        if not replace and not dry_run:
            _ensure_target_empty(engine, candidates)

        for table in candidates:
            target_columns = _target_columns(engine, table)
            if not target_columns:
                continue
            if table not in present_source:
                reports.append(
                    TableReport(table, None, _count(engine, table), 0, ())
                )
                continue
            source_columns = _source_columns(conn, table)
            shared = [(name, kind) for name, kind in source_columns if name in target_columns]
            missing = tuple(
                name for name, _ in source_columns if name not in target_columns
            )
            target_only = tuple(c for c in target_columns if c not in dict(source_columns))
            if not shared:
                reports.append(
                    TableReport(
                        table,
                        _count_source(conn, table),
                        _count(engine, table),
                        0,
                        missing,
                    )
                )
                continue
            select_list = ", ".join(f'"{name}"' for name, _ in shared)
            raw_rows = list(conn.execute(f'SELECT {select_list} FROM "{table}"'))
            rows = []
            for raw in raw_rows:
                record = {}
                for (name, _kind), value in zip(shared, raw, strict=True):
                    record[name] = _coerce(value, target_columns[name])
                rows.append(record)

            pk = _primary_key(engine, table)
            if not pk:
                # Without a primary key idempotency cannot be guaranteed, so the
                # table is reported instead of silently duplicated on re-run.
                raise MigrationRefused(f"表 {table} 没有主键，无法幂等写入")

            copied = 0 if dry_run else _upsert(engine, table, rows, pk)
            reports.append(
                TableReport(
                    table=table,
                    source_rows=_count_source(conn, table),
                    target_rows=_count(engine, table),
                    copied=copied,
                    missing_columns=missing + target_only,
                )
            )
    finally:
        conn.close()
        engine.dispose()
    return reports


def _count_source(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as connection:
        return int(
            connection.execute(text(f"SELECT count(*) FROM {_quote(engine, table)}")).scalar_one()
        )


def _print_reports(reports: list[TableReport], *, dry_run: bool = False) -> bool:
    header = f"{'表名':<36}{'源行数':>10}{'目标行数':>12}{'一致':>8}"
    print(header)
    print("-" * len(header))
    all_ok = True
    for report in reports:
        source = "-" if report.source_rows is None else str(report.source_rows)
        ok = report.matches
        # A dry run writes nothing, so target counts are not a verdict.
        all_ok = all_ok and (ok or dry_run)
        if dry_run:
            flag = "DRY"
        elif ok and report.source_rows is None:
            flag = "源无此表"
        else:
            flag = "OK" if ok else "MISMATCH"
        print(f"{report.table:<36}{source:>10}{report.target_rows:>12}{flag:>8}")
        if report.missing_columns:
            joined = ", ".join(report.missing_columns)
            print(f"    列差异（仅一侧存在，未复制或保持默认）: {joined}")
    return all_ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SQLite → PostgreSQL 幂等数据迁移与逐表对账（源库只读）"
    )
    parser.add_argument("--source", required=True, help="源 SQLite 文件路径（只读）")
    parser.add_argument("--target", required=True, help="目标 PostgreSQL DATABASE_URL")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="目标库非空时允许覆盖（默认拒绝，避免静默合并）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只对账不写入")
    args = parser.parse_args(argv)
    try:
        reports = migrate(
            Path(args.source),
            args.target,
            replace=args.replace,
            dry_run=args.dry_run,
        )
    except MigrationRefused as exc:
        print(f"拒绝执行：{exc}", file=sys.stderr)
        return 2
    ok = _print_reports(reports, dry_run=args.dry_run)
    if not ok:
        print("存在行数不一致，迁移未通过对账。", file=sys.stderr)
        return 1
    print("全部表行数一致。" + ("（dry-run，未写入）" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
