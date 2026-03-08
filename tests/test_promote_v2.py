"""Tests for promote_node() v2 gate pipeline."""

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
from storage import sqlite_store
from tools.promote_node import promote_node


def _make_runtime_dir(prefix: str) -> Path:
    runtime_dir = ROOT / "tests" / f".runtime_{prefix}_{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _fetch_one(db_path: Path, sql: str, params: tuple = ()) -> sqlite3.Row | None:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _fetch_all(db_path: Path, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _insert_node(
    node_type: str = "Signal",
    content: str = "test signal",
    *,
    metadata: dict | None = None,
    project: str = "",
    layer: int | None = None,
) -> int:
    node_id = sqlite_store.insert_node(
        type=node_type,
        content=content,
        metadata=metadata or {},
        project=project,
        layer=layer if layer is not None else PROMOTE_LAYER.get(node_type),
        tier=2,
    )
    return node_id


@pytest.fixture()
def db_env():
    runtime_dir = _make_runtime_dir("promote")
    db_path = runtime_dir / "memory.db"

    with ExitStack() as stack:
        stack.enter_context(patch("config.DB_PATH", db_path))
        stack.enter_context(patch("storage.sqlite_store.DB_PATH", db_path))
        stack.enter_context(patch("storage.action_log.sqlite_store.DB_PATH", db_path))
        sqlite_store.init_db()
        yield db_path

    shutil.rmtree(runtime_dir, ignore_errors=True)


def test_promote_node_missing_node_returns_error(db_env: Path):
    result = promote_node(node_id=9999, target_type="Pattern", reason="missing")

    assert "error" in result
    assert result["message"] == "Promotion failed."


def test_promote_node_invalid_target_returns_valid_targets(db_env: Path):
    node_id = _insert_node(node_type="Signal", content="invalid target")

    result = promote_node(node_id=node_id, target_type="Framework", reason="bad path")

    assert result["error"] == "Invalid promotion: Signal \u2192 Framework"
    assert result["valid_targets"] == ["Pattern", "Insight"]


def test_promote_node_swr_failure_returns_not_ready_and_short_circuits(db_env: Path):
    node_id = _insert_node(node_type="Signal", content="gate one fail")

    with patch("tools.promote_node.swr_readiness", return_value=(False, 0.21)), \
         patch("tools.promote_node.promotion_probability") as mock_probability, \
         patch("tools.promote_node._mdl_gate") as mock_mdl:
        result = promote_node(node_id=node_id, target_type="Pattern", reason="swr fail")

    node = sqlite_store.get_node(node_id)
    assert result["status"] == "not_ready"
    assert result["swr_score"] == 0.21
    assert node["type"] == "Signal"
    mock_probability.assert_not_called()
    mock_mdl.assert_not_called()


def test_promote_node_bayesian_failure_returns_insufficient_evidence(db_env: Path):
    node_id = _insert_node(node_type="Signal", content="gate two fail")

    with patch("tools.promote_node.swr_readiness", return_value=(True, 0.91)), \
         patch("tools.promote_node.promotion_probability", return_value=0.24), \
         patch("tools.promote_node._mdl_gate") as mock_mdl:
        result = promote_node(node_id=node_id, target_type="Pattern", reason="bayesian fail")

    node = sqlite_store.get_node(node_id)
    assert result["status"] == "insufficient_evidence"
    assert result["p_real"] == 0.24
    assert node["type"] == "Signal"
    mock_mdl.assert_not_called()


def test_promote_node_mdl_failure_returns_mdl_failed(db_env: Path):
    node_id = _insert_node(node_type="Signal", content="mdl fail primary")
    related_id = _insert_node(node_type="Signal", content="mdl fail related")

    with patch("tools.promote_node.swr_readiness", return_value=(True, 0.92)), \
         patch("tools.promote_node.promotion_probability", return_value=0.88), \
         patch("tools.promote_node._mdl_gate", return_value=(False, "low_similarity=0.420_mdl_failed")):
        result = promote_node(
            node_id=node_id,
            target_type="Pattern",
            reason="mdl fail",
            related_ids=[related_id],
        )

    edges = _fetch_all(db_env, "SELECT * FROM edges WHERE target_id = ?", (node_id,))
    assert result["status"] == "mdl_failed"
    assert result["reason"] == "low_similarity=0.420_mdl_failed"
    assert edges == []


def test_promote_node_skip_gates_true_bypasses_gate_helpers(db_env: Path):
    node_id = _insert_node(node_type="Signal", content="skip gates primary")
    related_id = _insert_node(node_type="Signal", content="skip gates related")

    with patch("tools.promote_node.swr_readiness") as mock_swr, \
         patch("tools.promote_node.promotion_probability") as mock_probability, \
         patch("tools.promote_node._mdl_gate") as mock_mdl:
        result = promote_node(
            node_id=node_id,
            target_type="Pattern",
            reason="force promote",
            related_ids=[related_id],
            skip_gates=True,
        )

    assert result["new_type"] == "Pattern"
    assert result["gates_passed"] == []
    mock_swr.assert_not_called()
    mock_probability.assert_not_called()
    mock_mdl.assert_not_called()


def test_promote_node_skip_gates_false_records_all_passed_gates(db_env: Path):
    node_id = _insert_node(node_type="Signal", content="all gates primary")
    related_id = _insert_node(node_type="Signal", content="all gates related")

    with patch("tools.promote_node.swr_readiness", return_value=(True, 0.9)), \
         patch("tools.promote_node.promotion_probability", return_value=0.83), \
         patch("tools.promote_node._mdl_gate", return_value=(True, "high_similarity=0.910")):
        result = promote_node(
            node_id=node_id,
            target_type="Pattern",
            reason="all pass",
            related_ids=[related_id],
        )

    assert result["gates_passed"] == ["swr", "bayesian", "mdl"]
    assert result["new_layer"] == 2


def test_promote_node_updates_type_layer_and_history(db_env: Path):
    node_id = _insert_node(
        node_type="Signal",
        content="update state",
        metadata={"embedding_provisional": "true", "note": "keep"},
    )

    with patch("tools.promote_node.swr_readiness", return_value=(True, 0.9)), \
         patch("tools.promote_node.promotion_probability", return_value=0.78):
        result = promote_node(node_id=node_id, target_type="Pattern", reason="state update")

    row = _fetch_one(
        db_env,
        "SELECT type, layer, metadata, updated_at FROM nodes WHERE id = ?",
        (node_id,),
    )
    metadata = json.loads(row["metadata"])
    history = metadata["promotion_history"]

    assert result["new_type"] == "Pattern"
    assert row["type"] == "Pattern"
    assert row["layer"] == PROMOTE_LAYER["Pattern"]
    assert row["updated_at"]
    assert "embedding_provisional" not in metadata
    assert metadata["note"] == "keep"
    assert history[-1]["from"] == "Signal"
    assert history[-1]["to"] == "Pattern"
    assert history[-1]["reason"] == "state update"


def test_promote_node_creates_realized_as_edges_for_related_ids(db_env: Path):
    node_id = _insert_node(node_type="Signal", content="edge primary")
    related_a = _insert_node(node_type="Signal", content="edge related a")
    related_b = _insert_node(node_type="Signal", content="edge related b")

    with patch("tools.promote_node.swr_readiness", return_value=(True, 0.9)), \
         patch("tools.promote_node.promotion_probability", return_value=0.8), \
         patch("tools.promote_node._mdl_gate", return_value=(True, "high_similarity=0.880")):
        result = promote_node(
            node_id=node_id,
            target_type="Pattern",
            reason="create edges",
            related_ids=[related_a, related_b],
        )

    rows = _fetch_all(
        db_env,
        "SELECT source_id, target_id, relation FROM edges WHERE relation = 'realized_as' ORDER BY source_id",
    )

    assert result["realized_as_edges"]
    assert [(row["source_id"], row["target_id"], row["relation"]) for row in rows] == [
        (related_a, node_id, "realized_as"),
        (related_b, node_id, "realized_as"),
    ]


def test_promote_node_calls_action_log_record_with_expected_payload(db_env: Path):
    node_id = _insert_node(node_type="Signal", content="log primary")
    related_id = _insert_node(node_type="Signal", content="log related")

    with patch("tools.promote_node.swr_readiness", return_value=(True, 0.95)), \
         patch("tools.promote_node.promotion_probability", return_value=0.87), \
         patch("tools.promote_node._mdl_gate", return_value=(True, "high_similarity=0.900")), \
         patch("storage.action_log.record", return_value=123) as mock_log:
        result = promote_node(
            node_id=node_id,
            target_type="Pattern",
            reason="audit",
            related_ids=[related_id],
        )

    kwargs = mock_log.call_args.kwargs
    params = json.loads(kwargs["params"])
    record_result = json.loads(kwargs["result"])

    assert result["new_type"] == "Pattern"
    assert kwargs["action_type"] == "node_promoted"
    assert kwargs["target_id"] == node_id
    assert params["from_type"] == "Signal"
    assert params["to_type"] == "Pattern"
    assert params["skip_gates"] is False
    assert params["gates_passed"] == ["swr", "bayesian", "mdl"]
    assert record_result["new_layer"] == PROMOTE_LAYER["Pattern"]
    assert len(record_result["realized_as_edges"]) == 1


def test_promote_node_without_related_ids_skips_mdl_gate(db_env: Path):
    node_id = _insert_node(node_type="Signal", content="no related ids")

    with patch("tools.promote_node.swr_readiness", return_value=(True, 0.85)), \
         patch("tools.promote_node.promotion_probability", return_value=0.8), \
         patch("tools.promote_node._mdl_gate") as mock_mdl:
        result = promote_node(node_id=node_id, target_type="Pattern", reason="no mdl input")

    assert result["new_type"] == "Pattern"
    assert result["gates_passed"] == ["swr", "bayesian"]
    mock_mdl.assert_not_called()
