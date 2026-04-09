#!/usr/bin/env python3
"""Normalize active edges that use legacy or non-schema relation names."""

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

from config import DB_PATH, canonicalize_relation_for_storage


def _map_relation(relation: str, src_layer: int | None, tgt_layer: int | None) -> str | None:
    if relation == "realizes":
        if src_layer is not None and tgt_layer is not None and src_layer < tgt_layer:
            return "realized_as"
        return "expressed_as"
    mapped = canonicalize_relation_for_storage(relation)
    return mapped if mapped != relation else None


def collect_candidates(conn: sqlite3.Connection, sample_limit: int = 20) -> dict:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT e.id, e.relation, e.generation_method,
               s.id AS source_id, s.layer AS source_layer, s.status AS source_status,
               t.id AS target_id, t.layer AS target_layer, t.status AS target_status
        FROM edges e
        JOIN nodes s ON s.id = e.source_id
        JOIN nodes t ON t.id = e.target_id
        WHERE e.status='active'
          AND e.relation NOT IN (SELECT name FROM relation_defs WHERE status='active')
        ORDER BY e.id DESC
        """
    ).fetchall()
    mapped = []
    for row in rows:
        replacement = _map_relation(row["relation"], row["source_layer"], row["target_layer"])
        if replacement:
            mapped.append({
                "id": row["id"],
                "old_relation": row["relation"],
                "new_relation": replacement,
                "generation_method": row["generation_method"],
                "source_id": row["source_id"],
                "target_id": row["target_id"],
            })
    counts: dict[str, int] = {}
    for item in mapped:
        key = f'{item["old_relation"]}->{item["new_relation"]}'
        counts[key] = counts.get(key, 0) + 1
    return {
        "candidate_count": len(mapped),
        "by_mapping": counts,
        "sample": mapped[:sample_limit],
        "candidates": mapped,
    }


def apply_updates(conn: sqlite3.Connection, candidates: list[dict]) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    for item in candidates:
        cur = conn.execute(
            "UPDATE edges SET relation=?, updated_at=? WHERE id=? AND status='active'",
            (item["new_relation"], now, item["id"]),
        )
        updated += cur.rowcount or 0
    conn.commit()
    return {"updated_edges": updated, "updated_at": now}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="normalize non-schema active edge relations")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="memory.db path")
    parser.add_argument("--apply", action="store_true", help="apply relation updates")
    parser.add_argument("--report", type=Path, help="write JSON report")
    parser.add_argument("--sample-limit", type=int, default=20, help="sample row count")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(str(args.db))
    try:
        candidates = collect_candidates(conn, sample_limit=args.sample_limit)
        payload: dict[str, object] = {
            "db": str(args.db),
            "apply": args.apply,
            "before": {k: v for k, v in candidates.items() if k != "candidates"},
        }
        if args.apply:
            payload["applied"] = apply_updates(conn, candidates["candidates"])
            after = collect_candidates(conn, sample_limit=args.sample_limit)
            payload["after"] = {k: v for k, v in after.items() if k != "candidates"}
    finally:
        conn.close()

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
