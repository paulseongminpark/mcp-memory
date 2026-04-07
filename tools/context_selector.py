"""context_selector — get_context.py와 session_context.py의 공용 selector.

v3.3: 단일 진실원. 두 진입점은 renderer만 담당.
"""

from datetime import datetime, timedelta
from storage import sqlite_store


def select_context(project: str = "") -> dict:
    """세션 시작 시 보여줄 노드를 선택한다.

    Returns:
        dict with keys: l2_core, signals, observations, decisions,
        questions, failures, insights, promotion_ready, warnings,
        last_session, active_pipeline
    """
    conn = sqlite_store._connect()
    conn.row_factory = __import__("sqlite3").Row
    sections = {}

    now = datetime.utcnow()
    cutoff_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    def _proj(alias=""):
        prefix = f"{alias}." if alias else ""
        if project:
            return f"AND {prefix}project = ?", [project]
        return "", []

    # ── L2+ 핵심 패턴/원칙 (quality 상위 15개) — v5: epistemic 필터 ──
    pc, pp = _proj()
    rows = conn.execute(f"""
        SELECT id, type, content, summary, quality_score, layer, epistemic_status
        FROM nodes
        WHERE layer >= 2 AND status = 'active'
          AND type IN ('Pattern','Insight','Principle','Identity','Framework')
          AND epistemic_status NOT IN ('outdated', 'superseded', 'flagged')
          AND node_role NOT IN ('external_noise', 'work_item')
          {pc}
        ORDER BY quality_score DESC NULLS LAST LIMIT 15
    """, pp).fetchall()
    if rows:
        sections["l2_core"] = [
            {"id": r["id"], "type": r["type"],
             "content": (r["summary"] or r["content"])[:80],
             "quality": round(r["quality_score"] or 0, 2)}
            for r in rows
        ]

    # ── v5: Corrections / Warnings (epistemic separation) ──
    pc, pp = _proj()
    rows = conn.execute(f"""
        SELECT n.id, n.content, n.created_at,
               e.target_id as flagged_node_id
        FROM nodes n
        LEFT JOIN edges e ON e.source_id = n.id AND e.relation = 'contradicts' AND e.status = 'active'
        WHERE n.type = 'Correction' AND n.status = 'active'
          {pc}
        ORDER BY n.created_at DESC LIMIT 5
    """, pp).fetchall()
    if rows:
        sections["corrections"] = [
            {"id": r["id"],
             "content": r["content"][:80],
             "flagged_node": r["flagged_node_id"],
             "date": (r["created_at"] or "")[:10]}
            for r in rows
        ]

    # ── 최근 30일 Signal ──
    pc, pp = _proj()
    rows = conn.execute(f"""
        SELECT id, type, content, summary, created_at
        FROM nodes WHERE type = 'Signal' AND status = 'active'
          AND created_at >= ? {pc}
        ORDER BY created_at DESC LIMIT 10
    """, [cutoff_30d] + pp).fetchall()
    if rows:
        sections["signals"] = [
            {"id": r["id"], "content": (r["summary"] or r["content"])[:80]}
            for r in rows
        ]

    # ── 최근 7일 Observation ──
    pc, pp = _proj()
    rows = conn.execute(f"""
        SELECT id, type, content, summary, created_at
        FROM nodes WHERE type = 'Observation' AND status = 'active'
          AND created_at >= ? {pc}
        ORDER BY created_at DESC LIMIT 5
    """, [cutoff_7d] + pp).fetchall()
    if rows:
        sections["observations"] = [
            {"id": r["id"], "content": (r["summary"] or r["content"])[:80]}
            for r in rows
        ]

    # ── 최근 Decision 3개 (knowledge_candidate 이상만) ──
    pc, pp = _proj()
    rows = conn.execute(f"""
        SELECT id, content, created_at, node_role FROM nodes
        WHERE type = 'Decision' AND status = 'active'
          AND (node_role = '' OR node_role NOT IN ('work_item', 'external_noise'))
          {pc}
        ORDER BY created_at DESC LIMIT 3
    """, pp).fetchall()
    if rows:
        sections["decisions"] = [
            {"id": r["id"], "content": r["content"][:80], "date": r["created_at"][:10]}
            for r in rows
        ]

    # ── 미해결 Question (work_item 제외) ──
    pc, pp = _proj()
    rows = conn.execute(f"""
        SELECT id, content FROM nodes
        WHERE type = 'Question' AND status = 'active'
          AND (node_role = '' OR node_role NOT IN ('work_item', 'external_noise'))
          {pc}
        ORDER BY created_at DESC LIMIT 3
    """, pp).fetchall()
    if rows:
        sections["questions"] = [
            {"id": r["id"], "content": r["content"][:80]}
            for r in rows
        ]

    # ── 최근 Failure 2개 ──
    pc, pp = _proj()
    rows = conn.execute(f"""
        SELECT id, content FROM nodes
        WHERE type = 'Failure' AND status = 'active' {pc}
        ORDER BY created_at DESC LIMIT 2
    """, pp).fetchall()
    if rows:
        sections["failures"] = [
            {"id": r["id"], "content": r["content"][:80]}
            for r in rows
        ]

    # ── 최근 Insight 2개 ──
    pc, pp = _proj()
    rows = conn.execute(f"""
        SELECT id, content FROM nodes
        WHERE type = 'Insight' AND status = 'active' {pc}
        ORDER BY created_at DESC LIMIT 2
    """, pp).fetchall()
    if rows:
        sections["insights"] = [
            {"id": r["id"], "content": r["content"][:80]}
            for r in rows
        ]

    # ── 승격 후보 (visit_count >= 5) ──
    pc, pp = _proj()
    rows = conn.execute(f"""
        SELECT id, type, visit_count, substr(content,1,80) as preview
        FROM nodes
        WHERE status='active' AND type IN ('Signal','Pattern','Observation')
          AND visit_count >= 5 {pc}
        ORDER BY visit_count DESC LIMIT 3
    """, pp).fetchall()
    if rows:
        sections["promotion_ready"] = [
            {"id": r["id"], "type": r["type"], "visits": r["visit_count"], "preview": r["preview"]}
            for r in rows
        ]

    # ── 반복 실패 경고 ──
    pc, pp = _proj()
    rows = conn.execute(f"""
        SELECT project, COUNT(*) as cnt FROM nodes
        WHERE type='Failure' AND status='active'
          AND created_at >= ? {pc}
        GROUP BY project HAVING cnt >= 3
        ORDER BY cnt DESC LIMIT 3
    """, [cutoff_30d] + pp).fetchall()
    if rows:
        sections["warnings"] = [
            {"project": r["project"], "count": r["cnt"]}
            for r in rows
        ]

    # ── 최근 세션 ──
    try:
        sess = conn.execute(
            "SELECT session_id, summary, active_pipeline FROM sessions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if sess and sess["summary"]:
            sections["last_session"] = {
                "id": sess["session_id"],
                "summary": sess["summary"][:200],
                "pipeline": sess["active_pipeline"] or "",
            }
    except Exception:
        pass

    # ── active_pipeline ──
    try:
        row = conn.execute(
            "SELECT active_pipeline FROM sessions WHERE active_pipeline != '' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            sections["active_pipeline"] = row["active_pipeline"]
    except Exception:
        pass

    conn.close()
    return sections
