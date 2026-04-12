"""v8 Phase 0 Harden — edge case 테스트 7개.

독립 실행 가능: in-memory DB에 v8 스키마 직접 생성.
conftest.py 의존 없음.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

import pytest


# ── v8 스키마 DDL (sqlite_store.py init_db에서 추출) ──

V8_SCHEMA = """
CREATE TABLE IF NOT EXISTS captures (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    content TEXT NOT NULL,
    project TEXT DEFAULT '',
    session_id TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_captures_actor ON captures(actor);
CREATE INDEX IF NOT EXISTS idx_captures_session ON captures(session_id);
CREATE INDEX IF NOT EXISTS idx_captures_created ON captures(created_at);
CREATE INDEX IF NOT EXISTS idx_captures_source_type ON captures(source_type);

CREATE TRIGGER IF NOT EXISTS captures_no_update BEFORE UPDATE ON captures
BEGIN
    SELECT RAISE(FAIL, 'captures is append-only (invariant 1)');
END;
CREATE TRIGGER IF NOT EXISTS captures_no_delete BEFORE DELETE ON captures
BEGIN
    SELECT RAISE(FAIL, 'captures is append-only (invariant 1)');
END;

CREATE TABLE IF NOT EXISTS feedback_events (
    id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    feedback_type TEXT NOT NULL,
    content TEXT DEFAULT '',
    actor TEXT NOT NULL DEFAULT 'paul',
    created_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_feedback_target ON feedback_events(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback_events(feedback_type);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback_events(created_at);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    capture_id TEXT NOT NULL,
    text TEXT NOT NULL,
    claim_type TEXT DEFAULT '',
    confidence REAL DEFAULT 0.5,
    extractor_model TEXT DEFAULT '',
    extracted_at TEXT NOT NULL,
    status TEXT DEFAULT 'provisional',
    metadata TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_claims_capture ON claims(capture_id);
CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(status);
CREATE INDEX IF NOT EXISTS idx_claims_extracted ON claims(extracted_at);

CREATE TABLE IF NOT EXISTS self_model_traits (
    id TEXT PRIMARY KEY,
    dimension TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT DEFAULT 'provisional',
    approval TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL,
    verified_at TEXT,
    metadata TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_traits_dimension ON self_model_traits(dimension);
CREATE INDEX IF NOT EXISTS idx_traits_status ON self_model_traits(status);
CREATE INDEX IF NOT EXISTS idx_traits_approval ON self_model_traits(approval);

CREATE TABLE IF NOT EXISTS self_trait_evidence (
    id TEXT PRIMARY KEY,
    trait_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    strength REAL DEFAULT 1.0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trevidence_trait ON self_trait_evidence(trait_id);
CREATE INDEX IF NOT EXISTS idx_trevidence_claim ON self_trait_evidence(claim_id);

CREATE TRIGGER IF NOT EXISTS trevidence_claim_fk BEFORE INSERT ON self_trait_evidence
BEGIN
    SELECT CASE
        WHEN NEW.claim_id NOT IN (SELECT id FROM claims)
        THEN RAISE(FAIL, 'D20: claim_id must reference existing claim')
    END;
END;
CREATE TRIGGER IF NOT EXISTS trevidence_claim_fk_update
BEFORE UPDATE ON self_trait_evidence
WHEN NEW.claim_id != OLD.claim_id
BEGIN
    SELECT CASE
        WHEN NEW.claim_id NOT IN (SELECT id FROM claims)
        THEN RAISE(FAIL, 'D20: claim_id must reference existing claim')
    END;
END;

CREATE TABLE IF NOT EXISTS self_trait_conflicts (
    id TEXT PRIMARY KEY,
    trait_id TEXT NOT NULL,
    conflicting_source_type TEXT,
    conflicting_source_id TEXT,
    description TEXT,
    resolved INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_trconflicts_trait ON self_trait_conflicts(trait_id);
CREATE INDEX IF NOT EXISTS idx_trconflicts_resolved ON self_trait_conflicts(resolved);

CREATE TABLE IF NOT EXISTS retrieval_logs (
    id TEXT PRIMARY KEY,
    session_id TEXT DEFAULT '',
    query TEXT DEFAULT '',
    context_pack_id TEXT DEFAULT '',
    returned_ids TEXT NOT NULL DEFAULT '[]',
    slot_distribution TEXT DEFAULT '{}',
    cross_domain INTEGER DEFAULT 0,
    feedback_linked INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rlogs_session ON retrieval_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_rlogs_created ON retrieval_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_rlogs_context_pack ON retrieval_logs(context_pack_id);
"""

# apply_slot_precedence가 참조하는 nodes 테이블 최소 스텁
NODES_STUB = """
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    content TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT ''
);
"""

V8_TABLES = {
    'captures', 'claims', 'self_model_traits', 'self_trait_evidence',
    'self_trait_conflicts', 'feedback_events', 'retrieval_logs',
}

V8_TRIGGERS = {
    'captures_no_update', 'captures_no_delete',
    'trevidence_claim_fk', 'trevidence_claim_fk_update',
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


def _make_db() -> sqlite3.Connection:
    """독립 in-memory DB에 v8 스키마 적용."""
    conn = sqlite3.connect(':memory:')
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(V8_SCHEMA)
    return conn


def _insert_capture(conn: sqlite3.Connection, capture_id: str | None = None) -> str:
    """헬퍼: captures 행 삽입 후 id 반환."""
    cid = capture_id or _uid()
    conn.execute(
        "INSERT INTO captures (id, source_type, actor, content, created_at) VALUES (?,?,?,?,?)",
        (cid, 'manual', 'paul', 'test content', _now()),
    )
    conn.commit()
    return cid


def _insert_claim(conn: sqlite3.Connection, capture_id: str, claim_id: str | None = None) -> str:
    """헬퍼: claims 행 삽입 후 id 반환."""
    clid = claim_id or _uid()
    conn.execute(
        "INSERT INTO claims (id, capture_id, text, extracted_at) VALUES (?,?,?,?)",
        (clid, capture_id, 'test claim', _now()),
    )
    conn.commit()
    return clid


def _insert_trait(conn: sqlite3.Connection, trait_id: str | None = None,
                  status: str = 'provisional', approval: str = 'pending',
                  dimension: str = 'preference') -> str:
    """헬퍼: self_model_traits 행 삽입 후 id 반환."""
    tid = trait_id or _uid()
    conn.execute(
        "INSERT INTO self_model_traits (id, dimension, content, status, approval, created_at) VALUES (?,?,?,?,?,?)",
        (tid, dimension, 'test trait', status, approval, _now()),
    )
    conn.commit()
    return tid


# ====================================================================
# 1. D20 trigger INSERT: 존재하지 않는 claim_id → FAIL
# ====================================================================
class TestD20TriggerInsert:
    """D20 evidence bridge — INSERT 시 claim_id FK 트리거 검증."""

    def test_insert_with_nonexistent_claim_id_fails(self):
        """존재하지 않는 claim_id로 self_trait_evidence INSERT → IntegrityError."""
        conn = _make_db()
        trait_id = _insert_trait(conn)
        fake_claim_id = _uid()

        with pytest.raises(sqlite3.IntegrityError, match="D20"):
            conn.execute(
                "INSERT INTO self_trait_evidence (id, trait_id, claim_id, created_at) VALUES (?,?,?,?)",
                (_uid(), trait_id, fake_claim_id, _now()),
            )

    def test_insert_with_existing_claim_id_succeeds(self):
        """존재하는 claim_id로 INSERT → 정상 동작."""
        conn = _make_db()
        cap_id = _insert_capture(conn)
        claim_id = _insert_claim(conn, cap_id)
        trait_id = _insert_trait(conn)

        conn.execute(
            "INSERT INTO self_trait_evidence (id, trait_id, claim_id, created_at) VALUES (?,?,?,?)",
            (_uid(), trait_id, claim_id, _now()),
        )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM self_trait_evidence").fetchone()[0]
        assert count == 1


# ====================================================================
# 2. D20 trigger UPDATE: claim_id를 존재하지 않는 값으로 UPDATE → FAIL
# ====================================================================
class TestD20TriggerUpdate:
    """D20 evidence bridge — UPDATE 시 claim_id FK 트리거 검증."""

    def test_update_claim_id_to_nonexistent_fails(self):
        """기존 evidence의 claim_id를 존재하지 않는 값으로 UPDATE → IntegrityError."""
        conn = _make_db()
        cap_id = _insert_capture(conn)
        claim_id = _insert_claim(conn, cap_id)
        trait_id = _insert_trait(conn)
        ev_id = _uid()

        conn.execute(
            "INSERT INTO self_trait_evidence (id, trait_id, claim_id, created_at) VALUES (?,?,?,?)",
            (ev_id, trait_id, claim_id, _now()),
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError, match="D20"):
            conn.execute(
                "UPDATE self_trait_evidence SET claim_id=? WHERE id=?",
                (_uid(), ev_id),
            )

    def test_update_non_claim_field_succeeds(self):
        """claim_id 외 필드(strength) UPDATE → 트리거 미발동, 정상 동작."""
        conn = _make_db()
        cap_id = _insert_capture(conn)
        claim_id = _insert_claim(conn, cap_id)
        trait_id = _insert_trait(conn)
        ev_id = _uid()

        conn.execute(
            "INSERT INTO self_trait_evidence (id, trait_id, claim_id, created_at) VALUES (?,?,?,?)",
            (ev_id, trait_id, claim_id, _now()),
        )
        conn.commit()

        conn.execute("UPDATE self_trait_evidence SET strength=0.8 WHERE id=?", (ev_id,))
        conn.commit()

        row = conn.execute("SELECT strength FROM self_trait_evidence WHERE id=?", (ev_id,)).fetchone()
        assert row[0] == pytest.approx(0.8)


# ====================================================================
# 3. captures append-only: UPDATE/DELETE 모두 FAIL
# ====================================================================
class TestCapturesAppendOnly:
    """captures 불변식 1 — UPDATE/DELETE 물리 차단."""

    def test_update_fails(self):
        """captures UPDATE → IntegrityError."""
        conn = _make_db()
        cap_id = _insert_capture(conn)

        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE captures SET content='modified' WHERE id=?", (cap_id,))

    def test_delete_fails(self):
        """captures DELETE → IntegrityError."""
        conn = _make_db()
        cap_id = _insert_capture(conn)

        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM captures WHERE id=?", (cap_id,))

    def test_insert_succeeds(self):
        """captures INSERT → 정상 동작 (append는 허용)."""
        conn = _make_db()
        _insert_capture(conn)
        _insert_capture(conn)

        count = conn.execute("SELECT COUNT(*) FROM captures").fetchone()[0]
        assert count == 2


# ====================================================================
# 4. init_db 스키마 검증: 7 테이블 + 4 트리거 존재
# ====================================================================
class TestSchemaVerification:
    """v8 스키마 초기화 후 필수 객체 존재 확인."""

    def test_all_v8_tables_exist(self):
        """7개 v8 테이블 전부 존재."""
        conn = _make_db()
        found = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        missing = V8_TABLES - found
        assert missing == set(), f"누락 테이블: {missing}"

    def test_all_v8_triggers_exist(self):
        """4개 v8 트리거 전부 존재."""
        conn = _make_db()
        found = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()}
        missing = V8_TRIGGERS - found
        assert missing == set(), f"누락 트리거: {missing}"

    def test_index_count_minimum(self):
        """v8 인덱스 최소 15개 존재 (스키마에 정의된 수)."""
        conn = _make_db()
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        ).fetchone()[0]
        assert count >= 15, f"인덱스 {count}개, 최소 15개 필요"


# ====================================================================
# 5. claims FK NOT NULL: capture_id 빈 값 → 실패
# ====================================================================
class TestClaimsFkNotNull:
    """claims.capture_id NOT NULL 제약 검증."""

    def test_null_capture_id_fails(self):
        """capture_id=NULL → IntegrityError."""
        conn = _make_db()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO claims (id, capture_id, text, extracted_at) VALUES (?,?,?,?)",
                (_uid(), None, 'test', _now()),
            )

    def test_empty_string_capture_id_succeeds(self):
        """capture_id='' → NOT NULL 통과 (빈 문자열은 NULL이 아님).

        주의: 빈 문자열은 SQL 레벨에서 통과하지만, 앱 레벨에서
        실제 capture를 가리키지 않는 orphan claim이 됨.
        v8에서는 loose link이므로 FK 트리거 없음 — 의도적 설계.
        """
        conn = _make_db()

        conn.execute(
            "INSERT INTO claims (id, capture_id, text, extracted_at) VALUES (?,?,?,?)",
            (_uid(), '', 'test', _now()),
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
        assert count == 1


# ====================================================================
# 6. self_model_traits status enum: archived → active 쿼리에서 제외
# ====================================================================
class TestTraitStatusEnum:
    """archived trait이 active 쿼리(verified+approved)에서 제외."""

    def test_archived_excluded_from_active_query(self):
        """status='archived' trait은 verified+approved 쿼리에서 나오지 않음."""
        conn = _make_db()
        _insert_trait(conn, status='verified', approval='approved', dimension='preference')
        _insert_trait(conn, status='archived', approval='approved', dimension='preference')
        _insert_trait(conn, status='verified', approval='approved', dimension='emotion')

        rows = conn.execute(
            """SELECT id FROM self_model_traits
            WHERE status='verified' AND approval='approved'"""
        ).fetchall()
        assert len(rows) == 2

    def test_dormant_excluded_from_active_query(self):
        """status='dormant' trait도 verified+approved 쿼리에서 제외."""
        conn = _make_db()
        _insert_trait(conn, status='verified', approval='approved')
        _insert_trait(conn, status='dormant', approval='approved')

        rows = conn.execute(
            """SELECT id FROM self_model_traits
            WHERE status='verified' AND approval='approved'"""
        ).fetchall()
        assert len(rows) == 1

    def test_provisional_not_in_active(self):
        """status='provisional' (기본값) → verified 쿼리에서 제외."""
        conn = _make_db()
        _insert_trait(conn)  # default: provisional, pending

        rows = conn.execute(
            """SELECT id FROM self_model_traits
            WHERE status='verified' AND approval='approved'"""
        ).fetchall()
        assert len(rows) == 0


# ====================================================================
# 7. feedback_events reject → slot precedence: rejected trait 제외
# ====================================================================
class TestFeedbackRejectSlotPrecedence:
    """feedback_events reject → apply_slot_precedence에서 trait 제외."""

    def _get_active_rejects(self, conn: sqlite3.Connection) -> set[str]:
        """context_pack.py get_active_rejects 로직 복제."""
        rows = conn.execute(
            """SELECT DISTINCT target_id FROM feedback_events
            WHERE feedback_type='reject' AND target_type='trait'"""
        ).fetchall()
        return {r[0] for r in rows}

    def _apply_slot_precedence_reject(self, pack: dict, active_rejects: set[str]) -> dict:
        """apply_slot_precedence의 reject blacklist 로직만 추출."""
        for slot in ('applicable_principles', 'preferences_and_boundaries'):
            items = pack.get(slot, [])
            pack[slot] = [it for it in items if it.get('trait_id') not in active_rejects]
        return pack

    def test_rejected_trait_excluded_from_pack(self):
        """reject feedback이 있는 trait → context pack에서 제외."""
        conn = _make_db()
        conn.executescript(NODES_STUB)

        # trait 2개 생성
        trait_ok = _insert_trait(conn, status='verified', approval='approved')
        trait_bad = _insert_trait(conn, status='verified', approval='approved')

        # trait_bad에 reject feedback
        conn.execute(
            "INSERT INTO feedback_events (id, target_type, target_id, feedback_type, actor, created_at) VALUES (?,?,?,?,?,?)",
            (_uid(), 'trait', trait_bad, 'reject', 'paul', _now()),
        )
        conn.commit()

        active_rejects = self._get_active_rejects(conn)
        assert trait_bad in active_rejects
        assert trait_ok not in active_rejects

        # pack 시뮬레이션
        pack = {
            'applicable_principles': [
                {'trait_id': trait_ok, 'content': 'good'},
                {'trait_id': trait_bad, 'content': 'should be removed'},
            ],
            'preferences_and_boundaries': [
                {'trait_id': trait_bad, 'content': 'also removed'},
            ],
        }

        result = self._apply_slot_precedence_reject(pack, active_rejects)
        assert len(result['applicable_principles']) == 1
        assert result['applicable_principles'][0]['trait_id'] == trait_ok
        assert len(result['preferences_and_boundaries']) == 0

    def test_non_reject_feedback_does_not_exclude(self):
        """approve/correct feedback → trait 제외하지 않음."""
        conn = _make_db()
        trait_id = _insert_trait(conn, status='verified', approval='approved')

        conn.execute(
            "INSERT INTO feedback_events (id, target_type, target_id, feedback_type, actor, created_at) VALUES (?,?,?,?,?,?)",
            (_uid(), 'trait', trait_id, 'approve', 'paul', _now()),
        )
        conn.commit()

        active_rejects = self._get_active_rejects(conn)
        assert trait_id not in active_rejects

    def test_reject_on_non_trait_target_ignored(self):
        """target_type='claim'인 reject → trait reject set에 포함 안 됨."""
        conn = _make_db()
        cap_id = _insert_capture(conn)
        claim_id = _insert_claim(conn, cap_id)

        conn.execute(
            "INSERT INTO feedback_events (id, target_type, target_id, feedback_type, actor, created_at) VALUES (?,?,?,?,?,?)",
            (_uid(), 'claim', claim_id, 'reject', 'paul', _now()),
        )
        conn.commit()

        active_rejects = self._get_active_rejects(conn)
        assert len(active_rejects) == 0
