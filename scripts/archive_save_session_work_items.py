#!/usr/bin/env python3
"""Legacy save_session work_item 노드를 archive-first로 정리한다."""

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


def collect_candidates(conn: sqlite3.Connection, limit: int = 20) -> dict:
    count = conn.execute(
        """
        SELECT COUNT(*)
        FROM nodes
        WHERE status = 'active'
          AND source = 'save_session'
          AND node_role = 'work_item'
          AND type IN ('Decision', 'Question')
        """
    ).fetchone()[0]

    samples = [
        dict(row) for row in conn.execute(
            """
            SELECT id, type, project, LENGTH(TRIM(COALESCE(content, ''))) AS content_len,
                   substr(content, 1, 120) AS content
            FROM nodes
            WHERE status = 'active'
              AND source = 'save_session'
              AND node_role = 'work_item'
              AND type IN ('Decision', 'Question')
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    ]

    return {
        "candidate_count": int(count),
        "samples": samples,
    }


def apply_archive(conn: sqlite3.Connection) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    rows = conn.execute(
        """
        SELECT id
        FROM nodes
        WHERE status = 'active'
          AND source = 'save_session'
          AND node_role = 'work_item'
          AND type IN ('Decision', 'Question')
        """
    ).fetchall()
    ids = [row["id"] for row in rows]
    if not ids:
        return {"archived_count": 0, "updated_at": now}

    conn.executemany(
        "UPDATE nodes SET status = 'archived', updated_at = ? WHERE id = ?",
        [(now, node_id) for node_id in ids],
    )
    conn.commit()
    return {
        "archived_count": len(ids),
        "updated_at": now,
        "sample_ids": ids[:20],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="archive legacy save_session work_item nodes")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="memory.db path")
    parser.add_argument("--apply", action="store_true", help="실제 archive 수행")
    parser.add_argument("--report", type=Path, help="JSON report output path")
    parser.add_argument("--sample-limit", type=int, default=20, help="sample row count")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    try:
        payload: dict[str, object] = {
            "db": str(args.db),
            "apply": args.apply,
            "candidates": collect_candidates(conn, limit=args.sample_limit),
        }
        if args.apply:
            payload["applied"] = apply_archive(conn)

        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        print(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
