"""R2 generation_method saturation backfill.

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


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _starts_auto(description: str) -> bool:
    lowered = description.lower()
    return lowered.startswith("auto:") or lowered.startswith("auto :")


def _is_descriptive_text(description: str) -> bool:
    stripped = description.strip()
    lowered = stripped.lower()
    if len(stripped) <= 5:
        return False
    if stripped == "[]":
        return False
    if stripped.startswith("[") or stripped.startswith("{"):
        return False
    if _starts_auto(stripped):
        return False
    if "similarity=" in lowered:
        return False
    if "fallback:" in lowered:
        return False
    if "session" in lowered:
        return False
    return True


def _classify_edge(row: sqlite3.Row) -> tuple[str, str]:
    relation = (row["relation"] or "").strip()
    description = (row["description"] or "").strip()
    lowered = description.lower()

    if relation == "co_retrieved":
        return "co_retrieved", "co_retrieval"
    if _starts_auto(description):
        return "auto description", "semantic_auto"
    if "similarity=" in lowered:
        return "auto description", "semantic_auto"
    if description.startswith("복구: pdr"):
        return "pdr session", "session_anchor"
    if "promote" in lowered:
        return "promote", "rule"
    if description == "[]":
        return "description='[]'", "enrichment"
    if _is_descriptive_text(description):
        return "descriptive text", "enrichment"
    if not description:
        return "empty/null description", "legacy_unknown"
    return "unmatched", "legacy_unknown"


def _format_pct(filled: int, total: int) -> str:
    pct = (filled / total * 100.0) if total else 0.0
    return f"{filled}/{total} ({pct:.1f}%)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R2 generation_method saturation backfill")
    parser.add_argument("--apply", action="store_true", help="실제 DB 변경 수행")
    args = parser.parse_args(argv)

    with _db() as conn:
        total_active = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE status='active'"
        ).fetchone()[0]
        current_filled = conn.execute(
            """SELECT COUNT(*)
               FROM edges
               WHERE status='active'
                 AND generation_method IS NOT NULL
                 AND generation_method != ''"""
        ).fetchone()[0]

        blank_rows = conn.execute(
            """SELECT id, relation, description, generation_method
               FROM edges
               WHERE status='active'
                 AND (generation_method IS NULL OR generation_method='')"""
        ).fetchall()

        step1_counts: Counter[str] = Counter()
        step2_counts: Counter[str] = Counter()
        step3_counts: Counter[str] = Counter()
        updates: list[tuple[str, int]] = []

        for row in blank_rows:
            reason, method = _classify_edge(row)
            updates.append((method, row["id"]))
            if reason in {"co_retrieved", "auto description", "pdr session", "promote"}:
                step1_counts[f"{reason} -> {method}"] += 1
            elif reason in {"description='[]'", "descriptive text"}:
                step2_counts[f"{reason} -> {method}"] += 1
            else:
                step3_counts[f"{reason} -> {method}"] += 1

        after_filled = current_filled + len(updates)
        mode = "APPLIED" if args.apply else "DRY-RUN"

        print(f"=== generation_method R2 Backfill ({mode}) ===")
        print("Step 1 - Exact classification:")
        for key in (
            "co_retrieved -> co_retrieval",
            "auto description -> semantic_auto",
            "pdr session -> session_anchor",
            "promote -> rule",
        ):
            print(f"  {key}: {step1_counts.get(key, 0)}")

        print("Step 2 - Enrichment classification:")
        for key in (
            "description='[]' -> enrichment",
            "descriptive text -> enrichment",
        ):
            print(f"  {key}: {step2_counts.get(key, 0)}")

        print("Step 3 - Legacy:")
        for key in (
            "empty/null description -> legacy_unknown",
            "unmatched -> legacy_unknown",
        ):
            print(f"  {key}: {step3_counts.get(key, 0)}")

        print(f"Total changes: {len(updates)}")
        print(f"Current fill: {_format_pct(current_filled, total_active)}")
        print(f"After fill:   {_format_pct(after_filled, total_active)}")

        if args.apply and updates:
            conn.executemany(
                """UPDATE edges
                   SET generation_method = ?, updated_at = datetime('now')
                   WHERE id = ?
                     AND status='active'
                     AND (generation_method IS NULL OR generation_method='')""",
                updates,
            )
            conn.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
