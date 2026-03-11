#!/usr/bin/env python3
"""MEMORY.md 자동 렌더링 — mcp-memory DB → MEMORY.md.

AI 토큰 0. DB 직접 쿼리로 MEMORY.md를 생성.
고정 섹션은 MEMORY.md의 "# Auto Memory" ~ "---DYNAMIC---" 마커까지 유지.
마커 이후는 DB 쿼리 결과로 대체.

사용: python render_memory_md.py [--dry-run]
"""

import sys
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH, UNENRICHED_DEFAULT_QS

MEMORY_MD = Path("C:/dev") / ".claude" / "projects" / "C--dev" / "memory" / "MEMORY.md"
if not MEMORY_MD.exists():
    MEMORY_MD = Path("/c/Users/pauls/.claude/projects/C--dev/memory/MEMORY.md")

DYNAMIC_MARKER = "<!-- DYNAMIC: 이 줄 아래는 render_memory_md.py가 자동 생성 -->"
MAX_LINES = 200


def get_db():
    return sqlite3.connect(str(DB_PATH))


def query_l3_nodes(conn) -> list[dict]:
    """L3 (Principle, Identity) 전체."""
    rows = conn.execute(
        """SELECT type, content, COALESCE(quality_score, ?) as qs
           FROM nodes WHERE layer = 3
           ORDER BY qs DESC""",
        (UNENRICHED_DEFAULT_QS.get(3, 0.75),)
    ).fetchall()
    return [{"type": r[0], "content": r[1][:80], "qs": r[2]} for r in rows]


def query_l2_top(conn, limit=15) -> list[dict]:
    """L2 (Pattern, Insight, Framework) 상위 N개."""
    rows = conn.execute(
        """SELECT type, content, COALESCE(quality_score, ?) as qs
           FROM nodes WHERE layer = 2
           ORDER BY qs DESC LIMIT ?""",
        (UNENRICHED_DEFAULT_QS.get(2, 0.65), limit)
    ).fetchall()
    return [{"type": r[0], "content": r[1][:80], "qs": r[2]} for r in rows]


def query_recent_decisions(conn, days=7, limit=5) -> list[dict]:
    """최근 N일 Decision 상위."""
    since = (datetime.now(tz=None) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT content, created_at
           FROM nodes WHERE type = 'Decision' AND created_at > ?
           ORDER BY created_at DESC LIMIT ?""",
        (since, limit)
    ).fetchall()
    return [{"content": r[0][:80], "date": r[1][:10]} for r in rows]


def query_open_questions(conn) -> list[dict]:
    """미해결 Question 전체."""
    rows = conn.execute(
        """SELECT content, created_at FROM nodes
           WHERE type = 'Question'
           ORDER BY created_at DESC"""
    ).fetchall()
    return [{"content": r[0][:80], "date": r[1][:10]} for r in rows]


def query_recent_failures(conn, limit=3) -> list[dict]:
    """최근 Failure 3개."""
    rows = conn.execute(
        """SELECT content, created_at FROM nodes
           WHERE type = 'Failure'
           ORDER BY created_at DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    return [{"content": r[0][:80], "date": r[1][:10]} for r in rows]


def render_dynamic(conn) -> str:
    """동적 섹션 렌더링."""
    lines = [DYNAMIC_MARKER, ""]

    # L3 Principles
    l3 = query_l3_nodes(conn)
    if l3:
        lines.append("## Core (L3)")
        for n in l3:
            lines.append(f"- [{n['type']}] {n['content']}")
        lines.append("")

    # L2 Top
    l2 = query_l2_top(conn)
    if l2:
        lines.append("## Structural (L2 Top 15)")
        for n in l2:
            lines.append(f"- [{n['type']}] {n['content']}")
        lines.append("")

    # Recent Decisions
    decisions = query_recent_decisions(conn)
    if decisions:
        lines.append("## Recent Decisions (7d)")
        for d in decisions:
            lines.append(f"- [{d['date']}] {d['content']}")
        lines.append("")

    # Open Questions
    questions = query_open_questions(conn)
    if questions:
        lines.append(f"## Open Questions ({len(questions)})")
        for q in questions:
            lines.append(f"- [{q['date']}] {q['content']}")
        lines.append("")

    # Recent Failures
    failures = query_recent_failures(conn)
    if failures:
        lines.append("## Recent Failures")
        for f in failures:
            lines.append(f"- [{f['date']}] {f['content']}")
        lines.append("")

    return "\n".join(lines)


def main():
    dry_run = "--dry-run" in sys.argv

    # 1. 기존 MEMORY.md에서 고정 섹션 추출
    if MEMORY_MD.exists():
        content = MEMORY_MD.read_text(encoding="utf-8")
        if DYNAMIC_MARKER in content:
            fixed = content[:content.index(DYNAMIC_MARKER)]
        else:
            fixed = content + "\n"
    else:
        fixed = "# Auto Memory\n\n"

    # 2. DB 쿼리
    conn = get_db()
    dynamic = render_dynamic(conn)
    conn.close()

    # 3. 결합
    result = fixed + dynamic
    result_lines = result.splitlines()

    if len(result_lines) > MAX_LINES:
        print(f"WARNING: {len(result_lines)}줄 > {MAX_LINES}줄. 잘라냄.")
        result = "\n".join(result_lines[:MAX_LINES]) + "\n"

    if dry_run:
        print(result)
        print(f"\n--- {len(result_lines)}줄 ---")
    else:
        MEMORY_MD.write_text(result, encoding="utf-8")
        print(f"MEMORY.md 갱신: {len(result_lines)}줄")


if __name__ == "__main__":
    main()
