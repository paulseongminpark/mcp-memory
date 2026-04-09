from __future__ import annotations

import config
from storage import hybrid, sqlite_store


def _node(
    node_id: int,
    content: str,
    *,
    type_: str = "Principle",
    source: str = "obsidian:test.md#chunk",
    project: str = "orchestration",
    layer: int = 3,
    quality: float = 0.9,
    confidence: float = 1.0,
) -> dict:
    return {
        "id": node_id,
        "type": type_,
        "content": content,
        "source": source,
        "project": project,
        "layer": layer,
        "quality_score": quality,
        "confidence": confidence,
        "node_role": "knowledge_candidate",
        "last_accessed_at": "2026-04-08T00:00:00+00:00",
        "updated_at": "2026-04-08T00:00:00+00:00",
        "promotion_candidate": 0,
    }


def test_hybrid_auto_skips_graph_when_vector_channel_unavailable(monkeypatch):
    nodes = {1: _node(1, "AI는 도구가 아니라 팀원이다")}

    monkeypatch.setattr(
        hybrid.vector_store,
        "search",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("embed offline")),
    )
    monkeypatch.setattr(
        sqlite_store,
        "search_fts",
        lambda *args, **kwargs: [(1, "AI는 도구가 아니라 팀원이다", -10.0)],
    )
    monkeypatch.setattr(sqlite_store, "get_node", lambda node_id, active_only=True: nodes.get(node_id))
    monkeypatch.setattr(config, "get_maturity_level", lambda: 3)
    monkeypatch.setattr(hybrid, "_apply_type_diversity", lambda candidates, top_k: candidates[:top_k])
    monkeypatch.setattr(
        hybrid, "_traverse_sql",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("graph should be skipped")),
    )
    monkeypatch.setattr(
        hybrid, "_get_graph",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("graph should be skipped")),
    )

    results = hybrid.hybrid_search("AI는 도구가 아니라 팀원이다", top_k=5, mode="auto")

    assert [node["id"] for node in results] == [1]


def test_hybrid_dedupes_exact_duplicate_content_candidates(monkeypatch):
    nodes = {
        1: _node(1, "동일한 내용의 중복 노드", quality=0.9),
        2: _node(2, "동일한 내용의 중복 노드", quality=0.85),
    }

    monkeypatch.setattr(hybrid.vector_store, "search", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        sqlite_store,
        "search_fts",
        lambda *args, **kwargs: [
            (1, "동일한 내용의 중복 노드", -10.0),
            (2, "동일한 내용의 중복 노드", -9.0),
        ],
    )
    monkeypatch.setattr(sqlite_store, "get_node", lambda node_id, active_only=True: nodes.get(node_id))
    monkeypatch.setattr(config, "get_maturity_level", lambda: 3)
    monkeypatch.setattr(hybrid, "_apply_type_diversity", lambda candidates, top_k: candidates[:top_k])

    results = hybrid.hybrid_search("중복 노드", top_k=5, mode="auto")

    assert [node["id"] for node in results] == [1]


def test_hybrid_quality_and_confidence_bonus_break_tie(monkeypatch):
    nodes = {
        1: _node(1, "상위 후보지만 품질이 낮다", quality=0.6, confidence=0.6),
        2: _node(2, "랭크는 밀리지만 품질이 높다", quality=0.95, confidence=1.0),
    }

    monkeypatch.setattr(hybrid.vector_store, "search", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        sqlite_store,
        "search_fts",
        lambda *args, **kwargs: [
            (1, "상위 후보지만 품질이 낮다", -10.0),
            (2, "랭크는 밀리지만 품질이 높다", -9.9),
        ],
    )
    monkeypatch.setattr(sqlite_store, "get_node", lambda node_id, active_only=True: nodes.get(node_id))
    monkeypatch.setattr(config, "get_maturity_level", lambda: 3)
    monkeypatch.setattr(hybrid, "_apply_type_diversity", lambda candidates, top_k: candidates[:top_k])

    results = hybrid.hybrid_search("품질 회귀 테스트", top_k=2, mode="auto")

    assert [node["id"] for node in results[:2]] == [2, 1]


def test_hybrid_exact_query_bonus_beats_generic_control_doc(monkeypatch):
    nodes = {
        1: _node(
            1,
            "## 핵심 원칙\n1. STATE.md가 유일한 진실이다",
            source="obsidian:README.md#chunk",
            quality=0.92,
        ),
        2: _node(
            2,
            "## 1. 단일 진실 소스 (Single Source of Truth)\n문제: STATE.md가 유일한 진실이다",
            source="obsidian:01_projects\\01_orchestration\\_history\\archive\\docs\\philosophy.md#chunk",
            quality=0.92,
        ),
    }

    monkeypatch.setattr(hybrid.vector_store, "search", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        sqlite_store,
        "search_fts",
        lambda *args, **kwargs: [
            (1, nodes[1]["content"], -10.0),
            (2, nodes[2]["content"], -9.9),
        ],
    )
    monkeypatch.setattr(sqlite_store, "get_node", lambda node_id, active_only=True: nodes.get(node_id))
    monkeypatch.setattr(config, "get_maturity_level", lambda: 3)
    monkeypatch.setattr(hybrid, "_apply_type_diversity", lambda candidates, top_k: candidates[:top_k])

    results = hybrid.hybrid_search("STATE.md가 유일한 진실이다", top_k=2, mode="auto")

    assert [node["id"] for node in results[:2]] == [2, 1]
