#!/usr/bin/env python3
"""scripts/pruning.py — BSP (Bayesian-Signal Pruning) 실행 스크립트.

설계: d-r3-13, d-r3-14
사용법:
  python scripts/pruning.py              # dry-run (기본, 변경 없음)
  python scripts/pruning.py --execute    # 실제 실행
  python scripts/pruning.py --status     # 현황 조회만
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


def stage1_identify_candidates(conn: sqlite3.Connection) -> list[int]:
    """Stage 1: pruning 후보 식별.

    조건: L0/L1, quality<0.3, obs<2, 90일 비활성, edge<3.
    """
    rows = conn.execute("""
        SELECT
            n.id,
            COUNT(e.id) AS edge_count
        FROM nodes n
        LEFT JOIN edges e ON (e.source_id = n.id OR e.target_id = n.id)
        WHERE n.status = 'active'
          AND COALESCE(n.quality_score, 0) < 0.3
          AND COALESCE(n.observation_count, 0) < 2
          AND (n.updated_at IS NULL OR n.updated_at < datetime('now', '-90 days'))
          AND n.layer IN (0, 1)
        GROUP BY n.id
        HAVING edge_count < 3
        ORDER BY COALESCE(n.quality_score, 0) ASC
        LIMIT 100
    """).fetchall()

    return [r["id"] for r in rows]


def stage2_mark_candidates(
    conn: sqlite3.Connection,
    candidate_ids: list[int],
    dry_run: bool = True,
    actor: str = "system:pruning",
) -> int:
    """Stage 2: pruning_candidate 전환 (접근 제어 포함)."""
    if not candidate_ids:
        return 0

    blocked = []
    allowed_ids = []

    for nid in candidate_ids:
        if check_access(nid, "write", actor, conn):
            allowed_ids.append(nid)
        else:
            blocked.append(nid)

    if blocked:
        print(f"  접근 차단: {len(blocked)}개 노드 (L4/L5 또는 Top-10 허브)")

    if dry_run:
        print(f"[DRY RUN] {len(allowed_ids)}개 → pruning_candidate 예정")
        return len(allowed_ids)

    now = datetime.now(timezone.utc).isoformat()
    for nid in allowed_ids:
        conn.execute(
            "UPDATE nodes SET status='pruning_candidate', updated_at=? WHERE id=?",
            (now, nid),
        )
        conn.execute(
            "INSERT INTO correction_log "
            "(node_id, field, old_value, new_value, reason, corrected_by, created_at) "
            "VALUES (?, 'status', 'active', 'pruning_candidate', "
            "'BSP Stage 2: low quality + low activation + few edges', ?, datetime('now'))",
            (nid, actor),
        )

    conn.commit()
    print(f"Stage 2 완료: {len(allowed_ids)}개 → pruning_candidate")
    return len(allowed_ids)


def stage3_archive_expired(
    conn: sqlite3.Connection,
    dry_run: bool = True,
    actor: str = "system:pruning",
) -> int:
    """Stage 3: 30일 경과 pruning_candidate → archived."""
    expired = conn.execute(
        "SELECT id FROM nodes "
        "WHERE status = 'pruning_candidate' "
        "  AND updated_at < datetime('now', '-30 days')"
    ).fetchall()

    expired_ids = [r["id"] for r in expired]

    if not expired_ids:
        print("  Stage 3: 만료 후보 없음.")
        return 0

    if dry_run:
        print(f"[DRY RUN] {len(expired_ids)}개 → archived 예정")
        return len(expired_ids)

    now = datetime.now(timezone.utc).isoformat()
    for nid in expired_ids:
        conn.execute(
            "UPDATE nodes SET status='archived', updated_at=? WHERE id=?",
            (now, nid),
        )
        conn.execute(
            "INSERT INTO correction_log "
            "(node_id, field, old_value, new_value, reason, corrected_by, created_at) "
            "VALUES (?, 'status', 'pruning_candidate', 'archived', "
            "'BSP Stage 3: 30-day grace period expired', ?, datetime('now'))",
            (nid, actor),
        )

    conn.commit()
    print(f"Stage 3 완료: {len(expired_ids)}개 → archived")
    return len(expired_ids)


def print_status(conn: sqlite3.Connection) -> None:
    """현재 pruning 현황 출력."""
    active = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE status='active'"
    ).fetchone()[0]
    candidates = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE status='pruning_candidate'"
    ).fetchone()[0]
    archived = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE status='archived'"
    ).fetchone()[0]

    print("\n=== Pruning Status ===")
    print(f"  active:             {active:,}")
    print(f"  pruning_candidate:  {candidates:,}")
    print(f"  archived:           {archived:,}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BSP pruning runner")
    parser.add_argument("--execute", action="store_true",
                        help="실제 실행 (기본: dry-run)")
    parser.add_argument("--status", action="store_true",
                        help="현황 조회만")
    parser.add_argument("--actor", default="system:pruning",
                        help="actor (기본 system:pruning)")
    args = parser.parse_args()

    conn = _get_conn()

    if args.status:
        print_status(conn)
        conn.close()
        sys.exit(0)

    dry_run = not args.execute
    if dry_run:
        print("[DRY RUN 모드] 실제 변경 없음. --execute로 실제 실행.")

    # Stage 1: 후보 식별
    print("\n[Stage 1] 후보 식별...")
    candidate_ids = stage1_identify_candidates(conn)
    print(f"  후보: {len(candidate_ids)}개")

    # Stage 2: pruning_candidate 표시
    print("\n[Stage 2] pruning_candidate 표시...")
    stage2_mark_candidates(conn, candidate_ids, dry_run=dry_run, actor=args.actor)

    # Stage 3: 만료 노드 archive
    print("\n[Stage 3] 만료 archive...")
    stage3_archive_expired(conn, dry_run=dry_run, actor=args.actor)

    print_status(conn)
    conn.close()
