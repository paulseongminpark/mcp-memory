"""context_selector project scoping tests."""

from contextlib import ExitStack
from pathlib import Path
import shutil
import sqlite3
import sys
import uuid
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from storage import sqlite_store
from tools.context_selector import select_context


def _make_runtime_dir() -> Path:
    runtime_dir = ROOT / "tests" / f".runtime_context_{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


@pytest.fixture()
def context_db():
    runtime_dir = _make_runtime_dir()
    db_path = runtime_dir / "memory.db"

    with ExitStack() as stack:
        stack.enter_context(patch("config.DB_PATH", db_path))
        stack.enter_context(patch("storage.sqlite_store.DB_PATH", db_path))
        stack.enter_context(patch("storage.action_log.sqlite_store.DB_PATH", db_path))
        stack.enter_context(patch("utils.access_control.DB_PATH", db_path))
        sqlite_store.init_db()
        yield db_path

    shutil.rmtree(runtime_dir, ignore_errors=True)


def test_select_context_scopes_last_session_timeline_and_active_pipeline(context_db):
    conn = sqlite3.connect(str(context_db))
    try:
        conn.execute(
            """
            INSERT INTO sessions
                (session_id, summary, decisions, unresolved, project, started_at, ended_at, active_pipeline)
            VALUES (?, ?, '[]', '[]', ?, ?, ?, ?)
            """,
            (
                "sess-portfolio",
                "portfolio latest summary",
                "portfolio",
                "2026-04-08T09:00:00+00:00",
                "2026-04-08T09:30:00+00:00",
                "portfolio-pipeline",
            ),
        )
        conn.execute(
            """
            INSERT INTO sessions
                (session_id, summary, decisions, unresolved, project, started_at, ended_at, active_pipeline)
            VALUES (?, ?, '[]', '[]', ?, ?, ?, ?)
            """,
            (
                "sess-mcp",
                "mcp-memory summary",
                "mcp-memory",
                "2026-04-08T08:00:00+00:00",
                "2026-04-08T08:45:00+00:00",
                "mcp-pipeline",
            ),
        )

        conn.execute(
            """
            INSERT INTO action_log
                (actor, session_id, action_type, params, result, context, created_at)
            VALUES (?, ?, ?, '{}', '{}', ?, ?)
            """,
            ("claude", "sess-portfolio", "decision_recorded", "portfolio event", "2026-04-08T09:05:00+00:00"),
        )
        conn.execute(
            """
            INSERT INTO action_log
                (actor, session_id, action_type, params, result, context, created_at)
            VALUES (?, ?, ?, '{}', '{}', ?, ?)
            """,
            ("claude", "sess-mcp", "decision_recorded", "mcp event", "2026-04-08T08:05:00+00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    sections = select_context(project="mcp-memory")

    assert sections["last_session"]["id"] == "sess-mcp"
    assert sections["last_session"]["pipeline"] == "mcp-pipeline"
    assert sections["active_pipeline"] == "mcp-pipeline"
    assert sections["timeline"] == [
        {"time": "08:05", "type": "decision", "summary": "mcp event"}
    ]
