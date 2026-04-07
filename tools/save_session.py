"""save_session() — 세션 구조화 저장 + 그래프 노드 생성.

v3.3: knowledge gate — short Decision/Question → work_item role.
"""

import json
from datetime import datetime, timezone

from config import (
    SAVE_SESSION_DECISION_MIN_LEN,
    SAVE_SESSION_QUESTION_MIN_LEN,
    SAVE_SESSION_SKIP_PATTERNS,
)
from storage import sqlite_store
from tools.remember import remember


def _should_skip(content: str) -> bool:
    """SKIP_PATTERNS 매칭 시 노드 미생성."""
    stripped = content.strip()
    if not stripped:
        return True
    return any(p in stripped for p in SAVE_SESSION_SKIP_PATTERNS)


def _classify_role(content: str, min_len: int) -> str:
    """길이 기반 node_role 분류."""
    if len(content.strip()) < min_len:
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
            role = _classify_role(d, SAVE_SESSION_DECISION_MIN_LEN)
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
            role = _classify_role(q, SAVE_SESSION_QUESTION_MIN_LEN)
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
