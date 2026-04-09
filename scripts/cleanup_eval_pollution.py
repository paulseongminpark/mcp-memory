#!/usr/bin/env python3
"""Phase 3: eval traffic로 오염된 학습 신호를 audit/cleanup 한다.

기본은 dry-run이다. 안전하게 되돌릴 수 있는 신호만 먼저 다룬다.
- nodes.visit_count: goldset query로 기록된 recall_log hit 수만큼 차감
- meta.total_recall_count: recall_id가 있는 goldset invocation 수만큼 차감

주의:
- recall_log row 자체는 삭제하지 않는다.
- edge.frequency / co_retrieval은 여기서 건드리지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import DB_PATH

GOLDSET_V4 = ROOT / "scripts" / "eval" / "goldset_v4.yaml"
GOLDSET_LEGACY = ROOT / "scripts" / "eval" / "goldset_corrected.yaml"
CLEANUP_MARKER_KEY = "eval_pollution_cleanup_v1_applied_at"
CLEANUP_RECALL_DELTA_KEY = "eval_pollution_cleanup_v1_recall_delta"
CLEANUP_VISIT_DELTA_KEY = "eval_pollution_cleanup_v1_visit_delta"
CLEANUP_GOLDSET_KEY = "eval_pollution_cleanup_v1_goldset"


def _default_goldset_path() -> Path:
    return GOLDSET_V4 if GOLDSET_V4.exists() else GOLDSET_LEGACY


def _load_goldset_queries(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    queries = []
    for item in data.get("queries", []):
        query = (item.get("query") or "").strip()
        if query:
            queries.append(query)
    return sorted(set(queries))


def _chunked(items: list[str], size: int = 400) -> list[list[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _fetch_goldset_rows(conn: sqlite3.Connection, queries: list[str]) -> list[sqlite3.Row]:
    rows: list[sqlite3.Row] = []
    for chunk in _chunked(queries):
        placeholders = ",".join("?" for _ in chunk)
        rows.extend(
            conn.execute(
                f"""
                SELECT id, query, node_id, recall_id, timestamp
                FROM recall_log
                WHERE query IN ({placeholders})
                """,
                chunk,
            ).fetchall()
        )
    return rows


def _fetch_node_info(conn: sqlite3.Connection, node_ids: list[str]) -> dict[str, sqlite3.Row]:
    info: dict[str, sqlite3.Row] = {}
    for chunk in _chunked(node_ids):
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"""
            SELECT id, type, project, COALESCE(visit_count, 0) AS visit_count
            FROM nodes
            WHERE id IN ({placeholders})
            """,
            chunk,
        ).fetchall()
        for row in rows:
            info[str(row["id"])] = row
    return info


def collect_pollution_stats(conn: sqlite3.Connection, queries: list[str], top_n: int = 15) -> dict:
    goldset_rows = _fetch_goldset_rows(conn, queries)
    node_hits: Counter[str] = Counter()
    recall_ids: set[str] = set()
    legacy_rows_without_recall_id = 0

    for row in goldset_rows:
        node_id = (row["node_id"] or "").strip()
        if node_id:
            node_hits[node_id] += 1
        recall_id = (row["recall_id"] or "").strip()
        if recall_id:
            recall_ids.add(recall_id)
        else:
            legacy_rows_without_recall_id += 1

    node_info = _fetch_node_info(conn, list(node_hits.keys()))
    missing_node_ids = sorted(set(node_hits.keys()) - set(node_info.keys()))

    top_affected_nodes = []
    total_visit_count_delta = 0
    for node_id, hits in node_hits.most_common(top_n):
        row = node_info.get(node_id)
        if row is None:
            continue
        visit_before = int(row["visit_count"] or 0)
        visit_after = max(0, visit_before - hits)
        delta = visit_before - visit_after
        total_visit_count_delta += delta
        top_affected_nodes.append(
            {
                "node_id": int(node_id) if node_id.isdigit() else node_id,
                "type": row["type"],
                "project": row["project"],
                "eval_hits": hits,
                "visit_count_before": visit_before,
                "visit_count_after": visit_after,
                "delta": delta,
            }
        )

    meta_row = conn.execute(
        "SELECT value FROM meta WHERE key = 'total_recall_count'"
    ).fetchone()
    total_recall_before = int(meta_row["value"]) if meta_row and meta_row["value"] else 0
    total_recall_after = max(0, total_recall_before - len(recall_ids))

    total_node_visit_delta = 0
    for node_id, hits in node_hits.items():
        row = node_info.get(node_id)
        if row is None:
            continue
        total_node_visit_delta += min(int(row["visit_count"] or 0), hits)

    return {
        "goldset_queries": len(queries),
        "recall_log_rows_for_goldset": len(goldset_rows),
        "distinct_nodes_hit_by_goldset": len(node_hits),
        "reducible_recall_invocations": len(recall_ids),
        "legacy_rows_without_recall_id": legacy_rows_without_recall_id,
        "nodes_missing_from_nodes_table": len(missing_node_ids),
        "missing_node_ids_sample": missing_node_ids[:20],
        "total_recall_count_before": total_recall_before,
        "total_recall_count_after": total_recall_after,
        "total_recall_count_delta": total_recall_before - total_recall_after,
        "visit_count_delta_if_applied": total_node_visit_delta,
        "top_affected_nodes": top_affected_nodes,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def read_cleanup_marker(conn: sqlite3.Connection) -> dict | None:
    rows = conn.execute(
        """
        SELECT key, value
        FROM meta
        WHERE key IN (?, ?, ?, ?)
        """,
        (
            CLEANUP_MARKER_KEY,
            CLEANUP_RECALL_DELTA_KEY,
            CLEANUP_VISIT_DELTA_KEY,
            CLEANUP_GOLDSET_KEY,
        ),
    ).fetchall()
    if not rows:
        return None

    marker = {row["key"]: row["value"] for row in rows}
    applied_at = marker.get(CLEANUP_MARKER_KEY)
    if not applied_at:
        return None
    return {
        "applied_at": applied_at,
        "recall_delta": int(marker.get(CLEANUP_RECALL_DELTA_KEY) or 0),
        "visit_delta": int(marker.get(CLEANUP_VISIT_DELTA_KEY) or 0),
        "goldset": marker.get(CLEANUP_GOLDSET_KEY) or "",
    }


def apply_cleanup(conn: sqlite3.Connection, queries: list[str], goldset_label: str) -> dict:
    goldset_rows = _fetch_goldset_rows(conn, queries)
    node_hits: Counter[str] = Counter()
    recall_ids: set[str] = set()

    for row in goldset_rows:
        node_id = (row["node_id"] or "").strip()
        if node_id:
            node_hits[node_id] += 1
        recall_id = (row["recall_id"] or "").strip()
        if recall_id:
            recall_ids.add(recall_id)

    node_info = _fetch_node_info(conn, list(node_hits.keys()))
    now = datetime.now(timezone.utc).isoformat()

    node_updates = []
    total_visit_delta = 0
    for node_id, hits in node_hits.items():
        row = node_info.get(node_id)
        if row is None:
            continue
        current = int(row["visit_count"] or 0)
        next_value = max(0, current - hits)
        total_visit_delta += current - next_value
        if next_value != current:
            node_updates.append((next_value, now, node_id))

    if node_updates:
        conn.executemany(
            "UPDATE nodes SET visit_count = ?, updated_at = ? WHERE id = ?",
            node_updates,
        )

    meta_row = conn.execute(
        "SELECT value FROM meta WHERE key = 'total_recall_count'"
    ).fetchone()
    current_total = int(meta_row["value"]) if meta_row and meta_row["value"] else 0
    next_total = max(0, current_total - len(recall_ids))
    conn.execute(
        """
        INSERT INTO meta (key, value, updated_at)
        VALUES ('total_recall_count', ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (str(next_total), now),
    )
    conn.executemany(
        """
        INSERT INTO meta (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        [
            (CLEANUP_MARKER_KEY, now, now),
            (CLEANUP_RECALL_DELTA_KEY, str(current_total - next_total), now),
            (CLEANUP_VISIT_DELTA_KEY, str(total_visit_delta), now),
            (CLEANUP_GOLDSET_KEY, goldset_label, now),
        ],
    )
    conn.commit()

    return {
        "nodes_updated": len(node_updates),
        "visit_count_delta_applied": total_visit_delta,
        "total_recall_count_before": current_total,
        "total_recall_count_after": next_total,
        "total_recall_count_delta_applied": current_total - next_total,
        "generated_at": now,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="audit/cleanup eval pollution")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="memory.db path")
    parser.add_argument("--goldset", type=Path, default=_default_goldset_path(), help="goldset yaml path")
    parser.add_argument("--apply", action="store_true", help="실제 visit_count/meta 변경 수행")
    parser.add_argument("--force", action="store_true", help="cleanup marker가 있어도 강제 실행")
    parser.add_argument("--report", type=Path, help="JSON report output path")
    parser.add_argument("--top", type=int, default=15, help="top affected nodes count")
    args = parser.parse_args(argv)

    queries = _load_goldset_queries(args.goldset)
    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    try:
        stats = collect_pollution_stats(conn, queries, top_n=args.top)
        marker = read_cleanup_marker(conn)
        payload: dict[str, object] = {
            "db": str(args.db),
            "goldset": str(args.goldset),
            "apply": args.apply,
            "force": args.force,
            "stats": stats,
            "marker": marker,
        }

        if args.apply:
            if marker and not args.force:
                payload["applied"] = {
                    "status": "skipped",
                    "reason": "cleanup marker exists",
                    "marker": marker,
                }
            else:
                payload["applied"] = apply_cleanup(conn, queries, str(args.goldset))

        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        print(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
