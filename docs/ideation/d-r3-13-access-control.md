# D-r3-13: utils/access_control.py 완성 코드 설계

> 세션 D | Round 3 | 2026-03-05
> D-9 hub_monitor 공존 + A-10 방화벽(F1-F6) 3계층 통합

---

## 개요

D-9에서 스케치한 `check_node_access()` → 완전한 `check_access()` 로 확장.
A-10 방화벽(F1-F6)과 D-3 RBAC(허브/레이어 보호)를 **단일 진입점**으로 통합.

```
호출자 (pruning, hub_monitor, enrichment, remember 등)
         ↓
  check_access(node_id, operation, actor)
         ↓
  Layer 1: A-10 방화벽 (F1-F6: L4/L5 콘텐츠 보호)
         ↓ ALLOWED
  Layer 2: 허브 보호 (D-3: Top-10 IHS + L2/L3 delete 제한)
         ↓ ALLOWED
  Layer 3: LAYER_PERMISSIONS 테이블
         ↓
  True(허용) | False(거부)
```

---

## 1. LAYER_PERMISSIONS 정의

```python
# utils/access_control.py

# operation: 허용 actor 집합 (특수값 "all" = 전체 허용)
# actor 접두어: "enrichment:" (enrichment 태스크들), "system:" (자동화)
LAYER_PERMISSIONS: dict[int, dict[str, list[str]]] = {
    0: {  # L0: Observation, Narrative, Conversation, Preference
        "read":           ["all"],
        "write":          ["paul", "claude", "system", "enrichment"],
        "delete":         ["paul", "claude"],
        "modify_content": ["paul", "claude", "enrichment"],
        "modify_metadata":["paul", "claude", "system", "enrichment"],
    },
    1: {  # L1: Workflow, Decision, Tool, Skill, Project, Goal, ...
        "read":           ["all"],
        "write":          ["paul", "claude", "system", "enrichment"],
        "delete":         ["paul", "claude"],
        "modify_content": ["paul", "claude", "enrichment"],
        "modify_metadata":["paul", "claude", "system", "enrichment"],
    },
    2: {  # L2: Pattern, Framework, Insight, Connection, Tension
        "read":           ["all"],
        "write":          ["paul", "claude"],        # enrichment는 쓰기 허용 (enrichment는 접두어로 구분)
        "delete":         ["paul"],                  # L2 이상 삭제는 paul만
        "modify_content": ["paul", "claude"],
        "modify_metadata":["paul", "claude", "system"],
    },
    3: {  # L3: Principle, Identity
        "read":           ["all"],
        "write":          ["paul", "claude"],
        "delete":         ["paul"],
        "modify_content": ["paul", "claude"],
        "modify_metadata":["paul", "claude"],
    },
    4: {  # L4: Value, Philosophy, Belief — A-10 F1 적용
        "read":           ["all"],
        "write":          ["paul"],                  # F1: L4 write는 paul만
        "delete":         ["paul"],
        "modify_content": ["paul"],                  # F1: 콘텐츠 변경 paul만
        "modify_metadata":["paul", "claude"],        # 메타데이터는 claude도 가능
    },
    5: {  # L5: Axiom — 가장 엄격
        "read":           ["all"],
        "write":          ["paul"],
        "delete":         ["paul"],
        "modify_content": ["paul"],
        "modify_metadata":["paul", "claude"],
    },
}

# enrichment 태스크 접두어: "enrichment:E1", "enrichment:E7" 등
# L2 이상 write 처리: enrichment는 L2에서 summary/key_concepts 등 메타데이터만 수정
# → modify_content에는 없고, write에는 있지만 실제로는 metadata성 필드만 수정
# 구분이 필요하면 operation="modify_metadata"를 명시적으로 사용.
```

---

## 2. check_access() 완전 구현

```python
# utils/access_control.py (전체 파일)

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

# LAYER_PERMISSIONS: 위에서 정의

DB_PATH = Path(__file__).parent.parent / "data" / "memory.db"


# ── A-10 방화벽 규칙 (F1-F6) ─────────────────────────────────────────────

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


# ── 허브 보호 (D-3) ───────────────────────────────────────────────────────

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

    여기서는 Top-10 허브 보호만 담당.
    """
    if operation in ("delete", "write") and node_id in hub_ids:
        return False  # Top-10 허브 수정은 차단 (human-in-the-loop 필요)
    return True


# ── LAYER_PERMISSIONS 검사 ────────────────────────────────────────────────

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


# ── 메인 진입점 ──────────────────────────────────────────────────────────

def check_access(
    node_id: int,
    operation: str,
    actor: str,
    conn: sqlite3.Connection | None = None,
) -> bool:
    """
    node_id에 대한 operation 접근 권한 확인.

    Args:
        node_id:   대상 노드 ID (INTEGER)
        operation: "read" | "write" | "delete" | "modify_content" | "modify_metadata"
        actor:     "paul" | "claude" | "system" | "enrichment:E1" | "system:daily_enrich" 등
        conn:      DB 연결 (없으면 자동 생성)

    Returns:
        True  → 허용
        False → 차단 (caller가 human-in-the-loop 처리)

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
        # 노드 레이어 조회
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


# ── 편의 함수 ─────────────────────────────────────────────────────────────

def require_access(node_id: int, operation: str, actor: str, conn=None) -> None:
    """
    check_access() 래퍼. 차단 시 PermissionError 발생.
    pruning.py, hub_monitor.py 등에서 사용.
    """
    if not check_access(node_id, operation, actor, conn):
        raise PermissionError(
            f"Access denied: actor='{actor}' cannot '{operation}' node {node_id}"
        )
```

---

## 3. hub_monitor.py — check_access() 실제 사용 코드

```python
# scripts/hub_monitor.py — check_access 통합 (기존 코드에 추가)

from utils.access_control import check_access, require_access


def recommend_hub_action(
    node_id: int,
    action: str,
    actor: str = "system",
    conn=None,
) -> dict:
    """
    허브 노드에 대한 액션 추천 전 접근 권한 확인.

    Usage (hub_health_report에서 위험도 판단 후):
      if h["risk"] == "HIGH":
          rec = recommend_hub_action(h["node_id"], "delete", actor="system")
          if not rec["allowed"]:
              print(f"HUMAN REVIEW REQUIRED: {rec['reason']}")
    """
    allowed = check_access(node_id, action, actor, conn)
    if not allowed:
        return {
            "allowed": False,
            "reason": (
                f"actor='{actor}' cannot '{action}' hub node {node_id}. "
                "Human review required."
            ),
            "require_human": True,
        }
    return {"allowed": True, "reason": "ok", "require_human": False}


# hub_health_report() 내 위험 허브 처리 예시:
def print_hub_actions(report: list[dict], actor: str = "system"):
    """허브 리포트 출력 시 접근 제어 결과 함께 표시."""
    print("\n=== Hub Access Control ===")
    for h in report:
        if h["risk"] == "HIGH":
            rec = recommend_hub_action(h["node_id"], "delete", actor)
            status = "BLOCK" if not rec["allowed"] else "ALLOW"
            print(
                f"  [{status}] node {h['node_id']} ({h['preview'][:30]}...) "
                f"delete → {rec['reason']}"
            )
```

---

## 4. pruning.py — check_access() 통합

```python
# scripts/pruning.py — stage2_mark_candidates()에 접근 제어 추가

from utils.access_control import check_access


def stage2_mark_candidates(
    conn,
    candidate_ids: list[int],
    dry_run: bool = True,
    actor: str = "system:pruning",
) -> int:
    """Stage 2: pruning_candidate 전환 (접근 제어 포함)."""
    if not candidate_ids:
        return 0

    blocked = []
    allowed_ids = []

    for nid in candidate_ids:
        if check_access(nid, "write", actor, conn):
            allowed_ids.append(nid)
        else:
            blocked.append(nid)

    if blocked:
        print(f"  접근 차단: {len(blocked)}개 노드 (L4/L5 또는 Top-10 허브)")

    if dry_run:
        print(f"[DRY RUN] {len(allowed_ids)}개 → pruning_candidate 예정")
        return len(allowed_ids)

    now = datetime.now(timezone.utc).isoformat()
    for nid in allowed_ids:
        conn.execute(
            "UPDATE nodes SET status='pruning_candidate', updated_at=? WHERE id=?",
            (now, nid),
        )
        conn.execute(
            "INSERT INTO correction_log "
            "(node_id, field, old_value, new_value, reason, corrected_by, event_type) "
            "VALUES (?, 'status', 'active', 'pruning_candidate', "
            "'BSP Stage 2: low quality + low activation + few edges', ?, 'prune_stage2')",
            (nid, actor),
        )

    conn.commit()
    print(f"Stage 2 완료: {len(allowed_ids)}개 → pruning_candidate")
    return len(allowed_ids)
```

---

## 5. enrichment에서의 사용 (F1/F2 통합)

```python
# scripts/enrich/node_enricher.py — _apply() 시작 부분에 추가

from utils.access_control import check_access


def _apply(self, node: dict, tid: str, result, conn):
    """enrichment 결과를 DB에 적용하기 전 접근 제어 확인."""
    node_id = node.get("id")
    layer = node.get("layer", 0)

    # F1/F2: L4/L5 노드의 콘텐츠 변경은 enrichment가 제한적
    operation = "modify_content" if tid in ("E1", "E2", "E3") else "modify_metadata"
    actor = f"enrichment:{tid}"

    if not check_access(node_id, operation, actor, conn):
        # L4/L5 콘텐츠 변경 차단 → allowed_fields 필터 적용 (A-10 F2)
        allowed_fields = {"summary", "key_concepts", "quality_score"}
        # ... (기존 F2 로직 유지)
        return

    # 나머지 기존 _apply 로직...
```

---

## 6. 파일 요약

| 파일 | 변경 내용 | 위험도 |
|------|---------|--------|
| `utils/access_control.py` | 신규 (전체) | 낮음 (read-only fallback) |
| `scripts/hub_monitor.py` | `recommend_hub_action()` + `print_hub_actions()` 추가 | 낮음 |
| `scripts/pruning.py` | `stage2_mark_candidates()` 접근 제어 추가 | 낮음 |
| `scripts/enrich/node_enricher.py` | `_apply()` 앞에 check_access 삽입 | 중간 |

---

## 7. 운영 관계 다이어그램

```
[A-10 F1-F6 방화벽]                [D-3 Hub/RBAC]
  L4/L5 콘텐츠 보호                  Top-10 IHS 보호
  (paul만 write/delete)               (human-in-the-loop)
         ↓                                    ↓
         └──────────────┬─────────────────────┘
                        ↓
              check_access(node_id, op, actor)
                        ↓
         ┌──────────────┴─────────────────────┐
         ↓                                    ↓
    True (허용)                         False (차단)
         ↓                                    ↓
   정상 진행                     caller가 PermissionError 처리
                                 또는 human-review 큐에 추가
```

**설계 원칙:**
- `check_access()`는 **읽기 전용** (DB를 수정하지 않음)
- 차단 시 caller가 처리 결정 (예외 vs 조용히 skip)
- `require_access()`는 예외 발생 래퍼 (명시적 실패 원하는 곳에서 사용)
- A-10 방화벽 구현 전: F1만 확인 (layer >= 4 체크), 나머지 F2-F6은 개별 삽입 코드로 유지
