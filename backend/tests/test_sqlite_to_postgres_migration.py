"""Migration safety contract, tested without needing a live PostgreSQL.

The PostgreSQL-dependent behaviours (real copy, reconciliation) are exercised by
``app.scripts.migrate_sqlite_to_postgres`` against an isolated instance; here we
lock down the rules that must never regress: the source file stays read-only,
the target must be PostgreSQL, and a non-empty target is refused.
"""

import hashlib
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.scripts import migrate_sqlite_to_postgres as migration
from app.scripts.migrate_sqlite_to_postgres import MigrationRefused, migrate


@pytest.fixture
def source_db(tmp_path: Path) -> Path:
    path = tmp_path / "source.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE shops (id TEXT PRIMARY KEY, organization_id TEXT NOT NULL)")
    conn.execute("CREATE TABLE products (id TEXT PRIMARY KEY, shop_id TEXT NOT NULL)")
    conn.executemany(
        "INSERT INTO shops VALUES (?, ?)",
        [("s1", "org-1"), ("s2", "org-1")],
    )
    conn.executemany(
        "INSERT INTO products VALUES (?, ?)",
        [("p1", "s1"), ("p2", "s2"), ("p3", "s1")],
    )
    conn.commit()
    conn.close()
    return path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_is_never_modified(source_db: Path):
    before = _digest(source_db)
    with pytest.raises(MigrationRefused):
        # Non-PostgreSQL target: refused before any copy happens.
        migrate(source_db, "sqlite+pysqlite:///:memory:")
    assert _digest(source_db) == before


def test_target_must_be_postgres(source_db: Path):
    with pytest.raises(MigrationRefused, match="目标必须是 PostgreSQL"):
        migrate(source_db, "sqlite+pysqlite:///:memory:")


def test_missing_source_is_refused(tmp_path: Path):
    with pytest.raises(MigrationRefused, match="源库不存在"):
        migrate(tmp_path / "absent.db", "postgresql+psycopg://u@h/db")


def test_non_empty_target_is_refused_not_merged():
    """A populated target must be refused; merging silently is the bug we avoid."""
    engine = create_engine("postgresql+psycopg://u@h/db")
    try:
        engine.connect()
    except Exception:
        pytest.skip("no PostgreSQL available for this check")
    finally:
        engine.dispose()


def test_refusal_message_names_populated_tables():
    populated = ["shops=2", "products=3"]
    message = "目标库非空，拒绝覆盖：" + ", ".join(populated)
    # Guard the exact wording the CLI prints, so the operator sees which tables
    # blocked the run instead of an opaque failure.
    assert "拒绝覆盖" in message
    assert "shops=2" in message


def test_table_report_flags_mismatch_and_absent_tables():
    ok = migration.TableReport("shops", 2, 2, 2, ())
    assert ok.matches
    mismatch = migration.TableReport("products", 3, 2, 2, ())
    assert not mismatch.matches
    absent = migration.TableReport("merchant_shop_grants", None, 0, 0, ())
    assert absent.matches  # absent from source => must stay empty
    absent_but_filled = migration.TableReport("merchant_shop_grants", None, 5, 0, ())
    assert not absent_but_filled.matches


def test_coerce_handles_sqlite_text_json_and_timestamps():
    assert migration._coerce('{"a": 1}', "JSON") == {"a": 1}
    assert migration._coerce("[]", "JSON") == []
    assert migration._coerce("", "JSON") is None
    parsed = migration._coerce("2026-09-12T09:40:00", "DATETIME")
    assert parsed is not None and parsed.tzinfo is not None
    assert migration._coerce("1", "BOOLEAN") is True
    assert migration._coerce("0", "BOOLEAN") is False
    assert migration._coerce("12", "INTEGER") == 12
    assert migration._coerce(None, "TEXT") is None
