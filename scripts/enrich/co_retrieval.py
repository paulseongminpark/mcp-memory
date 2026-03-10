"""Ontology v3 Step 3 — co-retrieval 계산.

recall_log에서 co-occurrence 패턴 계산 → edges에 반영.
recall_id 기반 세션화 (H2) + 레거시 fallback (query+timestamp).

실행: python -m scripts.enrich.co_retrieval [--min-co-count 5] [--dry-run]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from storage.sqlite_store import _db


def _get_hub_ids(conn, hub_percentile=95):
    """상위 N% degree 노드 식별."""
    degrees = conn.execute("""
        SELECT node_id, COUNT(*) as deg FROM (
            SELECT source_id as node_id FROM edges WHERE status='active'
            UNION ALL
            SELECT target_id as node_id FROM edges WHERE status='active'
        ) GROUP BY node_id ORDER BY deg DESC
    """).fetchall()
    if not degrees:
        return set()
    threshold_idx = int(len(degrees) * (1 - hub_percentile / 100))
    hub_threshold = degrees[threshold_idx][1] if threshold_idx < len(degrees) else 999
    return {d[0] for d in degrees if d[1] >= hub_threshold}


def calculate_co_retrieval(min_co_count=5, hub_percentile=95, dry_run=False):
    """recall_log에서 co-occurrence 계산 → edges에 반영."""
    stats = {"recall_id_sessions": 0, "legacy_sessions": 0,
             "pairs": 0, "hub_filtered": 0, "updated": 0}

    with _db() as conn:
        hub_ids = _get_hub_ids(conn, hub_percentile)
        print(f"허브 노드: {len(hub_ids)}개 (상위 {100-hub_percentile}%)")

        # 1. recall_id 기반 세션 (H2)
        recall_id_pairs = conn.execute("""
            WITH sessions AS (
                SELECT recall_id, GROUP_CONCAT(node_id) as nids
                FROM recall_log
                WHERE recall_id IS NOT NULL
                GROUP BY recall_id
                HAVING COUNT(*) >= 2
            )
            SELECT a.value as a_id, b.value as b_id, COUNT(*) as co_count
            FROM sessions s,
                 json_each('[' || s.nids || ']') a,
                 json_each('[' || s.nids || ']') b
            WHERE CAST(a.value AS INT) < CAST(b.value AS INT)
            GROUP BY a_id, b_id
            HAVING co_count >= ?
        """, (min_co_count,)).fetchall()
        stats["recall_id_sessions"] = len(recall_id_pairs)

        # 2. 레거시 fallback (query+timestamp)
        legacy_pairs = conn.execute("""
            WITH sessions AS (
                SELECT query, timestamp, GROUP_CONCAT(node_id) as nids
                FROM recall_log
                WHERE recall_id IS NULL
                GROUP BY query, timestamp
                HAVING COUNT(*) >= 2
            )
            SELECT a.value as a_id, b.value as b_id, COUNT(*) as co_count
            FROM sessions s,
                 json_each('[' || s.nids || ']') a,
                 json_each('[' || s.nids || ']') b
            WHERE CAST(a.value AS INT) < CAST(b.value AS INT)
            GROUP BY a_id, b_id
            HAVING co_count >= ?
        """, (min_co_count,)).fetchall()
        stats["legacy_sessions"] = len(legacy_pairs)

        # 병합
        pair_map = {}
        for a_id, b_id, co_count in list(recall_id_pairs) + list(legacy_pairs):
            key = (int(a_id), int(b_id))
            pair_map[key] = pair_map.get(key, 0) + co_count

        stats["pairs"] = len(pair_map)
        print(f"co-retrieval pairs: {len(pair_map)} (recall_id: {stats['recall_id_sessions']}, legacy: {stats['legacy_sessions']})")

        # edges 컬럼 존재 확인
        cols_e = {c[1] for c in conn.execute("PRAGMA table_info(edges)").fetchall()}
        if "co_retrieval_count" not in cols_e:
            conn.execute("ALTER TABLE edges ADD COLUMN co_retrieval_count INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE edges ADD COLUMN co_retrieval_boost REAL DEFAULT 0.0")

        # 3. edge 반영
        for (a, b), co_count in pair_map.items():
            if co_count < min_co_count:
                continue
            if a in hub_ids and b in hub_ids:
                stats["hub_filtered"] += 1
                continue

            boost = min(0.1 * (co_count - min_co_count + 1), 0.5)

            if not dry_run:
                # UPSERT: 기존 edge 있으면 update, 없으면 insert
                existing = conn.execute(
                    "SELECT id FROM edges WHERE source_id=? AND target_id=? AND relation='co_retrieved' AND status='active'",
                    (a, b)
                ).fetchone()

                if existing:
                    conn.execute("""
                        UPDATE edges SET co_retrieval_count=?, co_retrieval_boost=?
                        WHERE id=?
                    """, (co_count, boost, existing[0]))
                else:
                    conn.execute("""
                        INSERT INTO edges (source_id, target_id, relation, strength,
                            co_retrieval_count, co_retrieval_boost, status, created_at)
                        VALUES (?, ?, 'co_retrieved', ?, ?, ?, 'active', datetime('now'))
                    """, (a, b, boost, co_count, boost))

            stats["updated"] += 1

        if not dry_run:
            conn.commit()

    return stats


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    min_co_count = 5
    if "--min-co-count" in sys.argv:
        idx = sys.argv.index("--min-co-count")
        min_co_count = int(sys.argv[idx + 1])

    stats = calculate_co_retrieval(min_co_count=min_co_count, dry_run=dry_run)
    print(f"\n결과: {json.dumps(stats, indent=2)}")
