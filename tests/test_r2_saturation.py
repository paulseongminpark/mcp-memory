from __future__ import annotations

import sqlite3

from config import DB_PATH


def _scalar(query: str) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(query).fetchone()[0]


def test_node_role_fill_rate_above_80():
    total = _scalar("SELECT COUNT(*) FROM nodes WHERE status='active'")
    blank = _scalar(
        "SELECT COUNT(*) FROM nodes WHERE status='active' AND (node_role IS NULL OR node_role='')"
    )
    assert total > 0
    assert blank / total < 0.20


def test_generation_method_fill_rate_above_85():
    total = _scalar("SELECT COUNT(*) FROM edges WHERE status='active'")
    blank = _scalar(
        "SELECT COUNT(*) FROM edges WHERE status='active' AND (generation_method IS NULL OR generation_method='')"
    )
    assert total > 0
    assert blank / total < 0.15


def test_external_noise_preserved():
    count = _scalar(
        "SELECT COUNT(*) FROM nodes WHERE status='active' AND node_role='external_noise'"
    )
    assert count == 37


def test_knowledge_core_preserved():
    count = _scalar(
        "SELECT COUNT(*) FROM nodes WHERE status='active' AND node_role='knowledge_core'"
    )
    assert count >= 8


def test_session_anchor_edges_preserved():
    count = _scalar(
        "SELECT COUNT(*) FROM edges WHERE status='active' AND generation_method='session_anchor'"
    )
    assert count >= 1307


def test_no_blank_co_retrieved():
    count = _scalar(
        """SELECT COUNT(*)
           FROM edges
           WHERE status='active'
             AND relation='co_retrieved'
             AND (generation_method IS NULL OR generation_method='')"""
    )
    assert count == 0


def test_narrative_is_session_anchor():
    count = _scalar(
        """SELECT COUNT(*)
           FROM nodes
           WHERE status='active'
             AND type='Narrative'
             AND COALESCE(node_role, '') NOT IN ('session_anchor', 'external_noise')"""
    )
    assert count == 0
