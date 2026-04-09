#!/usr/bin/env python3
"""auto_promote.py — 성장 사이클 자동화.

단순 조건으로 승격 후보를 찾아 promote_node()를 실행한다.
3-Gate 중 Gate 3(MDL, OpenAI 의존)을 제거하고 Gate 1+2만 사용.

Usage:
  python scripts/auto_promote.py              # dry-run (기본)
  python scripts/auto_promote.py --execute    # 실제 승격
  python scripts/auto_promote.py --verbose    # 상세 출력
"""

import json
import os
import sys

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from config import VALID_PROMOTIONS, PROMOTE_LAYER
from storage import sqlite_store
from tools.promote_node import swr_readiness, promotion_frequency_check


def find_candidates(verbose: bool = False) -> list[dict]:
    """승격 가능한 노드를 찾는다.

    조건 (2026-04-09 완화):
      1. 현재 타입이 VALID_PROMOTIONS에 소스로 존재
      2. Gate 2: visit_count >= 3
      3. Quality floor: quality_score >= 0.75
      4. edges >= 3 (고립 노드 제외)
         — visit >= 10이면 edges >= 2로 완화 (충분히 검증된 노드)
      5. 이웃 project >= 1 (같은 프로젝트 내 연결도 유효)
         — edges >= 5이면 project 조건 면제 (풍부한 연결 자체가 증거)
      6. Gate 1: SWR readiness > threshold (경고만)
    """
    candidates = []
    promotable_types = list(VALID_PROMOTIONS.keys())

    with sqlite_store._db() as conn:
        rows = conn.execute(
            f"""SELECT id, type, visit_count, quality_score, project,
                       node_role, epistemic_status
                FROM nodes
                WHERE status = 'active'
                  AND type IN ({','.join('?' for _ in promotable_types)})
                  AND (visit_count >= 3 OR visit_count IS NULL)
                  AND epistemic_status != 'validated'
                ORDER BY visit_count DESC""",
            promotable_types,
        ).fetchall()

        for row in rows:
            nid, ntype, vc, qs, project, role, epist = row
            vc = vc or 0
            qs = qs or 0.0

            # Gate 2: frequency check
            if vc < 3:
                continue

            # Quality floor
            if qs < 0.75:
                if verbose:
                    print(f"  SKIP #{nid} ({ntype}): quality {qs:.2f} < 0.75")
                continue

            # Edge count check — visit >= 10이면 edges >= 2로 완화
            edge_count = conn.execute(
                """SELECT COUNT(*) FROM edges
                   WHERE (source_id=? OR target_id=?) AND status='active'""",
                (nid, nid),
            ).fetchone()[0]

            min_edges = 2 if vc >= 10 else 3
            if edge_count < min_edges:
                if verbose:
                    print(f"  SKIP #{nid} ({ntype}): edges {edge_count} < {min_edges}")
                continue

            # Cross-domain check — edges >= 5이면 project 조건 면제
            neighbor_projects = conn.execute(
                """SELECT DISTINCT n.project FROM edges e
                   JOIN nodes n ON n.id = CASE WHEN e.source_id=? THEN e.target_id ELSE e.source_id END
                   WHERE (e.source_id=? OR e.target_id=?) AND e.status='active'
                     AND n.project IS NOT NULL AND n.project != ''""",
                (nid, nid, nid),
            ).fetchall()
            n_projects = len(set(p[0] for p in neighbor_projects))

            if edge_count < 5 and n_projects < 1:
                if verbose:
                    print(f"  SKIP #{nid} ({ntype}): neighbor projects {n_projects} < 1 (edges {edge_count} < 5)")
                continue

            # Gate 1: SWR readiness (optional — 통과 못하면 경고만)
            swr_ok, swr_score = swr_readiness(nid)

            # Determine target type (first valid target)
            targets = VALID_PROMOTIONS[ntype]
            target = targets[0]  # 기본: 첫 번째 유효 타겟

            candidates.append({
                "id": nid,
                "type": ntype,
                "target": target,
                "visit_count": vc,
                "quality": qs,
                "edges": edge_count,
                "neighbor_projects": n_projects,
                "swr_ok": swr_ok,
                "swr_score": swr_score,
                "project": project,
            })

    return candidates


def execute_promotions(candidates: list[dict], dry_run: bool = True) -> dict:
    """후보 노드들을 승격한다."""
    from tools.promote_node import promote_node

    promoted = 0
    failed = 0
    results = []

    for c in candidates:
        if dry_run:
            results.append({
                "id": c["id"],
                "promotion": f"{c['type']} → {c['target']}",
                "vc": c["visit_count"],
                "qs": c["quality"],
                "swr": c["swr_score"],
                "action": "DRY_RUN",
            })
            continue

        result = promote_node(
            node_id=c["id"],
            target_type=c["target"],
            reason=f"auto_promote: vc={c['visit_count']}, qs={c['quality']:.2f}, edges={c['edges']}, projects={c['neighbor_projects']}",
            skip_gates=True,  # 이미 위에서 검증함
        )

        if result.get("error"):
            failed += 1
            results.append({"id": c["id"], "error": result["error"]})
        else:
            promoted += 1
            results.append({
                "id": c["id"],
                "promotion": f"{c['type']} → {c['target']}",
                "action": "PROMOTED",
            })

    return {
        "total_candidates": len(candidates),
        "promoted": promoted,
        "failed": failed,
        "dry_run": dry_run,
        "results": results,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Auto-promote mature nodes")
    parser.add_argument("--execute", action="store_true", help="Actually promote (default: dry-run)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    print("=== Auto-Promote ===")
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY-RUN'}")
    print()

    candidates = find_candidates(verbose=args.verbose)
    print(f"Found {len(candidates)} promotion candidates:")
    print()

    for c in candidates:
        swr_mark = "OK" if c["swr_ok"] else "WARN"
        print(f"  #{c['id']:>5} {c['type']:>12} -> {c['target']:<12} "
              f"vc={c['visit_count']:>3} qs={c['quality']:.2f} "
              f"edges={c['edges']:>2} projects={c['neighbor_projects']} "
              f"swr={c['swr_score']:.3f}[{swr_mark}]")

    if not candidates:
        print("  (none)")
        sys.exit(0)

    print()
    result = execute_promotions(candidates, dry_run=not args.execute)

    if args.execute:
        print(f"\nPromoted: {result['promoted']}, Failed: {result['failed']}")
    else:
        print(f"\n[DRY-RUN] Would promote {result['total_candidates']} nodes. Use --execute to apply.")
