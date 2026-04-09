"""co_retrieval rebuild tests."""

from contextlib import ExitStack
from pathlib import Path
import shutil
import sqlite3
import sys
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.enrich.co_retrieval import calculate_co_retrieval


def _make_runtime_dir() -> Path:
    runtime_dir = ROOT / "tests" / f".runtime_co_retrieval_{uuid.uuid4().hex}"
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
                frequency INTEGER DEFAULT 0,
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

        # Existing active co_retrieval edge to archive.
        conn.execute(
            """
            INSERT INTO edges (
                source_id, target_id, relation, strength, created_at, updated_at,
                base_strength, frequency, status, co_retrieval_count,
                co_retrieval_boost, generation_method
            ) VALUES (1, 2, 'co_retrieved', 0.5, datetime('now'), datetime('now'),
                      0.5, 3, 'active', 99, 0.5, 'co_retrieval')
            """
        )
        # Structural edge so hub query works.
        conn.executemany(
            """
            INSERT INTO edges (
                source_id, target_id, relation, strength, created_at, status, generation_method
            ) VALUES (?, ?, ?, ?, datetime('now'), 'active', ?)
            """,
            [
                (1, 3, "supports", 0.8, "semantic_auto"),
                (2, 3, "supports", 0.7, "semantic_auto"),
            ],
        )

        # Goldset sessions to exclude.
        for recall_id in ("g1", "g2"):
            conn.executemany(
                """
                INSERT INTO recall_log (query, node_id, rank, score, mode, timestamp, recall_id, sources)
                VALUES ('goldset query', ?, 1, 0.9, 'generic', '2026-04-08T00:00:00+00:00', ?, '[]')
                """,
                [("1", recall_id), ("2", recall_id)],
            )

        # Live recall_id sessions -> pair (1,3) count 3
        for recall_id in ("l1", "l2", "l3"):
            conn.executemany(
                """
                INSERT INTO recall_log (query, node_id, rank, score, mode, timestamp, recall_id, sources)
                VALUES ('live query', ?, 1, 0.9, 'generic', '2026-04-08T00:10:00+00:00', ?, '[]')
                """,
                [("1", recall_id), ("3", recall_id)],
            )

        # Legacy grouped by query+timestamp -> pair (2,3) count 2
        for _ in range(2):
            conn.executemany(
                """
                INSERT INTO recall_log (query, node_id, rank, score, mode, timestamp, recall_id, sources)
                VALUES ('legacy live', ?, 1, 0.9, 'generic', '2026-04-08T00:20:00+00:00', NULL, '[]')
                """,
                [("2",), ("3",)],
            )

        conn.commit()
    finally:
        conn.close()


def test_calculate_co_retrieval_excludes_goldset_and_archives_existing():
    runtime_dir = _make_runtime_dir()
    db_path = runtime_dir / "memory.db"
    _init_test_db(db_path)

    try:
        with ExitStack() as stack:
            stack.enter_context(patch("config.DB_PATH", db_path))
            stack.enter_context(patch("storage.sqlite_store.DB_PATH", db_path))
            stats = calculate_co_retrieval(
                min_co_count=2,
                hub_percentile=0,
                dry_run=False,
                exclude_queries={"goldset query"},
                archive_existing=True,
            )

        assert stats["excluded_queries"] == 1
        assert stats["archived_existing"] == 1
        assert stats["updated"] == 2

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            archived = conn.execute(
                """
                SELECT COUNT(*)
                FROM edges
                WHERE generation_method='co_retrieval' AND status='archived'
                """
            ).fetchone()[0]
            active_rows = conn.execute(
                """
                SELECT source_id, target_id, relation, strength, base_strength, frequency,
                       co_retrieval_count, co_retrieval_boost, generation_method, status
                FROM edges
                WHERE generation_method='co_retrieval' AND status='active'
                ORDER BY source_id, target_id
                """
            ).fetchall()
        finally:
            conn.close()

        assert archived == 1
        assert [(row["source_id"], row["target_id"], row["relation"]) for row in active_rows] == [
            (1, 3, "co_retrieved"),
            (2, 3, "co_retrieved"),
        ]
        assert active_rows[0]["co_retrieval_count"] == 3
        assert active_rows[0]["co_retrieval_boost"] == 0.2
        assert active_rows[0]["strength"] == 0.2
        assert active_rows[0]["base_strength"] == 0.2
        assert active_rows[0]["frequency"] == 0
        assert active_rows[0]["generation_method"] == "co_retrieval"
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)
