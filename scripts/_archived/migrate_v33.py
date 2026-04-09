"""v3.3 storage migration helper.

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

NODE_COLUMNS = {"source_kind", "source_ref", "node_role", "epistemic_status"}
EDGE_COLUMNS = {"generation_method"}


def _columns(table: str) -> set[str]:
    with sqlite_store._db() as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="mcp-memory v3.3 migration")
    parser.add_argument("--apply", action="store_true", help="실제 DB 변경 수행")
    args = parser.parse_args(argv)

    node_cols_before = _columns("nodes")
    edge_cols_before = _columns("edges")
    missing_nodes = sorted(NODE_COLUMNS - node_cols_before)
    missing_edges = sorted(EDGE_COLUMNS - edge_cols_before)

    print(f"[v3.3] nodes missing: {missing_nodes}")
    print(f"[v3.3] edges missing: {missing_edges}")

    if not args.apply:
        print("[v3.3] dry-run only. 변경 없음.")
        return 0

    sqlite_store.init_db()

    node_cols_after = _columns("nodes")
    edge_cols_after = _columns("edges")
    print(f"[v3.3] nodes ready: {NODE_COLUMNS <= node_cols_after}")
    print(f"[v3.3] edges ready: {EDGE_COLUMNS <= edge_cols_after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
