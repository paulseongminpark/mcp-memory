"""Audit and optionally soft-delete weak orphan_repair edges."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH, RELATION_RULES


REPORT_PATH = ROOT / "data" / "orphan_audit_report.json"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _strength_bucket(strength: float) -> str:
    if strength < 0.3:
        return "weak"
    if strength < 0.5:
        return "marginal"
    return "ok"


def _type_compatibility(src_type: str, tgt_type: str) -> str:
    if (src_type, tgt_type) in RELATION_RULES or (tgt_type, src_type) in RELATION_RULES:
        return "typed"
    return "untyped"


def _project_bucket(src_project: str, tgt_project: str) -> str:
    return "same_project" if (src_project or "") == (tgt_project or "") else "cross_project"


def _is_delete_candidate(strength: float, type_compatibility: str) -> tuple[bool, str | None]:
    if strength < 0.15:
        return True, "ultra-weak (< 0.15)"
    if strength < 0.3 and type_compatibility == "untyped":
        return True, "weak + untyped"
    return False, None


def _other_active_edges(conn: sqlite3.Connection, node_id: int, edge_id: int) -> int:
    return conn.execute(
        """SELECT COUNT(*)
           FROM edges
           WHERE (source_id = ? OR target_id = ?)
             AND status = 'active'
             AND id != ?""",
        (node_id, node_id, edge_id),
    ).fetchone()[0]


def _simulate_new_orphans(conn: sqlite3.Connection, delete_ids: set[int]) -> int:
    if not delete_ids:
        return 0
    placeholders = ",".join("?" for _ in delete_ids)
    rows = conn.execute(
        f"""WITH filtered AS (
                SELECT * FROM edges
                WHERE status='active'
                  AND id NOT IN ({placeholders})
            )
            SELECT COUNT(*)
            FROM (
                SELECT n.id
                FROM nodes n
                LEFT JOIN filtered e
                  ON (n.id=e.source_id OR n.id=e.target_id)
                WHERE n.status='active'
                GROUP BY n.id
                HAVING COUNT(e.id)=0
            )""",
        tuple(delete_ids),
    ).fetchone()[0]
    return rows


def _write_report(payload: dict) -> None:
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit orphan_repair edges")
    parser.add_argument("--apply", action="store_true", help="실제 soft-delete 수행")
    args = parser.parse_args(argv)

    with _db() as conn:
        rows = conn.execute(
            """SELECT e.id, e.source_id, e.target_id, e.relation, e.strength,
                      n1.type AS source_type, n1.project AS source_project,
                      n2.type AS target_type, n2.project AS target_project
               FROM edges e
               JOIN nodes n1 ON e.source_id = n1.id
               JOIN nodes n2 ON e.target_id = n2.id
               WHERE e.status='active'
                 AND e.generation_method='orphan_repair'
               ORDER BY e.strength ASC, e.id ASC"""
        ).fetchall()

        total = len(rows)
        strength_dist: Counter[str] = Counter()
        type_dist: Counter[str] = Counter()
        project_dist: Counter[str] = Counter()
        raw_reason_counts: Counter[str] = Counter()
        delete_candidates: list[sqlite3.Row] = []
        protected = 0
        final_delete_ids: list[int] = []

        for row in rows:
            strength = float(row["strength"] or 0.0)
            s_bucket = _strength_bucket(strength)
            t_bucket = _type_compatibility(row["source_type"], row["target_type"])
            p_bucket = _project_bucket(row["source_project"], row["target_project"])
            strength_dist[s_bucket] += 1
            type_dist[t_bucket] += 1
            project_dist[p_bucket] += 1

            is_candidate, reason = _is_delete_candidate(strength, t_bucket)
            if is_candidate:
                raw_reason_counts[reason] += 1
                delete_candidates.append(row)

        for row in delete_candidates:
            src_other = _other_active_edges(conn, row["source_id"], row["id"])
            tgt_other = _other_active_edges(conn, row["target_id"], row["id"])
            if src_other == 0 or tgt_other == 0:
                protected += 1
                continue
            final_delete_ids.append(row["id"])

        delete_id_set = set(final_delete_ids)
        remaining_after_delete = total - len(delete_id_set)
        new_orphans_after_delete = _simulate_new_orphans(conn, delete_id_set)

        if args.apply and delete_id_set:
            placeholders = ",".join("?" for _ in delete_id_set)
            conn.execute(
                f"""UPDATE edges
                    SET status='deleted', updated_at=datetime('now')
                    WHERE id IN ({placeholders})
                      AND status='active'""",
                tuple(delete_id_set),
            )
            conn.commit()

        mode = "APPLIED" if args.apply else "DRY-RUN"
        print("=== Orphan Repair Edge Audit ===")
        print(f"Mode: {mode}")
        print(f"Total orphan_repair edges: {total}")
        print()
        print("Strength distribution:")
        print(f"  weak (< 0.3): {strength_dist.get('weak', 0)}")
        print(f"  marginal (0.3-0.5): {strength_dist.get('marginal', 0)}")
        print(f"  ok (>= 0.5): {strength_dist.get('ok', 0)}")
        print()
        print("Type compatibility:")
        print(f"  typed: {type_dist.get('typed', 0)}")
        print(f"  untyped: {type_dist.get('untyped', 0)}")
        print()
        print("Delete candidates:")
        print(f"  weak + untyped: {raw_reason_counts.get('weak + untyped', 0)}")
        print(f"  ultra-weak (< 0.15): {raw_reason_counts.get('ultra-weak (< 0.15)', 0)}")
        print(f"  Total unique delete candidates: {len(delete_id_set)}")
        print()
        print("Sample delete candidates (10개):")
        sample_ids = set(final_delete_ids[:10])
        sample_rows = [row for row in delete_candidates if row["id"] in sample_ids][:10]
        if sample_rows:
            for row in sample_rows:
                print(
                    f"  edge#{row['id']} src=#{row['source_id']}({row['source_type']}) "
                    f"→ tgt=#{row['target_id']}({row['target_type']}) "
                    f"strength={float(row['strength'] or 0.0):.2f} relation={row['relation']}"
                )
        else:
            print("  (none)")
        print()
        print("After deletion:")
        print(f"  Remaining orphan_repair: {remaining_after_delete}")
        print(f"  New orphans created: {new_orphans_after_delete}")
        print(f"  Protected by orphan guard: {protected}")

        report = {
            "timestamp": datetime.now(UTC).isoformat(),
            "total_audited": total,
            "strength_distribution": {
                "weak": strength_dist.get("weak", 0),
                "marginal": strength_dist.get("marginal", 0),
                "ok": strength_dist.get("ok", 0),
            },
            "type_compatibility": {
                "typed": type_dist.get("typed", 0),
                "untyped": type_dist.get("untyped", 0),
            },
            "project_distribution": {
                "same_project": project_dist.get("same_project", 0),
                "cross_project": project_dist.get("cross_project", 0),
            },
            "delete_candidates": len(delete_id_set),
            "protected_by_orphan_guard": protected,
            "deleted": len(delete_id_set) if args.apply else 0,
            "remaining_orphan_repair": remaining_after_delete,
            "new_orphans_after_delete": new_orphans_after_delete,
        }
        _write_report(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
