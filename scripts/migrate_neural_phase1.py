#!/usr/bin/env python3
"""
migrate_neural_phase1.py — 뉴럴 메커니즘 Phase 1 DB 마이그레이션

변경 내용:
  nodes: theta_m, activity_history, visit_count 컬럼 추가 (B-12 BCM+UCB)
  edges: description = '[]' 초기화 (B-10 재공고화)

Usage:
  python scripts/migrate_neural_phase1.py              # 실행
  python scripts/migrate_neural_phase1.py --dry-run    # 변경 없이 상태 확인
  python scripts/migrate_neural_phase1.py --check      # 상태 확인만
"""

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import DB_PATH

BACKUP_DIR = ROOT / "data" / "backup"


def check_columns(conn: sqlite3.Connection) -> dict:
    cursor = conn.execute("PRAGMA table_info(nodes)")
    node_cols = {row[1] for row in cursor.fetchall()}
    cursor = conn.execute("PRAGMA table_info(edges)")
    edge_cols = {row[1] for row in cursor.fetchall()}

    return {
        "nodes.theta_m": "theta_m" in node_cols,
        "nodes.activity_history": "activity_history" in node_cols,
        "nodes.visit_count": "visit_count" in node_cols,
    }


def print_status(conn: sqlite3.Connection):
    status = check_columns(conn)
    print("\n=== 마이그레이션 상태 ===")
    for col, exists in status.items():
        mark = "OK" if exists else "MISSING"
        print(f"  {mark:7}  {col}")

    # edges description 상태
    bad = conn.execute(
        "SELECT COUNT(*) FROM edges WHERE description IS NULL OR description = '' "
        "OR json_valid(description) = 0"
    ).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    print(f"  edges.description 미초기화: {bad}/{total}")
    print()


def run_migration(dry_run: bool = False):
    if not DB_PATH.exists():
        print(f"DB 없음: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    print_status(conn)
    status = check_columns(conn)
    all_done = all(status.values())

    if all_done:
        # edges description 초기화만 남아있는지 확인
        bad = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE description IS NULL OR description = '' "
            "OR json_valid(description) = 0"
        ).fetchone()[0]
        if bad == 0:
            print("이미 완전히 마이그레이션된 상태입니다.")
            conn.close()
            return
        if dry_run:
            print(f"[DRY-RUN] edges.description {bad}행 초기화 예정")
            conn.close()
            return

    if dry_run:
        for col, exists in status.items():
            if not exists:
                print(f"[DRY-RUN] {col} 컬럼 추가 예정")
        conn.close()
        return

    # 백업
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / f"memory_before_neural_phase1_{ts}.db"
    shutil.copy2(DB_PATH, backup)
    print(f"백업: {backup}")

    # nodes 컬럼 추가
    if not status["nodes.theta_m"]:
        conn.execute("ALTER TABLE nodes ADD COLUMN theta_m REAL DEFAULT 0.5")
        print("  nodes.theta_m 추가")
    if not status["nodes.activity_history"]:
        conn.execute("ALTER TABLE nodes ADD COLUMN activity_history TEXT DEFAULT '[]'")
        print("  nodes.activity_history 추가")
    if not status["nodes.visit_count"]:
        conn.execute("ALTER TABLE nodes ADD COLUMN visit_count INTEGER DEFAULT 0")
        print("  nodes.visit_count 추가")

    # ALTER TABLE DEFAULT는 기존 행에 적용 안 됨 → 명시적 UPDATE
    updated = conn.execute(
        "UPDATE nodes SET theta_m = 0.5 WHERE theta_m IS NULL"
    ).rowcount
    if updated:
        print(f"  theta_m NULL → 0.5: {updated}행")

    updated = conn.execute(
        "UPDATE nodes SET activity_history = '[]' WHERE activity_history IS NULL"
    ).rowcount
    if updated:
        print(f"  activity_history NULL → '[]': {updated}행")

    # edges.description 초기화 (B-10 재공고화 준비)
    updated = conn.execute(
        "UPDATE edges SET description = '[]' "
        "WHERE description IS NULL OR description = '' OR json_valid(description) = 0"
    ).rowcount
    print(f"  edges.description 초기화: {updated}행")

    conn.commit()
    conn.close()
    print("\n마이그레이션 완료.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        print_status(conn)
        conn.close()
    else:
        run_migration(dry_run=args.dry_run)
