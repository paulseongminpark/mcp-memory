"""R2 node_role saturation backfill.

기본은 dry-run이며, 실제 변경은 --apply일 때만 수행한다.
기존 값이 있는 row는 건드리지 않는다.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH


DEFAULT_ROLE_BY_SOURCE_KIND = {
    "obsidian": "knowledge_candidate",
    "pdr": "knowledge_candidate",
    "checkpoint": "knowledge_candidate",
    "claude": "knowledge_candidate",
    "user": "knowledge_candidate",
    "migrate": "knowledge_candidate",
    "hook": "work_item",
    "compressor": "session_anchor",
}

EXTERNAL_ROLE_GUARDS = {"external_noise", "knowledge_core"}


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _classify_row(row: sqlite3.Row) -> tuple[str, str]:
    current_role = (row["node_role"] or "").strip()
    if current_role in EXTERNAL_ROLE_GUARDS:
        return "skip", current_role

    if (row["epistemic_status"] or "").strip() == "validated":
        return "validated", "knowledge_core"
    if (row["type"] or "").strip() == "Narrative":
        return "narrative", "session_anchor"
    if (row["type"] or "").strip() == "Correction":
        return "correction", "correction"
    if (row["type"] or "").strip() == "Signal" and (row["source"] or "").strip() == "signal_synthesis":
        return "signal_synthesis", "knowledge_candidate"

    source_kind = (row["source_kind"] or "").strip()
    return f"source:{source_kind or 'unknown'}", DEFAULT_ROLE_BY_SOURCE_KIND.get(
        source_kind, "knowledge_candidate"
    )


def _format_pct(filled: int, total: int) -> str:
    pct = (filled / total * 100.0) if total else 0.0
    return f"{filled}/{total} ({pct:.1f}%)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R2 node_role saturation backfill")
    parser.add_argument("--apply", action="store_true", help="실제 DB 변경 수행")
    args = parser.parse_args(argv)

    with _db() as conn:
        total_active = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE status='active'"
        ).fetchone()[0]
        current_filled = conn.execute(
            """SELECT COUNT(*)
               FROM nodes
               WHERE status='active'
                 AND node_role IS NOT NULL
                 AND node_role != ''"""
        ).fetchone()[0]

        blank_rows = conn.execute(
            """SELECT id, type, source, source_kind, node_role, epistemic_status
               FROM nodes
               WHERE status='active'
                 AND (node_role IS NULL OR node_role='')"""
        ).fetchall()

        default_counts: Counter[str] = Counter()
        exception_counts: Counter[str] = Counter()
        updates: list[tuple[str, int]] = []

        for row in blank_rows:
            reason, next_role = _classify_row(row)
            if reason == "skip":
                continue
            updates.append((next_role, row["id"]))
            if reason.startswith("source:"):
                source_kind = reason.split(":", 1)[1]
                default_counts[f"{source_kind} -> {next_role}"] += 1
            else:
                exception_counts[f"{reason} -> {next_role}"] += 1

        after_filled = current_filled + len(updates)
        mode = "APPLIED" if args.apply else "DRY-RUN"

        print(f"=== node_role R2 Backfill ({mode}) ===")
        print("Source-based defaults:")
        for source_kind in (
            "obsidian",
            "pdr",
            "checkpoint",
            "claude",
            "user",
            "migrate",
            "hook",
            "compressor",
            "unknown",
        ):
            key = f"{source_kind} -> {DEFAULT_ROLE_BY_SOURCE_KIND.get(source_kind, 'knowledge_candidate')}"
            if source_kind == "hook":
                key = "hook -> work_item"
            elif source_kind == "compressor":
                key = "compressor -> session_anchor"
            elif source_kind == "unknown":
                key = "unknown -> knowledge_candidate"
            count = default_counts.get(key, 0)
            if count:
                print(f"  {key}: {count}")

        print("Exception overrides:")
        for key in (
            "validated -> knowledge_core",
            "narrative -> session_anchor",
            "correction -> correction",
            "signal_synthesis -> knowledge_candidate",
        ):
            print(f"  {key}: {exception_counts.get(key, 0)}")

        print(f"Total changes: {len(updates)}")
        print(f"Current fill: {_format_pct(current_filled, total_active)}")
        print(f"After fill:   {_format_pct(after_filled, total_active)}")

        if args.apply and updates:
            conn.executemany(
                """UPDATE nodes
                   SET node_role = ?, updated_at = datetime('now')
                   WHERE id = ?
                     AND status='active'
                     AND (node_role IS NULL OR node_role='')""",
                updates,
            )
            conn.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
