"""cleanup_edge_learning_pollution script tests."""

from contextlib import ExitStack
from pathlib import Path
import json
import shutil
import sqlite3
import sys
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.cleanup_edge_learning_pollution import main


def _make_runtime_dir() -> Path:
    runtime_dir = ROOT / "tests" / f".runtime_cleanup_edges_{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _init_test_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                relation TEXT NOT NULL,
                description TEXT DEFAULT '',
                strength REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                direction TEXT,
                reason TEXT,
                updated_at TEXT,
                base_strength REAL,
                frequency REAL DEFAULT 0,
                last_activated TEXT,
                decay_rate REAL DEFAULT 0.005,
                layer_distance INTEGER,
                layer_penalty REAL,
                status TEXT DEFAULT 'active',
                co_retrieval_count INTEGER DEFAULT 0,
                co_retrieval_boost REAL DEFAULT 0.0,
                generation_method TEXT DEFAULT ''
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
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                recall_id TEXT DEFAULT NULL,
                sources TEXT DEFAULT NULL
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
            """
            INSERT INTO edges (
                source_id, target_id, relation, strength, created_at, updated_at,
                base_strength, frequency, last_activated, status, generation_method,
                co_retrieval_count, co_retrieval_boost
            ) VALUES (?, ?, ?, ?, datetime('now'), datetime('now'),
                      ?, ?, ?, 'active', ?, ?, ?)
            """,
            [
                (1, 2, "supports", 0.9, 0.7, 2.3, "2026-04-08T00:00:00+00:00", "enrichment", 0, 0.0),
                (1, 3, "co_retrieved", 0.5, 0.5, 1.1, "2026-04-08T00:00:00+00:00", "co_retrieval", 9, 0.5),
                (2, 3, "supports", 0.4, None, 0.6, "2026-04-08T00:00:00+00:00", "semantic_auto", 0, 0.0),
            ],
        )
        # Goldset sessions excluded.
        for recall_id in ("g1", "g2"):
            conn.executemany(
                """
                INSERT INTO recall_log (query, node_id, rank, score, mode, timestamp, recall_id, sources)
                VALUES ('goldset query', ?, 1, 0.9, 'generic', '2026-04-08T00:00:00+00:00', ?, '[]')
                """,
                [("1", recall_id), ("3", recall_id)],
            )
        # Live sessions kept -> pair (2,3)
        for recall_id in ("live1", "live2"):
            conn.executemany(
                """
                INSERT INTO recall_log (query, node_id, rank, score, mode, timestamp, recall_id, sources)
                VALUES ('live query', ?, 1, 0.9, 'generic', '2026-04-08T00:10:00+00:00', ?, '[]')
                """,
                [("2", recall_id), ("3", recall_id)],
            )
        conn.commit()
    finally:
        conn.close()


def test_cleanup_edge_learning_pollution_apply():
    runtime_dir = _make_runtime_dir()
    try:
        db_path = runtime_dir / "memory.db"
        goldset_path = runtime_dir / "goldset.yaml"
        report_path = runtime_dir / "report.json"
        _init_test_db(db_path)
        goldset_path.write_text("queries:\n  - query: goldset query\n", encoding="utf-8")

        with ExitStack() as stack:
            stack.enter_context(patch("config.DB_PATH", db_path))
            stack.enter_context(patch("storage.sqlite_store.DB_PATH", db_path))
            rc = main(
                [
                    "--db",
                    str(db_path),
                    "--goldset",
                    str(goldset_path),
                    "--apply",
                    "--min-co-count",
                    "2",
                    "--hub-percentile",
                    "0",
                    "--report",
                    str(report_path),
                ]
            )
        assert rc == 0

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            restored = conn.execute(
                "SELECT strength, frequency, last_activated FROM edges WHERE relation='supports' AND source_id=1 AND target_id=2"
            ).fetchone()
            old_co = conn.execute(
                "SELECT COUNT(*) FROM edges WHERE generation_method='co_retrieval' AND status='archived'"
            ).fetchone()[0]
            new_co = conn.execute(
                """
                SELECT source_id, target_id, strength, base_strength, frequency, co_retrieval_count
                FROM edges
                WHERE generation_method='co_retrieval' AND status='active'
                ORDER BY id DESC LIMIT 1
                """
            ).fetchone()
            marker = conn.execute(
                "SELECT value FROM meta WHERE key='edge_learning_cleanup_v1_applied_at'"
            ).fetchone()[0]
        finally:
            conn.close()

        assert restored["strength"] == 0.7
        assert restored["frequency"] == 0
        assert restored["last_activated"] is None
        assert old_co == 1
        assert (new_co["source_id"], new_co["target_id"]) == (2, 3)
        assert new_co["strength"] == 0.1
        assert new_co["base_strength"] == 0.1
        assert new_co["frequency"] == 0
        assert new_co["co_retrieval_count"] == 2
        assert marker

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["applied"]["frequency_reset_edges"] == 3
        assert payload["applied"]["strength_restored_edges"] == 1
        assert payload["co_retrieval_rebuild"]["archived_existing"] == 1
        assert payload["co_retrieval_rebuild"]["updated"] == 1
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)
