#!/usr/bin/env python3
"""세션 시작 시 메모리 컨텍스트 출력 — session-start.sh에서 호출."""

import os
import sys

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from config import DB_PATH


def get_context_cli(project: str = "") -> str:
    if not DB_PATH.exists():
        return ""

    import sqlite3

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    lines = []

    def _query_type(type_name, limit):
        if project:
            return conn.execute(
                "SELECT content, created_at FROM nodes WHERE type = ? AND project = ? ORDER BY created_at DESC LIMIT ?",
                (type_name, project, limit),
            ).fetchall()
        return conn.execute(
            "SELECT content, created_at FROM nodes WHERE type = ? ORDER BY created_at DESC LIMIT ?",
            (type_name, limit),
        ).fetchall()

    # 최근 Decision 3개
    decisions = _query_type("Decision", 3)
    if decisions:
        lines.append("최근 결정:")
        for d in decisions:
            lines.append(f"  - {d['content'][:60]} ({d['created_at'][:10]})")

    # 미해결 Question
    questions = _query_type("Question", 3)
    if questions:
        lines.append("미해결 질문:")
        for q in questions:
            lines.append(f"  - {q['content'][:60]}")

    # 최근 Failure
    failures = _query_type("Failure", 2)
    if failures:
        lines.append("최근 실패:")
        for f in failures:
            lines.append(f"  - {f['content'][:60]}")

    # 최근 Insight
    insights = _query_type("Insight", 2)
    if insights:
        lines.append("최근 인사이트:")
        for i in insights:
            lines.append(f"  - {i['content'][:60]}")

    conn.close()

    if not lines:
        return ""
    return "\n".join(lines)


if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else ""
    result = get_context_cli(project)
    if result:
        print(result)
