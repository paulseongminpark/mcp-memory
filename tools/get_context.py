"""get_context() — 세션 시작 컨텍스트 (~300 토큰).

v3.2: 품질 신호 + 세션 연속성 + 승격 후보 + proactive warnings.
"""

from storage import sqlite_store


def get_context(project: str = "") -> dict:
    # 0. 최근 세션의 active_pipeline
    active_pipeline = ""
    try:
        with sqlite_store._db() as conn:
            row = conn.execute(
                "SELECT active_pipeline FROM sessions WHERE active_pipeline != '' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                active_pipeline = row[0]
    except Exception:
        pass

    # 1. 최근 결정 3개
    decisions = sqlite_store.get_recent_nodes(project=project, limit=3, type_filter="Decision")

    # 2. 미결 질문 (Question 타입, status=active)
    questions = sqlite_store.get_recent_nodes(project=project, limit=3, type_filter="Question")

    # 3. 최근 패턴/인사이트
    insights = sqlite_store.get_recent_nodes(project=project, limit=2, type_filter="Insight")

    # 4. 최근 실패/교훈
    failures = sqlite_store.get_recent_nodes(project=project, limit=2, type_filter="Failure")

    def _fmt(nodes: list[dict]) -> list[dict]:
        """v3.2: 품질 신호 포함 포맷."""
        return [{
            "id": n["id"],
            "content": n["content"][:120],
            "layer": n.get("layer", 1),
            "confidence": round(n.get("confidence") or 0.5, 2),
            "source": n.get("source", ""),
        } for n in nodes]

    sections = {}
    if decisions:
        sections["recent_decisions"] = _fmt(decisions)
    if questions:
        sections["open_questions"] = _fmt(questions)
    if insights:
        sections["recent_insights"] = _fmt(insights)
    if failures:
        sections["recent_failures"] = _fmt(failures)

    # v3.2: 최근 세션 요약 (세션 연속성)
    try:
        with sqlite_store._db() as conn:
            sess = conn.execute(
                """SELECT session_id, summary, active_pipeline
                   FROM sessions ORDER BY id DESC LIMIT 1"""
            ).fetchone()
            if sess and sess[1]:
                sections["last_session"] = {
                    "id": sess[0], "summary": sess[1][:200],
                    "pipeline": sess[2] or "",
                }
    except Exception:
        pass

    # v3.2: 승격 후보 (Signal/Pattern with high visit_count)
    try:
        with sqlite_store._db() as conn:
            promo_filter = f"AND project='{project}'" if project else ""
            candidates = conn.execute(f"""
                SELECT id, type, visit_count, substr(content,1,80) as preview
                FROM nodes
                WHERE status='active' AND type IN ('Signal','Pattern','Observation')
                AND visit_count >= 5 {promo_filter}
                ORDER BY visit_count DESC LIMIT 3
            """).fetchall()
            if candidates:
                sections["promotion_ready"] = [
                    {"id": c[0], "type": c[1], "visits": c[2], "preview": c[3]}
                    for c in candidates
                ]
    except Exception:
        pass

    # v3.2: proactive warning — 최근 Failure와 유사한 패턴 감지
    try:
        if failures:
            with sqlite_store._db() as conn:
                recent_failure = failures[0]
                # 같은 project에서 반복 실패 패턴 확인
                repeat_failures = conn.execute("""
                    SELECT COUNT(*) FROM nodes
                    WHERE type='Failure' AND status='active'
                    AND project=? AND created_at > datetime('now', '-30 days')
                """, (recent_failure.get("project", ""),)).fetchone()
                if repeat_failures and repeat_failures[0] >= 3:
                    sections["warning"] = (
                        f"Project '{recent_failure.get('project', '')}' has "
                        f"{repeat_failures[0]} failures in last 30 days. "
                        f"Check for recurring patterns."
                    )
    except Exception:
        pass

    if not sections:
        return {"context": "No memories stored yet.", "project": project}

    result = {
        "project": project or "all",
        **sections,
    }
    if active_pipeline:
        result["active_pipeline"] = active_pipeline
    return result
