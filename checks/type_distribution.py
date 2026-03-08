"""checks/type_distribution.py — 타입/관계 분포 검증."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from checks import CheckResult


def run() -> list[CheckResult]:
    from storage.sqlite_store import _db
    from config import PROMOTE_LAYER, ALL_RELATIONS

    results = []
    with _db() as conn:
        # 1. 노드 타입별 count (상위 20)
        type_dist = conn.execute("""
            SELECT type, COUNT(*) as cnt
            FROM nodes WHERE status='active'
            GROUP BY type ORDER BY cnt DESC LIMIT 20
        """).fetchall()
        type_counts = {r[0]: r[1] for r in type_dist}

        # 2. 미사용 타입 (count=0)
        all_types = set(PROMOTE_LAYER.keys()) - {"Unclassified"}
        used_types = set(type_counts.keys())
        unused_types = sorted(all_types - used_types)

        results.append(CheckResult(
            name="node_type_distribution",
            category="type",
            status="PASS",
            details={
                "top_20": type_counts,
                "unused_types": unused_types,
                "unused_count": len(unused_types),
            },
        ))

        # 3. 관계 타입별 count (상위 20)
        rel_dist = conn.execute("""
            SELECT relation, COUNT(*) as cnt
            FROM edges WHERE status='active'
            GROUP BY relation ORDER BY cnt DESC LIMIT 20
        """).fetchall()
        rel_counts = {r[0]: r[1] for r in rel_dist}

        # 4. 미사용 관계
        used_relations = set(rel_counts.keys())
        unused_relations = sorted(set(ALL_RELATIONS) - used_relations)
        results.append(CheckResult(
            name="relation_type_distribution",
            category="type",
            status="PASS",
            details={
                "top_20": rel_counts,
                "unused_relations": unused_relations,
                "unused_count": len(unused_relations),
            },
        ))

        # 5. 레이어별 노드 분포
        layer_dist = conn.execute("""
            SELECT layer, COUNT(*) as cnt
            FROM nodes WHERE status='active'
            GROUP BY layer ORDER BY layer
        """).fetchall()
        layer_counts = {str(r[0]): r[1] for r in layer_dist}
        results.append(CheckResult(
            name="layer_distribution",
            category="type",
            status="PASS",
            details={"by_layer": layer_counts},
        ))

    return results
