#!/usr/bin/env python3
"""sessions 테이블 → 그래프 노드 마이그레이션.

기존 sessions 테이블 데이터를 새 save_session()으로 재실행하여
Narrative + Decision + Question 노드 + 명시적 edge를 생성한다.

content_hash 기반 dedup으로 중복 안전.
DRY_RUN=True로 먼저 확인 후 실행.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage import sqlite_store
from tools.save_session import save_session

DRY_RUN = True  # True: 미리보기만, False: 실제 실행


def migrate_sessions():
    """sessions 테이블의 모든 세션을 노드로 변환."""
    with sqlite_store._db() as conn:
        rows = conn.execute(
            "SELECT session_id, summary, decisions, unresolved, project FROM sessions"
        ).fetchall()

    print(f"총 {len(rows)}개 세션 발견\n")

    for row in rows:
        sid = row[0]
        summary = row[1] or ""
        decisions = json.loads(row[2]) if row[2] else []
        unresolved = json.loads(row[3]) if row[3] else []
        project = row[4] or ""

        print(f"--- {sid} ---")
        print(f"  summary: {summary[:80]}")
        print(f"  decisions: {len(decisions)}개")
        print(f"  unresolved: {len(unresolved)}개")
        print(f"  project: {project}")

        if DRY_RUN:
            print("  [DRY_RUN] 스킵\n")
            continue

        result = save_session(
            session_id=sid,
            summary=summary,
            decisions=decisions,
            unresolved=unresolved,
            project=project,
        )
        nc = result.get("nodes_created", {})
        print(f"  → {nc.get('narrative', 0)}N + {nc.get('decisions', 0)}D + {nc.get('questions', 0)}Q, {nc.get('edges', 0)} edges\n")

    print("완료.")


def migrate_lessons():
    """lessons.md → Insight(L2) 노드."""
    # Windows + MSYS 호환
    lessons_path = Path("C:/dev/01_projects/01_orchestration/lessons.md")
    if not lessons_path.exists():
        lessons_path = Path("/c/dev/01_projects/01_orchestration/lessons.md")
    if not lessons_path.exists():
        print("lessons.md 없음, 스킵")
        return

    from tools.remember import remember

    text = lessons_path.read_text(encoding="utf-8")
    count = 0
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("- ["):
            continue
        # 형식: - [2026-03-08] 내용
        try:
            date_end = line.index("]", 3)
            date_str = line[3:date_end]
            content = line[date_end + 2:]
        except ValueError:
            continue

        print(f"  lesson: [{date_str}] {content[:60]}")
        if DRY_RUN:
            count += 1
            continue

        remember(
            content=f"[{date_str}] {content}",
            type="Insight",
            project="orchestration",
            source="migrate:lessons",
            confidence=0.75,
        )
        count += 1

    print(f"\nlessons: {count}개 {'발견 (DRY_RUN)' if DRY_RUN else '마이그레이션 완료'}")


if __name__ == "__main__":
    if "--run" in sys.argv:
        DRY_RUN = False
        print("⚠️  실제 실행 모드\n")
    else:
        print("🔍 DRY_RUN 모드 (--run 으로 실제 실행)\n")

    print("=== Sessions → Nodes ===")
    migrate_sessions()
    print()
    print("=== Lessons → Insight Nodes ===")
    migrate_lessons()
