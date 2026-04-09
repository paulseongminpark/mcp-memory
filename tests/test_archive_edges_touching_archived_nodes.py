from __future__ import annotations

import sqlite3

from scripts.archive_edges_touching_archived_nodes import apply_archive, collect_stats
from storage import sqlite_store


def test_apply_archive_removes_edges_touching_archived_nodes(fresh_db):
    left = sqlite_store.insert_node(type="Observation", content="left")
    right = sqlite_store.insert_node(type="Observation", content="right")
    third = sqlite_store.insert_node(type="Observation", content="third")

    stale_edge = sqlite_store.insert_edge(left, right, "supports", description="[]")
    live_edge = sqlite_store.insert_edge(left, third, "supports", description="[]")

    conn = sqlite3.connect(str(fresh_db))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("UPDATE nodes SET status='archived' WHERE id=?", (right,))
        conn.commit()

        before = collect_stats(conn)
        assert before["stale_edge_count"] == 1

        applied = apply_archive(conn)
        assert applied["archived_edges"] == 1

        stale_status = conn.execute("SELECT status FROM edges WHERE id=?", (stale_edge,)).fetchone()[0]
        live_status = conn.execute("SELECT status FROM edges WHERE id=?", (live_edge,)).fetchone()[0]
        assert stale_status == "archived"
        assert live_status == "active"
    finally:
        conn.close()
