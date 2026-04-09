#!/usr/bin/env python3
"""온톨로지 월간 리뷰 리포트.

실행: python3 scripts/ontology_review.py
출력: 터미널 + data/ontology-review.md
"""

import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH, DATA_DIR
from scripts.health_metrics import get_health_snapshot

def run_review() -> str:
    if not DB_PATH.exists():
        return "DB not found"

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    lines = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines.append(f"# Ontology Review — {now}\n")

    # 1. 타입별 분포
    lines.append("## 1. 노드 타입 분포\n")
    rows = conn.execute(
        "SELECT type, COUNT(*) c FROM nodes WHERE status='active' GROUP BY type ORDER BY c DESC"
    ).fetchall()
    total = sum(r["c"] for r in rows)
    lines.append(f"총 {total}개 노드\n")
    lines.append("| 타입 | 개수 | 비율 |")
    lines.append("|------|------|------|")
    for r in rows:
        pct = r["c"] / total * 100 if total else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"| {r['type']} | {r['c']} | {bar} {pct:.0f}% |")

    # 2. 안 쓰이는 타입
    lines.append("\n## 2. 미사용 타입\n")
    from ontology.validators import get_valid_node_types
    used = {r["type"] for r in rows}
    unused = sorted(set(get_valid_node_types()) - used)
    if unused:
        lines.append(f"{len(unused)}개: {', '.join(unused)}")
    else:
        lines.append("없음 — 전 타입 사용 중")

    # 3. Unclassified 분석
    lines.append("\n## 3. Unclassified 노드\n")
    unclassified = conn.execute(
        "SELECT id, content, metadata FROM nodes WHERE status='active' AND type = 'Unclassified'"
    ).fetchall()
    if unclassified:
        lines.append(f"{len(unclassified)}건:")
        for u in unclassified:
            lines.append(f"- #{u['id']}: {u['content'][:80]}")
        if len(unclassified) >= 3:
            lines.append("\n⚠️ 3건 이상 — 새 타입 추가 검토 필요")
    else:
        lines.append("없음")

    # 4. 관계 밀도
    lines.append("\n## 4. 관계 그래프 통계\n")
    health = get_health_snapshot(conn)
    edge_count = health["active_edges"]
    lines.append(f"총 {edge_count}개 에지")

    if edge_count > 0:
        rel_dist = conn.execute(
            "SELECT relation, COUNT(*) c FROM edges WHERE status='active' GROUP BY relation ORDER BY c DESC"
        ).fetchall()
        lines.append("\n| 관계 | 개수 |")
        lines.append("|------|------|")
        for r in rel_dist:
            lines.append(f"| {r['relation']} | {r['c']} |")

    lines.append(f"\n고립 노드 (active-only): {health['true_orphans']}개 / {total}개 ({health['true_orphans']/total*100:.0f}%)")
    lines.append(
        "enrichment coverage: "
        f"summary {health['summary_present']}/{total}, "
        f"key_concepts {health['key_concepts_present']}/{total}, "
        f"retrieval_queries {health['retrieval_queries_present']}/{total}, "
        f"atomic_claims {health['atomic_claims_present']}/{total}"
    )
    lines.append(
        f"stale 30d / zero-visit: created_at {health['stale_zero_visit_created_30d']}, "
        f"updated_at {health['stale_zero_visit_updated_30d']}"
    )

    # 5. 프로젝트별 분포
    lines.append("\n## 5. 프로젝트별 분포\n")
    proj_rows = conn.execute(
        "SELECT COALESCE(NULLIF(project,''), '(없음)') p, COUNT(*) c FROM nodes WHERE status='active' GROUP BY p ORDER BY c DESC"
    ).fetchall()
    lines.append("| 프로젝트 | 개수 |")
    lines.append("|----------|------|")
    for r in proj_rows:
        lines.append(f"| {r['p']} | {r['c']} |")

    # 6. 최근 7일 활동
    lines.append("\n## 6. 최근 7일 활동\n")
    recent = conn.execute("""
        SELECT DATE(created_at) d, COUNT(*) c
        FROM nodes
        WHERE status='active'
          AND created_at > datetime('now', '-7 days')
        GROUP BY d ORDER BY d DESC
    """).fetchall()
    if recent:
        for r in recent:
            lines.append(f"- {r['d']}: {r['c']}건")
    else:
        lines.append("없음")

    conn.close()

    report = "\n".join(lines)

    # 파일 저장
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "ontology-review.md"
    out.write_text(report, encoding="utf-8")

    return report


if __name__ == "__main__":
    print(run_review())
