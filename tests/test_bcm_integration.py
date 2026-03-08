"""Integration tests for BCM update and SPRT accumulation."""

from __future__ import annotations

import json
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

from storage import hybrid, sqlite_store
from storage.hybrid import post_search_learn


def _make_runtime_dir(prefix: str) -> Path:
    runtime_dir = ROOT / "tests" / f".runtime_{prefix}_{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _query_one(db_path: Path, sql: str, params: tuple = ()) -> sqlite3.Row | None:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _ensure_learning_schema(db_path: Path) -> None:
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
    hybrid._GRAPH_CACHE = None
    hybrid._GRAPH_CACHE_TS = 0.0


def _insert_node(node_type: str, content: str, *, project: str, layer: int) -> int:
    return sqlite_store.insert_node(
        type=node_type,
        content=content,
        metadata={},
        project=project,
        layer=layer,
        tier=2,
    )


def _scored_results(signal_id: int, pattern_id: int) -> list[dict]:
    signal = sqlite_store.get_node(signal_id)
    pattern = sqlite_store.get_node(pattern_id)
    signal["score"] = 1.0
    pattern["score"] = 0.9
    return [signal, pattern]


@pytest.fixture()
def db_env():
    runtime_dir = _make_runtime_dir("bcm_integration")
    db_path = runtime_dir / "memory.db"

    with ExitStack() as stack:
        stack.enter_context(patch("config.DB_PATH", db_path))
        stack.enter_context(patch("storage.sqlite_store.DB_PATH", db_path))
        stack.enter_context(patch("storage.action_log.sqlite_store.DB_PATH", db_path))
        sqlite_store.init_db()
        _ensure_learning_schema(db_path)
        _reset_hybrid_cache()
        yield db_path
        _reset_hybrid_cache()

    shutil.rmtree(runtime_dir, ignore_errors=True)


def test_post_search_learn_updates_theta_visit_count_and_edge_strength(db_env: Path):
    signal_id = _insert_node("Signal", "BCM source signal", project="alpha", layer=1)
    pattern_id = _insert_node("Pattern", "BCM target pattern", project="alpha", layer=2)
    sqlite_store.insert_edge(
        source_id=signal_id,
        target_id=pattern_id,
        relation="supports",
        description="[]",
        strength=0.5,
    )

    before_signal = _query_one(
        db_env,
        "SELECT theta_m, visit_count FROM nodes WHERE id = ?",
        (signal_id,),
    )
    before_edge = _query_one(
        db_env,
        "SELECT strength FROM edges WHERE source_id = ? AND target_id = ?",
        (signal_id, pattern_id),
    )

    post_search_learn(_scored_results(signal_id, pattern_id), query="bcm integration")

    after_signal = _query_one(
        db_env,
        "SELECT theta_m, visit_count FROM nodes WHERE id = ?",
        (signal_id,),
    )
    after_pattern = _query_one(
        db_env,
        "SELECT visit_count FROM nodes WHERE id = ?",
        (pattern_id,),
    )
    after_edge = _query_one(
        db_env,
        """
        SELECT strength, description
        FROM edges
        WHERE source_id = ? AND target_id = ?
        """,
        (signal_id, pattern_id),
    )

    assert before_signal["theta_m"] == 0.5
    assert after_signal["theta_m"] != before_signal["theta_m"]
    assert after_signal["theta_m"] == pytest.approx(1.0)
    assert after_signal["visit_count"] == before_signal["visit_count"] + 1
    assert after_pattern["visit_count"] == 1
    assert after_edge["strength"] != before_edge["strength"]
    assert after_edge["strength"] > before_edge["strength"]
    assert json.loads(after_edge["description"])[0]["q"] == "bcm integration"


def test_post_search_learn_accumulates_sprt_history_and_sets_promotion_candidate(db_env: Path):
    signal_id = _insert_node("Signal", "SPRT candidate signal", project="alpha", layer=1)
    pattern_id = _insert_node("Pattern", "SPRT supporting pattern", project="alpha", layer=2)
    sqlite_store.insert_edge(
        source_id=signal_id,
        target_id=pattern_id,
        relation="supports",
        description="[]",
        strength=0.5,
    )

    for idx in range(5):
        post_search_learn(
            _scored_results(signal_id, pattern_id),
            query=f"sprt integration {idx}",
        )

    row = _query_one(
        db_env,
        """
        SELECT score_history, promotion_candidate, visit_count
        FROM nodes
        WHERE id = ?
        """,
        (signal_id,),
    )
    history = json.loads(row["score_history"])

    assert history == [1.0, 1.0, 1.0, 1.0, 1.0]
    assert row["promotion_candidate"] == 1
    assert row["visit_count"] == 5
