#!/usr/bin/env python3
"""Archive leftover hook nodes stored under project='dev'."""

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


def collect_candidates(conn: sqlite3.Connection, sample_limit: int = 20) -> dict:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, source, source_kind, type, node_role, source_ref,
               substr(replace(content, char(10), ' '), 1, 180) AS preview
        FROM nodes
        WHERE status='active'
          AND project='dev'
          AND source_kind='hook'
        ORDER BY id DESC
        """
    ).fetchall()
    return {
        "candidate_count": len(rows),
        "sample": [dict(row) for row in rows[:sample_limit]],
        "ids": [row["id"] for row in rows],
    }


def apply_archive(conn: sqlite3.Connection, ids: list[int]) -> dict:
    if not ids:
        return {"archived_nodes": 0, "updated_at": ""}
    now = datetime.now(timezone.utc).isoformat()
    ph = ",".join("?" * len(ids))
    cur = conn.execute(
        f"UPDATE nodes SET status='archived', updated_at=? WHERE id IN ({ph}) AND status='active'",
        [now, *ids],
    )
    conn.commit()
    return {"archived_nodes": cur.rowcount or 0, "updated_at": now}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="archive unresolved dev hook nodes")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="memory.db path")
    parser.add_argument("--apply", action="store_true", help="apply archive update")
    parser.add_argument("--report", type=Path, help="write JSON report")
    parser.add_argument("--sample-limit", type=int, default=20, help="sample row count")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(str(args.db))
    try:
        candidates = collect_candidates(conn, sample_limit=args.sample_limit)
        payload: dict[str, object] = {
            "db": str(args.db),
            "apply": args.apply,
            "before": {k: v for k, v in candidates.items() if k != "ids"},
        }
        if args.apply:
            payload["applied"] = apply_archive(conn, candidates["ids"])
            after = collect_candidates(conn, sample_limit=args.sample_limit)
            payload["after"] = {k: v for k, v in after.items() if k != "ids"}
    finally:
        conn.close()

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
