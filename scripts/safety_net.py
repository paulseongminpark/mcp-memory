#!/usr/bin/env python3
"""SessionEnd 안전망 — 세션 중 remember() 호출 횟수 체크.

Claude Code SessionEnd hook에서 호출.
LLM 불필요 — 단순 통계 기반.
"""

import sys
import os
import sqlite3

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
from pathlib import Path
from datetime import datetime, timezone, timedelta

# mcp-memory 데이터 경로
DB_PATH = Path(__file__).parent.parent / "data" / "memory.db"


def check_session_health() -> str:
    """최근 세션의 기억 저장 건전성 체크."""
    if not DB_PATH.exists():
        return "memory DB not found"

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # 최근 2시간 내 저장된 노드 수
    two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM nodes WHERE created_at > ?",
        (two_hours_ago,),
    ).fetchone()
    recent_count = row["cnt"] if row else 0

    # 미해결 질문 수
    questions = conn.execute(
        "SELECT COUNT(*) as cnt FROM nodes WHERE type = 'Question' AND status = 'active'"
    ).fetchone()
    q_count = questions["cnt"] if questions else 0

    conn.close()

    lines = []
    if recent_count == 0:
        lines.append("⚠️ memory: 이 세션에서 remember() 호출 0회 — 저장할 것 없었나 확인")
    else:
        lines.append(f"✅ memory: 최근 2시간 {recent_count}건 저장")

    if q_count > 0:
        lines.append(f"📋 memory: 미해결 질문 {q_count}건")

    return "\n".join(lines)


if __name__ == "__main__":
    print(check_session_health())
