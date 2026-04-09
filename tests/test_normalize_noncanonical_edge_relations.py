from __future__ import annotations

import sqlite3

from scripts.normalize_noncanonical_edge_relations import apply_updates, collect_candidates
from storage import sqlite_store


def test_normalize_noncanonical_edge_relations_maps_realizes_and_aliases(fresh_db):
    source = sqlite_store.insert_node(type="Signal", content="signal", layer=1)
    target = sqlite_store.insert_node(type="Observation", content="obs", layer=0)

    conn = sqlite3.connect(str(fresh_db))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO edges (source_id, target_id, relation, description, strength, created_at, status, generation_method)
            VALUES (?, ?, 'realizes', '[]', 1.0, datetime('now'), 'active', 'rule')
            """,
            (source, target),
        )
        conn.execute(
            """
            INSERT INTO edges (source_id, target_id, relation, description, strength, created_at, status, generation_method)
            VALUES (?, ?, 'co_occurs', '[]', 1.0, datetime('now'), 'active', 'fallback')
            """,
            (source, target),
        )
        conn.commit()

        before = collect_candidates(conn)
        assert before["candidate_count"] == 2

        applied = apply_updates(conn, before["candidates"])
        assert applied["updated_edges"] == 2

        relations = {
            row[0]
            for row in conn.execute("SELECT relation FROM edges").fetchall()
        }
        assert "realizes" not in relations
        assert "co_occurs" not in relations
        assert "expressed_as" in relations
        assert "connects_with" in relations
    finally:
        conn.close()
