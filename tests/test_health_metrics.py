import sqlite3

from scripts.health_metrics import get_active_orphan_count, get_health_snapshot


def _setup(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE nodes (
            id INTEGER PRIMARY KEY,
            status TEXT,
            summary TEXT,
            key_concepts TEXT,
            retrieval_queries TEXT,
            atomic_claims TEXT,
            enriched_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            visit_count INTEGER,
            tags TEXT,
            node_role TEXT
        );
        CREATE TABLE edges (
            id INTEGER PRIMARY KEY,
            source_id INTEGER,
            target_id INTEGER,
            relation TEXT,
            status TEXT,
            description TEXT
        );
        """
    )


def test_active_health_snapshot_ignores_archived_endpoints():
    conn = sqlite3.connect(":memory:")
    _setup(conn)
    conn.executemany(
        "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "active", "s", "[]", "[]", "[]", "2026-04-08", "2026-02-01", "2026-02-01", 0, "a", "knowledge_candidate"),
            (2, "active", "s", "[]", "[]", "[]", "2026-04-08", "2026-04-01", "2026-04-01", 1, "b", "knowledge_candidate"),
            (3, "archived", "s", "[]", "[]", "[]", "2026-04-08", "2026-02-01", "2026-02-01", 0, "c", "knowledge_candidate"),
            (4, "active", "s", "[]", "[]", "[]", "2026-04-08", "2026-02-01", "2026-04-08", 0, "d", "knowledge_candidate"),
        ],
    )
    conn.executemany(
        "INSERT INTO edges VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, 1, 2, "supports", "active", "[]"),
            (2, 1, 3, "supports", "active", "[]"),
        ],
    )

    snap = get_health_snapshot(conn)
    assert snap["active_nodes"] == 3
    assert snap["active_edges"] == 2
    assert snap["active_active_edges"] == 1
    assert snap["stale_active_edges"] == 1
    assert snap["true_orphans"] == 1
    assert snap["summary_present"] == 3
    assert snap["stale_zero_visit_created_30d"] == 2
    assert snap["stale_zero_visit_updated_30d"] == 1
    assert snap["blank_edge_desc"] == 2
    assert get_active_orphan_count(conn) == 1
