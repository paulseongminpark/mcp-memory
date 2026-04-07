#!/usr/bin/env python3
"""세션 시작 시 메모리 컨텍스트 출력 — session-start.sh에서 호출."""

import os
import sys
from datetime import datetime, timedelta

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

    now = datetime.utcnow()
    cutoff_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    def _project_clause(alias=""):
        prefix = f"{alias}." if alias else ""
        if project:
            return f"AND {prefix}project = ?", [project]
        return "", []

    # ── [신규] L2+ 핵심 패턴/원칙/정체성 (quality 상위 15개) ──────────────
    proj_clause, proj_params = _project_clause()
    l2_rows = conn.execute(
        f"""
        SELECT id, type, content, summary, tags, quality_score, layer
        FROM nodes
        WHERE layer >= 2
          AND status = 'active'
          AND type IN ('Pattern','Insight','Principle','Identity','Framework')
          {proj_clause}
        ORDER BY quality_score DESC NULLS LAST
        LIMIT 15
        """,
        proj_params,
    ).fetchall()

    if l2_rows:
        lines.append("핵심 패턴/원칙 (L2+, quality 상위):")
        for r in l2_rows:
            text = r["summary"] or r["content"]
            lines.append(f"  - [{r['type']}] {text[:80]}")

    # ── [신규] 최근 30일 Signal (미승격 관찰 중) ──────────────────────────
    proj_clause, proj_params = _project_clause()
    signal_rows = conn.execute(
        f"""
        SELECT id, type, content, summary, tags, created_at
        FROM nodes
        WHERE type = 'Signal'
          AND status = 'active'
          AND created_at >= ?
          {proj_clause}
        ORDER BY created_at DESC
        LIMIT 10
        """,
        [cutoff_30d] + proj_params,
    ).fetchall()

    if signal_rows:
        lines.append("관찰 중 (Signal, 최근 30일):")
        for r in signal_rows:
            text = r["summary"] or r["content"]
            lines.append(f"  - [Signal] {text[:80]}")

    # ── [신규] 최근 7일 Observation (직접 언급) ───────────────────────────
    proj_clause, proj_params = _project_clause()
    obs_rows = conn.execute(
        f"""
        SELECT id, type, content, summary, tags, created_at
        FROM nodes
        WHERE type = 'Observation'
          AND status = 'active'
          AND created_at >= ?
          {proj_clause}
        ORDER BY created_at DESC
        LIMIT 5
        """,
        [cutoff_7d] + proj_params,
    ).fetchall()

    if obs_rows:
        lines.append("최근 언급 (Observation, 최근 7일):")
        for r in obs_rows:
            text = r["summary"] or r["content"]
            lines.append(f"  - [Obs] {text[:80]}")

    # 구분선 (기존 섹션과 분리)
    if lines:
        lines.append("")

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

    # ── v3.2: 승격 후보 (visit_count >= 5) ──────────────────────────
    proj_clause, proj_params = _project_clause()
    promo_rows = conn.execute(
        f"""
        SELECT id, type, visit_count, substr(content,1,60) as preview
        FROM nodes
        WHERE status='active' AND type IN ('Signal','Pattern','Observation')
        AND visit_count >= 5 {proj_clause}
        ORDER BY visit_count DESC LIMIT 3
        """,
        proj_params,
    ).fetchall()
    if promo_rows:
        lines.append("승격 후보 (반복 검증됨):")
        for r in promo_rows:
            lines.append(f"  - #{r['id']} [{r['type']}] v={r['visit_count']} {r['preview']}")

    # ── v3.2: 반복 실패 경고 ──────────────────────────────────────
    proj_clause, proj_params = _project_clause()
    fail_counts = conn.execute(
        f"""
        SELECT project, COUNT(*) as cnt FROM nodes
        WHERE type='Failure' AND status='active'
        AND created_at >= ? {proj_clause}
        GROUP BY project HAVING cnt >= 3
        ORDER BY cnt DESC LIMIT 3
        """,
        [cutoff_30d] + proj_params,
    ).fetchall()
    if fail_counts:
        lines.append("반복 실패 경고:")
        for r in fail_counts:
            lines.append(f"  - {r['project']}: {r['cnt']}건 (30일)")

    conn.close()

    if not lines:
        return ""
    return "\n".join(lines)


if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else ""
    result = get_context_cli(project)
    if result:
        print(result)
