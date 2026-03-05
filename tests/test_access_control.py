"""tests/test_access_control.py — utils/access_control.py 테스트.

설계: d-r3-13
in-memory SQLite로 테스트 (실제 DB 불필요).
커버리지:
  TC01 L0 read (all actor)
  TC02 L4 write (paul only)
  TC03 L4 write (claude blocked by F1 firewall)
  TC04 L4 write (enrichment:E1 blocked by F1 firewall)
  TC05 L4 modify_metadata (claude allowed)
  TC06 L5 delete (paul allowed)
  TC07 L5 delete (claude blocked)
  TC08 L2 delete (paul allowed, enrichment blocked)
  TC09 Hub top-10 write blocked (all actors)
  TC10 Hub top-10 read allowed
  TC11 Node not in DB → defaults to L0
  TC12 Actor prefix matching (enrichment:E7 → enrichment)
  TC13 require_access raises PermissionError
  TC14 Hub top-10 write by paul also blocked (human-review)
  TC15 L0 write by enrichment allowed
"""
from __future__ import annotations

import sqlite3
import pytest

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.access_control import (
    check_access,
    require_access,
    _check_a10_firewall,
    _check_layer_permissions,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_conn(nodes: list[tuple[int, int]] | None = None,
               hub_ids: list[int] | None = None) -> sqlite3.Connection:
    """in-memory DB 생성. nodes=[(id, layer), ...], hub_ids=[id, ...]."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE nodes (id INTEGER PRIMARY KEY, layer INTEGER)"
    )
    conn.execute(
        "CREATE TABLE hub_snapshots "
        "(node_id INTEGER, snapshot_date TEXT, ihs_score REAL)"
    )
    if nodes:
        conn.executemany("INSERT INTO nodes VALUES (?, ?)", nodes)
    if hub_ids:
        conn.executemany(
            "INSERT INTO hub_snapshots VALUES (?, '2026-01-01', 1.0)",
            [(nid,) for nid in hub_ids],
        )
    conn.commit()
    return conn


# ── Unit: A-10 방화벽 ─────────────────────────────────────────────────────────

def test_tc_firewall_l0_always_passes():
    """TC-FW1: L0-L3은 방화벽 항상 통과."""
    for layer in range(4):
        for op in ("write", "delete", "modify_content"):
            assert _check_a10_firewall(layer, op, "enrichment") is True


def test_tc_firewall_l4_content_paul_only():
    """TC-FW2: L4 content ops는 paul만 허용."""
    for op in ("write", "delete", "modify_content"):
        assert _check_a10_firewall(4, op, "paul") is True
        assert _check_a10_firewall(4, op, "claude") is False
        assert _check_a10_firewall(4, op, "enrichment:E1") is False
        assert _check_a10_firewall(4, op, "system") is False


def test_tc_firewall_l4_meta_paul_claude():
    """TC-FW3: L4 modify_metadata는 paul+claude 허용."""
    assert _check_a10_firewall(4, "modify_metadata", "paul") is True
    assert _check_a10_firewall(4, "modify_metadata", "claude") is True
    assert _check_a10_firewall(4, "modify_metadata", "system") is False


def test_tc_firewall_l4_read_all():
    """TC-FW4: L4 read는 모두 허용."""
    for actor in ("paul", "claude", "system", "enrichment:E1"):
        assert _check_a10_firewall(4, "read", actor) is True


def test_tc_firewall_l5_content_paul_only():
    """TC-FW5: L5도 동일 — content ops paul만."""
    assert _check_a10_firewall(5, "write", "paul") is True
    assert _check_a10_firewall(5, "write", "claude") is False


# ── Unit: LAYER_PERMISSIONS ───────────────────────────────────────────────────

def test_tc_perm_actor_prefix_matching():
    """TC12: enrichment:E7 → actor_base = enrichment.
    L0: enrichment write 허용 / L2: write paul+claude만 (enrichment 차단)."""
    # L0: enrichment는 write 허용
    assert _check_layer_permissions(0, "write", "enrichment:E7") is True
    # L2: write는 paul/claude만 — enrichment:E7 차단
    assert _check_layer_permissions(2, "write", "enrichment:E7") is False
    assert _check_layer_permissions(2, "delete", "enrichment:E7") is False
    # L0: modify_metadata — enrichment 허용
    assert _check_layer_permissions(0, "modify_metadata", "enrichment:E7") is True


def test_tc_perm_l2_delete_paul_only():
    """TC08 unit: L2 delete은 paul만."""
    assert _check_layer_permissions(2, "delete", "paul") is True
    assert _check_layer_permissions(2, "delete", "claude") is False
    assert _check_layer_permissions(2, "delete", "system") is False


def test_tc_perm_unknown_operation_paul_only():
    """미정의 operation → paul만 허용."""
    assert _check_layer_permissions(0, "unknown_op", "paul") is True
    assert _check_layer_permissions(0, "unknown_op", "claude") is False


# ── Integration: check_access ─────────────────────────────────────────────────

def test_tc01_l0_read_all_actors():
    """TC01: L0 read는 모든 actor 허용."""
    conn = _make_conn(nodes=[(1, 0)])
    for actor in ("paul", "claude", "system", "enrichment:E1", "anonymous"):
        assert check_access(1, "read", actor, conn) is True


def test_tc02_l4_write_paul_allowed():
    """TC02: L4 write는 paul 허용."""
    conn = _make_conn(nodes=[(10, 4)])
    assert check_access(10, "write", "paul", conn) is True


def test_tc03_l4_write_claude_blocked():
    """TC03: L4 write는 claude 차단 (F1 방화벽)."""
    conn = _make_conn(nodes=[(10, 4)])
    assert check_access(10, "write", "claude", conn) is False


def test_tc04_l4_write_enrichment_blocked():
    """TC04: L4 write는 enrichment:E1 차단 (F1 방화벽)."""
    conn = _make_conn(nodes=[(10, 4)])
    assert check_access(10, "write", "enrichment:E1", conn) is False


def test_tc05_l4_modify_metadata_claude_allowed():
    """TC05: L4 modify_metadata는 claude 허용."""
    conn = _make_conn(nodes=[(10, 4)])
    assert check_access(10, "modify_metadata", "claude", conn) is True


def test_tc06_l5_delete_paul_allowed():
    """TC06: L5 delete는 paul 허용."""
    conn = _make_conn(nodes=[(20, 5)])
    assert check_access(20, "delete", "paul", conn) is True


def test_tc07_l5_delete_claude_blocked():
    """TC07: L5 delete는 claude 차단 (F1 방화벽)."""
    conn = _make_conn(nodes=[(20, 5)])
    assert check_access(20, "delete", "claude", conn) is False


def test_tc08_l2_delete():
    """TC08: L2 delete — paul 허용, enrichment 차단."""
    conn = _make_conn(nodes=[(30, 2)])
    assert check_access(30, "delete", "paul", conn) is True
    assert check_access(30, "delete", "enrichment:E5", conn) is False


def test_tc09_hub_top10_write_blocked():
    """TC09: Hub top-10 write/delete는 모든 actor 차단."""
    conn = _make_conn(nodes=[(100, 1)], hub_ids=[100])
    for actor in ("paul", "claude", "system"):
        assert check_access(100, "write", actor, conn) is False
        assert check_access(100, "delete", actor, conn) is False


def test_tc10_hub_top10_read_allowed():
    """TC10: Hub top-10 read는 허용."""
    conn = _make_conn(nodes=[(100, 1)], hub_ids=[100])
    assert check_access(100, "read", "paul", conn) is True
    assert check_access(100, "read", "system", conn) is True


def test_tc11_node_not_in_db_defaults_l0():
    """TC11: DB에 없는 노드 → layer 0으로 처리 (L0 write 허용)."""
    conn = _make_conn(nodes=[])
    # node 999 미존재 → layer=0 → write by enrichment 허용
    assert check_access(999, "write", "enrichment:E1", conn) is True
    # write by system도 허용 (L0)
    assert check_access(999, "write", "system", conn) is True


def test_tc14_hub_top10_write_paul_also_blocked():
    """TC14: Hub top-10 write는 paul도 차단 (human-review 필요)."""
    conn = _make_conn(nodes=[(100, 3)], hub_ids=[100])
    assert check_access(100, "write", "paul", conn) is False


def test_tc15_l0_write_enrichment_allowed():
    """TC15: L0 write는 enrichment 허용."""
    conn = _make_conn(nodes=[(1, 0)])
    assert check_access(1, "write", "enrichment:E1", conn) is True


def test_tc13_require_access_raises_permission_error():
    """TC13: require_access는 차단 시 PermissionError 발생."""
    conn = _make_conn(nodes=[(10, 4)])
    with pytest.raises(PermissionError, match="cannot 'write' node 10"):
        require_access(10, "write", "claude", conn)


def test_tc_require_access_passes_silently():
    """TC13b: require_access — 허용 시 예외 없음."""
    conn = _make_conn(nodes=[(10, 4)])
    require_access(10, "write", "paul", conn)  # no exception
