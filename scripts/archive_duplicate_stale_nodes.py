#!/usr/bin/env python3
"""오래된 미접근 exact duplicate 노드를 archive-first로 정리한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
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

SOURCE_EXCLUSIONS = (
    "obsidian:AGENTS.md%",
    "obsidian:CLAUDE.md%",
    "obsidian:GEMINI.md%",
    "obsidian:HOME.md%",
    r"obsidian:.rulesync\%",
)


def _base_where(days: int) -> str:
    exclusions = " AND ".join(
        f"source NOT LIKE '{pattern}' ESCAPE '\\'" for pattern in SOURCE_EXCLUSIONS
    )
    return f"""
        status='active'
        AND COALESCE(visit_count, 0)=0
        AND datetime(created_at) < datetime('now', '-{days} day')
        AND source LIKE 'obsidian:%' ESCAPE '\\'
        AND COALESCE(node_role, '') != 'knowledge_core'
        AND COALESCE(epistemic_status, '') != 'validated'
        AND content IS NOT NULL
        AND trim(content) <> ''
        AND {exclusions}
    """


def _normalize_content(content: str) -> str:
    return " ".join((content or "").split())


def _content_hash(content: str) -> str:
    return hashlib.sha1(_normalize_content(content).encode("utf-8")).hexdigest()


def _source_priority(source: str) -> tuple[int, int]:
    source_lower = (source or "").lower()
    archivedish = 1 if any(
        token in source_lower for token in ("_archived", r"_history\\", "changelog.md")
    ) else 0
    variantish = 1 if r"\page-" in source_lower and "-v" in source_lower else 0
    return archivedish, variantish


def _choose_keeper(rows: list[sqlite3.Row]) -> sqlite3.Row:
    return min(
        rows,
        key=lambda row: (
            *_source_priority(row["source"] or ""),
            len(row["source"] or ""),
            row["id"],
        ),
    )


def _collect_groups(conn: sqlite3.Connection, days: int) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT id, source, project, type, created_at, content
        FROM nodes
        WHERE {_base_where(days)}
        ORDER BY id
        """
    ).fetchall()

    grouped: dict[tuple[str, str, str], list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        grouped[(row["project"], row["type"], _content_hash(row["content"] or ""))].append(row)

    groups = []
    for (project, node_type, content_hash), dup_rows in grouped.items():
        if len(dup_rows) < 2:
            continue
        keeper = _choose_keeper(dup_rows)
        archive_rows = [row for row in dup_rows if row["id"] != keeper["id"]]
        groups.append(
            {
                "project": project,
                "type": node_type,
                "content_hash": content_hash,
                "group_size": len(dup_rows),
                "keeper": {
                    "id": keeper["id"],
                    "source": keeper["source"],
                    "created_at": keeper["created_at"],
                },
                "archive_ids": [row["id"] for row in archive_rows],
                "archive_sources": [row["source"] for row in archive_rows],
                "content_preview": _normalize_content(keeper["content"] or "")[:160],
            }
        )

    groups.sort(key=lambda item: (-item["group_size"], item["keeper"]["id"]))
    return groups


def collect_candidates(conn: sqlite3.Connection, days: int, sample_limit: int = 20) -> dict:
    groups = _collect_groups(conn, days)
    archive_ids = [node_id for group in groups for node_id in group["archive_ids"]]
    return {
        "group_count": len(groups),
        "candidate_count": len(archive_ids),
        "sample_groups": groups[:sample_limit],
    }


def apply_archive(conn: sqlite3.Connection, days: int) -> dict:
    groups = _collect_groups(conn, days)
    archive_ids = [node_id for group in groups for node_id in group["archive_ids"]]
    now = datetime.now(timezone.utc).isoformat()
    if not archive_ids:
        return {"archived_count": 0, "updated_at": now}

    conn.executemany(
        "UPDATE nodes SET status='archived', updated_at=? WHERE id=?",
        [(now, node_id) for node_id in archive_ids],
    )
    conn.commit()
    return {
        "archived_count": len(archive_ids),
        "group_count": len(groups),
        "updated_at": now,
        "sample_ids": archive_ids[:30],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="archive stale duplicate nodes")
    parser.add_argument("--db", type=Path, default=config.DB_PATH, help="memory.db path")
    parser.add_argument("--days", type=int, default=30, help="minimum age in days")
    parser.add_argument("--apply", action="store_true", help="실제 archive 수행")
    parser.add_argument("--report", type=Path, help="JSON report output path")
    parser.add_argument("--sample-limit", type=int, default=20, help="sample group count")
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
