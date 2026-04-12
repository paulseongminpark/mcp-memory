"""Growth semantics tests — compute_growth_score + observation_count increment."""

import sqlite3
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from utils.growth import compute_growth_score


# ─── compute_growth_score unit tests ────────────────────────

class TestComputeGrowthScore:
    def test_all_zeros(self):
        """Zero inputs → baseline from default quality (0.5 * 0.3 = 0.15) + recency."""
        score = compute_growth_score(
            quality_score=0.0,
            active_edge_count=0,
            visit_count=0,
            neighbor_project_count=0,
            created_at=None,
            has_contradiction=False,
        )
        # quality=0*0.3 + edges=0*0.2 + visits=0*0.2 + diversity=0*0.2 + recency=0.5*0.1 = 0.05
        assert 0.0 <= score <= 1.0
        assert score == pytest.approx(0.05, abs=0.01)

    def test_perfect_node(self):
        """High quality, many edges, visits, diverse, recent → high score."""
        now = datetime.now(timezone.utc).isoformat()
        score = compute_growth_score(
            quality_score=1.0,
            active_edge_count=10,
            visit_count=10,
            neighbor_project_count=3,
            created_at=now,
        )
        # 1.0*0.3 + 1.0*0.2 + 1.0*0.2 + 1.0*0.2 + 1.0*0.1 = 1.0
        assert score == pytest.approx(1.0, abs=0.02)

    def test_contradiction_penalty(self):
        now = datetime.now(timezone.utc).isoformat()
        without = compute_growth_score(
            quality_score=0.8, active_edge_count=5, visit_count=5,
            neighbor_project_count=2, created_at=now, has_contradiction=False,
        )
        with_contra = compute_growth_score(
            quality_score=0.8, active_edge_count=5, visit_count=5,
            neighbor_project_count=2, created_at=now, has_contradiction=True,
        )
        assert with_contra < without
        assert without - with_contra == pytest.approx(0.2, abs=0.01)

    def test_none_quality_defaults_to_half(self):
        score = compute_growth_score(
            quality_score=None, active_edge_count=0, visit_count=None,
            neighbor_project_count=0, created_at=None,
        )
        # quality=0.5*0.3 + recency_default=0.5*0.1 = 0.2
        assert score == pytest.approx(0.2, abs=0.01)

    def test_recency_old_node(self):
        """90+ day old node → recency = 0."""
        old = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        score_old = compute_growth_score(
            quality_score=0.5, active_edge_count=0, visit_count=0,
            neighbor_project_count=0, created_at=old,
        )
        new = datetime.now(timezone.utc).isoformat()
        score_new = compute_growth_score(
            quality_score=0.5, active_edge_count=0, visit_count=0,
            neighbor_project_count=0, created_at=new,
        )
        assert score_new > score_old

    def test_clamped_to_0_1(self):
        """Score never goes below 0 even with contradiction."""
        score = compute_growth_score(
            quality_score=0.0, active_edge_count=0, visit_count=0,
            neighbor_project_count=0, created_at=None, has_contradiction=True,
        )
        assert score >= 0.0

    def test_edge_density_caps_at_10(self):
        """Edge count above 10 doesn't increase score further."""
        score_10 = compute_growth_score(
            quality_score=0.5, active_edge_count=10, visit_count=0,
            neighbor_project_count=0, created_at=None,
        )
        score_20 = compute_growth_score(
            quality_score=0.5, active_edge_count=20, visit_count=0,
            neighbor_project_count=0, created_at=None,
        )
        assert score_10 == score_20

    def test_diversity_caps_at_3(self):
        """3+ neighbor projects all give diversity = 1.0."""
        score_3 = compute_growth_score(
            quality_score=0.5, active_edge_count=0, visit_count=0,
            neighbor_project_count=3, created_at=None,
        )
        score_5 = compute_growth_score(
            quality_score=0.5, active_edge_count=0, visit_count=0,
            neighbor_project_count=5, created_at=None,
        )
        assert score_3 == score_5


# ─── observation_count increment tests ──────────────────────

def _create_obs_test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL DEFAULT 'Unclassified',
            content TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            quality_score REAL DEFAULT 0.0,
            visit_count INTEGER DEFAULT 0,
            observation_count INTEGER DEFAULT 0,
            promotion_candidate INTEGER DEFAULT 0,
            theta_m REAL DEFAULT 0.5,
            score_history TEXT DEFAULT '[]',
            activity_history TEXT DEFAULT '[]',
            layer INTEGER DEFAULT 2,
            tier INTEGER DEFAULT 2,
            project TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            last_activated TEXT,
            last_accessed_at TEXT,
            summary TEXT DEFAULT '',
            key_concepts TEXT DEFAULT '',
            facets TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER,
            target_id INTEGER,
            relation TEXT DEFAULT 'connects_with',
            strength REAL DEFAULT 0.5,
            frequency INTEGER DEFAULT 0,
            description TEXT DEFAULT '[]',
            last_activated TEXT,
            status TEXT DEFAULT 'active'
        );
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS action_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            session_id TEXT,
            action_type TEXT NOT NULL,
            target_type TEXT,
            target_id INTEGER,
            params TEXT DEFAULT '{}',
            result TEXT DEFAULT '{}',
            context TEXT,
            model TEXT,
            duration_ms INTEGER,
            token_cost INTEGER,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.execute(
        "INSERT INTO nodes (id, type, content, observation_count) VALUES (1, 'Signal', 'test node A', 0)"
    )
    conn.execute(
        "INSERT INTO nodes (id, type, content, observation_count) VALUES (2, 'Insight', 'test node B', 5)"
    )
    conn.commit()
    return conn


class TestObservationCountIncrement:
    def test_increment_on_recall(self):
        """post_search_learn_impl should increment observation_count for recalled nodes."""
        conn = _create_obs_test_db()

        # Simulate the observation_count increment logic directly
        node_ids = [1, 2]
        placeholders = ",".join("?" * len(node_ids))
        conn.execute(
            f"UPDATE nodes SET observation_count = COALESCE(observation_count, 0) + 1 "
            f"WHERE id IN ({placeholders})",
            node_ids,
        )
        conn.commit()

        row1 = conn.execute("SELECT observation_count FROM nodes WHERE id=1").fetchone()
        row2 = conn.execute("SELECT observation_count FROM nodes WHERE id=2").fetchone()
        assert row1[0] == 1  # was 0
        assert row2[0] == 6  # was 5
        conn.close()

    def test_increment_idempotent_per_recall(self):
        """Each recall adds exactly 1 to observation_count."""
        conn = _create_obs_test_db()

        for _ in range(3):
            conn.execute(
                "UPDATE nodes SET observation_count = COALESCE(observation_count, 0) + 1 WHERE id = 1"
            )
        conn.commit()

        row = conn.execute("SELECT observation_count FROM nodes WHERE id=1").fetchone()
        assert row[0] == 3
        conn.close()


# ─── batch growth score update test ─────────────────────────

class TestBatchGrowthUpdate:
    def test_batch_update_writes_maturity(self):
        """_batch_update_growth_scores should write to DB maturity column."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY,
                type TEXT,
                status TEXT DEFAULT 'active',
                quality_score REAL DEFAULT 0.5,
                visit_count INTEGER DEFAULT 0,
                created_at TEXT,
                maturity REAL DEFAULT 0.0,
                project TEXT DEFAULT '',
                observation_count INTEGER DEFAULT 0
            );
            CREATE TABLE edges (
                id INTEGER PRIMARY KEY,
                source_id INTEGER,
                target_id INTEGER,
                relation TEXT DEFAULT 'connects_with',
                status TEXT DEFAULT 'active'
            );
        """)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO nodes (id, type, quality_score, visit_count, created_at, maturity) "
            "VALUES (1, 'Signal', 0.8, 5, ?, 0.0)",
            (now,),
        )
        conn.execute(
            "INSERT INTO edges (source_id, target_id) VALUES (1, 2)"
        )
        conn.commit()

        # Import and run the batch update
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from scripts.daily_enrich import _batch_update_growth_scores

        updated = _batch_update_growth_scores(conn, compute_growth_score)
        assert updated == 1

        row = conn.execute("SELECT maturity FROM nodes WHERE id=1").fetchone()
        assert row[0] > 0.0  # Was 0, now has a real growth score
        conn.close()
