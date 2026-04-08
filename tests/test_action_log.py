"""action_log.record() 테스트."""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# config를 모킹하기 위해 먼저 패치
_tmp = tempfile.mkdtemp()
_test_db = Path(_tmp) / "test.db"


@pytest.fixture(autouse=True)
def setup_test_db():
    """매 테스트마다 깨끗한 DB 생성."""
    if _test_db.exists():
        _test_db.unlink()

    conn = sqlite3.connect(str(_test_db))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS action_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            session_id TEXT,
            action_type TEXT NOT NULL,
            target_type TEXT,
            target_id INTEGER,
            params TEXT DEFAULT '{}',
            result TEXT DEFAULT '{}',
            context TEXT,
            model TEXT,
            duration_ms INTEGER,
            token_cost INTEGER,
            created_at TEXT NOT NULL
        );
    """)
    conn.close()

    with patch("config.DB_PATH", _test_db), \
         patch("storage.sqlite_store.DB_PATH", _test_db):
        yield

    if _test_db.exists():
        _test_db.unlink()


def test_record_basic():
    """기본 record() — 최소 파라미터."""
    from storage.action_log import record
    log_id = record(action_type="recall", actor="claude")
    assert log_id is not None
    assert isinstance(log_id, int)
    assert log_id > 0


def test_record_full_params():
    """전체 파라미터 record()."""
    from storage.action_log import record
    log_id = record(
        action_type="node_created",
        actor="claude",
        session_id="sess-001",
        target_type="node",
        target_id=42,
        params=json.dumps({"content": "test"}),
        result=json.dumps({"id": 42}),
        context="test context",
        model="claude-opus-4-6",
        duration_ms=150,
        token_cost=1000,
    )
    assert log_id is not None

    # DB에서 확인
    conn = sqlite3.connect(str(_test_db))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM action_log WHERE id=?", (log_id,)).fetchone()
    conn.close()

    assert row["actor"] == "claude"
    assert row["action_type"] == "node_created"
    assert row["session_id"] == "sess-001"
    assert row["target_type"] == "node"
    assert row["target_id"] == 42
    assert row["model"] == "claude-opus-4-6"
    assert row["duration_ms"] == 150


def test_record_with_external_conn():
    """외부 conn 전달 — 트랜잭션 참여."""
    from storage.action_log import record
    from storage.sqlite_store import _connect

    conn = _connect()
    log_id = record(action_type="bcm_update", actor="system", conn=conn)
    assert log_id is not None

    # 아직 커밋 안 함 — 같은 conn에서만 보여야 함
    row = conn.execute("SELECT id FROM action_log WHERE id=?", (log_id,)).fetchone()
    assert row is not None

    conn.commit()
    conn.close()


def test_record_silent_fail():
    """DB 에러 시 None 반환, 예외 없음."""
    from storage.action_log import record

    # 없는 테이블에 쓰려고 시도 (action_log를 DROP하여 시뮬레이션)
    conn = sqlite3.connect(str(_test_db))
    conn.execute("DROP TABLE action_log")
    conn.commit()
    conn.close()

    result = record(action_type="recall", actor="claude")
    assert result is None  # 예외가 아닌 None


def test_record_default_params_result():
    """params/result 기본값은 '{}'."""
    from storage.action_log import record
    log_id = record(action_type="session_start")
    assert log_id is not None

    conn = sqlite3.connect(str(_test_db))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT params, result FROM action_log WHERE id=?", (log_id,)).fetchone()
    conn.close()

    assert row["params"] == "{}"
    assert row["result"] == "{}"


def test_taxonomy_count():
    """ACTION_TAXONOMY 29개 확인."""
    from storage.action_log import ACTION_TAXONOMY
    assert len(ACTION_TAXONOMY) == 29


def test_record_created_at_populated():
    """created_at이 자동 채워짐."""
    from storage.action_log import record
    log_id = record(action_type="migration")

    conn = sqlite3.connect(str(_test_db))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT created_at FROM action_log WHERE id=?", (log_id,)).fetchone()
    conn.close()

    assert row["created_at"] is not None
    assert "T" in row["created_at"]  # ISO format
