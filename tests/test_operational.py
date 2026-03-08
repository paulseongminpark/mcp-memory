"""Operational tests for recall/remember threading and boundary cases."""

from __future__ import annotations

import importlib
import shutil
import sqlite3
import sys
import threading
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
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(nodes)").fetchall()
        }
        if "last_activated" not in columns:
            conn.execute("ALTER TABLE nodes ADD COLUMN last_activated TEXT")
        conn.commit()
    finally:
        conn.close()


def _reset_hybrid_cache() -> None:
    from storage import hybrid

    hybrid._GRAPH_CACHE = None
    hybrid._GRAPH_CACHE_TS = 0.0


def _seed_nodes(contents: list[str]) -> list[int]:
    node_ids: list[int] = []
    for content in contents:
        node_ids.append(
            sqlite_store.insert_node(
                type="Observation",
                content=content,
                metadata={},
                layer=0,
                tier=2,
            )
        )
    _reset_hybrid_cache()
    return node_ids


def _server_stack(server_module):
    stack = ExitStack()
    stack.enter_context(
        patch.object(server_module, "validate_node_type", return_value=(True, None))
    )
    stack.enter_context(
        patch("tools.remember.validate_node_type", return_value=(True, None))
    )
    stack.enter_context(patch("storage.vector_store.add", return_value=None))
    stack.enter_context(patch("storage.vector_store.search", return_value=[]))
    return stack


@pytest.fixture()
def db_env():
    runtime_dir = _make_runtime_dir("operational")
    db_path = runtime_dir / "memory.db"

    with ExitStack() as stack:
        stack.enter_context(patch("config.DB_PATH", db_path))
        stack.enter_context(patch("storage.sqlite_store.DB_PATH", db_path))
        stack.enter_context(patch("storage.action_log.sqlite_store.DB_PATH", db_path))
        stack.enter_context(patch("utils.access_control.DB_PATH", db_path))
        sqlite_store.init_db()
        _ensure_test_schema(db_path)
        _reset_hybrid_cache()
        yield db_path
        _reset_hybrid_cache()

    shutil.rmtree(runtime_dir, ignore_errors=True)


def test_concurrent_recall_threads_complete_without_errors(db_env: Path):
    server = _import_server()
    _seed_nodes([f"alpha concurrent recall {i}" for i in range(5)])

    start_barrier = threading.Barrier(5)
    results: list[dict] = []
    errors: list[BaseException] = []
    threads: list[threading.Thread] = []

    def worker() -> None:
        try:
            start_barrier.wait(timeout=5)
            results.append(server.recall(query="alpha", top_k=5))
        except BaseException as exc:
            errors.append(exc)

    with _server_stack(server):
        for idx in range(5):
            thread = threading.Thread(target=worker, name=f"recall-worker-{idx}")
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert len(results) == 5
    assert all(result["count"] == 5 for result in results)


def test_concurrent_remember_threads_store_without_duplicates(db_env: Path):
    server = _import_server()
    results: list[dict] = []
    errors: list[BaseException] = []
    threads: list[threading.Thread] = []
    lookup_barrier = threading.Barrier(3)

    from tools import remember as remember_module

    original_lookup = remember_module.sqlite_store.get_node_by_hash

    def synchronized_lookup(content_hash: str):
        row = original_lookup(content_hash)
        lookup_barrier.wait(timeout=5)
        return row

    def worker() -> None:
        try:
            results.append(
                server.remember(
                    content="same concurrent remember content",
                    type="Observation",
                    actor="system",
                )
            )
        except BaseException as exc:
            errors.append(exc)

    with _server_stack(server):
        with patch(
            "tools.remember.sqlite_store.get_node_by_hash",
            side_effect=synchronized_lookup,
        ):
            for idx in range(3):
                thread = threading.Thread(target=worker, name=f"remember-worker-{idx}")
                threads.append(thread)
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

    stored_ids = {result["node_id"] for result in results if result.get("node_id") is not None}

    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert len(results) == 3
    assert _query_scalar(db_env, "SELECT COUNT(*) FROM nodes") == 1
    assert len(stored_ids) == 1


def test_large_top_k_50_recall_returns_at_most_50_results(db_env: Path):
    server = _import_server()
    _seed_nodes([f"alpha topk boundary node {i}" for i in range(60)])

    with _server_stack(server):
        result = server.recall(query="alpha", top_k=50)

    assert result["count"] == 50
    assert len(result["results"]) == 50


def test_empty_query_recall_returns_empty_results_without_crash(db_env: Path):
    server = _import_server()
    _seed_nodes(["alpha empty query control"])

    with _server_stack(server):
        result = server.recall(query="", top_k=5)

    assert result.get("count", 0) == 0
    assert result["results"] == []
    assert "No memories found." in result["message"]


def test_very_long_content_remember_stores_10000_characters(db_env: Path):
    server = _import_server()
    content = "x" * 10000

    with _server_stack(server):
        result = server.remember(content=content, type="Observation", actor="system")

    stored_length = _query_scalar(
        db_env,
        "SELECT LENGTH(content) FROM nodes WHERE id = ?",
        (result["node_id"],),
    )

    assert result["node_id"] is not None
    assert stored_length == 10000


def test_rapid_sequential_recall_returns_consistent_results(db_env: Path):
    server = _import_server()
    target_id = _seed_nodes(
        [
            "stable uniquesequencetoken alpha target",
            "unrelated beta node",
            "another unrelated gamma node",
        ]
    )[0]

    with _server_stack(server):
        id_lists = [
            [item["id"] for item in server.recall(query="uniquesequencetoken", top_k=5)["results"]]
            for _ in range(10)
        ]

    assert id_lists[0] == [target_id]
    assert all(ids == id_lists[0] for ids in id_lists)


def test_bcm_theta_m_stays_in_reasonable_range_after_10_recalls(db_env: Path):
    server = _import_server()
    source_id, target_id = _seed_nodes(
        [
            "theta alpha source memory",
            "theta alpha target memory",
        ]
    )
    sqlite_store.insert_edge(
        source_id=source_id,
        target_id=target_id,
        relation="connects_with",
        description="[]",
        strength=0.5,
    )
    _reset_hybrid_cache()

    with _server_stack(server):
        for _ in range(10):
            result = server.recall(query="theta alpha", top_k=2)
            assert result["count"] == 2

    # background BCM thread 완료 대기
    from storage.hybrid import drain_background_jobs
    drain_background_jobs(timeout=15.0)

    theta_m = _query_scalar(
        db_env,
        "SELECT theta_m FROM nodes WHERE id = ?",
        (source_id,),
    )
    visit_count = _query_scalar(
        db_env,
        "SELECT visit_count FROM nodes WHERE id = ?",
        (source_id,),
    )

    assert theta_m is not None
    assert 0.0 <= float(theta_m) <= 10.0
    assert visit_count >= 10


def test_init_db_fresh_creates_meta_and_recall_log_tables():
    runtime_dir = _make_runtime_dir("initdb")
    db_path = runtime_dir / "memory.db"

    try:
        with ExitStack() as stack:
            stack.enter_context(patch("config.DB_PATH", db_path))
            stack.enter_context(patch("storage.sqlite_store.DB_PATH", db_path))
            stack.enter_context(patch("storage.action_log.sqlite_store.DB_PATH", db_path))
            stack.enter_context(patch("utils.access_control.DB_PATH", db_path))
            sqlite_store.init_db()

        tables = {
            row["name"]
            for row in _query_rows(
                db_path,
                "SELECT name FROM sqlite_master WHERE type = 'table'",
            )
        }
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)

    assert "meta" in tables
    assert "recall_log" in tables
