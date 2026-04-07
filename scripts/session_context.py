#!/usr/bin/env python3
"""세션 시작 시 메모리 컨텍스트 출력 — session-start.sh에서 호출.

v3.3: context_selector 공유. 이 파일은 text renderer만 담당.
"""

import os
import sys

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from config import DB_PATH


def get_context_cli(project: str = "") -> str:
    if not DB_PATH.exists():
        return ""

    from tools.context_selector import select_context
    sections = select_context(project)

    if not sections:
        return ""

    lines = []

    # L2+ 핵심 패턴/원칙
    if "l2_core" in sections:
        lines.append("핵심 패턴/원칙 (L2+, quality 상위):")
        for r in sections["l2_core"]:
            lines.append(f"  - [{r['type']}] {r['content']}")

    # Signal
    if "signals" in sections:
        lines.append("관찰 중 (Signal, 최근 30일):")
        for r in sections["signals"]:
            lines.append(f"  - [Signal] {r['content']}")

    # Observation
    if "observations" in sections:
        lines.append("최근 언급 (Observation, 최근 7일):")
        for r in sections["observations"]:
            lines.append(f"  - [Obs] {r['content']}")

    if lines:
        lines.append("")

    # Decision
    if "decisions" in sections:
        lines.append("최근 결정:")
        for d in sections["decisions"]:
            lines.append(f"  - {d['content']} ({d.get('date', '')})")

    # Question
    if "questions" in sections:
        lines.append("미해결 질문:")
        for q in sections["questions"]:
            lines.append(f"  - {q['content']}")

    # Failure
    if "failures" in sections:
        lines.append("최근 실패:")
        for f in sections["failures"]:
            lines.append(f"  - {f['content']}")

    # Insight
    if "insights" in sections:
        lines.append("최근 인사이트:")
        for i in sections["insights"]:
            lines.append(f"  - {i['content']}")

    # 승격 후보
    if "promotion_ready" in sections:
        lines.append("승격 후보 (반복 검증됨):")
        for r in sections["promotion_ready"]:
            lines.append(f"  - #{r['id']} [{r['type']}] v={r['visits']} {r['preview']}")

    # 반복 실패 경고
    if "warnings" in sections:
        lines.append("반복 실패 경고:")
        for r in sections["warnings"]:
            lines.append(f"  - {r['project']}: {r['count']}건 (30일)")

    return "\n".join(lines)


if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else ""
    result = get_context_cli(project)
    if result:
        print(result)
