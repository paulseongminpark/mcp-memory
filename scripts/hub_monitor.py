#!/usr/bin/env python3
"""scripts/hub_monitor.py — Hub health monitoring + access control.

설계: d-r3-13
사용법:
  python scripts/hub_monitor.py              # 리포트 출력
  python scripts/hub_monitor.py --snapshot   # hub_snapshots 저장
  python scripts/hub_monitor.py --top 20     # Top-20 허브
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from utils.access_control import check_access


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def compute_ihs(conn: sqlite3.Connection, top_n: int = 20) -> list[dict]:
    """
    IHS (In-Hub Score) = incoming edge count.
    Returns list sorted by ihs_score DESC.
    """
    rows = conn.execute("""
        SELECT n.id, n.type, n.layer, n.content,
               COUNT(e.id) AS ihs_score
        FROM nodes n
        LEFT JOIN edges e ON e.target_id = n.id
        WHERE n.status = 'active'
        GROUP BY n.id
        ORDER BY ihs_score DESC
        LIMIT ?
    """, (top_n,)).fetchall()

    return [
        {
            "node_id": r["id"],
            "type": r["type"],
            "layer": r["layer"],
            "preview": (r["content"] or "")[:80],
            "ihs_score": r["ihs_score"],
        }
        for r in rows
    ]


def take_snapshot(conn: sqlite3.Connection) -> int:
    """hub_snapshots 테이블에 현재 Top-20 허브 저장."""
    hubs = compute_ihs(conn, top_n=20)
    today = datetime.now(timezone.utc).date().isoformat()

    conn.execute(
        "DELETE FROM hub_snapshots WHERE snapshot_date = ?", (today,)
    )
    conn.executemany(
        "INSERT INTO hub_snapshots (node_id, snapshot_date, ihs_score) VALUES (?,?,?)",
        [(h["node_id"], today, h["ihs_score"]) for h in hubs],
    )
    conn.commit()
    return len(hubs)


def hub_health_report(conn: sqlite3.Connection, top_n: int = 10) -> list[dict]:
    """
    Hub 상태 리포트 생성.

    risk 판정:
      HIGH:   ihs_score > 50 (연결 과다 → 병목 위험)
      MEDIUM: ihs_score > 20
      LOW:    그 외
    """
    hubs = compute_ihs(conn, top_n=top_n)

    report = []
    for h in hubs:
        score = h["ihs_score"]
        if score > 50:
            risk = "HIGH"
        elif score > 20:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        report.append({**h, "risk": risk})

    return report


def recommend_hub_action(
    node_id: int,
    action: str,
    actor: str = "system",
    conn: sqlite3.Connection | None = None,
) -> dict:
    """
    허브 노드에 대한 액션 추천 전 접근 권한 확인.

    Usage (hub_health_report에서 위험도 판단 후):
      if h["risk"] == "HIGH":
          rec = recommend_hub_action(h["node_id"], "delete", actor="system")
          if not rec["allowed"]:
              print(f"HUMAN REVIEW REQUIRED: {rec['reason']}")
    """
    allowed = check_access(node_id, action, actor, conn)
    if not allowed:
        return {
            "allowed": False,
            "reason": (
                f"actor='{actor}' cannot '{action}' hub node {node_id}. "
                "Human review required."
            ),
            "require_human": True,
        }
    return {"allowed": True, "reason": "ok", "require_human": False}


def print_hub_actions(report: list[dict], actor: str = "system") -> None:
    """허브 리포트 출력 시 접근 제어 결과 함께 표시."""
    print("\n=== Hub Access Control ===")
    for h in report:
        if h["risk"] == "HIGH":
            rec = recommend_hub_action(h["node_id"], "delete", actor)
            status = "BLOCK" if not rec["allowed"] else "ALLOW"
            print(
                f"  [{status}] node {h['node_id']} ({h['preview'][:30]}...) "
                f"delete → {rec['reason']}"
            )


def print_report(report: list[dict]) -> None:
    """hub_health_report 결과 출력."""
    print("\n=== Hub Health Report ===")
    for i, h in enumerate(report, 1):
        print(
            f"  #{i:2d} [{h['risk']:6s}] node {h['node_id']:5d} "
            f"ihs={h['ihs_score']:4d}  type={h['type'] or 'n/a'}"
        )
        if h["preview"]:
            print(f"       {h['preview'][:60]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hub monitor")
    parser.add_argument("--snapshot", action="store_true",
                        help="hub_snapshots 저장")
    parser.add_argument("--top", type=int, default=10,
                        help="Top N 허브 (기본 10)")
    parser.add_argument("--actor", default="system",
                        help="접근 제어 actor (기본 system)")
    args = parser.parse_args()

    conn = _get_conn()

    if args.snapshot:
        n = take_snapshot(conn)
        print(f"Snapshot 저장 완료: {n}개 허브")

    report = hub_health_report(conn, top_n=args.top)
    print_report(report)
    print_hub_actions(report, actor=args.actor)

    conn.close()
