#!/usr/bin/env python3
"""Shared active-graph health metrics for ops scripts."""

from __future__ import annotations

import sqlite3


ACTIVE_ORPHAN_SQL = """
WITH active_nodes AS (
    SELECT id FROM nodes WHERE status='active'
),
connected AS (
    SELECT source_id AS id
    FROM edges e
    JOIN active_nodes s ON s.id = e.source_id
    JOIN active_nodes t ON t.id = e.target_id
    WHERE e.status='active'
    UNION
    SELECT target_id AS id
    FROM edges e
    JOIN active_nodes s ON s.id = e.source_id
    JOIN active_nodes t ON t.id = e.target_id
    WHERE e.status='active'
)
SELECT COUNT(*)
FROM active_nodes a
LEFT JOIN connected c ON c.id = a.id
WHERE c.id IS NULL
"""


def get_active_orphan_count(conn: sqlite3.Connection) -> int:
    return conn.execute(ACTIVE_ORPHAN_SQL).fetchone()[0]


def get_health_snapshot(conn: sqlite3.Connection) -> dict[str, int]:
    snapshot: dict[str, int] = {}
    snapshot["active_nodes"] = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE status='active'"
    ).fetchone()[0]
    snapshot["archived_nodes"] = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE status='archived'"
    ).fetchone()[0]
    snapshot["active_edges"] = conn.execute(
        "SELECT COUNT(*) FROM edges WHERE status='active'"
    ).fetchone()[0]
    snapshot["active_active_edges"] = conn.execute(
        """
        SELECT COUNT(*)
        FROM edges e
        JOIN nodes s ON s.id = e.source_id
        JOIN nodes t ON t.id = e.target_id
        WHERE e.status='active'
          AND s.status='active'
          AND t.status='active'
        """
    ).fetchone()[0]
    snapshot["stale_active_edges"] = conn.execute(
        """
        SELECT COUNT(*)
        FROM edges e
        LEFT JOIN nodes s ON s.id = e.source_id
        LEFT JOIN nodes t ON t.id = e.target_id
        WHERE e.status='active'
          AND (
            COALESCE(s.status, 'missing') <> 'active'
            OR COALESCE(t.status, 'missing') <> 'active'
          )
        """
    ).fetchone()[0]
    snapshot["true_orphans"] = get_active_orphan_count(conn)
    snapshot["summary_present"] = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE status='active' AND summary IS NOT NULL AND trim(summary) != ''"
    ).fetchone()[0]
    snapshot["key_concepts_present"] = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE status='active' AND key_concepts IS NOT NULL AND trim(key_concepts) != ''"
    ).fetchone()[0]
    snapshot["retrieval_queries_present"] = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE status='active' AND retrieval_queries IS NOT NULL AND trim(retrieval_queries) != ''"
    ).fetchone()[0]
    snapshot["atomic_claims_present"] = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE status='active' AND atomic_claims IS NOT NULL AND trim(atomic_claims) != ''"
    ).fetchone()[0]
    snapshot["enriched_at_present"] = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE status='active' AND enriched_at IS NOT NULL AND trim(enriched_at) != ''"
    ).fetchone()[0]
    snapshot["stale_zero_visit_created_30d"] = conn.execute(
        """
        SELECT COUNT(*)
        FROM nodes
        WHERE status='active'
          AND (created_at IS NULL OR created_at <= datetime('now', '-30 day'))
          AND COALESCE(visit_count, 0) = 0
        """
    ).fetchone()[0]
    snapshot["stale_zero_visit_updated_30d"] = conn.execute(
        """
        SELECT COUNT(*)
        FROM nodes
        WHERE status='active'
          AND (updated_at IS NULL OR updated_at <= datetime('now', '-30 day'))
          AND COALESCE(visit_count, 0) = 0
        """
    ).fetchone()[0]
    snapshot["blank_edge_desc"] = conn.execute(
        """
        SELECT COUNT(*)
        FROM edges
        WHERE status='active'
          AND (description IS NULL OR trim(description) = '' OR description = '[]')
        """
    ).fetchone()[0]
    return snapshot
