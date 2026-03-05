"""utils/access_control.py — 3계층 접근 제어 (A-10 방화벽 + Hub 보호 + RBAC).

설계: d-r3-13
check_access() = 읽기 전용 판정 함수. DB를 수정하지 않는다.
차단 시 caller가 처리 결정 (예외 vs 조용히 skip).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "memory.db"

# ── LAYER_PERMISSIONS ────────────────────────────────────────────────────────
#
# operation: 허용 actor 집합 (특수값 "all" = 전체 허용)
# actor 접두어: "enrichment:" (enrichment 태스크들), "system:" (자동화)

LAYER_PERMISSIONS: dict[int, dict[str, list[str]]] = {
    0: {  # L0: Observation, Narrative, Conversation, Preference
        "read":            ["all"],
        "write":           ["paul", "claude", "system", "enrichment"],
        "delete":          ["paul", "claude"],
        "modify_content":  ["paul", "claude", "enrichment"],
        "modify_metadata": ["paul", "claude", "system", "enrichment"],
    },
    1: {  # L1: Workflow, Decision, Tool, Skill, Project, Goal, ...
        "read":            ["all"],
        "write":           ["paul", "claude", "system", "enrichment"],
        "delete":          ["paul", "claude"],
        "modify_content":  ["paul", "claude", "enrichment"],
        "modify_metadata": ["paul", "claude", "system", "enrichment"],
    },
    2: {  # L2: Pattern, Framework, Insight, Connection, Tension
        "read":            ["all"],
        "write":           ["paul", "claude"],
        "delete":          ["paul"],                   # L2 이상 삭제는 paul만
        "modify_content":  ["paul", "claude"],
        "modify_metadata": ["paul", "claude", "system"],
    },
    3: {  # L3: Principle, Identity
        "read":            ["all"],
        "write":           ["paul", "claude"],
        "delete":          ["paul"],
        "modify_content":  ["paul", "claude"],
        "modify_metadata": ["paul", "claude"],
    },
    4: {  # L4: Value, Philosophy, Belief — A-10 F1 적용
        "read":            ["all"],
        "write":           ["paul"],                   # F1: L4 write는 paul만
        "delete":          ["paul"],
        "modify_content":  ["paul"],                   # F1: 콘텐츠 변경 paul만
        "modify_metadata": ["paul", "claude"],         # 메타데이터는 claude도 가능
    },
    5: {  # L5: Axiom — 가장 엄격
        "read":            ["all"],
        "write":           ["paul"],
        "delete":          ["paul"],
        "modify_content":  ["paul"],
        "modify_metadata": ["paul", "claude"],
    },
}

# ── A-10 방화벽 (F1) ─────────────────────────────────────────────────────────

_FIREWALL_CONTENT_OPS = {"write", "modify_content", "delete"}
_FIREWALL_META_OPS = {"modify_metadata"}


def _check_a10_firewall(layer: int, operation: str, actor: str) -> bool:
    """
    A-10 방화벽 F1: L4/L5 콘텐츠 보호.
    True = 허용, False = 차단.

    F1 규칙:
      - L4/L5 content 변경/삭제: actor='paul' 만
      - L4/L5 metadata 변경: actor in ('paul', 'claude')
      - L4/L5 read: 모두 허용
    """
    if layer < 4:
        return True  # L0-L3: 방화벽 통과

    if operation in _FIREWALL_CONTENT_OPS:
        return actor == "paul"

    if operation in _FIREWALL_META_OPS:
        return actor in ("paul", "claude")

    # read 등 기타: 허용
    return True


# ── 허브 보호 (D-3) ───────────────────────────────────────────────────────────

def _get_top10_hub_ids(conn: sqlite3.Connection) -> set[int]:
    """hub_snapshots에서 최신 스냅샷의 Top-10 허브 ID 반환."""
    try:
        rows = conn.execute(
            "SELECT node_id FROM hub_snapshots "
            "WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM hub_snapshots) "
            "ORDER BY ihs_score DESC LIMIT 10"
        ).fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


def _check_hub_protection(
    node_id: int,
    layer: int,
    operation: str,
    hub_ids: set[int],
) -> bool:
    """
    D-3 허브 보호.
    Top-10 허브: delete/write에 human-review 필요 → False 반환.
    L2/L3 delete: paul 이외 차단 (LAYER_PERMISSIONS에서 처리됨).
    """
    if operation in ("delete", "write") and node_id in hub_ids:
        return False  # Top-10 허브 수정은 차단 (human-in-the-loop 필요)
    return True


# ── LAYER_PERMISSIONS 검사 ────────────────────────────────────────────────────

def _check_layer_permissions(layer: int, operation: str, actor: str) -> bool:
    """
    LAYER_PERMISSIONS 테이블 기반 권한 검사.
    actor가 "enrichment:E7" 형태면 "enrichment" 접두어로 매칭.
    """
    layer_key = min(layer, 5) if layer is not None else 0
    perms = LAYER_PERMISSIONS.get(layer_key, LAYER_PERMISSIONS[0])
    allowed = perms.get(operation, ["paul"])  # 미정의 operation → paul만

    if "all" in allowed:
        return True

    # 접두어 매칭: "enrichment:E7" → "enrichment"
    actor_base = actor.split(":")[0] if ":" in actor else actor

    return actor_base in allowed or actor in allowed


# ── 메인 진입점 ───────────────────────────────────────────────────────────────

def check_access(
    node_id: int,
    operation: str,
    actor: str,
    conn: sqlite3.Connection | None = None,
) -> bool:
    """
    node_id에 대한 operation 접근 권한 확인.

    Args:
        node_id:   대상 노드 ID
        operation: "read" | "write" | "delete" | "modify_content" | "modify_metadata"
        actor:     "paul" | "claude" | "system" | "enrichment:E1" | "system:pruning" 등
        conn:      DB 연결 (없으면 자동 생성)

    Returns:
        True  → 허용
        False → 차단 (caller가 처리 결정)

    우선순위:
      Layer 1: A-10 방화벽 (F1: L4/L5 콘텐츠 보호)
      Layer 2: Hub 보호 (D-3: Top-10 IHS 허브 write/delete 차단)
      Layer 3: LAYER_PERMISSIONS (레이어별 actor 권한)
    """
    _close_conn = False
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        _close_conn = True

    try:
        row = conn.execute(
            "SELECT layer FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()

        layer: int = row["layer"] if row and row["layer"] is not None else 0

        # Layer 1: A-10 방화벽
        if not _check_a10_firewall(layer, operation, actor):
            return False

        # Layer 2: Hub 보호
        hub_ids = _get_top10_hub_ids(conn)
        if not _check_hub_protection(node_id, layer, operation, hub_ids):
            return False

        # Layer 3: LAYER_PERMISSIONS
        return _check_layer_permissions(layer, operation, actor)

    finally:
        if _close_conn:
            conn.close()


# ── 편의 함수 ─────────────────────────────────────────────────────────────────

def require_access(
    node_id: int,
    operation: str,
    actor: str,
    conn: sqlite3.Connection | None = None,
) -> None:
    """
    check_access() 래퍼. 차단 시 PermissionError 발생.
    pruning.py, hub_monitor.py 등에서 사용.
    """
    if not check_access(node_id, operation, actor, conn):
        raise PermissionError(
            f"Access denied: actor='{actor}' cannot '{operation}' node {node_id}"
        )
