#!/usr/bin/env python3
"""Archive stale orphan control-doc chunks that never activated."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "memory.db"
CONTROL_PREFIXES = (
    "obsidian:.agents\\skills\\",
    "obsidian:.claude\\rules\\",
    "obsidian:.codex\\memories\\",
    "obsidian:.rulesync\\rules\\",
)


SQL = """
WITH active_nodes AS (
    SELECT id, source, type, project, visit_count, created_at,
           substr(replace(content, char(10), ' '), 1, 160) AS preview
    FROM nodes
    WHERE status='active'
),
connected AS (
    SELECT source_id AS id
    FROM edges e
    JOIN nodes s ON s.id = e.source_id
    JOIN nodes t ON t.id = e.target_id
    WHERE e.status='active' AND s.status='active' AND t.status='active'
    UNION
    SELECT target_id AS id
    FROM edges e
    JOIN nodes s ON s.id = e.source_id
    JOIN nodes t ON t.id = e.target_id
    WHERE e.status='active' AND s.status='active' AND t.status='active'
)
SELECT a.id, a.project, a.source, a.type, a.preview
FROM active_nodes a
LEFT JOIN connected c ON c.id = a.id
WHERE c.id IS NULL
  AND COALESCE(a.visit_count, 0) = 0
  AND (a.created_at IS NULL OR a.created_at <= datetime('now', '-30 day'))
  AND (
    a.source LIKE ? OR a.source LIKE ? OR a.source LIKE ? OR a.source LIKE ?
  )
ORDER BY a.source, a.id
"""


def collect(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        SQL,
        tuple(prefix + "%" for prefix in CONTROL_PREFIXES),
    ).fetchall()
    return [
        {
            "id": row[0],
            "project": row[1],
            "source": row[2],
            "type": row[3],
            "preview": row[4],
        }
        for row in rows
    ]


def run(apply: bool = False, report_path: Path | None = None) -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        candidates = collect(conn)
        report = {
            "db": str(DB_PATH),
            "apply": apply,
            "candidate_count": len(candidates),
            "archive_ids": [row["id"] for row in candidates],
            "sample": candidates[:20],
        }
        if apply and candidates:
            ids = [row["id"] for row in candidates]
            placeholders = ",".join("?" for _ in ids)
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                f"UPDATE nodes SET status='archived', updated_at=? WHERE id IN ({placeholders})",
                [now, *ids],
            )
            conn.commit()
            report["archived_count"] = len(ids)
        else:
            report["archived_count"] = 0
        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Archive stale orphan control-doc chunks")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = run(apply=args.apply, report_path=args.report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
