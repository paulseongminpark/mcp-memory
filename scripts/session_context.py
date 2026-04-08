#!/usr/bin/env python3
"""세션 시작 시 메모리 컨텍스트 출력 — session-start.sh에서 호출.

v3.3: context_selector 공유. 이 파일은 text renderer만 담당.
"""

import os
import sys

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from config import DB_PATH


def _load_proven_knowledge() -> str:
    """proven_knowledge.md에서 검증된 지식 요약 로드."""
    pk_path = DB_PATH.parent / "proven_knowledge.md"
    if not pk_path.exists():
        return ""
    try:
        text = pk_path.read_text(encoding="utf-8")
        # 헤더 제거, 내용만
        lines = []
        for line in text.split("\n"):
            if line.startswith("# ") or line.startswith("_Auto-generated"):
                continue
            if line.startswith("검증된 지식"):
                continue
            if line.strip():
                lines.append(line)
        return "\n".join(lines[:40])  # 최대 40줄
    except Exception:
        return ""


def get_context_cli(project: str = "") -> str:
    if not DB_PATH.exists():
        return ""

    from tools.context_selector import select_context
    sections = select_context(project)

    if not sections:
        return ""

    lines = []

    # ── Layer 1: Core Knowledge (DB 직접, SoT primary) ──
    if "knowledge_core" in sections:
        lines.append("=== 검증된 지식 (knowledge_core, DB live) ===")
        for r in sections["knowledge_core"]:
            lines.append(f"  - [{r['type']}] #{r['id']} ({r['project']}) {r['content']}")
        lines.append("")
    else:
        # DB fallback: proven_knowledge.md
        proven = _load_proven_knowledge()
        if proven:
            lines.append("=== 검증된 지식 (proven_knowledge.md fallback) ===")
            lines.append(proven)
            lines.append("")

    # L2+ 핵심 패턴/원칙 (knowledge_core에 포함 안 된 것)
    if "l2_core" in sections:
        lines.append("핵심 패턴/원칙 (L2+, quality 상위):")
        for r in sections["l2_core"]:
            lines.append(f"  - [{r['type']}] {r['content']}")

    # ── Layer 2: Active Signals ──
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

    # v5: Corrections / Warnings (epistemic separation — core와 분리)
    if "corrections" in sections:
        lines.append("교정 경고:")
        for c in sections["corrections"]:
            flagged = f" (→#{c['flagged_node']})" if c.get('flagged_node') else ""
            lines.append(f"  - [{c.get('date','')}] {c['content']}{flagged}")
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
