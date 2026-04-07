"""get_context() — 세션 시작 컨텍스트 (MCP JSON renderer).

v3.3: context_selector 공유. 이 파일은 renderer만 담당.
"""

from tools.context_selector import select_context


def get_context(project: str = "") -> dict:
    sections = select_context(project)

    if not sections:
        return {"context": "No memories stored yet.", "project": project}

    result = {"project": project or "all"}
    # 기존 API 호환: 키 이름 유지
    if "decisions" in sections:
        result["recent_decisions"] = sections["decisions"]
    if "questions" in sections:
        result["open_questions"] = sections["questions"]
    if "insights" in sections:
        result["recent_insights"] = sections["insights"]
    if "failures" in sections:
        result["recent_failures"] = sections["failures"]
    if "l2_core" in sections:
        result["l2_core"] = sections["l2_core"]
    if "signals" in sections:
        result["signals"] = sections["signals"]
    if "observations" in sections:
        result["observations"] = sections["observations"]
    if "last_session" in sections:
        result["last_session"] = sections["last_session"]
    if "promotion_ready" in sections:
        result["promotion_ready"] = sections["promotion_ready"]
    if "warnings" in sections:
        result["warning"] = "; ".join(
            f"{w['project']}: {w['count']}건 (30일)" for w in sections["warnings"]
        )
    if "active_pipeline" in sections:
        result["active_pipeline"] = sections["active_pipeline"]

    return result
