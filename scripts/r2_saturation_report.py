"""Emit R2 saturation report."""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import OrderedDict
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _distribution(conn: sqlite3.Connection, table: str, column: str) -> OrderedDict[str, int]:
    rows = conn.execute(
        f"""SELECT COALESCE({column}, '') AS value, COUNT(*) AS c
            FROM {table}
            WHERE status='active'
            GROUP BY value
            ORDER BY c DESC, value ASC"""
    ).fetchall()
    return OrderedDict((row["value"], row["c"]) for row in rows)


def _filled_blank(conn: sqlite3.Connection, table: str, column: str) -> tuple[int, int, int, float]:
    total = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE status='active'"
    ).fetchone()[0]
    filled = conn.execute(
        f"""SELECT COUNT(*)
            FROM {table}
            WHERE status='active' AND {column} IS NOT NULL AND {column} != ''"""
    ).fetchone()[0]
    blank = total - filled
    rate = (filled / total) if total else 0.0
    return total, filled, blank, rate


def main() -> int:
    with _db() as conn:
        node_total, node_filled, node_blank, node_rate = _filled_blank(conn, "nodes", "node_role")
        edge_total, edge_filled, edge_blank, edge_rate = _filled_blank(conn, "edges", "generation_method")

        report = {
            "timestamp": datetime.now(UTC).isoformat(),
            "node_role": {
                "total_active": node_total,
                "filled": node_filled,
                "blank": node_blank,
                "fill_rate": round(node_rate, 4),
                "distribution": dict(_distribution(conn, "nodes", "node_role")),
            },
            "generation_method": {
                "total_active": edge_total,
                "filled": edge_filled,
                "blank": edge_blank,
                "fill_rate": round(edge_rate, 4),
                "distribution": dict(_distribution(conn, "edges", "generation_method")),
            },
            "gate_passed": {
                "node_role_80": node_rate >= 0.80,
                "generation_method_85": edge_rate >= 0.85,
            },
        }

    out_path = ROOT / "data" / "r2_saturation_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    print(json.dumps(report["gate_passed"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
