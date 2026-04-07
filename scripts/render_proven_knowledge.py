#!/usr/bin/env python3
"""proven_knowledge.md 생성 — 검증된 지식만 렌더.

출력:
  data/proven_knowledge.md  — knowledge_core + validated + high-signal + corrections
  data/merger_manifest.json — 반영 이력 추적

세션 시작 시 session_context.py가 이 artifact를 읽는다.
"""

import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
os.chdir(ROOT)

DB = os.path.join(ROOT, "data", "memory.db")
OUTPUT = os.path.join(ROOT, "data", "proven_knowledge.md")
MANIFEST = os.path.join(ROOT, "data", "merger_manifest.json")


def _query(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def collect_proven_nodes(conn):
    """렌더 기준에 맞는 노드 수집."""
    nodes = []

    # 1. knowledge_core — 무조건 포함
    rows = _query(conn, """
        SELECT id, type, content, summary, project, quality_score, visit_count,
               confidence, epistemic_status, node_role
        FROM nodes
        WHERE node_role = 'knowledge_core' AND status = 'active'
        ORDER BY quality_score DESC
    """)
    for r in rows:
        nodes.append(dict(r) | {"reason": "knowledge_core"})

    seen = {r["id"] for r in rows}

    # 2. validated AND quality >= 0.85
    rows = _query(conn, """
        SELECT id, type, content, summary, project, quality_score, visit_count,
               confidence, epistemic_status, node_role
        FROM nodes
        WHERE epistemic_status = 'validated' AND status = 'active'
          AND quality_score >= 0.85 AND id NOT IN ({})
        ORDER BY quality_score DESC
    """.format(",".join(str(s) for s in seen) or "0"))
    for r in rows:
        if r["id"] not in seen:
            nodes.append(dict(r) | {"reason": "validated"})
            seen.add(r["id"])

    # 3. Signal with visit_count >= 5
    rows = _query(conn, """
        SELECT id, type, content, summary, project, quality_score, visit_count,
               confidence, epistemic_status, node_role
        FROM nodes
        WHERE type = 'Signal' AND status = 'active'
          AND visit_count >= 5
        ORDER BY visit_count DESC, quality_score DESC LIMIT 15
    """)
    for r in rows:
        if r["id"] not in seen:
            nodes.append(dict(r) | {"reason": "high_signal"})
            seen.add(r["id"])

    # 4. Active Corrections
    rows = _query(conn, """
        SELECT id, type, content, summary, project, quality_score, visit_count,
               confidence, epistemic_status, node_role
        FROM nodes
        WHERE type = 'Correction' AND status = 'active'
        ORDER BY created_at DESC LIMIT 10
    """)
    for r in rows:
        if r["id"] not in seen:
            nodes.append(dict(r) | {"reason": "correction"})
            seen.add(r["id"])

    return nodes


def render_markdown(nodes):
    """프로젝트별 그룹핑된 proven_knowledge.md 생성."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # v5: epistemic separation — core/signal과 correction 분리
    core_nodes = [n for n in nodes if n["reason"] != "correction"]
    correction_nodes = [n for n in nodes if n["reason"] == "correction"]

    by_project = defaultdict(list)
    for n in core_nodes:
        by_project[n["project"] or "system"].append(n)

    lines = [
        "# Proven Knowledge",
        f"_Auto-generated: {now} | {len(nodes)} nodes_\n",
    ]

    # Section 1: Core Knowledge
    lines.append("## Core Knowledge")
    lines.append("검증된 핵심 지식. knowledge_core + validated + high-signal.\n")

    for proj in sorted(by_project.keys()):
        proj_nodes = by_project[proj]
        lines.append(f"### {proj}")
        for n in proj_nodes:
            content = (n["summary"] or n["content"] or "")[:120]
            content = content.replace("\n", " ").strip()
            tag = n["reason"]
            q = n["quality_score"] or 0
            v = n["visit_count"] or 0
            conf = n["confidence"] or 0
            lines.append(
                f"- **[{n['type']}]** #{n['id']} (q={q:.2f} v={v} conf={conf:.2f} _{tag}_) "
                f"{content}"
            )
        lines.append("")

    # Section 2: Corrections / Warnings (분리)
    if correction_nodes:
        lines.append("## Corrections / Warnings")
        lines.append("교정된 노드. 해당 정보를 신뢰하지 마세요.\n")
        for n in correction_nodes:
            content = (n["content"] or "")[:120].replace("\n", " ").strip()
            lines.append(f"- **[Correction]** #{n['id']} {content}")
        lines.append("")

    return "\n".join(lines)


def update_manifest(nodes):
    """merger_manifest.json 갱신 — 기존 항목 보존, 새 항목 추가."""
    now = datetime.now(timezone.utc).isoformat()

    if os.path.exists(MANIFEST):
        with open(MANIFEST, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = {"entries": [], "last_generated": ""}

    existing_ids = {e["node_id"] for e in manifest["entries"]}

    for n in nodes:
        if n["id"] not in existing_ids:
            manifest["entries"].append({
                "node_id": n["id"],
                "type": n["type"],
                "project": n["project"] or "system",
                "reason": n["reason"],
                "rendered_to": "data/proven_knowledge.md",
                "first_rendered": now,
            })

    manifest["last_generated"] = now
    manifest["total_nodes"] = len(nodes)

    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return len(manifest["entries"])


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    nodes = collect_proven_nodes(conn)
    conn.close()

    md = render_markdown(nodes)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(md)

    manifest_count = update_manifest(nodes)

    print(f"proven_knowledge.md: {len(nodes)} nodes rendered")
    print(f"merger_manifest.json: {manifest_count} entries")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
