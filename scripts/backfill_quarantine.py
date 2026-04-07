"""Backfill nodes.node_role for obvious external noise.

기본은 dry-run이며, 실제 변경은 --apply일 때만 수행한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage import sqlite_store

NOISE_MARKERS = (
    ".venv\\",
    ".venv/",
    "site-packages",
    "license.md",
    "\\02_programs\\",
    "/02_programs/",
)


def _is_noise(row: dict) -> bool:
    haystacks = [
        row.get("content") or "",
        row.get("tags") or "",
        row.get("project") or "",
        row.get("source_ref") or "",
        row.get("metadata") or "",
    ]
    merged = "\n".join(haystacks).lower()
    return any(marker in merged for marker in NOISE_MARKERS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="quarantine external noise nodes")
    parser.add_argument("--apply", action="store_true", help="실제 DB 변경 수행")
    args = parser.parse_args(argv)

    with sqlite_store._db() as conn:
        rows = conn.execute(
            """SELECT id, content, tags, project, source_ref, metadata, node_role
               FROM nodes
               WHERE status = 'active'"""
        ).fetchall()

        updates: list[tuple[int]] = []
        for row in rows:
            if _is_noise(dict(row)) and (row["node_role"] or "") != "external_noise":
                updates.append((row["id"],))

        print(f"[quarantine] candidates={len(updates)} apply={args.apply}")
        if updates:
            print(f"[quarantine] sample_ids={[u[0] for u in updates[:10]]}")

        if args.apply and updates:
            conn.executemany(
                """UPDATE nodes
                   SET node_role = 'external_noise',
                       source_kind = CASE
                           WHEN COALESCE(source_kind, '') = '' THEN 'external'
                           ELSE source_kind
                       END,
                       updated_at = datetime('now')
                   WHERE id = ?""",
                updates,
            )
            conn.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
