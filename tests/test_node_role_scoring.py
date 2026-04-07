from __future__ import annotations

from storage import hybrid, sqlite_store


def test_node_role_penalty_pushes_work_item_down(fresh_db, monkeypatch):
    work_item = sqlite_store.insert_node(
        type="Decision",
        content="short work item",
        layer=1,
        node_role="work_item",
    )
    knowledge = sqlite_store.insert_node(
        type="Decision",
        content="durable knowledge candidate",
        layer=1,
        node_role="knowledge_candidate",
    )

    monkeypatch.setattr(
        hybrid.vector_store,
        "search",
        lambda *args, **kwargs: [(work_item, 0.01, {}), (knowledge, 0.02, {})],
    )
    monkeypatch.setattr(
        hybrid.sqlite_store,
        "search_fts",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(hybrid, "_traverse_sql", lambda *args, **kwargs: set())
    monkeypatch.setattr(hybrid, "_apply_type_diversity", lambda candidates, top_k: candidates[:top_k])

    results = hybrid.hybrid_search("decision regression query", top_k=2, mode="focus")

    assert [node["id"] for node in results[:2]] == [knowledge, work_item]
