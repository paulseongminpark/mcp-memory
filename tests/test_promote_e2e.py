"""End-to-end promotion tests with SPRT preparation."""

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

from config import PROMOTE_LAYER
from storage import hybrid, sqlite_store
from storage.hybrid import post_search_learn
from tools.promote_node import promote_node


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


def _query_all(db_path: Path, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _ensure_promotion_test_schema(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        node_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(nodes)").fetchall()
        }
        if "last_activated" not in node_columns:
            conn.execute("ALTER TABLE nodes ADD COLUMN last_activated TEXT")
        if "frequency" not in node_columns:
            conn.execute("ALTER TABLE nodes ADD COLUMN frequency INTEGER DEFAULT 0")

        recall_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(recall_log)").fetchall()
        }
        if "source" not in recall_columns:
            conn.execute("ALTER TABLE recall_log ADD COLUMN source TEXT")

        conn.commit()
    finally:
        conn.close()


def _reset_hybrid_cache() -> None:
    hybrid._GRAPH_CACHE = None
    hybrid._GRAPH_CACHE_TS = 0.0


def _insert_node(
    node_type: str,
    content: str,
    *,
    project: str,
    metadata: dict | None = None,
) -> int:
    return sqlite_store.insert_node(
        type=node_type,
        content=content,
        metadata=metadata or {},
        project=project,
        layer=PROMOTE_LAYER.get(node_type),
        tier=2,
    )


def _seed_gate_readiness(candidate_id: int) -> None:
    with sqlite_store._db() as conn:
        conn.execute("UPDATE nodes SET visit_count = 15 WHERE id = ?", (candidate_id,))
        for rank in range(5):
            conn.execute(
                """
                INSERT INTO recall_log (query, node_id, rank, score, mode)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("promotion gate seed", candidate_id, rank + 1, 0.9, "focus"),
            )
        conn.commit()


def _accumulate_sprt_pass(signal_id: int, peer_id: int) -> None:
    _reset_hybrid_cache()
    for idx in range(5):
        results = [
            sqlite_store.get_node(signal_id),
            sqlite_store.get_node(peer_id),
        ]
        results[0]["score"] = 1.0
        results[1]["score"] = 0.9
        t = post_search_learn(results, query=f"sprt pass {idx}")
        if t is not None:
            t.join(timeout=10)


@pytest.fixture()
def db_env():
    runtime_dir = _make_runtime_dir("promote_e2e")
    db_path = runtime_dir / "memory.db"

    with ExitStack() as stack:
        stack.enter_context(patch("config.DB_PATH", db_path))
        stack.enter_context(patch("storage.sqlite_store.DB_PATH", db_path))
        stack.enter_context(patch("storage.action_log.sqlite_store.DB_PATH", db_path))
        sqlite_store.init_db()
        _ensure_promotion_test_schema(db_path)
        _reset_hybrid_cache()
        yield db_path
        _reset_hybrid_cache()

    shutil.rmtree(runtime_dir, ignore_errors=True)


def test_signal_passes_sprt_and_promotes_to_pattern_e2e(db_env: Path):
    candidate_id = _insert_node(
        "Signal",
        "candidate signal ready for pattern promotion",
        project="project-alpha",
        metadata={"note": "preserve"},
    )
    related_id = _insert_node(
        "Signal",
        "related signal from another project",
        project="project-beta",
    )
    sqlite_store.insert_edge(
        source_id=candidate_id,
        target_id=related_id,
        relation="supports",
        description="[]",
        strength=0.5,
    )
    _seed_gate_readiness(candidate_id)
    _accumulate_sprt_pass(candidate_id, related_id)

    before = _query_one(
        db_env,
        "SELECT type, layer, metadata, score_history, promotion_candidate FROM nodes WHERE id = ?",
        (candidate_id,),
    )
    before_edges = _query_all(
        db_env,
        "SELECT source_id, target_id, relation FROM edges WHERE source_id = ? OR target_id = ? ORDER BY id",
        (candidate_id, candidate_id),
    )

    result = promote_node(
        node_id=candidate_id,
        target_type="Pattern",
        reason="SPRT passed and cluster confirmed",
        related_ids=[related_id],
    )

    after = _query_one(
        db_env,
        "SELECT type, layer, metadata, score_history, promotion_candidate FROM nodes WHERE id = ?",
        (candidate_id,),
    )
    after_edges = _query_all(
        db_env,
        "SELECT source_id, target_id, relation FROM edges WHERE source_id = ? OR target_id = ? ORDER BY id",
        (candidate_id, candidate_id),
    )
    after_metadata = json.loads(after["metadata"])

    assert json.loads(before["score_history"]) == [1.0, 1.0, 1.0, 1.0, 1.0]
    assert before["promotion_candidate"] == 1
    assert before["type"] == "Signal"
    assert before["layer"] == PROMOTE_LAYER["Signal"]
    assert [(row["source_id"], row["target_id"], row["relation"]) for row in before_edges] == [
        (candidate_id, related_id, "supports")
    ]

    assert result["previous_type"] == "Signal"
    assert result["new_type"] == "Pattern"
    assert result["new_layer"] == PROMOTE_LAYER["Pattern"]
    assert result["gates_passed"] == ["swr", "frequency", "mdl"]
    assert after["type"] == "Pattern"
    assert after["layer"] == PROMOTE_LAYER["Pattern"]
    assert after_metadata["note"] == "preserve"
    assert after_metadata["promotion_history"][-1]["from"] == "Signal"
    assert after_metadata["promotion_history"][-1]["to"] == "Pattern"
    assert after_metadata["promotion_history"][-1]["gates_skipped"] is False
    assert [(row["source_id"], row["target_id"], row["relation"]) for row in after_edges] == [
        (candidate_id, related_id, "supports"),
        (related_id, candidate_id, "realized_as"),
    ]


def test_promote_node_skip_gates_bypasses_all_gate_helpers(db_env: Path):
    candidate_id = _insert_node(
        "Signal",
        "force-promoted signal",
        project="project-force",
    )
    related_id = _insert_node(
        "Signal",
        "force promotion peer",
        project="project-related",
    )

    with patch("tools.promote_node.swr_readiness") as mock_swr, \
         patch("tools.promote_node.promotion_frequency_check") as mock_frequency_check, \
         patch("tools.promote_node._mdl_gate") as mock_mdl:
        result = promote_node(
            node_id=candidate_id,
            target_type="Pattern",
            reason="admin override",
            related_ids=[related_id],
            skip_gates=True,
        )

    row = _query_one(
        db_env,
        "SELECT type, layer, metadata FROM nodes WHERE id = ?",
        (candidate_id,),
    )
    metadata = json.loads(row["metadata"])
    realized_edges = _query_all(
        db_env,
        """
        SELECT source_id, target_id, relation
        FROM edges
        WHERE relation = 'realized_as'
        ORDER BY id
        """,
    )

    assert result["new_type"] == "Pattern"
    assert result["new_layer"] == PROMOTE_LAYER["Pattern"]
    assert result["gates_passed"] == []
    assert row["type"] == "Pattern"
    assert row["layer"] == PROMOTE_LAYER["Pattern"]
    assert metadata["promotion_history"][-1]["gates_skipped"] is True
    assert [(row["source_id"], row["target_id"], row["relation"]) for row in realized_edges] == [
        (related_id, candidate_id, "realized_as")
    ]
    mock_swr.assert_not_called()
    mock_frequency_check.assert_not_called()
    mock_mdl.assert_not_called()
