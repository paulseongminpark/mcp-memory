"""checks/data_integrity.py — 데이터 무결성 검증."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from checks import CheckResult
from config import VERIFY_THRESHOLDS


def run() -> list[CheckResult]:
    from storage.sqlite_store import _db

    results = []
    with _db() as conn:
        # 1. NULL layer 노드 수 (Unclassified 제외, active만)
        null_layer = conn.execute("""
            SELECT COUNT(*) FROM nodes
            WHERE status='active' AND layer IS NULL AND type != 'Unclassified'
        """).fetchone()[0]
        total_active = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE status='active'"
        ).fetchone()[0]
        null_layer_pct = null_layer / total_active if total_active else 0.0
        results.append(CheckResult(
            name="null_layer_pct",
            category="data",
            score=null_layer_pct,
            threshold=VERIFY_THRESHOLDS["null_layer_pct"],
            higher_is_better=False,
            details={"null_layer_count": null_layer, "total_active": total_active},
        ))

        # 2. content_hash 보유율
        has_hash = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE status='active' AND content_hash IS NOT NULL"
        ).fetchone()[0]
        hash_coverage = has_hash / total_active if total_active else 1.0
        results.append(CheckResult(
            name="content_hash_coverage",
            category="data",
            score=hash_coverage,
            threshold=VERIFY_THRESHOLDS["content_hash_coverage"],
            details={"has_hash": has_hash, "total_active": total_active},
        ))

        # 3. 중복 content_hash 그룹 수
        dup_groups = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT content_hash FROM nodes
                WHERE content_hash IS NOT NULL AND status='active'
                GROUP BY content_hash HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
        results.append(CheckResult(
            name="duplicate_content_hash_groups",
            category="data",
            score=float(dup_groups),
            threshold=0.0,
            details={"duplicate_groups": dup_groups},
        ))

        # 4. status='deleted' 노드의 edge 정리 여부
        deleted_nodes = conn.execute(
            "SELECT id FROM nodes WHERE status='deleted'"
        ).fetchall()
        deleted_ids = [r[0] for r in deleted_nodes]
        if deleted_ids:
            placeholders = ",".join("?" * len(deleted_ids))
            active_edges_for_deleted = conn.execute(f"""
                SELECT COUNT(*) FROM edges
                WHERE (source_id IN ({placeholders}) OR target_id IN ({placeholders}))
                AND status='active'
            """, deleted_ids + deleted_ids).fetchone()[0]
        else:
            active_edges_for_deleted = 0
        results.append(CheckResult(
            name="deleted_node_edges_cleaned",
            category="data",
            status="PASS" if active_edges_for_deleted == 0 else "WARN",
            details={"active_edges_for_deleted": active_edges_for_deleted},
        ))

        # 5. orphan 노드 (edge 0개) 비율
        orphan_count = conn.execute("""
            SELECT COUNT(*) FROM nodes n
            WHERE n.status='active'
            AND NOT EXISTS (
                SELECT 1 FROM edges e
                WHERE e.status='active'
                AND (e.source_id=n.id OR e.target_id=n.id)
            )
        """).fetchone()[0]
        orphan_pct = orphan_count / total_active if total_active else 0.0
        results.append(CheckResult(
            name="orphan_pct",
            category="data",
            score=orphan_pct,
            threshold=VERIFY_THRESHOLDS["orphan_pct"],
            higher_is_better=False,
            details={"orphan_count": orphan_count, "total_active": total_active},
        ))

    return results
