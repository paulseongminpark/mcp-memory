#!/usr/bin/env python3
"""같은 source 안의 exact duplicate active 노드를 archive-first로 정리한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH


def _content_hash(text: str) -> str:
    return hashlib.sha1((text or "").strip().encode("utf-8")).hexdigest()


def collect_groups(conn: sqlite3.Connection, sample_limit: int = 20) -> dict:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, source, type, content, visit_count, quality_score
        FROM nodes
        WHERE status='active'
        ORDER BY source, id
        """
    ).fetchall()

    buckets: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (row["source"], _content_hash(row["content"] or ""))
        buckets.setdefault(key, []).append(dict(row))

    groups = [group for group in buckets.values() if len(group) > 1]
    groups.sort(
        key=lambda group: (
            -len(group),
            group[0]["source"],
            min(item["id"] for item in group),
        )
    )

    decisions = []
    archive_ids: list[int] = []
    for group in groups:
        ranked = sorted(
            group,
            key=lambda item: (
                -(item.get("visit_count") or 0),
                -((item.get("quality_score") or 0.0)),
                item["id"],
            ),
        )
        keeper = ranked[0]
        archived = ranked[1:]
        archive_ids.extend(item["id"] for item in archived)
        decisions.append(
            {
                "source": keeper["source"],
                "keep_id": keeper["id"],
                "archive_ids": [item["id"] for item in archived],
                "group_size": len(group),
                "sample": [
                    {
                        "id": item["id"],
                        "type": item["type"],
                        "visit_count": item.get("visit_count") or 0,
                        "quality_score": item.get("quality_score"),
                    }
                    for item in ranked[: min(len(ranked), 6)]
                ],
            }
        )

    return {
        "group_count": len(groups),
        "archive_count": len(archive_ids),
        "archive_ids": archive_ids,
        "sample": decisions[:sample_limit],
    }


def apply_archive(conn: sqlite3.Connection, archive_ids: list[int]) -> dict:
    if not archive_ids:
        return {"archived_nodes": 0, "updated_at": ""}
    now = datetime.now(timezone.utc).isoformat()
    placeholders = ",".join("?" * len(archive_ids))
    cur = conn.execute(
        f"""
        UPDATE nodes
        SET status='archived', updated_at=?
        WHERE status='active' AND id IN ({placeholders})
        """,
        [now, *archive_ids],
    )
    conn.commit()
    return {"archived_nodes": cur.rowcount, "updated_at": now}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="archive same-source exact duplicates")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--sample-limit", type=int, default=20)
    args = parser.parse_args(argv)

    conn = sqlite3.connect(str(args.db))
    try:
        payload = {
            "db": str(args.db),
            "apply": args.apply,
            "before": collect_groups(conn, sample_limit=args.sample_limit),
        }
        if args.apply:
            payload["applied"] = apply_archive(conn, payload["before"]["archive_ids"])
            payload["after"] = collect_groups(conn, sample_limit=args.sample_limit)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
