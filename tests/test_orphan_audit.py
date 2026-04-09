from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from config import DB_PATH


REPORT_PATH = Path(__file__).resolve().parent.parent / "data" / "orphan_audit_report.json"


def _scalar(query: str) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(query).fetchone()[0]


def _report() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_no_new_orphans_after_audit():
    report = _report()
    assert report["new_orphans_after_delete"] == 0
    orphan_count = _scalar(
        """SELECT COUNT(*)
           FROM (
               SELECT n.id
               FROM nodes n
               LEFT JOIN edges e
                 ON (n.id=e.source_id OR n.id=e.target_id)
                AND e.status='active'
               WHERE n.status='active'
               GROUP BY n.id
               HAVING COUNT(e.id)=0
           )"""
    )
    assert orphan_count == 0


def test_deleted_edges_are_soft_deleted():
    report = _report()
    active_count = _scalar(
        "SELECT COUNT(*) FROM edges WHERE generation_method='orphan_repair' AND status='active'"
    )
    deleted_count = _scalar(
        "SELECT COUNT(*) FROM edges WHERE generation_method='orphan_repair' AND status='deleted'"
    )
    assert deleted_count == report["deleted"]
    assert active_count == report["remaining_orphan_repair"]
    assert active_count + deleted_count == report["total_audited"]


def test_remaining_orphan_repair_edges_above_threshold():
    count = _scalar(
        """SELECT COUNT(*)
           FROM edges
           WHERE generation_method='orphan_repair'
             AND status='active'
             AND strength < 0.15"""
    )
    assert count == 0
