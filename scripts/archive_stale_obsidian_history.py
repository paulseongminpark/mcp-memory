#!/usr/bin/env python3
"""오래된 미접근 Obsidian history/archive/changelog 노드를 archive-first로 정리한다."""

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

import config

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SOURCE_RULES = (
    (
        "obsidian_history",
        "source LIKE 'obsidian:%_history%' ESCAPE '\\' "
        "AND source NOT LIKE 'obsidian:%_history\\archive%' ESCAPE '\\'",
    ),
    (
        "obsidian_archived",
        "("
        "source LIKE 'obsidian:%_history\\archive%' ESCAPE '\\' "
        "OR source LIKE 'obsidian:%_archived%' ESCAPE '\\'"
        ")",
    ),
    ("obsidian_changelog", "source LIKE 'obsidian:%CHANGELOG.md%' ESCAPE '\\'"),
)


def _where_clause(days: int) -> str:
    source_clause = " OR ".join(rule for _, rule in SOURCE_RULES)
    return f"""
        status='active'
        AND COALESCE(visit_count, 0)=0
        AND datetime(created_at) < datetime('now', '-{days} day')
        AND ({source_clause})
        AND COALESCE(node_role, '') != 'knowledge_core'
        AND COALESCE(epistemic_status, '') != 'validated'
    """


def collect_candidates(conn: sqlite3.Connection, days: int, sample_limit: int = 30) -> dict:
    where = _where_clause(days)
    rows = conn.execute(
        f"""
        SELECT id, source, type, project, created_at, content
        FROM nodes
        WHERE {where}
        ORDER BY id
        """
    ).fetchall()

    by_rule = {}
    for label, rule in SOURCE_RULES:
        count = conn.execute(
            f"SELECT COUNT(*) FROM nodes WHERE {_where_clause(days)} AND {rule}"
        ).fetchone()[0]
        by_rule[label] = count

    samples = [
        {
            "id": row["id"],
            "source": row["source"],
            "type": row["type"],
            "project": row["project"],
            "created_at": row["created_at"],
            "content": (row["content"] or "")[:160],
        }
        for row in rows[:sample_limit]
    ]

    return {
        "candidate_count": len(rows),
        "by_rule": by_rule,
        "samples": samples,
    }


def apply_archive(conn: sqlite3.Connection, days: int) -> dict:
    where = _where_clause(days)
    ids = [
        row[0]
        for row in conn.execute(
            f"SELECT id FROM nodes WHERE {where} ORDER BY id"
        ).fetchall()
    ]
    now = datetime.now(timezone.utc).isoformat()
    if not ids:
        return {"archived_count": 0, "updated_at": now}

    conn.executemany(
        "UPDATE nodes SET status='archived', updated_at=? WHERE id=?",
        [(now, node_id) for node_id in ids],
    )
    conn.commit()
    return {
        "archived_count": len(ids),
        "updated_at": now,
        "sample_ids": ids[:30],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="archive stale obsidian history/archive/changelog nodes")
    parser.add_argument("--db", type=Path, default=config.DB_PATH, help="memory.db path")
    parser.add_argument("--days", type=int, default=30, help="minimum age in days")
    parser.add_argument("--apply", action="store_true", help="실제 archive 수행")
    parser.add_argument("--report", type=Path, help="JSON report output path")
    parser.add_argument("--sample-limit", type=int, default=30, help="sample row count")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    try:
        payload: dict[str, object] = {
            "db": str(args.db),
            "days": args.days,
            "apply": args.apply,
            "candidates": collect_candidates(conn, args.days, sample_limit=args.sample_limit),
        }
        if args.apply:
            payload["applied"] = apply_archive(conn, args.days)

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
