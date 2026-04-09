"""archive_save_session_work_items script tests."""

from pathlib import Path
import json
import shutil
import sqlite3
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.archive_save_session_work_items import main


def _make_runtime_dir() -> Path:
    runtime_dir = ROOT / "tests" / f".runtime_archive_work_items_{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _init_test_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY,
                type TEXT,
                project TEXT,
                status TEXT,
                source TEXT,
                node_role TEXT,
                content TEXT,
                updated_at TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO nodes (id, type, project, status, source, node_role, content, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            [
                (1, "Decision", "mcp-memory", "active", "save_session", "work_item", "짧은 작업 항목"),
                (2, "Question", "mcp-memory", "active", "save_session", "work_item", "검증 필요"),
                (3, "Decision", "mcp-memory", "active", "save_session", "knowledge_candidate", "남겨야 할 판단"),
                (4, "Narrative", "mcp-memory", "active", "save_session", "session_anchor", "세션 요약"),
                (5, "Decision", "mcp-memory", "archived", "save_session", "work_item", "이미 archive"),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_archive_save_session_work_items_dry_run_and_apply():
    runtime_dir = _make_runtime_dir()
    try:
        db_path = runtime_dir / "memory.db"
        report_path = runtime_dir / "report.json"
        _init_test_db(db_path)

        rc = main(["--db", str(db_path), "--report", str(report_path)])
        assert rc == 0

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["apply"] is False
        assert payload["candidates"]["candidate_count"] == 2

        rc = main(["--db", str(db_path), "--apply", "--report", str(report_path)])
        assert rc == 0

        conn = sqlite3.connect(str(db_path))
        try:
            statuses = conn.execute(
                "SELECT id, status FROM nodes ORDER BY id"
            ).fetchall()
        finally:
            conn.close()

        assert statuses == [
            (1, "archived"),
            (2, "archived"),
            (3, "active"),
            (4, "active"),
            (5, "archived"),
        ]

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["applied"]["archived_count"] == 2
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)
