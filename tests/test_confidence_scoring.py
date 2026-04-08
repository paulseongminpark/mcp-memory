from __future__ import annotations
import pytest

from storage import hybrid, sqlite_store


@pytest.mark.skip(reason="WS-1.1: confidence_bonus 제거됨. maturity level 2 도달 시 재활성.")
def test_confidence_bonus_reorders_candidates(fresh_db, monkeypatch):
    low_conf = sqlite_store.insert_node(
        type="Insight",
        content="confidence low",
        confidence=0.1,
        layer=2,
    )
    high_conf = sqlite_store.insert_node(
        type="Insight",
        content="confidence high",
        confidence=1.0,
        layer=2,
    )

    monkeypatch.setattr(
        hybrid.vector_store,
        "search",
        lambda *args, **kwargs: [(low_conf, 0.01, {}), (high_conf, 0.02, {})],
    )
    monkeypatch.setattr(
        hybrid.sqlite_store,
        "search_fts",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(hybrid, "_traverse_sql", lambda *args, **kwargs: set())
    monkeypatch.setattr(hybrid, "_apply_type_diversity", lambda candidates, top_k: candidates[:top_k])

    results = hybrid.hybrid_search("confidence regression query", top_k=2, mode="focus")

    assert [node["id"] for node in results[:2]] == [high_conf, low_conf]
