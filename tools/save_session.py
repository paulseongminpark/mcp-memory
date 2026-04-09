"""save_session() — 세션 구조화 저장 + 그래프 노드 생성.

v3.3: knowledge gate — short Decision/Question → work_item role.
"""

import json
import re
from datetime import datetime, timezone

from config import (
    SAVE_SESSION_DECISION_MIN_LEN,
    SAVE_SESSION_QUESTION_MIN_LEN,
    SAVE_SESSION_SKIP_PATTERNS,
)
from storage import sqlite_store
from tools.remember import remember

_SAVE_SESSION_TACTICAL_PATTERNS = (
    "확인", "검토", "점검", "검증", "여부", "필요", "미정", "미완", "미구현",
    "수정", "조정", "반영", "연결", "구현", "실행", "재실행", "재수집",
    "커밋", "푸시", "push", "배포", "동기화", "적용", "삭제", "롤백",
    "untracked", "빌드 에러", "스케줄", "schedule", "enable", "disable",
    "정비", "정리", "미실행", "미확인", "누락", "실패", "버그", "잔여",
    "로드맵", "일정", "유지 vs", "실측", "미커밋",
)
_SAVE_SESSION_STRONG_TACTICAL_PATTERNS = (
    "미완", "미구현", "미실행", "미확인", "재실행", "재수집", "누락",
    "정리 필요", "반영 필요", "추가 필요", "수정 필요", "실패", "버그",
    "잔여", "로드맵", "일정", "유지 vs", "실측", "미커밋",
)
_SAVE_SESSION_DURABLE_PATTERNS = (
    "온톨로지", "기억", "memory", "recall", "pattern", "principle",
    "layer", "gate", "threshold", "quality", "weight", "weights", "bonus",
    "swr", "ndcg", "goldset", "checkpoint", "가중치", "bias", "enrichment",
    "정책", "규칙", "원칙", "철학", "역할", "스코프", "금지", "workflow",
    "relation", "node", "edge", "tone", "독자", "서사", "글쓰기",
    "컨텍스트", "구조", "시스템", "단일 소스", "타입 매핑", "패턴",
    "sot", "scope",
)
_SAVE_SESSION_FILE_HINT_RE = re.compile(
    r"(\b(scene|diagram|hero|toc|svg|github|vercel|readme|master|origin|schedule|cron)\b|"
    r"[A-Za-z0-9_./-]+\.(md|py|tsx|ts|js|json|html|css|ya?ml))",
    re.IGNORECASE,
)


def _should_skip(content: str) -> bool:
    """SKIP_PATTERNS 매칭 시 노드 미생성."""
    stripped = content.strip()
    if not stripped:
        return True
    return any(p in stripped for p in SAVE_SESSION_SKIP_PATTERNS)


def _looks_tactical(content: str) -> bool:
    stripped = content.strip()
    lowered = stripped.lower()
    return (
        any(p in lowered for p in _SAVE_SESSION_TACTICAL_PATTERNS)
        or _SAVE_SESSION_FILE_HINT_RE.search(stripped) is not None
    )


def _looks_strongly_tactical(content: str) -> bool:
    stripped = content.strip()
    lowered = stripped.lower()
    return (
        any(p in lowered for p in _SAVE_SESSION_STRONG_TACTICAL_PATTERNS)
        or _SAVE_SESSION_FILE_HINT_RE.search(stripped) is not None
    )


def _looks_durable(content: str) -> bool:
    lowered = _SAVE_SESSION_FILE_HINT_RE.sub(" ", content.strip().lower())
    return any(p in lowered for p in _SAVE_SESSION_DURABLE_PATTERNS)


def classify_session_item_role(content: str, item_type: str) -> str:
    """save_session 항목을 durable vs work_item으로 분류."""
    stripped = content.strip()
    if item_type == "Question":
        min_len = SAVE_SESSION_QUESTION_MIN_LEN
        tactical_max_len = 90
    else:
        min_len = SAVE_SESSION_DECISION_MIN_LEN
        tactical_max_len = 70

    if len(stripped) < min_len:
        return "work_item"
    tactical = _looks_tactical(stripped)
    strong_tactical = _looks_strongly_tactical(stripped)
    durable = _looks_durable(stripped)
    if item_type == "Question" and tactical and not durable:
        return "work_item"
    if strong_tactical and not durable:
        return "work_item"
    if len(stripped) < tactical_max_len and tactical and not durable:
        return "work_item"
    return "knowledge_candidate"


def save_session(
    session_id: str = "",
    summary: str = "",
    decisions: list[str] | None = None,
    unresolved: list[str] | None = None,
    project: str = "",
    active_pipeline: str = "",
) -> dict:
    if not session_id:
        session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    now = datetime.now(timezone.utc).isoformat()
    with sqlite_store._db() as conn:
        # UPSERT: 이미 있으면 업데이트
        conn.execute(
            """INSERT INTO sessions (session_id, summary, decisions, unresolved, project, started_at, active_pipeline)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                 summary = excluded.summary,
                 decisions = excluded.decisions,
                 unresolved = excluded.unresolved,
                 active_pipeline = excluded.active_pipeline,
                 ended_at = ?""",
            (
                session_id,
                summary,
                json.dumps(decisions or [], ensure_ascii=False),
                json.dumps(unresolved or [], ensure_ascii=False),
                project,
                now,
                active_pipeline,
                now,
            ),
        )
        conn.commit()

    # ── 그래프 노드 생성 (sessions 테이블 저장은 항상 유지) ──
    node_counts = {"narrative": 0, "decisions": 0, "questions": 0, "edges": 0}
    skipped = {"decisions": 0, "questions": 0}
    try:
        # Narrative 노드 — session_anchor role
        narr = remember(
            content=f"[Session] {session_id}: {summary}",
            type="Narrative",
            project=project,
            source="save_session",
            confidence=0.65,
            source_kind="save_session",
            node_role="session_anchor",
        )
        session_node_id = narr.get("node_id")
        if session_node_id:
            node_counts["narrative"] = 1

            # v3.2: Narrative chain
            if project:
                with sqlite_store._db() as conn:
                    prev = conn.execute(
                        """SELECT id FROM nodes
                           WHERE type='Narrative' AND source='save_session'
                             AND project=? AND status='active' AND id != ?
                           ORDER BY created_at DESC LIMIT 1""",
                        (project, session_node_id),
                    ).fetchone()
                if prev:
                    sqlite_store.insert_edge(
                        source_id=prev[0],
                        target_id=session_node_id,
                        relation="succeeded_by",
                        strength=0.9,
                        generation_method="session_anchor",
                    )
                    node_counts["edges"] += 1

        # Decision 노드 + knowledge gate
        decision_ids = []
        for d in (decisions or []):
            if _should_skip(d):
                skipped["decisions"] += 1
                continue
            role = classify_session_item_role(d, "Decision")
            if role == "work_item":
                skipped["decisions"] += 1
                continue
            r = remember(
                content=d,
                type="Decision",
                project=project,
                source="save_session",
                confidence=0.70,
                source_kind="save_session",
                node_role=role,
            )
            nid = r.get("node_id")
            if nid:
                decision_ids.append(nid)
        node_counts["decisions"] = len(decision_ids)

        # Question 노드 + knowledge gate
        question_ids = []
        for q in (unresolved or []):
            if _should_skip(q):
                skipped["questions"] += 1
                continue
            role = classify_session_item_role(q, "Question")
            if role == "work_item":
                skipped["questions"] += 1
                continue
            r = remember(
                content=q,
                type="Question",
                project=project,
                source="save_session",
                confidence=0.65,
                source_kind="save_session",
                node_role=role,
            )
            nid = r.get("node_id")
            if nid:
                question_ids.append(nid)
        node_counts["questions"] = len(question_ids)

        # 명시적 edge 생성 — session_anchor generation_method
        if session_node_id:
            for did in decision_ids:
                sqlite_store.insert_edge(
                    source_id=session_node_id,
                    target_id=did,
                    relation="contains",
                    strength=0.9,
                    generation_method="session_anchor",
                )
                node_counts["edges"] += 1
            for qid in question_ids:
                sqlite_store.insert_edge(
                    source_id=session_node_id,
                    target_id=qid,
                    relation="contains",
                    strength=0.8,
                    generation_method="session_anchor",
                )
                node_counts["edges"] += 1

    except Exception as e:
        import logging
        logging.getLogger("mcp_memory").warning("save_session node/edge creation failed: %s", e)

    return {
        "session_id": session_id,
        "summary": summary[:100],
        "decisions_count": len(decisions or []),
        "unresolved_count": len(unresolved or []),
        "nodes_created": node_counts,
        "skipped_low_signal": skipped,
        "message": f"Session '{session_id}' saved with {node_counts['narrative']}N + {node_counts['decisions']}D + {node_counts['questions']}Q nodes, {node_counts['edges']} edges (skipped: {skipped['decisions']}D + {skipped['questions']}Q)",
    }
