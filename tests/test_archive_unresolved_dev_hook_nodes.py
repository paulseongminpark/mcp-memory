from __future__ import annotations

import sqlite3

from scripts.archive_unresolved_dev_hook_nodes import apply_archive, collect_candidates


def test_archive_unresolved_dev_hook_nodes_only_archives_active_dev_hook_rows(fresh_db):
    conn = sqlite3.connect(str(fresh_db))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO nodes (
                type, content, metadata, project, tags, confidence, source, status,
                created_at, updated_at, source_kind, node_role
            ) VALUES (
                'Observation', 'dev hook', '{}', 'dev', '', 1.0, 'hook:test', 'active',
                datetime('now'), datetime('now'), 'hook', 'work_item'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO nodes (
                type, content, metadata, project, tags, confidence, source, status,
                created_at, updated_at, source_kind, node_role
            ) VALUES (
                'Observation', 'normal hook', '{}', 'orchestration', '', 1.0, 'hook:test', 'active',
                datetime('now'), datetime('now'), 'hook', 'work_item'
            )
            """
        )
        conn.commit()

        candidates = collect_candidates(conn)
        assert candidates["candidate_count"] == 1

        applied = apply_archive(conn, candidates["ids"])
        assert applied["archived_nodes"] == 1

        statuses = conn.execute(
            "SELECT project, status FROM nodes WHERE source='hook:test' ORDER BY id"
        ).fetchall()
        assert statuses == [("dev", "archived"), ("orchestration", "active")]
    finally:
        conn.close()
