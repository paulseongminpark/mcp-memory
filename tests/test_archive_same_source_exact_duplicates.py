from __future__ import annotations

import sqlite3

from scripts.archive_same_source_exact_duplicates import collect_groups, apply_archive


def _setup(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE nodes (
            id INTEGER PRIMARY KEY,
            source TEXT,
            type TEXT,
            content TEXT,
            visit_count INTEGER,
            quality_score REAL,
            status TEXT,
            updated_at TEXT
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO nodes (id, source, type, content, visit_count, quality_score, status, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'active', '')
        """,
        [
            (1, "obsidian:README.md#x", "Principle", "same text", 1, 0.8),
            (2, "obsidian:README.md#x", "Principle", "same text", 5, 0.8),
            (3, "obsidian:README.md#x", "Tool", "same text", 0, 0.9),
            (4, "obsidian:OTHER.md#x", "Principle", "same text", 0, 0.7),
            (5, "obsidian:OTHER.md#x", "Principle", "other text", 0, 0.7),
        ],
    )
    conn.commit()


def test_archive_same_source_exact_duplicates_keeps_best_candidate():
    conn = sqlite3.connect(":memory:")
    try:
        _setup(conn)
        before = collect_groups(conn)

        assert before["group_count"] == 1
        assert before["archive_count"] == 2
        assert set(before["archive_ids"]) == {1, 3}

        applied = apply_archive(conn, before["archive_ids"])
        assert applied["archived_nodes"] == 2

        rows = [tuple(row) for row in conn.execute("SELECT id, status FROM nodes ORDER BY id").fetchall()]
        assert rows == [
            (1, "archived"),
            (2, "active"),
            (3, "archived"),
            (4, "active"),
            (5, "active"),
        ]
    finally:
        conn.close()
