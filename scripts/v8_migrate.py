"""
v8 Phase 0 Migration — legacy nodes → self_model_traits 시드
SoT: 07_ontology-redesign_0410/foundation/principles.md Migration Contract R1-R10
실데이터 기반: Identity 63 (active 41) + 에지 ~80건 + Unclassified 38 + Correction contradicts 4

실행:
    cd /c/dev/01_projects/06_mcp-memory
    PYTHONIOENCODING=utf-8 python scripts/v8_migrate.py [--dry-run]

규칙:
- 기존 nodes 테이블은 건드리지 않음 (R1: concepts로 리브랜딩 예정)
- Unclassified 38개만 status='archived' (R6)
- Identity 41개 → self_model_traits 시드 (R4)
- generalizes_to/expressed_as/instantiated_as 에지 → self_trait_evidence (D20 bridge)
- Correction contradicts Identity → self_trait_conflicts (D20 보호)
- UUID v7 timestamp-sortable (간이 구현)
"""

import sqlite3
import json
import uuid
import time
import secrets
import sys
import argparse
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'data' / 'memory.db'


def uuid_v7() -> str:
    """UUID v7 (RFC 9562 draft) — timestamp-sortable.
    Layout: 48bit timestamp_ms + 4bit ver(7) + 12bit rand_a + 2bit var + 62bit rand_b
    """
    ts_ms = int(time.time() * 1000)
    ts_bytes = ts_ms.to_bytes(6, 'big')
    rand = secrets.token_bytes(10)
    byte6 = bytes([0x70 | (rand[0] & 0x0f)])
    byte7 = bytes([rand[1]])
    byte8 = bytes([0x80 | (rand[2] & 0x3f)])
    byte9 = bytes([rand[3]])
    rest = rand[4:]
    full = ts_bytes + byte6 + byte7 + byte8 + byte9 + rest
    return str(uuid.UUID(bytes=full))


def ensure_schema(conn: sqlite3.Connection) -> None:
    """v8 스키마 존재 확인."""
    required = {
        'captures', 'claims', 'self_model_traits',
        'self_trait_evidence', 'self_trait_conflicts',
        'feedback_events', 'retrieval_logs'
    }
    found = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    missing = required - found
    if missing:
        print(f"ERROR: v8 스키마 누락: {missing}")
        print("먼저 init_db() 실행 필요:")
        print("  python -c 'from storage.sqlite_store import init_db; init_db()'")
        sys.exit(1)


def migrate_identity_to_traits(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """Identity active 41개 → self_model_traits 시드 (R4)."""
    rows = conn.execute("""
        SELECT id, content, source, source_kind, epistemic_status, created_at
        FROM nodes
        WHERE type='Identity' AND status='active'
    """).fetchall()
    print(f"[R4] Identity active: {len(rows)}")

    migrated = 0
    for old_id, content, source, source_kind, epistemic_status, created_at in rows:
        new_id = uuid_v7()
        # epistemic_status → v8 status/approval
        if epistemic_status == 'validated':
            status, approval = 'verified', 'approved'
        elif epistemic_status == 'outdated':
            status, approval = 'dormant', 'expired'
        elif epistemic_status == 'flagged':
            status, approval = 'provisional', 'rejected'
        else:
            status, approval = 'provisional', 'pending'

        metadata = {
            'migrated_from_node_id': old_id,
            'migration_source': source,
            'migration_source_kind': source_kind,
            'dimension_needs_classification': True,
        }

        if dry_run:
            migrated += 1
            continue

        try:
            conn.execute("""
                INSERT INTO self_model_traits
                (id, dimension, content, status, approval, created_at, verified_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                new_id,
                'unclassified',  # Day 3 Paul 승인 세션에서 8차원 중 하나로 분류
                content,
                status,
                approval,
                created_at,
                created_at if status == 'verified' else None,
                json.dumps(metadata, ensure_ascii=False),
            ))
            migrated += 1
        except sqlite3.IntegrityError as e:
            print(f"  skip old_id={old_id}: {e}")

    if not dry_run:
        conn.commit()
    print(f"[R4] → self_model_traits: {migrated}")
    return migrated


def migrate_edges_to_evidence(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """X generalizes_to/expressed_as/instantiated_as Identity → self_trait_evidence (D20)."""
    rows = conn.execute("""
        SELECT e.source_id, e.target_id, e.relation, e.strength, e.created_at,
               n1.type AS source_type
        FROM edges e
        JOIN nodes n1 ON e.source_id = n1.id
        JOIN nodes n2 ON e.target_id = n2.id
        WHERE n2.type='Identity' AND n2.status='active' AND e.status='active'
          AND e.relation IN ('generalizes_to', 'expressed_as', 'instantiated_as')
    """).fetchall()
    print(f"[D20] Identity evidence edges: {len(rows)}")

    bridged = 0
    for src_id, tgt_id, relation, strength, created_at, source_type in rows:
        # target Identity의 new trait_id 조회
        trait_row = conn.execute("""
            SELECT id FROM self_model_traits
            WHERE json_extract(metadata, '$.migrated_from_node_id') = ?
        """, (tgt_id,)).fetchone()
        if not trait_row:
            continue
        new_trait_id = trait_row[0]

        # claim_id placeholder: legacy concept id를 문자열로 저장
        # Phase 1 PG 이주 시점에 실제 claim 매핑으로 전환
        claim_placeholder = f"legacy:{source_type}:{src_id}"

        if dry_run:
            bridged += 1
            continue

        try:
            conn.execute("""
                INSERT INTO self_trait_evidence
                (id, trait_id, claim_id, strength, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                uuid_v7(),
                new_trait_id,
                claim_placeholder,
                strength or 1.0,
                created_at,
            ))
            bridged += 1
        except sqlite3.IntegrityError as e:
            print(f"  skip evidence: {e}")

    if not dry_run:
        conn.commit()
    print(f"[D20] → self_trait_evidence: {bridged}")
    return bridged


def migrate_correction_to_conflicts(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """Correction contradicts Identity → self_trait_conflicts."""
    rows = conn.execute("""
        SELECT e.source_id, e.target_id, e.reason, e.description, e.created_at
        FROM edges e
        JOIN nodes n1 ON e.source_id = n1.id
        JOIN nodes n2 ON e.target_id = n2.id
        WHERE n1.type='Correction' AND n2.type='Identity' AND e.status='active'
          AND e.relation='contradicts'
    """).fetchall()
    print(f"[F2] Correction contradicts Identity: {len(rows)}")

    conflicted = 0
    for src_id, tgt_id, reason, description, created_at in rows:
        trait_row = conn.execute("""
            SELECT id FROM self_model_traits
            WHERE json_extract(metadata, '$.migrated_from_node_id') = ?
        """, (tgt_id,)).fetchone()
        if not trait_row:
            continue

        if dry_run:
            conflicted += 1
            continue

        desc = description or reason or ''
        try:
            conn.execute("""
                INSERT INTO self_trait_conflicts
                (id, trait_id, conflicting_source_type, conflicting_source_id, description, resolved, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                uuid_v7(),
                trait_row[0],
                'correction',
                f"legacy:node:{src_id}",
                desc,
                0,
                created_at,
            ))
            conflicted += 1
        except sqlite3.IntegrityError as e:
            print(f"  skip conflict: {e}")

    if not dry_run:
        conn.commit()
    print(f"[F2] → self_trait_conflicts: {conflicted}")
    return conflicted


def archive_unclassified(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """Unclassified 38개 → status='archived' (R6)."""
    rows = conn.execute("""
        SELECT COUNT(*) FROM nodes WHERE type='Unclassified' AND status='active'
    """).fetchone()
    count = rows[0]
    print(f"[R6] Unclassified active: {count}")

    if dry_run:
        return count

    cur = conn.execute("""
        UPDATE nodes SET status='archived', updated_at=datetime('now')
        WHERE type='Unclassified' AND status='active'
    """)
    conn.commit()
    print(f"[R6] archived: {cur.rowcount}")
    return cur.rowcount


def main():
    parser = argparse.ArgumentParser(description='v8 Phase 0 migration')
    parser.add_argument('--dry-run', action='store_true', help='실제 INSERT/UPDATE 없이 카운트만')
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: DB 없음: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    try:
        ensure_schema(conn)

        print(f"\n{'=' * 50}")
        print(f"v8 Migration {'(DRY RUN)' if args.dry_run else ''}")
        print(f"DB: {DB_PATH}")
        print(f"{'=' * 50}\n")

        traits = migrate_identity_to_traits(conn, args.dry_run)
        evidence = migrate_edges_to_evidence(conn, args.dry_run)
        conflicts = migrate_correction_to_conflicts(conn, args.dry_run)
        archived = archive_unclassified(conn, args.dry_run)

        print(f"\n{'=' * 50}")
        print(f"Migration {'preview' if args.dry_run else 'complete'}:")
        print(f"  self_model_traits:   {traits}")
        print(f"  self_trait_evidence: {evidence}")
        print(f"  self_trait_conflicts:{conflicts}")
        print(f"  nodes archived:      {archived}")
        print(f"{'=' * 50}")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
