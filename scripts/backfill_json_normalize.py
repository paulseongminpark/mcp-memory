"""Normalize CSV-like JSON array fields on nodes.

기본은 dry-run이며, 실제 변경은 --apply일 때만 수행한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage import sqlite_store

TARGET_FIELDS = ("domains", "facets", "secondary_types")


def _normalize_array_text(value: str | None) -> str | None:
    if value is None:
        return None

    text = value.strip()
    if not text:
        return "[]"

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            normalized = [str(item).strip() for item in parsed if str(item).strip()]
            return json.dumps(normalized, ensure_ascii=False)
    except Exception:
        pass

    tokens = [part.strip() for part in text.replace(";", ",").split(",")]
    normalized = [token for token in tokens if token]
    return json.dumps(normalized, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="normalize JSON-array fields")
    parser.add_argument("--apply", action="store_true", help="실제 DB 변경 수행")
    args = parser.parse_args(argv)

    with sqlite_store._db() as conn:
        rows = conn.execute(
            """SELECT id, domains, facets, secondary_types
               FROM nodes
               WHERE status = 'active'"""
        ).fetchall()

        updates: list[tuple[str | None, str | None, str | None, int]] = []
        for row in rows:
            next_values = tuple(_normalize_array_text(row[field]) for field in TARGET_FIELDS)
            current_values = tuple(row[field] for field in TARGET_FIELDS)
            if next_values != current_values:
                updates.append((*next_values, row["id"]))

        print(f"[json_normalize] candidates={len(updates)} apply={args.apply}")
        if updates:
            print(f"[json_normalize] sample_ids={[u[3] for u in updates[:10]]}")

        if args.apply and updates:
            conn.executemany(
                """UPDATE nodes
                   SET domains = ?, facets = ?, secondary_types = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                updates,
            )
            conn.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
