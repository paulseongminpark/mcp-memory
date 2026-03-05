"""hybrid.py BCM+UCB 테스트."""

import json
import math
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_tmp = tempfile.mkdtemp()
_test_db = Path(_tmp) / "test_hybrid.db"


def _create_test_db():
    """테스트용 DB 생성 — nodes + edges + action_log."""
    conn = sqlite3.connect(str(_test_db))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL DEFAULT 'Unclassified',
            content TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            project TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            layer INTEGER DEFAULT 2,
            tier INTEGER DEFAULT 2,
            status TEXT DEFAULT 'active',
            quality_score REAL DEFAULT 0.0,
            temporal_relevance REAL DEFAULT 0.0,
            theta_m REAL DEFAULT 0.5,
            activity_history TEXT DEFAULT '[]',
            visit_count INTEGER DEFAULT 0,
            last_activated TEXT,
            summary TEXT DEFAULT '',
            key_concepts TEXT DEFAULT '',
            facets TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER,
            target_id INTEGER,
            relation TEXT DEFAULT 'connects_with',
            strength REAL DEFAULT 0.5,
            frequency INTEGER DEFAULT 0,
            description TEXT DEFAULT '[]',
            last_activated TEXT
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
    """)

    # 테스트 노드 3개
    conn.execute("INSERT INTO nodes (id, type, content, layer, visit_count) VALUES (1, 'Insight', 'BCM test node A', 2, 5)")
    conn.execute("INSERT INTO nodes (id, type, content, layer, visit_count) VALUES (2, 'Pattern', 'BCM test node B', 2, 3)")
    conn.execute("INSERT INTO nodes (id, type, content, layer, visit_count) VALUES (3, 'Principle', 'BCM test node C', 3, 0)")

    # 테스트 edge 2개
    conn.execute("INSERT INTO edges (id, source_id, target_id, relation, strength, frequency, description) VALUES (1, 1, 2, 'supports', 0.5, 10, '[]')")
    conn.execute("INSERT INTO edges (id, source_id, target_id, relation, strength, frequency, description) VALUES (2, 2, 3, 'crystallized_into', 0.3, 5, '[]')")

    conn.commit()
    conn.close()


@pytest.fixture(autouse=True)
def setup_db():
    if _test_db.exists():
        _test_db.unlink()
    _create_test_db()
    with patch("config.DB_PATH", _test_db):
        yield
    if _test_db.exists():
        _test_db.unlink()


# ─── _auto_ucb_c 테스트 ──────────────────────────────────────────

def test_auto_ucb_c_focus_mode():
    from storage.hybrid import _auto_ucb_c, UCB_C_FOCUS
    assert _auto_ucb_c("any query", mode="focus") == UCB_C_FOCUS


def test_auto_ucb_c_dmn_mode():
    from storage.hybrid import _auto_ucb_c, UCB_C_DMN
    assert _auto_ucb_c("any query", mode="dmn") == UCB_C_DMN


def test_auto_ucb_c_long_query_auto():
    """5단어 이상 → focus."""
    from storage.hybrid import _auto_ucb_c, UCB_C_FOCUS
    assert _auto_ucb_c("this is a very long query about something") == UCB_C_FOCUS


def test_auto_ucb_c_short_query_auto():
    """2단어 이하 → dmn."""
    from storage.hybrid import _auto_ucb_c, UCB_C_DMN
    assert _auto_ucb_c("hello") == UCB_C_DMN


def test_auto_ucb_c_medium_query_auto():
    """3-4단어 → auto."""
    from storage.hybrid import _auto_ucb_c, UCB_C_AUTO
    assert _auto_ucb_c("medium length query") == UCB_C_AUTO


# ─── _bcm_update 테스트 ──────────────────────────────────────────

def test_bcm_update_frequency_changes():
    """BCM 업데이트 후 edge frequency 변화 확인."""
    from storage.hybrid import _bcm_update

    conn = sqlite3.connect(str(_test_db))
    old_freq = conn.execute("SELECT frequency FROM edges WHERE id=1").fetchone()[0]
    conn.close()

    all_edges = [
        {"id": 1, "source_id": 1, "target_id": 2, "relation": "supports",
         "strength": 0.5, "frequency": 10, "description": "[]"},
    ]
    _bcm_update([1, 2], [0.8, 0.6], all_edges, query="test query")

    conn = sqlite3.connect(str(_test_db))
    new_freq = conn.execute("SELECT frequency FROM edges WHERE id=1").fetchone()[0]
    conn.close()

    assert new_freq != old_freq  # frequency 변화 확인


def test_bcm_update_theta_m_changes():
    """BCM 업데이트 후 theta_m 갱신 확인."""
    from storage.hybrid import _bcm_update

    all_edges = [
        {"id": 1, "source_id": 1, "target_id": 2, "relation": "supports",
         "strength": 0.5, "frequency": 10, "description": "[]"},
    ]
    _bcm_update([1, 2], [0.9, 0.7], all_edges, query="theta test")

    conn = sqlite3.connect(str(_test_db))
    theta = conn.execute("SELECT theta_m FROM nodes WHERE id=1").fetchone()[0]
    conn.close()

    assert theta != 0.5  # 초기값에서 변화


def test_bcm_update_visit_count_incremented():
    """결과 노드의 visit_count +1 확인."""
    from storage.hybrid import _bcm_update

    _bcm_update([1, 2, 3], [0.8, 0.6, 0.4], [], query="")

    conn = sqlite3.connect(str(_test_db))
    vc1 = conn.execute("SELECT visit_count FROM nodes WHERE id=1").fetchone()[0]
    vc3 = conn.execute("SELECT visit_count FROM nodes WHERE id=3").fetchone()[0]
    conn.close()

    assert vc1 == 6  # 5 + 1
    assert vc3 == 1  # 0 + 1


def test_bcm_update_reconsolidation():
    """재공고화: edge.description에 query 맥락 추가."""
    from storage.hybrid import _bcm_update

    all_edges = [
        {"id": 1, "source_id": 1, "target_id": 2, "relation": "supports",
         "strength": 0.5, "frequency": 10, "description": "[]"},
    ]
    _bcm_update([1, 2], [0.8, 0.6], all_edges, query="reconsolidation test")

    conn = sqlite3.connect(str(_test_db))
    desc = conn.execute("SELECT description FROM edges WHERE id=1").fetchone()[0]
    conn.close()

    ctx_log = json.loads(desc)
    assert len(ctx_log) == 1
    assert ctx_log[0]["q"] == "reconsolidation test"


def test_bcm_update_empty_ids():
    """빈 result_ids → 아무 일도 안 함."""
    from storage.hybrid import _bcm_update
    _bcm_update([], [], [], query="")  # 예외 없음


def test_bcm_update_no_query_skips_reconsolidation():
    """query 없으면 재공고화 스킵."""
    from storage.hybrid import _bcm_update

    all_edges = [
        {"id": 1, "source_id": 1, "target_id": 2, "relation": "supports",
         "strength": 0.5, "frequency": 10, "description": "[]"},
    ]
    _bcm_update([1, 2], [0.8, 0.6], all_edges, query="")

    conn = sqlite3.connect(str(_test_db))
    desc = conn.execute("SELECT description FROM edges WHERE id=1").fetchone()[0]
    conn.close()

    assert desc == "[]"  # query 없으면 description 변경 없음


# ─── TTL 캐시 테스트 ──────────────────────────────────────────────

def test_get_graph_cache():
    """_get_graph() 캐시 히트 확인."""
    from storage import hybrid
    # 캐시 초기화
    hybrid._GRAPH_CACHE = None
    hybrid._GRAPH_CACHE_TS = 0.0

    with patch.object(sqlite3, "connect"):
        # build_graph 모킹
        mock_edges = [{"id": 1, "source_id": 1, "target_id": 2}]
        mock_graph = MagicMock()
        with patch("storage.hybrid.sqlite_store") as mock_store, \
             patch("storage.hybrid.build_graph", return_value=mock_graph):
            mock_store.get_all_edges.return_value = mock_edges

            result1 = hybrid._get_graph()
            result2 = hybrid._get_graph()

            # 두 번째 호출에서는 캐시 히트 — get_all_edges 1번만 호출
            assert mock_store.get_all_edges.call_count == 1
            assert result1 == result2


# ─── _ucb_traverse 테스트 ─────────────────────────────────────────

def test_ucb_traverse_basic():
    """UCB 탐색 기본 동작."""
    import networkx as nx
    from storage.hybrid import _ucb_traverse

    g = nx.DiGraph()
    g.add_node(1, visit_count=5)
    g.add_node(2, visit_count=3)
    g.add_node(3, visit_count=0)
    g.add_edge(1, 2, strength=0.8)
    g.add_edge(2, 3, strength=0.5)

    neighbors = _ucb_traverse(g, [1], depth=2, c=1.0)
    assert 2 in neighbors  # 1-hop 이웃
    assert 3 in neighbors  # 2-hop 이웃
    assert 1 not in neighbors  # seed 제외


def test_ucb_traverse_empty_seeds():
    """빈 seed → 빈 결과."""
    import networkx as nx
    from storage.hybrid import _ucb_traverse

    g = nx.DiGraph()
    result = _ucb_traverse(g, [], depth=2, c=1.0)
    assert result == set()


def test_ucb_traverse_dmn_prefers_unvisited():
    """DMN 모드(높은 c)는 visit_count=0 노드를 우선."""
    import networkx as nx
    from storage.hybrid import _ucb_traverse

    g = nx.DiGraph()
    g.add_node(1, visit_count=10)
    g.add_node(2, visit_count=100)  # 많이 방문한 노드
    g.add_node(3, visit_count=0)    # 미방문 노드
    g.add_edge(1, 2, strength=0.9)  # 강한 연결
    g.add_edge(1, 3, strength=0.1)  # 약한 연결

    # DMN (c=2.5): 미방문 보너스가 강한 연결을 이김
    neighbors = _ucb_traverse(g, [1], depth=1, c=2.5)
    assert 3 in neighbors  # 미방문 노드 포함


# ─── _log_recall_activations 테스트 ──────────────────────────────

def test_log_recall_activations():
    """활성화 로깅 — action_log에 기록 확인."""
    from storage.hybrid import _log_recall_activations

    results = [
        {"id": 1, "type": "Insight", "score": 0.85, "layer": 2},
        {"id": 2, "type": "Pattern", "score": 0.72, "layer": 2},
    ]
    _log_recall_activations(results, "test query", session_id="sess-test")

    conn = sqlite3.connect(str(_test_db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM action_log ORDER BY id").fetchall()
    conn.close()

    # 1 recall + 2 node_activated = 3
    assert len(rows) == 3
    assert rows[0]["action_type"] == "recall"
    assert rows[1]["action_type"] == "node_activated"
    assert rows[2]["action_type"] == "node_activated"
