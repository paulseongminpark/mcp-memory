"""Backfill blank nodes.project values.

기본은 dry-run이며, 실제 변경은 --apply일 때만 수행한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import PROJECT_DEFAULT_EXTERNAL, PROJECT_DEFAULT_GLOBAL
from storage import sqlite_store


def _infer_project(row: dict) -> str:
    if (row.get("project") or "").strip():
        return row["project"]
    if (row.get("node_role") or "").strip() == "external_noise":
        return PROJECT_DEFAULT_EXTERNAL
    return PROJECT_DEFAULT_GLOBAL


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="backfill blank project values")
    parser.add_argument("--apply", action="store_true", help="실제 DB 변경 수행")
    args = parser.parse_args(argv)

    with sqlite_store._db() as conn:
        rows = conn.execute(
            "SELECT id, project, node_role FROM nodes WHERE status = 'active'"
        ).fetchall()

        updates: list[tuple[str, int]] = []
        for row in rows:
            next_project = _infer_project(dict(row))
            if (row["project"] or "").strip() != next_project:
                updates.append((next_project, row["id"]))

        print(f"[project] candidates={len(updates)} apply={args.apply}")
        if updates:
            print(f"[project] sample_ids={[u[1] for u in updates[:10]]}")

        if args.apply and updates:
            conn.executemany(
                "UPDATE nodes SET project = ?, updated_at = datetime('now') WHERE id = ?",
                updates,
            )
            conn.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
