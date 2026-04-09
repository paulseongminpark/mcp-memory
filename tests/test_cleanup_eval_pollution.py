"""cleanup_eval_pollution script tests."""

from pathlib import Path
import json
import shutil
import sqlite3
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.cleanup_eval_pollution import collect_pollution_stats, main


def _make_runtime_dir() -> Path:
    runtime_dir = ROOT / "tests" / f".runtime_cleanup_eval_{uuid.uuid4().hex}"
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
                visit_count INTEGER,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE recall_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT,
                node_id TEXT,
                rank INTEGER,
                score REAL,
                mode TEXT,
                timestamp TEXT,
                recall_id TEXT,
                sources TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE meta (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO nodes (id, type, project, visit_count, updated_at) VALUES (?, ?, ?, ?, NULL)",
            [
                (1, "Principle", "mcp-memory", 10),
                (2, "Pattern", "portfolio", 4),
                (3, "Tool", "orchestration", 7),
            ],
        )
        conn.executemany(
            """
            INSERT INTO recall_log
                (query, node_id, rank, score, mode, timestamp, recall_id, sources)
            VALUES (?, ?, 1, 0.9, 'generic', '2026-04-08T00:00:00+00:00', ?, '["semantic"]')
            """,
            [
                ("goldset one", "1", "eval-1"),
                ("goldset one", "1", "eval-2"),
                ("goldset two", "2", "eval-3"),
                ("goldset two", "2", None),
                ("live query", "1", "live-1"),
                ("live query", "3", "live-2"),
            ],
        )
        conn.execute(
            "INSERT INTO meta (key, value, updated_at) VALUES ('total_recall_count', '20', NULL)"
        )
        conn.commit()
    finally:
        conn.close()


def test_collect_pollution_stats_and_apply_cleanup():
    runtime_dir = _make_runtime_dir()
    try:
        db_path = runtime_dir / "memory.db"
        goldset_path = runtime_dir / "goldset.yaml"
        report_path = runtime_dir / "report.json"
        _init_test_db(db_path)
        goldset_path.write_text(
            "queries:\n  - query: goldset one\n  - query: goldset two\n",
            encoding="utf-8",
        )

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            stats = collect_pollution_stats(conn, ["goldset one", "goldset two"], top_n=5)
        finally:
            conn.close()

        assert stats["recall_log_rows_for_goldset"] == 4
        assert stats["distinct_nodes_hit_by_goldset"] == 2
        assert stats["reducible_recall_invocations"] == 3
        assert stats["legacy_rows_without_recall_id"] == 1
        assert stats["visit_count_delta_if_applied"] == 4
        assert stats["total_recall_count_after"] == 17

        rc = main(
            [
                "--db",
                str(db_path),
                "--goldset",
                str(goldset_path),
                "--apply",
                "--report",
                str(report_path),
            ]
        )
        assert rc == 0

        conn = sqlite3.connect(str(db_path))
        try:
            node1 = conn.execute("SELECT visit_count FROM nodes WHERE id = 1").fetchone()[0]
            node2 = conn.execute("SELECT visit_count FROM nodes WHERE id = 2").fetchone()[0]
            node3 = conn.execute("SELECT visit_count FROM nodes WHERE id = 3").fetchone()[0]
            total_recall = conn.execute(
                "SELECT value FROM meta WHERE key = 'total_recall_count'"
            ).fetchone()[0]
        finally:
            conn.close()

        assert node1 == 8
        assert node2 == 2
        assert node3 == 7
        assert total_recall == "17"

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["apply"] is True
        assert payload["applied"]["nodes_updated"] == 2
        assert payload["applied"]["visit_count_delta_applied"] == 4
        assert payload["applied"]["total_recall_count_delta_applied"] == 3

        rc = main(
            [
                "--db",
                str(db_path),
                "--goldset",
                str(goldset_path),
                "--apply",
            ]
        )
        assert rc == 0

        conn = sqlite3.connect(str(db_path))
        try:
            node1 = conn.execute("SELECT visit_count FROM nodes WHERE id = 1").fetchone()[0]
            total_recall = conn.execute(
                "SELECT value FROM meta WHERE key = 'total_recall_count'"
            ).fetchone()[0]
            marker = conn.execute(
                "SELECT value FROM meta WHERE key = 'eval_pollution_cleanup_v1_applied_at'"
            ).fetchone()[0]
        finally:
            conn.close()

        assert node1 == 8
        assert total_recall == "17"
        assert marker
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)
