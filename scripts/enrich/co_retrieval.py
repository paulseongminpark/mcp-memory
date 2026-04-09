"""Ontology v3 Step 3 — co-retrieval 계산.

recall_log에서 co-occurrence 패턴 계산 → edges에 반영.
recall_id 기반 세션화 (H2) + 레거시 fallback (query+timestamp).

실행:
  python -m scripts.enrich.co_retrieval [--min-co-count 5] [--dry-run]
  python -m scripts.enrich.co_retrieval --exclude-goldset --archive-existing
"""

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from storage.sqlite_store import _db

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def load_goldset_queries(goldset_path: str | Path) -> set[str]:
    path = Path(goldset_path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    queries = {
        (item.get("query") or "").strip()
        for item in data.get("queries", [])
        if (item.get("query") or "").strip()
    }
    return queries


def _build_query_exclusion_clause(exclude_queries: set[str] | None) -> tuple[str, list[str]]:
    if not exclude_queries:
        return "", []
    ordered = sorted(q for q in exclude_queries if q)
    if not ordered:
        return "", []
    placeholders = ",".join("?" for _ in ordered)
    return f" AND query NOT IN ({placeholders})", ordered


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


def calculate_co_retrieval(
    min_co_count=5,
    hub_percentile=95,
    dry_run=False,
    exclude_queries: set[str] | None = None,
    archive_existing: bool = False,
):
    """recall_log에서 co-occurrence 계산 → edges에 반영."""
    stats = {"recall_id_sessions": 0, "legacy_sessions": 0,
             "pairs": 0, "hub_filtered": 0, "updated": 0,
             "excluded_queries": len(exclude_queries or []),
             "archived_existing": 0}

    with _db() as conn:
        hub_ids = _get_hub_ids(conn, hub_percentile)
        print(f"허브 노드: {len(hub_ids)}개 (상위 {100-hub_percentile}%)")
        query_filter_sql, query_filter_params = _build_query_exclusion_clause(exclude_queries)

        if archive_existing and not dry_run:
            cur = conn.execute(
                """
                UPDATE edges
                   SET status='archived', updated_at=datetime('now')
                 WHERE status='active'
                   AND generation_method='co_retrieval'
                """
            )
            stats["archived_existing"] = cur.rowcount if cur.rowcount is not None else 0

        # 1. recall_id 기반 세션 (H2)
        recall_id_pairs = conn.execute("""
            WITH sessions AS (
                SELECT recall_id, GROUP_CONCAT(node_id) as nids
                FROM recall_log
                WHERE recall_id IS NOT NULL
                {query_filter_sql}
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
        """.format(query_filter_sql=query_filter_sql), query_filter_params + [min_co_count]).fetchall()
        stats["recall_id_sessions"] = len(recall_id_pairs)

        # 2. 레거시 fallback (query+timestamp)
        legacy_pairs = conn.execute("""
            WITH sessions AS (
                SELECT query, timestamp, GROUP_CONCAT(node_id) as nids
                FROM recall_log
                WHERE recall_id IS NULL
                {query_filter_sql}
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
        """.format(query_filter_sql=query_filter_sql), query_filter_params + [min_co_count]).fetchall()
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
                        UPDATE edges
                           SET co_retrieval_count=?,
                               co_retrieval_boost=?,
                               strength=?,
                               base_strength=?,
                               frequency=0,
                               last_activated=NULL,
                               generation_method='co_retrieval',
                               updated_at=datetime('now')
                        WHERE id=?
                    """, (co_count, boost, boost, boost, existing[0]))
                else:
                    conn.execute("""
                        INSERT INTO edges (
                            source_id, target_id, relation, strength, base_strength,
                            frequency, last_activated, co_retrieval_count,
                            co_retrieval_boost, status, created_at, updated_at,
                            generation_method
                        )
                        VALUES (
                            ?, ?, 'co_retrieved', ?, ?, 0, NULL, ?, ?, 'active',
                            datetime('now'), datetime('now'), 'co_retrieval'
                        )
                    """, (a, b, boost, boost, co_count, boost))

            stats["updated"] += 1

        if not dry_run:
            conn.commit()

    return stats


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    min_co_count = 5
    exclude_queries: set[str] | None = None
    archive_existing = "--archive-existing" in sys.argv

    if "--min-co-count" in sys.argv:
        idx = sys.argv.index("--min-co-count")
        min_co_count = int(sys.argv[idx + 1])
    if "--exclude-goldset" in sys.argv:
        goldset_path = Path(__file__).resolve().parent.parent / "eval" / "goldset_v4.yaml"
        if not goldset_path.exists():
            goldset_path = Path(__file__).resolve().parent.parent / "eval" / "goldset_corrected.yaml"
        exclude_queries = load_goldset_queries(goldset_path)
    if "--goldset" in sys.argv:
        idx = sys.argv.index("--goldset")
        exclude_queries = load_goldset_queries(sys.argv[idx + 1])

    stats = calculate_co_retrieval(
        min_co_count=min_co_count,
        dry_run=dry_run,
        exclude_queries=exclude_queries,
        archive_existing=archive_existing,
    )
    print(f"\n결과: {json.dumps(stats, indent=2)}")
