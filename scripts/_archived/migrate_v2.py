#!/usr/bin/env python3
"""
migrate_v2.py — mcp-memory v1 → v2.0 스키마 마이그레이션

해결하는 리스크: C4(스키마), C8(신규노드판별), S8(edges컬럼), S10(correction_log)

Usage:
  python scripts/migrate_v2.py              # 실행
  python scripts/migrate_v2.py --dry-run    # DB 변경 없이 상태 확인
  python scripts/migrate_v2.py --check      # 마이그레이션 상태만 확인
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

# v2.0 type → layer 매핑 (45 active types)
TYPE_TO_LAYER = {
    # Layer 0 — 원시 경험
    "Observation": 0, "Evidence": 0, "Trigger": 0, "Context": 0,
    "Conversation": 0, "Narrative": 0, "Question": 0, "Preference": 0,
    # Layer 1 — 행위/사건
    "Decision": 1, "Plan": 1, "Workflow": 1, "Experiment": 1,
    "Failure": 1, "Breakthrough": 1, "Evolution": 1, "Signal": 1,
    "Goal": 1, "Ritual": 1, "Tool": 1, "Skill": 1,
    "AntiPattern": 1, "Constraint": 1, "Assumption": 1,
    "SystemVersion": 1, "Agent": 1, "Project": 1,
    # Layer 2 — 개념/패턴
    "Pattern": 2, "Insight": 2, "Framework": 2, "Heuristic": 2,
    "Trade-off": 2, "Tension": 2, "Metaphor": 2, "Connection": 2,
    "Concept": 2,
    # Layer 3 — 원칙/정체성
    "Principle": 3, "Identity": 3, "Boundary": 3, "Vision": 3,
    "Paradox": 3, "Commitment": 3,
    # Layer 4 — 세계관
    "Belief": 4, "Philosophy": 4, "Mental Model": 4, "Lens": 4,
    # Layer 5 — 가치/존재론
    "Axiom": 5, "Value": 5, "Wonder": 5, "Aporia": 5,
}


def backup_db() -> Path:
    """마이그레이션 전 DB 백업."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dest = BACKUP_DIR / f"memory_pre_v2_{ts}.db"
    shutil.copy2(str(DB_PATH), str(dest))
    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"  백업: {dest.name} ({size_mb:.1f}MB)")
    return dest


def get_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """테이블의 현재 컬럼 목록."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def add_column(conn: sqlite3.Connection, table: str, name: str,
               col_type: str, default=None) -> bool:
    """컬럼이 없으면 추가. 추가했으면 True."""
    if name in get_columns(conn, table):
        return False
    sql = f"ALTER TABLE {table} ADD COLUMN {name} {col_type}"
    if default is not None:
        if isinstance(default, str):
            sql += f" DEFAULT '{default}'"
        else:
            sql += f" DEFAULT {default}"
    conn.execute(sql)
    return True


# ─── Step 1: nodes 스키마 ─────────────────────────────────

def step1_nodes_schema(conn: sqlite3.Connection) -> int:
    print("\n[1/7] nodes 스키마 확장...")
    cols = [
        ("layer",              "INTEGER", None),
        ("summary",            "TEXT",    None),
        ("key_concepts",       "TEXT",    None),       # JSON array
        ("facets",             "TEXT",    None),       # JSON array
        ("domains",            "TEXT",    None),       # JSON array
        ("secondary_types",    "TEXT",    None),       # JSON array
        ("quality_score",      "REAL",    None),
        ("abstraction_level",  "REAL",    None),
        ("temporal_relevance", "REAL",    None),
        ("actionability",      "REAL",    None),
        ("enrichment_status",  "TEXT",    "{}"),       # JSON object
        ("enriched_at",        "TEXT",    None),
        ("tier",               "INTEGER", 2),          # 0=core, 1=reviewed, 2=auto
        ("maturity",           "REAL",    0.0),        # 0.0-1.0
        ("observation_count",  "INTEGER", 0),          # 유사 관찰 횟수
    ]
    added = 0
    for name, ctype, default in cols:
        if add_column(conn, "nodes", name, ctype, default):
            print(f"  + nodes.{name}")
            added += 1
    if added == 0:
        print("  (모든 컬럼 이미 존재)")
    return added


# ─── Step 2: edges 스키마 ─────────────────────────────────

def step2_edges_schema(conn: sqlite3.Connection) -> int:
    print("\n[2/7] edges 스키마 확장...")
    cols = [
        ("direction",      "TEXT",    None),
        ("reason",         "TEXT",    None),
        ("updated_at",     "TEXT",    None),
        ("base_strength",  "REAL",    None),
        ("frequency",      "INTEGER", 0),
        ("last_activated", "TEXT",    None),
        ("decay_rate",     "REAL",    0.005),
        ("layer_distance", "INTEGER", None),
        ("layer_penalty",  "REAL",    None),
    ]
    added = 0
    for name, ctype, default in cols:
        if add_column(conn, "edges", name, ctype, default):
            print(f"  + edges.{name}")
            added += 1
    if added == 0:
        print("  (모든 컬럼 이미 존재)")
    return added


# ─── Step 3: correction_log ───────────────────────────────

def step3_correction_log(conn: sqlite3.Connection):
    print("\n[3/7] correction_log 테이블...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS correction_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id      INTEGER NOT NULL REFERENCES nodes(id),
            field        TEXT    NOT NULL,
            old_value    TEXT,
            new_value    TEXT,
            reason       TEXT,
            corrected_by TEXT    DEFAULT 'system',
            created_at   TEXT    NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_correction_node ON correction_log(node_id)"
    )
    print("  correction_log 준비 완료")


# ─── Step 4: FTS5 재구축 ─────────────────────────────────

def step4_rebuild_fts(conn: sqlite3.Connection):
    print("\n[4/7] FTS5 재구축...")

    # 이미 v2 상태면 스킵
    fts_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='nodes_fts'"
    ).fetchone()
    if fts_row and fts_row[0] and "summary" in fts_row[0]:
        print("  FTS5 이미 v2 — 스킵")
        return

    # 트리거 삭제
    for t in ("nodes_ai", "nodes_ad", "nodes_au"):
        conn.execute(f"DROP TRIGGER IF EXISTS {t}")
    print("  트리거 삭제")

    # FTS 삭제 + 재생성
    conn.execute("DROP TABLE IF EXISTS nodes_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE nodes_fts USING fts5(
            content, tags, project, summary, key_concepts,
            content='nodes', content_rowid='id',
            tokenize='trigram'
        )
    """)
    print("  FTS5 테이블 재생성 (content, tags, project, summary, key_concepts)")

    # 트리거 재생성 — executescript 사용 (BEGIN...END 파싱 안전)
    conn.executescript("""
        CREATE TRIGGER nodes_ai AFTER INSERT ON nodes BEGIN
            INSERT INTO nodes_fts(rowid, content, tags, project, summary, key_concepts)
            VALUES (new.id, new.content, new.tags, new.project,
                    COALESCE(new.summary, ''), COALESCE(new.key_concepts, ''));
        END;

        CREATE TRIGGER nodes_ad AFTER DELETE ON nodes BEGIN
            INSERT INTO nodes_fts(nodes_fts, rowid, content, tags, project, summary, key_concepts)
            VALUES ('delete', old.id, old.content, old.tags, old.project,
                    COALESCE(old.summary, ''), COALESCE(old.key_concepts, ''));
        END;

        CREATE TRIGGER nodes_au AFTER UPDATE ON nodes BEGIN
            INSERT INTO nodes_fts(nodes_fts, rowid, content, tags, project, summary, key_concepts)
            VALUES ('delete', old.id, old.content, old.tags, old.project,
                    COALESCE(old.summary, ''), COALESCE(old.key_concepts, ''));
            INSERT INTO nodes_fts(rowid, content, tags, project, summary, key_concepts)
            VALUES (new.id, new.content, new.tags, new.project,
                    COALESCE(new.summary, ''), COALESCE(new.key_concepts, ''));
        END;
    """)
    print("  트리거 재생성")

    # 기존 데이터 인덱싱
    count = conn.execute("""
        INSERT INTO nodes_fts(rowid, content, tags, project, summary, key_concepts)
        SELECT id, content, tags, project,
               COALESCE(summary, ''), COALESCE(key_concepts, '')
        FROM nodes
    """).rowcount
    print(f"  FTS 인덱스 구축: {count}개 노드")


# ─── Step 5: layer 배정 ──────────────────────────────────

def step5_assign_layers(conn: sqlite3.Connection) -> dict:
    print("\n[5/7] 기존 노드 layer 배정...")
    types = conn.execute(
        "SELECT type, COUNT(*) FROM nodes GROUP BY type ORDER BY COUNT(*) DESC"
    ).fetchall()

    unmapped = {}
    total_mapped = 0
    for tname, cnt in types:
        layer = TYPE_TO_LAYER.get(tname)
        if layer is not None:
            updated = conn.execute(
                "UPDATE nodes SET layer = ? WHERE type = ? AND layer IS NULL",
                (layer, tname),
            ).rowcount
            total_mapped += updated
            if updated > 0:
                print(f"  {tname} ({updated}/{cnt}) → L{layer}")
        else:
            unmapped[tname] = cnt
            print(f"  {tname} ({cnt}) → NULL (미매핑)")

    print(f"  매핑 완료: {total_mapped}개")
    if unmapped:
        print(f"  미매핑: {sum(unmapped.values())}개 {unmapped}")
    return unmapped


# ─── Step 6: edge 기본값 ─────────────────────────────────

def step6_edge_defaults(conn: sqlite3.Connection):
    print("\n[6/7] edges 기본값...")

    # strength → base_strength
    n = conn.execute(
        "UPDATE edges SET base_strength = strength WHERE base_strength IS NULL"
    ).rowcount
    print(f"  strength → base_strength: {n}개")

    # layer_distance / layer_penalty (UPDATE...FROM 구문, SQLite 3.33+)
    n = conn.execute("""
        UPDATE edges SET
            layer_distance = ABS(s.layer - t.layer),
            layer_penalty = CASE
                WHEN ABS(s.layer - t.layer) <= 1 THEN 1.0
                WHEN ABS(s.layer - t.layer) = 2  THEN 0.6
                ELSE 0.3
            END
        FROM nodes s, nodes t
        WHERE edges.source_id = s.id AND edges.target_id = t.id
          AND s.layer IS NOT NULL AND t.layer IS NOT NULL
          AND edges.layer_distance IS NULL
    """).rowcount
    print(f"  layer_distance/penalty: {n}개")


# ─── Step 7: 인덱스 ──────────────────────────────────────

def step7_indexes(conn: sqlite3.Connection):
    print("\n[7/7] 인덱스 생성...")
    for name, table, col in [
        ("idx_nodes_layer",       "nodes", "layer"),
        ("idx_nodes_enriched_at", "nodes", "enriched_at"),
        ("idx_edges_direction",   "edges", "direction"),
        ("idx_edges_relation",    "edges", "relation"),
    ]:
        conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({col})")
        print(f"  {name}")


# ─── 상태 확인 ────────────────────────────────────────────

def check_status(conn: sqlite3.Connection) -> bool:
    print("\n=== v2.0 마이그레이션 상태 ===\n")
    ok = True

    # nodes 컬럼
    have = get_columns(conn, "nodes")
    need = {"layer", "summary", "key_concepts", "facets", "domains",
            "secondary_types", "quality_score", "abstraction_level",
            "temporal_relevance", "actionability", "enrichment_status",
            "enriched_at", "tier", "maturity", "observation_count"}
    miss = need - have
    status = "OK" if not miss else f"누락 {miss}"
    print(f"nodes 컬럼: {len(need) - len(miss)}/{len(need)} - {status}")
    ok = ok and not miss

    # edges 컬럼
    have = get_columns(conn, "edges")
    need = {"direction", "reason", "updated_at", "base_strength",
            "frequency", "last_activated", "decay_rate",
            "layer_distance", "layer_penalty"}
    miss = need - have
    status = "OK" if not miss else f"누락 {miss}"
    print(f"edges 컬럼: {len(need) - len(miss)}/{len(need)} - {status}")
    ok = ok and not miss

    # correction_log
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    has_cl = "correction_log" in tables
    print(f"correction_log: {'OK' if has_cl else 'MISSING'}")
    ok = ok and has_cl

    # FTS5
    fts = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='nodes_fts'"
    ).fetchone()
    has_fts = fts and fts[0] and "summary" in fts[0]
    print(f"FTS5 v2: {'OK' if has_fts else 'MISSING'}")
    ok = ok and has_fts

    # layer 커버리지
    total = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    if "layer" in get_columns(conn, "nodes"):
        layered = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE layer IS NOT NULL"
        ).fetchone()[0]
        pct = (layered / total * 100) if total else 0
        print(f"layer: {layered}/{total} ({pct:.1f}%)")
    else:
        print(f"layer: N/A (컬럼 없음, 노드 {total}개)")

    # edge base_strength
    etotal = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    if "base_strength" in get_columns(conn, "edges"):
        ebase = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE base_strength IS NOT NULL"
        ).fetchone()[0]
        print(f"base_strength: {ebase}/{etotal}")
    else:
        print(f"base_strength: N/A (컬럼 없음, 엣지 {etotal}개)")

    print(f"\n전체: {'READY' if ok else 'INCOMPLETE'}")
    return ok


# ─── main ─────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="mcp-memory v1 → v2.0 스키마 마이그레이션"
    )
    ap.add_argument("--dry-run", action="store_true",
                    help="DB 변경 없이 상태 확인")
    ap.add_argument("--check", action="store_true",
                    help="마이그레이션 상태만 확인")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"DB 없음: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    if args.check or args.dry_run:
        check_status(conn)
        conn.close()
        return

    print("=" * 50)
    print("mcp-memory v1 → v2.0 스키마 마이그레이션")
    print("=" * 50)

    backup_path = backup_db()

    try:
        step1_nodes_schema(conn)
        step2_edges_schema(conn)
        step3_correction_log(conn)
        step4_rebuild_fts(conn)
        step5_assign_layers(conn)
        step6_edge_defaults(conn)
        step7_indexes(conn)
        conn.commit()

        print("\n" + "=" * 50)
        print("v2.0 마이그레이션 완료")
        print("=" * 50)
        check_status(conn)

    except Exception as e:
        conn.rollback()
        print(f"\n[에러] {e}")
        print(f"롤백 완료. 백업: {backup_path}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
