#!/usr/bin/env python3
"""오래된 미접근 plan/task 노드를 archive-first로 정리한다."""

from __future__ import annotations

import argparse
import json
import re
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

TASKISH_PATTERNS = (
    re.compile(r"(^|\n)##\s*Task\b", re.I),
    re.compile(r"\*\*Files:\*\*", re.I),
    re.compile(r"(^|\n)\*\*Step\s+\d+", re.I),
    re.compile(r"(^|\n)\s*[-*]\s*(Create|Modify|Delete|Rename):", re.I),
    re.compile(r"`C:\\dev\\", re.I),
)


def _base_where(days: int) -> str:
    return f"""
        status='active'
        AND COALESCE(visit_count, 0)=0
        AND datetime(created_at) < datetime('now', '-{days} day')
        AND source LIKE 'obsidian:%plans%' ESCAPE '\\'
        AND COALESCE(node_role, '') != 'knowledge_core'
        AND COALESCE(epistemic_status, '') != 'validated'
        AND content IS NOT NULL
        AND trim(content) <> ''
    """


def _is_taskish(content: str) -> bool:
    text = content or ""
    return any(pattern.search(text) for pattern in TASKISH_PATTERNS)


def _collect_rows(conn: sqlite3.Connection, days: int) -> list[sqlite3.Row]:
    rows = conn.execute(
        f"""
        SELECT id, source, type, project, created_at, content
        FROM nodes
        WHERE {_base_where(days)}
        ORDER BY id
        """
    ).fetchall()
    return [row for row in rows if _is_taskish(row["content"] or "")]


def collect_candidates(conn: sqlite3.Connection, days: int, sample_limit: int = 30) -> dict:
    rows = _collect_rows(conn, days)
    samples = [
        {
            "id": row["id"],
            "source": row["source"],
            "type": row["type"],
            "project": row["project"],
            "created_at": row["created_at"],
            "content": " ".join((row["content"] or "").split())[:180],
        }
        for row in rows[:sample_limit]
    ]
    return {
        "candidate_count": len(rows),
        "samples": samples,
    }


def apply_archive(conn: sqlite3.Connection, days: int) -> dict:
    rows = _collect_rows(conn, days)
    ids = [row["id"] for row in rows]
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
    parser = argparse.ArgumentParser(description="archive stale plan task nodes")
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
