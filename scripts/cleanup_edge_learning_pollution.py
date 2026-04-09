#!/usr/bin/env python3
"""eval/live 혼합으로 오염된 edge 학습 신호를 정리한다.

기본 정책:
- active edge frequency/last_activated 리셋
- base_strength 있는 edge는 strength 원복
- co_retrieval edge는 archive 후 goldset 제외 recall_log 기준으로 재생성
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import DB_PATH
from scripts.enrich.co_retrieval import calculate_co_retrieval, load_goldset_queries

MARKER_KEY = "edge_learning_cleanup_v1_applied_at"
MARKER_FREQ_KEY = "edge_learning_cleanup_v1_frequency_reset"
MARKER_STRENGTH_KEY = "edge_learning_cleanup_v1_strength_restored"
MARKER_GOLDSET_KEY = "edge_learning_cleanup_v1_goldset"


def _default_goldset_path() -> Path:
    primary = ROOT / "scripts" / "eval" / "goldset_v4.yaml"
    if primary.exists():
        return primary
    return ROOT / "scripts" / "eval" / "goldset_corrected.yaml"


def read_marker(conn: sqlite3.Connection) -> dict | None:
    rows = conn.execute(
        """
        SELECT key, value
        FROM meta
        WHERE key IN (?, ?, ?, ?)
        """,
        (MARKER_KEY, MARKER_FREQ_KEY, MARKER_STRENGTH_KEY, MARKER_GOLDSET_KEY),
    ).fetchall()
    if not rows:
        return None
    marker = {row["key"]: row["value"] for row in rows}
    applied_at = marker.get(MARKER_KEY)
    if not applied_at:
        return None
    return {
        "applied_at": applied_at,
        "frequency_reset": int(marker.get(MARKER_FREQ_KEY) or 0),
        "strength_restored": int(marker.get(MARKER_STRENGTH_KEY) or 0),
        "goldset": marker.get(MARKER_GOLDSET_KEY) or "",
    }


def collect_stats(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS active_edges,
            SUM(CASE WHEN COALESCE(frequency, 0) > 0 THEN 1 ELSE 0 END) AS edges_with_frequency,
            ROUND(COALESCE(SUM(frequency), 0), 6) AS frequency_sum,
            SUM(CASE WHEN last_activated IS NOT NULL THEN 1 ELSE 0 END) AS last_activated_nonnull,
            SUM(CASE
                    WHEN base_strength IS NOT NULL
                     AND ABS(COALESCE(strength, 0) - COALESCE(base_strength, 0)) > 0.000001
                    THEN 1 ELSE 0
                END) AS strength_restore_candidates,
            SUM(CASE WHEN generation_method = 'co_retrieval' THEN 1 ELSE 0 END) AS co_retrieval_active
        FROM edges
        WHERE status='active'
        """
    ).fetchone()

    top_frequency = [
        dict(r) for r in conn.execute(
            """
            SELECT id, generation_method, relation,
                   ROUND(COALESCE(base_strength, 0), 6) AS base_strength,
                   ROUND(COALESCE(strength, 0), 6) AS strength,
                   ROUND(COALESCE(frequency, 0), 6) AS frequency
            FROM edges
            WHERE status='active' AND COALESCE(frequency, 0) > 0
            ORDER BY COALESCE(frequency, 0) DESC, id ASC
            LIMIT 15
            """
        ).fetchall()
    ]
    return {**dict(row), "top_frequency_edges": top_frequency}


def apply_edge_reset(conn: sqlite3.Connection, goldset_label: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    cur_freq = conn.execute(
        """
        UPDATE edges
           SET frequency = 0,
               last_activated = NULL,
               updated_at = ?
         WHERE status='active'
           AND (COALESCE(frequency, 0) != 0 OR last_activated IS NOT NULL)
        """,
        (now,),
    )
    cur_strength = conn.execute(
        """
        UPDATE edges
           SET strength = base_strength,
               updated_at = ?
         WHERE status='active'
           AND base_strength IS NOT NULL
           AND ABS(COALESCE(strength, 0) - COALESCE(base_strength, 0)) > 0.000001
        """,
        (now,),
    )
    conn.executemany(
        """
        INSERT INTO meta (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        [
            (MARKER_KEY, now, now),
            (MARKER_FREQ_KEY, str(cur_freq.rowcount or 0), now),
            (MARKER_STRENGTH_KEY, str(cur_strength.rowcount or 0), now),
            (MARKER_GOLDSET_KEY, goldset_label, now),
        ],
    )
    conn.commit()
    return {
        "frequency_reset_edges": cur_freq.rowcount or 0,
        "strength_restored_edges": cur_strength.rowcount or 0,
        "updated_at": now,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="cleanup polluted edge learning signals")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="memory.db path")
    parser.add_argument("--goldset", type=Path, default=_default_goldset_path(), help="goldset path to exclude")
    parser.add_argument("--apply", action="store_true", help="실제 edge cleanup 수행")
    parser.add_argument("--force", action="store_true", help="marker가 있어도 강제 수행")
    parser.add_argument("--report", type=Path, help="JSON report output path")
    parser.add_argument("--min-co-count", type=int, default=5, help="co_retrieval rebuild threshold")
    parser.add_argument("--hub-percentile", type=int, default=95, help="co_retrieval hub filter percentile")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    try:
        marker = read_marker(conn)
        stats = collect_stats(conn)
    finally:
        conn.close()

    exclude_queries = load_goldset_queries(args.goldset)
    payload: dict[str, object] = {
        "db": str(args.db),
        "goldset": str(args.goldset),
        "apply": args.apply,
        "force": args.force,
        "marker": marker,
        "stats": stats,
        "excluded_queries": len(exclude_queries),
    }

    if args.apply:
        if marker and not args.force:
            payload["applied"] = {
                "status": "skipped",
                "reason": "cleanup marker exists",
                "marker": marker,
            }
        else:
            conn = sqlite3.connect(str(args.db))
            conn.row_factory = sqlite3.Row
            try:
                payload["applied"] = apply_edge_reset(conn, str(args.goldset))
            finally:
                conn.close()
            rebuild_stats = calculate_co_retrieval(
                min_co_count=args.min_co_count,
                hub_percentile=args.hub_percentile,
                exclude_queries=exclude_queries,
                archive_existing=True,
                dry_run=False,
            )
            payload["co_retrieval_rebuild"] = rebuild_stats

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
