#!/usr/bin/env python3
"""Archive active edges whose endpoints are no longer active."""

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

from config import DB_PATH


def collect_stats(conn: sqlite3.Connection, sample_limit: int = 20) -> dict:
    conn.row_factory = sqlite3.Row
    stale_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM edges e
        JOIN nodes s ON s.id = e.source_id
        JOIN nodes t ON t.id = e.target_id
        WHERE e.status='active'
          AND (s.status!='active' OR t.status!='active')
        """
    ).fetchone()[0]
    active_active = conn.execute(
        """
        SELECT COUNT(*)
        FROM edges e
        JOIN nodes s ON s.id = e.source_id
        JOIN nodes t ON t.id = e.target_id
        WHERE e.status='active'
          AND s.status='active'
          AND t.status='active'
        """
    ).fetchone()[0]
    samples = [
        dict(row)
        for row in conn.execute(
            """
            SELECT e.id, e.relation, e.generation_method,
                   s.id AS source_id, s.status AS source_status, s.project AS source_project,
                   t.id AS target_id, t.status AS target_status, t.project AS target_project
            FROM edges e
            JOIN nodes s ON s.id = e.source_id
            JOIN nodes t ON t.id = e.target_id
            WHERE e.status='active'
              AND (s.status!='active' OR t.status!='active')
            ORDER BY e.id DESC
            LIMIT ?
            """,
            (sample_limit,),
        ).fetchall()
    ]
    by_relation = [
        {"relation": row[0], "count": row[1]}
        for row in conn.execute(
            """
            SELECT e.relation, COUNT(*)
            FROM edges e
            JOIN nodes s ON s.id = e.source_id
            JOIN nodes t ON t.id = e.target_id
            WHERE e.status='active'
              AND (s.status!='active' OR t.status!='active')
            GROUP BY e.relation
            ORDER BY COUNT(*) DESC, e.relation ASC
            LIMIT 20
            """
        ).fetchall()
    ]
    return {
        "stale_edge_count": stale_count,
        "active_active_edge_count": active_active,
        "sample": samples,
        "by_relation": by_relation,
    }


def apply_archive(conn: sqlite3.Connection) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """
        UPDATE edges
           SET status='archived',
               updated_at=?
         WHERE status='active'
           AND (
                EXISTS (SELECT 1 FROM nodes s WHERE s.id = edges.source_id AND s.status!='active')
             OR EXISTS (SELECT 1 FROM nodes t WHERE t.id = edges.target_id AND t.status!='active')
           )
        """,
        (now,),
    )
    conn.commit()
    return {"archived_edges": cur.rowcount or 0, "updated_at": now}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="archive active edges touching archived nodes")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="memory.db path")
    parser.add_argument("--apply", action="store_true", help="apply archive update")
    parser.add_argument("--report", type=Path, help="write JSON report")
    parser.add_argument("--sample-limit", type=int, default=20, help="sample row count")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(str(args.db))
    try:
        before = collect_stats(conn, sample_limit=args.sample_limit)
        payload: dict[str, object] = {
            "db": str(args.db),
            "apply": args.apply,
            "before": before,
        }
        if args.apply:
            payload["applied"] = apply_archive(conn)
            payload["after"] = collect_stats(conn, sample_limit=args.sample_limit)
    finally:
        conn.close()

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
