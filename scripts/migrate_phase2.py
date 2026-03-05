"""Phase 2 DB 마이그레이션 — score_history, θ_m, activity_history 컬럼 추가.

실행: python scripts/migrate_phase2.py [--dry-run]
"""
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "memory.db"

MIGRATIONS = [
    # nodes 테이블 확장
    "ALTER TABLE nodes ADD COLUMN score_history TEXT DEFAULT '[]'",
    "ALTER TABLE nodes ADD COLUMN promotion_candidate INTEGER DEFAULT 0",
    "ALTER TABLE nodes ADD COLUMN θ_m REAL DEFAULT 0.5",
    "ALTER TABLE nodes ADD COLUMN activity_history TEXT DEFAULT '[]'",
    # meta 테이블
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT DEFAULT '0')",
    "INSERT OR IGNORE INTO meta VALUES ('total_recall_count', '0')",
    # recall_log 테이블
    """CREATE TABLE IF NOT EXISTS recall_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        node_id INTEGER,
        source TEXT,
        query_hash TEXT,
        recalled_at TEXT
    )""",
]


def run(dry_run: bool = False) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 기존 컬럼 확인 (이미 있으면 스킵)
    cur.execute("PRAGMA table_info(nodes)")
    existing = {row[1] for row in cur.fetchall()}

    ok = 0
    skipped = 0
    for sql in MIGRATIONS:
        sql_clean = sql.strip()
        # ALTER TABLE 중복 방지
        if sql_clean.startswith("ALTER TABLE nodes ADD COLUMN"):
            col = sql_clean.split("ADD COLUMN")[1].strip().split()[0]
            if col in existing:
                print(f"  SKIP (exists): {col}")
                skipped += 1
                continue
        if dry_run:
            print(f"  DRY: {sql_clean[:80]}")
        else:
            try:
                cur.execute(sql_clean)
                print(f"  OK: {sql_clean[:80]}")
                ok += 1
            except sqlite3.OperationalError as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print(f"  SKIP (already exists): {sql_clean[:40]}")
                    skipped += 1
                else:
                    print(f"  ERROR: {e}")
                    conn.close()
                    sys.exit(1)

    if not dry_run:
        conn.commit()
    conn.close()
    print(f"\n완료: {ok}개 실행, {skipped}개 스킵{'(dry-run)' if dry_run else ''}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    if dry:
        print("=== DRY RUN (DB 변경 없음) ===")
    run(dry_run=dry)
