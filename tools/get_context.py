"""get_context() — 프로젝트/전체 컨텍스트 요약 (~200 토큰)."""

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

    def _fmt(nodes: list[dict]) -> list[str]:
        return [f"[#{n['id']}] {n['content'][:100]}" for n in nodes]

    sections = {}
    if decisions:
        sections["recent_decisions"] = _fmt(decisions)
    if questions:
        sections["open_questions"] = _fmt(questions)
    if insights:
        sections["recent_insights"] = _fmt(insights)
    if failures:
        sections["recent_failures"] = _fmt(failures)

    if not sections:
        return {"context": "No memories stored yet.", "project": project}

    result = {
        "project": project or "all",
        **sections,
    }
    if active_pipeline:
        result["active_pipeline"] = active_pipeline
    return result
