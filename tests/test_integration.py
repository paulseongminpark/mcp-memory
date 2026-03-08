"""End-to-end and server wrapper integration tests."""

from __future__ import annotations

import importlib
import shutil
import sqlite3
import sys
import uuid
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from storage import sqlite_store


def _make_runtime_dir(prefix: str) -> Path:
    runtime_dir = ROOT / "tests" / f".runtime_{prefix}_{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _import_server():
    return importlib.import_module("server")


def _query_scalar(db_path: Path, sql: str, params: tuple = ()) -> object:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _query_rows(db_path: Path, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _ensure_test_schema(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"
        )
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(nodes)").fetchall()
        }
        if "last_activated" not in columns:
            conn.execute("ALTER TABLE nodes ADD COLUMN last_activated TEXT")
        conn.commit()
    finally:
        conn.close()


def _memory_stack(
    server_module,
    *,
    swr: tuple[bool, float] | None = None,
    bayesian: float | None = None,
    mdl: tuple[bool, str] | None = None,
):
    stack = ExitStack()
    stack.enter_context(patch.object(server_module, "validate_node_type", return_value=(True, None)))
    stack.enter_context(patch("tools.remember.validate_node_type", return_value=(True, None)))
    stack.enter_context(patch("storage.vector_store.add", return_value=None))
    stack.enter_context(patch("storage.vector_store.search", return_value=[]))
    if swr is not None:
        stack.enter_context(patch("tools.promote_node.swr_readiness", return_value=swr))
    if bayesian is not None:
        stack.enter_context(patch("tools.promote_node.promotion_probability", return_value=bayesian))
    if mdl is not None:
        stack.enter_context(patch("tools.promote_node._mdl_gate", return_value=mdl))
    return stack


@pytest.fixture()
def db_env():
    runtime_dir = _make_runtime_dir("integration")
    db_path = runtime_dir / "memory.db"

    with ExitStack() as stack:
        stack.enter_context(patch("config.DB_PATH", db_path))
        stack.enter_context(patch("storage.sqlite_store.DB_PATH", db_path))
        stack.enter_context(patch("storage.action_log.sqlite_store.DB_PATH", db_path))
        stack.enter_context(patch("utils.access_control.DB_PATH", db_path))
        sqlite_store.init_db()
        _ensure_test_schema(db_path)

        from storage import hybrid

        hybrid._GRAPH_CACHE = None
        hybrid._GRAPH_CACHE_TS = 0.0
        yield db_path
        hybrid._GRAPH_CACHE = None
        hybrid._GRAPH_CACHE_TS = 0.0

    shutil.rmtree(runtime_dir, ignore_errors=True)


def test_e2e_init_remember_recall_promote_flow(db_env: Path):
    server = _import_server()

    with _memory_stack(server, swr=(True, 0.91), bayesian=0.94):
        stored = server.remember(
            content="alpha beta gamma memory",
            type="Observation",
            actor="system",
        )
        recalled = server.recall(query="alpha", top_k=5)
        promoted = server.promote_node(
            node_id=stored["node_id"],
            target_type="Signal",
            reason="e2e promotion",
            actor="system",
        )

    row = _query_rows(
        db_env,
        "SELECT type, layer FROM nodes WHERE id = ?",
        (stored["node_id"],),
    )[0]
    action_types = {
        row["action_type"]
        for row in _query_rows(db_env, "SELECT action_type FROM action_log")
    }

    assert stored["node_id"] is not None
    assert recalled["count"] == 1
    assert recalled["results"][0]["id"] == stored["node_id"]
    assert promoted["new_type"] == "Signal"
    assert row["type"] == "Signal"
    assert row["layer"] == 1
    assert {"node_created", "recall", "node_activated", "node_promoted"}.issubset(action_types)


def test_e2e_same_content_remember_is_deduplicated(db_env: Path):
    server = _import_server()

    with _memory_stack(server):
        first = server.remember(content="duplicate memory", type="Observation", actor="system")
        second = server.remember(content="duplicate memory", type="Observation", actor="system")

    node_count = _query_scalar(db_env, "SELECT COUNT(*) FROM nodes")

    assert first["node_id"] == second["node_id"]
    assert second["status"] == "duplicate"
    assert node_count == 1


def test_e2e_recall_returns_matching_node(db_env: Path):
    server = _import_server()

    with _memory_stack(server):
        alpha = server.remember(content="alpha specific content", type="Observation", actor="system")
        server.remember(content="unrelated delta content", type="Observation", actor="system")
        recalled = server.recall(query="alpha", top_k=5)

    assert recalled["count"] == 1
    assert recalled["results"][0]["id"] == alpha["node_id"]
    assert "alpha specific content" in recalled["results"][0]["content"]


def test_server_promote_node_check_access_blocks_system_on_layer4_node(db_env: Path):
    server = _import_server()
    node_id = sqlite_store.insert_node(
        type="Principle",
        content="protected node",
        metadata={},
        layer=4,
        tier=2,
    )

    with patch.object(server, "_promote_node", return_value={"ok": True}) as mock_promote:
        result = server.promote_node(
            node_id=node_id,
            target_type="Belief",
            reason="blocked by access control",
            actor="system",
        )

    assert "error" in result
    assert "check_access denied" in result["message"]
    mock_promote.assert_not_called()


def test_server_promote_node_check_access_allows_paul_on_layer4_node(db_env: Path):
    server = _import_server()
    node_id = sqlite_store.insert_node(
        type="Principle",
        content="protected node for paul",
        metadata={},
        layer=4,
        tier=2,
    )

    with patch.object(server, "_promote_node", return_value={"node_id": node_id, "ok": True}) as mock_promote:
        result = server.promote_node(
            node_id=node_id,
            target_type="Belief",
            reason="paul is allowed",
            actor="paul",
        )

    assert result == {"node_id": node_id, "ok": True}
    mock_promote.assert_called_once_with(
        node_id=node_id,
        target_type="Belief",
        reason="paul is allowed",
        related_ids=None,
        skip_gates=False,
    )


def test_server_recall_clamps_top_k_to_50(db_env: Path):
    server = _import_server()

    with patch.object(server, "_recall", return_value={"results": [], "count": 0, "message": "No memories found."}) as mock_recall:
        result = server.recall(query="alpha", top_k=999)

    assert result["count"] == 0
    mock_recall.assert_called_once_with(
        query="alpha",
        type_filter="",
        project="",
        top_k=50,
        mode="auto",
    )


def test_server_recall_preserves_small_top_k(db_env: Path):
    server = _import_server()

    with patch.object(server, "_recall", return_value={"results": [], "count": 0, "message": "No memories found."}) as mock_recall:
        server.recall(query="alpha", top_k=3)

    mock_recall.assert_called_once_with(
        query="alpha",
        type_filter="",
        project="",
        top_k=3,
        mode="auto",
    )


def test_e2e_promote_with_related_ids_creates_realized_as_edge(db_env: Path):
    server = _import_server()

    with _memory_stack(server, swr=(True, 0.9), bayesian=0.88, mdl=(True, "high_similarity=0.890")):
        primary = server.remember(content="cluster signal primary", type="Signal", actor="system")
        related = server.remember(content="cluster signal related", type="Signal", actor="system")
        recalled = server.recall(query="cluster", top_k=5)
        promoted = server.promote_node(
            node_id=primary["node_id"],
            target_type="Pattern",
            reason="cluster promotion",
            related_ids=[related["node_id"]],
            actor="system",
        )

    edges = _query_rows(
        db_env,
        "SELECT source_id, target_id, relation FROM edges WHERE relation = 'realized_as'",
    )

    assert recalled["count"] >= 2
    assert promoted["new_type"] == "Pattern"
    assert [(row["source_id"], row["target_id"], row["relation"]) for row in edges] == [
        (related["node_id"], primary["node_id"], "realized_as")
    ]
