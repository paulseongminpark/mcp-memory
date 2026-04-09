import sqlite3

from scripts.archive_stale_orphan_control_docs import collect


def test_collect_only_stale_orphan_control_docs():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE nodes (
            id INTEGER PRIMARY KEY,
            status TEXT,
            source TEXT,
            type TEXT,
            project TEXT,
            visit_count INTEGER,
            created_at TEXT,
            content TEXT,
            updated_at TEXT
        );
        CREATE TABLE edges (
            id INTEGER PRIMARY KEY,
            source_id INTEGER,
            target_id INTEGER,
            status TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO nodes (id, status, source, type, project, visit_count, created_at, content, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "active", r"obsidian:.agents\skills\diff-only\SKILL.md#abc", "Tool", "orchestration", 0, "2026-02-01", "old skill", "2026-02-01"),
            (2, "active", r"obsidian:.agents\skills\review-checklist\SKILL.md#abc", "Tool", "orchestration", 1, "2026-02-01", "visited skill", "2026-02-01"),
            (3, "active", r"obsidian:README.md#abc", "Tool", "orchestration", 0, "2026-02-01", "not control", "2026-02-01"),
            (4, "active", r"obsidian:.claude\rules\claude.md#abc", "Tool", "orchestration", 0, "2026-04-07", "too new", "2026-04-07"),
            (5, "active", r"obsidian:.rulesync\rules\gemini.md#abc", "Tool", "orchestration", 0, "2026-02-01", "connected", "2026-02-01"),
        ],
    )
    conn.execute("INSERT INTO edges (id, source_id, target_id, status) VALUES (1, 5, 3, 'active')")

    rows = collect(conn)
    assert [row["id"] for row in rows] == [1]
