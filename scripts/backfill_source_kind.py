"""Backfill nodes.source_kind / source_ref.

기본은 dry-run이며, 실제 변경은 --apply일 때만 수행한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import SOURCE_KINDS
from storage import sqlite_store


def _infer_source_fields(row: dict) -> tuple[str, str]:
    source = (row.get("source") or "").strip()
    if not source:
        return "external", ""

    prefix, _, suffix = source.partition(":")
    prefix = prefix.strip()
    suffix = suffix.strip()
    if prefix in SOURCE_KINDS:
        return prefix, suffix

    lower = source.lower()
    if lower.startswith("obsidian"):
        return "obsidian", suffix
    if lower.startswith("save_session"):
        return "save_session", suffix
    if lower.startswith("checkpoint"):
        return "checkpoint", suffix
    if lower.startswith("hook"):
        return "hook", suffix
    if lower.startswith("pdr"):
        return "pdr", suffix
    return "external", suffix


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="backfill source_kind/source_ref")
    parser.add_argument("--apply", action="store_true", help="실제 DB 변경 수행")
    args = parser.parse_args(argv)

    with sqlite_store._db() as conn:
        rows = conn.execute(
            "SELECT id, source, source_kind, source_ref FROM nodes WHERE status = 'active'"
        ).fetchall()

        updates: list[tuple[str, str, int]] = []
        for row in rows:
            current_kind = (row["source_kind"] or "").strip()
            current_ref = (row["source_ref"] or "").strip()
            next_kind, next_ref = _infer_source_fields(dict(row))
            if current_kind != next_kind or current_ref != next_ref:
                updates.append((next_kind, next_ref, row["id"]))

        print(f"[source_kind] candidates={len(updates)} apply={args.apply}")
        if updates:
            print(f"[source_kind] sample_ids={[u[2] for u in updates[:10]]}")

        if args.apply and updates:
            conn.executemany(
                "UPDATE nodes SET source_kind = ?, source_ref = ?, updated_at = datetime('now') WHERE id = ?",
                updates,
            )
            conn.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
