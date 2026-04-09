#!/usr/bin/env python3
"""Archive된 노드에 대응하는 Chroma 벡터를 정리한다."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from storage import vector_store


def get_active_node_ids(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT id FROM nodes WHERE status='active'").fetchall()
    return {str(row[0]) for row in rows}


def get_collection_ids(coll) -> set[str]:
    payload = coll.get(include=[])
    return set(payload.get("ids", []))


def collect_tombstones(conn: sqlite3.Connection, coll, sample_limit: int = 30) -> dict:
    active_ids = get_active_node_ids(conn)
    collection_ids = get_collection_ids(coll)
    stale_ids = sorted(collection_ids - active_ids, key=int)
    missing_ids = sorted(active_ids - collection_ids, key=int)
    return {
        "active_count": len(active_ids),
        "collection_count": len(collection_ids),
        "stale_count": len(stale_ids),
        "missing_count": len(missing_ids),
        "stale_sample": stale_ids[:sample_limit],
        "missing_sample": missing_ids[:sample_limit],
        "stale_ids": stale_ids,
    }


def apply_delete(coll, stale_ids: list[str], batch_size: int = 200) -> dict:
    if not stale_ids:
        return {"deleted_count": 0, "batch_size": batch_size}

    for i in range(0, len(stale_ids), batch_size):
        coll.delete(ids=stale_ids[i:i + batch_size])

    return {
        "deleted_count": len(stale_ids),
        "batch_size": batch_size,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="cleanup Chroma tombstone vectors")
    parser.add_argument("--db", type=Path, default=config.DB_PATH, help="memory.db path")
    parser.add_argument("--apply", action="store_true", help="실제 삭제 수행")
    parser.add_argument("--report", type=Path, help="JSON report output path")
    parser.add_argument("--sample-limit", type=int, default=30, help="sample row count")
    parser.add_argument("--batch-size", type=int, default=200, help="delete batch size")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(str(args.db))
    coll = vector_store._get_collection()
    try:
        tombstones = collect_tombstones(conn, coll, sample_limit=args.sample_limit)
        payload: dict[str, object] = {
            "db": str(args.db),
            "apply": args.apply,
            "tombstones": {
                k: v for k, v in tombstones.items() if k != "stale_ids"
            },
        }
        if args.apply:
            payload["applied"] = apply_delete(
                coll,
                tombstones["stale_ids"],
                batch_size=args.batch_size,
            )

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
