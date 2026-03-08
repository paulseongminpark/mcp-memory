"""checks/graph_health.py — 그래프 건강 상태 검증."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from checks import CheckResult


def run() -> list[CheckResult]:
    from storage.sqlite_store import _db

    results = []
    with _db() as conn:
        # 1. 총 edge 수
        total_edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        active_edges = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE status='active'"
        ).fetchone()[0]
        results.append(CheckResult(
            name="edge_counts",
            category="graph",
            status="PASS",
            details={"total": total_edges, "active": active_edges},
        ))

        # 2. edge relation 분포 상위 10개
        rel_dist = conn.execute("""
            SELECT relation, COUNT(*) as cnt
            FROM edges WHERE status='active'
            GROUP BY relation ORDER BY cnt DESC LIMIT 10
        """).fetchall()
        results.append(CheckResult(
            name="edge_relation_distribution",
            category="graph",
            status="PASS",
            details={"top_relations": {r[0]: r[1] for r in rel_dist}},
        ))

        # 3. 고립 노드 (incoming+outgoing edge 0) 수
        orphan_count = conn.execute("""
            SELECT COUNT(*) FROM nodes n
            WHERE n.status='active'
            AND NOT EXISTS (
                SELECT 1 FROM edges e
                WHERE e.status='active'
                AND (e.source_id=n.id OR e.target_id=n.id)
            )
        """).fetchone()[0]
        total_active = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE status='active'"
        ).fetchone()[0]
        results.append(CheckResult(
            name="orphan_nodes",
            category="graph",
            status="PASS" if orphan_count / max(total_active, 1) < 0.15 else "WARN",
            details={"orphan_count": orphan_count, "total_active": total_active},
        ))

        # 4. avg edge strength
        avg_strength = conn.execute(
            "SELECT AVG(strength) FROM edges WHERE status='active'"
        ).fetchone()[0] or 0.0
        results.append(CheckResult(
            name="avg_edge_strength",
            category="graph",
            status="PASS",
            details={"avg_strength": round(avg_strength, 4)},
        ))

        # 5. connected components 수 (SQL 기반 근사: 노드 중 isolated 비율)
        # 완전한 connected component는 NetworkX 없이 SQL로 정확히 구하기 어려우므로
        # 대신 "상호 연결된 노드 수 vs 전체"로 근사
        connected_nodes = conn.execute("""
            SELECT COUNT(DISTINCT n.id) FROM nodes n
            JOIN edges e ON e.status='active' AND (e.source_id=n.id OR e.target_id=n.id)
            WHERE n.status='active'
        """).fetchone()[0]
        results.append(CheckResult(
            name="connected_nodes_pct",
            category="graph",
            score=connected_nodes / max(total_active, 1),
            threshold=0.85,
            details={"connected": connected_nodes, "total": total_active},
        ))

    return results
