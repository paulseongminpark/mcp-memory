from __future__ import annotations

from storage import sqlite_store


def test_get_node_hides_non_active_by_default(fresh_db):
    active_id = sqlite_store.insert_node(type="Observation", content="active node token")
    deleted_id = sqlite_store.insert_node(type="Observation", content="deleted node token")

    with sqlite_store._db() as conn:
        conn.execute("UPDATE nodes SET status = 'deleted' WHERE id = ?", (deleted_id,))
        conn.commit()

    assert sqlite_store.get_node(active_id)["id"] == active_id
    assert sqlite_store.get_node(deleted_id) is None
    assert sqlite_store.get_node(deleted_id, active_only=False)["id"] == deleted_id


def test_get_edges_and_get_all_edges_hide_deleted_by_default(fresh_db):
    left = sqlite_store.insert_node(type="Observation", content="left")
    right = sqlite_store.insert_node(type="Observation", content="right")
    active_edge = sqlite_store.insert_edge(left, right, "supports", description="[]")
    deleted_edge = sqlite_store.insert_edge(left, right, "connects_with", description="[]")

    with sqlite_store._db() as conn:
        conn.execute("UPDATE edges SET status = 'deleted' WHERE id = ?", (deleted_edge,))
        conn.commit()

    visible_edges = sqlite_store.get_edges(left)
    all_visible = sqlite_store.get_all_edges()

    assert {edge["id"] for edge in visible_edges} == {active_edge}
    assert {edge["id"] for edge in all_visible} == {active_edge}
    assert {edge["id"] for edge in sqlite_store.get_edges(left, active_only=False)} == {
        active_edge,
        deleted_edge,
    }


def test_get_edges_and_get_all_edges_hide_edges_touching_archived_nodes(fresh_db):
    left = sqlite_store.insert_node(type="Observation", content="left")
    right = sqlite_store.insert_node(type="Observation", content="right")
    stale_edge = sqlite_store.insert_edge(left, right, "supports", description="[]")

    with sqlite_store._db() as conn:
        conn.execute("UPDATE nodes SET status = 'archived' WHERE id = ?", (right,))
        conn.commit()

    assert sqlite_store.get_edges(left) == []
    assert sqlite_store.get_all_edges() == []
    assert {edge["id"] for edge in sqlite_store.get_edges(left, active_only=False)} == {
        stale_edge,
    }


def test_search_fts_excludes_deleted_nodes(fresh_db):
    active_id = sqlite_store.insert_node(type="Observation", content="uniquedeletedtoken active")
    deleted_id = sqlite_store.insert_node(type="Observation", content="uniquedeletedtoken deleted")

    with sqlite_store._db() as conn:
        conn.execute("UPDATE nodes SET status = 'deleted' WHERE id = ?", (deleted_id,))
        conn.execute("INSERT INTO nodes_fts(nodes_fts) VALUES ('rebuild')")
        conn.commit()

    result_ids = [node_id for node_id, _, _ in sqlite_store.search_fts("uniquedeletedtoken", top_k=10)]
    assert active_id in result_ids
    assert deleted_id not in result_ids
