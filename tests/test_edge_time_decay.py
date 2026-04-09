"""Tests for Phase 6 Step 0: edge time decay."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.daily_enrich import _run_edge_time_decay


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE nodes (
            id INTEGER PRIMARY KEY,
            content TEXT,
            type TEXT DEFAULT 'observation',
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE edges (
            id INTEGER PRIMARY KEY,
            source_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            relation TEXT NOT NULL,
            strength REAL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            last_activated TEXT,
            status TEXT DEFAULT 'active',
            frequency INTEGER DEFAULT 0,
            decay_rate REAL DEFAULT 0.005
        )
    """)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO nodes (id, content, created_at) VALUES (1, 'A', ?)", (now,)
    )
    conn.execute(
        "INSERT INTO nodes (id, content, created_at) VALUES (2, 'B', ?)", (now,)
    )
    return conn


def _insert_edge(
    conn: sqlite3.Connection,
    edge_id: int,
    strength: float,
    days_ago: int,
    use_last_activated: bool = True,
) -> None:
    now = datetime.now(timezone.utc)
    created = (now - timedelta(days=days_ago + 10)).isoformat()
    last_act = (now - timedelta(days=days_ago)).isoformat() if use_last_activated else None
    conn.execute(
        "INSERT INTO edges (id, source_id, target_id, relation, strength, created_at, last_activated) "
        "VALUES (?, 1, 2, 'related_to', ?, ?, ?)",
        (edge_id, strength, created, last_act),
    )


class TestEdgeTimeDecay:
    def test_basic_decay(self):
        """30일 경과 edge의 strength가 감쇠된다."""
        conn = _make_db()
        _insert_edge(conn, 1, 1.0, days_ago=30)

        stats = _run_edge_time_decay(conn, dry_run=False)

        row = conn.execute("SELECT strength FROM edges WHERE id=1").fetchone()
        expected = 1.0 * (0.999 ** 30)  # ~0.9704
        assert abs(row["strength"] - expected) < 0.001
        assert stats["decayed"] == 1

    def test_floor_prevents_zero(self):
        """strength가 0.05 미만으로 떨어지지 않는다."""
        conn = _make_db()
        _insert_edge(conn, 1, 0.1, days_ago=3000)  # 0.1 * 0.999^3000 ≈ 0.005

        stats = _run_edge_time_decay(conn, dry_run=False)

        row = conn.execute("SELECT strength FROM edges WHERE id=1").fetchone()
        assert row["strength"] >= 0.05
        assert stats["skipped_floor"] >= 1

    def test_already_at_floor(self):
        """이미 floor 이하인 edge는 건드리지 않는다."""
        conn = _make_db()
        _insert_edge(conn, 1, 0.03, days_ago=100)

        stats = _run_edge_time_decay(conn, dry_run=False)

        row = conn.execute("SELECT strength FROM edges WHERE id=1").fetchone()
        assert row["strength"] == 0.03  # 변경 없음
        assert stats["skipped_floor"] >= 1
        assert stats["decayed"] == 0

    def test_null_last_activated_uses_created_at(self):
        """last_activated가 NULL이면 created_at 기준으로 감쇠."""
        conn = _make_db()
        _insert_edge(conn, 1, 1.0, days_ago=60, use_last_activated=False)

        stats = _run_edge_time_decay(conn, dry_run=False)

        row = conn.execute("SELECT strength FROM edges WHERE id=1").fetchone()
        # created_at은 days_ago + 10 = 70일 전
        expected = 1.0 * (0.999 ** 70)
        assert abs(row["strength"] - expected) < 0.001
        assert stats["decayed"] == 1

    def test_recent_edge_no_decay(self):
        """오늘 활성화된 edge는 감쇠 안 됨 (days=0)."""
        conn = _make_db()
        _insert_edge(conn, 1, 1.0, days_ago=0)

        stats = _run_edge_time_decay(conn, dry_run=False)

        row = conn.execute("SELECT strength FROM edges WHERE id=1").fetchone()
        assert row["strength"] == 1.0
        assert stats["decayed"] == 0

    def test_deleted_edges_skipped(self):
        """status='deleted' edge는 처리하지 않는다."""
        conn = _make_db()
        _insert_edge(conn, 1, 1.0, days_ago=30)
        conn.execute("UPDATE edges SET status='deleted' WHERE id=1")

        stats = _run_edge_time_decay(conn, dry_run=False)

        row = conn.execute("SELECT strength FROM edges WHERE id=1").fetchone()
        assert row["strength"] == 1.0  # 변경 없음
        assert stats["processed"] == 0

    def test_dry_run_no_modification(self):
        """dry_run=True이면 DB를 수정하지 않는다."""
        conn = _make_db()
        _insert_edge(conn, 1, 1.0, days_ago=30)

        stats = _run_edge_time_decay(conn, dry_run=True)

        row = conn.execute("SELECT strength FROM edges WHERE id=1").fetchone()
        assert row["strength"] == 1.0  # 변경 없음
        assert stats["decayed"] == 1  # 카운트는 올라감

    def test_multiple_edges(self):
        """여러 edge가 각각 올바르게 감쇠된다."""
        conn = _make_db()
        _insert_edge(conn, 1, 1.0, days_ago=10)
        _insert_edge(conn, 2, 0.5, days_ago=100)
        _insert_edge(conn, 3, 0.8, days_ago=0)  # 오늘

        stats = _run_edge_time_decay(conn, dry_run=False)

        r1 = conn.execute("SELECT strength FROM edges WHERE id=1").fetchone()
        r2 = conn.execute("SELECT strength FROM edges WHERE id=2").fetchone()
        r3 = conn.execute("SELECT strength FROM edges WHERE id=3").fetchone()

        assert abs(r1["strength"] - 1.0 * (0.999 ** 10)) < 0.001
        assert abs(r2["strength"] - 0.5 * (0.999 ** 100)) < 0.001
        assert r3["strength"] == 0.8  # 오늘이라 변경 없음
        assert stats["decayed"] == 2
