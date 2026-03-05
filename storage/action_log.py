"""storage/action_log.py — 시스템 활동 로깅 (A-9/A-12 확정)."""

import json
from datetime import datetime, timezone

from storage import sqlite_store


# A-9 확정: 25개 action_type
ACTION_TAXONOMY = {
    # remember
    "node_created":     "remember()로 노드 생성",
    "node_classified":  "classify()에서 타입 결정",
    "edge_auto":        "link()에서 자동 edge 생성",
    # recall
    "recall":           "recall() 검색 실행 (요약)",
    "node_activated":   "recall 결과로 반환된 개별 노드의 활성화 기록",
    # promote
    "node_promoted":    "promote_node()에서 타입 승격",
    "edge_realized":    "promote_node()에서 realized_as edge 생성",
    # edge
    "edge_created":     "insert_edge()에서 수동/자동 edge 생성",
    "edge_corrected":   "insert_edge()에서 relation 교정",
    # learning
    "hebbian_update":   "_hebbian_update()에서 frequency+1",
    "bcm_update":       "_bcm_update()에서 strength 조정",
    "reconsolidation":  "description에 맥락 추가",
    # enrichment
    "enrichment_start": "enrichment 배치 시작",
    "enrichment_done":  "enrichment 개별 노드 완료",
    "enrichment_fail":  "enrichment 개별 노드 실패",
    # ontology
    "type_deprecated":  "온톨로지 타입 deprecated",
    "type_migrated":    "온톨로지 타입 마이그레이션",
    "relation_corrected": "잘못된 관계 교정",
    # admin
    "session_start":    "세션 시작",
    "session_end":      "세션 종료",
    "config_changed":   "설정 변경",
    "migration":        "DB 마이그레이션 실행",
    # archive
    "node_archived":    "노드 아카이브",
    "node_reactivated": "아카이브 노드 재활성화",
    "edge_archived":    "edge 아카이브",
}


def record(
    action_type: str,
    actor: str = "system",
    session_id: str | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    params: str | None = None,
    result: str | None = None,
    context: str | None = None,
    model: str | None = None,
    duration_ms: int | None = None,
    token_cost: int | None = None,
    conn: "sqlite3.Connection | None" = None,
) -> int | None:
    """action_log에 1행 기록.

    Args:
        action_type: ACTION_TAXONOMY 키 중 하나.
        actor: "claude" | "system" | "enrichment" | "migration" | "paul"
        session_id: 현재 세션 ID (있으면).
        target_type: "node" | "edge" | "session" | "config" (있으면).
        target_id: 대상의 ID (있으면).
        params: JSON 문자열. 입력 파라미터.
        result: JSON 문자열. 실행 결과.
        context: 자유 텍스트. 추가 맥락.
        model: LLM 모델명 (enrichment 시).
        duration_ms: 실행 시간 ms.
        token_cost: 토큰 사용량.
        conn: 외부 트랜잭션에 참여할 때 전달. None이면 자체 conn 생성.

    Returns:
        삽입된 action_log.id (실패 시 None — 로깅 실패가 주 기능을 중단시키지 않음).
    """
    now = datetime.now(timezone.utc).isoformat()
    own_conn = conn is None

    try:
        if own_conn:
            conn = sqlite_store._connect()

        cur = conn.execute(
            """INSERT INTO action_log
               (actor, session_id, action_type, target_type, target_id,
                params, result, context, model, duration_ms, token_cost, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                actor, session_id, action_type, target_type, target_id,
                params or "{}", result or "{}", context, model,
                duration_ms, token_cost, now,
            ),
        )
        log_id = cur.lastrowid

        if own_conn:
            conn.commit()
        return log_id

    except Exception:
        # 로깅 실패는 주 기능에 영향을 주지 않는다
        return None
    finally:
        if own_conn and conn:
            conn.close()
