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

# mcp-memory 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "memory.db"


def run_auto_promote() -> str:
    """성장 사이클: 세션 종료 시 승격 후보를 찾아 자동 승격.

    API 비용 0 — DB 연산만. daily_enrich Phase 0과 동일 로직이지만
    세션마다 돌아서 remember()→recall()→Hebbian 강화→승격 사이클이 실시간 작동.
    """
    saved_cwd = os.getcwd()
    try:
        # auto_promote는 PROJECT_ROOT 기준 import 필요 (config, storage 등)
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        os.chdir(str(PROJECT_ROOT))

        from scripts.auto_promote import find_candidates, execute_promotions

        candidates = find_candidates()
        if not candidates:
            return ""

        result = execute_promotions(candidates, dry_run=False)
        promoted = result["promoted"]
        failed = result["failed"]
        total = result["total_candidates"]

        if promoted > 0:
            return f"🔺 memory: {promoted}건 자동 승격 (후보 {total}, 실패 {failed})"
        elif failed > 0:
            return f"⚠️ memory: 승격 실패 {failed}건 (후보 {total})"
        return ""
    except Exception as e:
        return f"⚠️ auto_promote: {e}"
    finally:
        os.chdir(saved_cwd)


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

    # 성장 사이클: 승격 체크
    promote_msg = run_auto_promote()
    if promote_msg:
        lines.append(promote_msg)

    return "\n".join(lines)


if __name__ == "__main__":
    print(check_session_health())
