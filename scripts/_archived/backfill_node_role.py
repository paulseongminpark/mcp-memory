"""Backfill nodes.node_role.

기본은 dry-run이며, 실제 변경은 --apply일 때만 수행한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import (
    SAVE_SESSION_DECISION_MIN_LEN,
    SAVE_SESSION_QUESTION_MIN_LEN,
    SAVE_SESSION_SKIP_PATTERNS,
)
from storage import sqlite_store


def _contains_skip_pattern(text: str) -> bool:
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in SAVE_SESSION_SKIP_PATTERNS)


def _infer_node_role(row: dict) -> str:
    current = (row.get("node_role") or "").strip()
    if current:
        return current

    node_type = row.get("type") or ""
    source = row.get("source") or ""
    source_kind = row.get("source_kind") or source.split(":", 1)[0]
    content = (row.get("content") or "").strip()
    layer = row.get("layer")

    if node_type == "Correction":
        return "correction"
    if source_kind == "save_session" and node_type == "Narrative":
        return "session_anchor"
    if source_kind == "save_session" and node_type == "Decision":
        if len(content) < SAVE_SESSION_DECISION_MIN_LEN or _contains_skip_pattern(content):
            return "work_item"
        return "knowledge_candidate"
    if source_kind == "save_session" and node_type == "Question":
        if len(content) < SAVE_SESSION_QUESTION_MIN_LEN or _contains_skip_pattern(content):
            return "work_item"
        return "knowledge_candidate"
    if node_type == "Signal":
        return "signal_candidate"
    if row.get("promotion_candidate") or (layer is not None and layer >= 2):
        return "knowledge_core"
    return "knowledge_candidate"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="backfill node_role")
    parser.add_argument("--apply", action="store_true", help="실제 DB 변경 수행")
    args = parser.parse_args(argv)

    with sqlite_store._db() as conn:
        rows = conn.execute(
            """SELECT id, type, content, source, source_kind, node_role,
                      promotion_candidate, layer
               FROM nodes
               WHERE status = 'active'"""
        ).fetchall()

        updates: list[tuple[str, int]] = []
        for row in rows:
            next_role = _infer_node_role(dict(row))
            if (row["node_role"] or "").strip() != next_role:
                updates.append((next_role, row["id"]))

        print(f"[node_role] candidates={len(updates)} apply={args.apply}")
        if updates:
            print(f"[node_role] sample_ids={[u[1] for u in updates[:10]]}")

        if args.apply and updates:
            conn.executemany(
                "UPDATE nodes SET node_role = ?, updated_at = datetime('now') WHERE id = ?",
                updates,
            )
            conn.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
