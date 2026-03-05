#!/usr/bin/env python3
"""migrate_v2_ontology.py — mcp-memory v2.1 Phase 0 마이그레이션.

실행: python scripts/migrate_v2_ontology.py
롤백: 각 단계별 독립 트랜잭션, 실패 시 해당 단계만 rollback.
안전: 기존 nodes/edges 데이터 무손실. 신규 테이블/컬럼 추가 + 관계 교정만.
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import DB_PATH


# ─── 데이터 정의 ────────────────────────────────────────────

ACTIVE_TYPES = [
    # (name, layer, super_type, description, rank)
    # Tier A — 100+ 노드, 13개
    ("Workflow",       1, "System",     "반복적 작업 흐름/프로세스",         "preferred"),
    ("Insight",        2, "Concept",    "관찰에서 도출된 통찰",              "preferred"),
    ("Principle",      3, "Identity",   "행동/판단의 기준이 되는 원칙",      "preferred"),
    ("Decision",       1, "Action",     "선택과 그 근거",                   "preferred"),
    ("Narrative",      0, "Experience", "경험의 서사적 기록",                "normal"),
    ("Tool",           1, "System",     "사용하는 도구/소프트웨어",          "normal"),
    ("Framework",      2, "Concept",    "체계적 사고/분석 틀",              "preferred"),
    ("Skill",          1, "System",     "습득한 기술/능력",                 "normal"),
    ("Project",        1, "System",     "진행 중인 프로젝트",               "normal"),
    ("Goal",           1, "System",     "달성하고자 하는 목표",             "normal"),
    ("Agent",          1, "System",     "AI 에이전트/자동화 구성요소",       "normal"),
    ("Pattern",        2, "Concept",    "반복적으로 관찰되는 구조",          "preferred"),
    ("SystemVersion",  1, "System",     "시스템/도구의 버전 기록",           "normal"),
    # Tier B — 10-100 노드, 11개
    ("Conversation",   0, "Experience", "대화/세션 맥락 기록",              "normal"),
    ("Failure",        1, "Action",     "실패와 그 원인",                   "normal"),
    ("Experiment",     1, "Action",     "실험과 결과",                      "normal"),
    ("Breakthrough",   1, "Action",     "돌파구/중요한 발견",               "normal"),
    ("Identity",       3, "Identity",   "정체성 관련 기록",                 "normal"),
    ("Unclassified",   None, None,      "미분류 노드 (메타)",               "normal"),
    ("Evolution",      1, "Action",     "시간에 따른 변화 기록",             "normal"),
    ("Connection",     2, "Concept",    "개념 간 연결/접합",                "normal"),
    ("Tension",        2, "Concept",    "상충하는 관점/긴장",               "normal"),
    ("Question",       1, "Signal",     "탐구해야 할 질문",                 "normal"),
    ("Observation",    0, "Experience", "관찰/원시 데이터",                 "normal"),
    # Tier C — 1-10 노드, 7개 (L4/L5 포함)
    ("Preference",     0, "Experience", "선호/취향",                        "normal"),
    ("Signal",         1, "Signal",     "아직 패턴이 안 된 관찰 신호",      "normal"),
    ("AntiPattern",    1, "Signal",     "피해야 할 반복 패턴",              "normal"),
    ("Value",          4, "Worldview",  "핵심 가치관",                      "preferred"),
    ("Philosophy",     4, "Worldview",  "세계관/철학적 입장",               "preferred"),
    ("Belief",         4, "Worldview",  "핵심 믿음",                        "preferred"),
    ("Axiom",          5, "Axiom",      "근본 공리/자명한 전제",             "preferred"),
]

DEPRECATED_TYPES = [
    # (name, layer, super_type, description, replaced_by)
    ("Evidence",      0, "Experience", "근거/증거",               "Observation"),
    ("Trigger",       0, "Experience", "트리거/촉발 요인",         "Signal"),
    ("Context",       0, "Experience", "맥락 정보",               "Conversation"),
    ("Plan",          1, "System",     "계획/실행 방안",           "Goal"),
    ("Ritual",        1, "System",     "반복적 의식/루틴",         "Workflow"),
    ("Constraint",    1, "System",     "제약 조건",               "Principle"),
    ("Assumption",    1, "Action",     "가정/전제",               "Belief"),
    ("Heuristic",     2, "Concept",    "경험 법칙",               "Pattern"),
    ("Trade-off",     2, "Concept",    "트레이드오프",             "Tension"),
    ("Metaphor",      2, "Concept",    "비유/은유",               "Connection"),
    ("Concept",       2, "Concept",    "일반 개념",               "Insight"),
    ("Boundary",      3, "Identity",   "경계/한계",               "Principle"),
    ("Vision",        3, "Identity",   "비전/지향점",             "Goal"),
    ("Paradox",       3, "Identity",   "역설/모순",               "Tension"),
    ("Commitment",    3, "Identity",   "약속/헌신",               "Decision"),
    ("Mental Model",  4, "Worldview",  "멘탈 모델",               "Framework"),
    ("Lens",          4, "Worldview",  "관점/시각",               "Framework"),
    ("Wonder",        5, "Axiom",      "경이/경탄",               "Question"),
    ("Aporia",        5, "Axiom",      "아포리아/해결 불가",       "Question"),
]

RELATION_DEFS = [
    # (name, category, direction_constraint, layer_constraint, reverse_of, status, rank)
    # causal (8)
    ("caused_by",       "causal",       "any",        "any",         "resulted_in",    "active", "normal"),
    ("led_to",          "causal",       "any",        "any",         "triggered_by",   "active", "preferred"),
    ("triggered_by",    "causal",       "any",        "any",         "led_to",         "active", "normal"),
    ("resulted_in",     "causal",       "any",        "any",         "caused_by",      "active", "normal"),
    ("resolved_by",     "causal",       "any",        "any",         None,             "active", "normal"),
    ("prevented_by",    "causal",       "any",        "any",         None,             "active", "normal"),
    ("enabled_by",      "causal",       "any",        "any",         None,             "active", "preferred"),
    ("blocked_by",      "causal",       "any",        "any",         None,             "active", "normal"),
    # structural (9, governs 포함)
    ("part_of",          "structural",  "any",        "any",         "contains",       "active", "preferred"),
    ("composed_of",      "structural",  "any",        "any",         None,             "active", "normal"),
    ("extends",          "structural",  "any",        "any",         "derived_from",   "active", "normal"),
    ("governed_by",      "structural",  "downward",   "any",         "governs",        "active", "normal"),
    ("governs",          "structural",  "upward",     "any",         "governed_by",    "active", "normal"),
    ("instantiated_as",  "structural",  "downward",   "cross-layer", None,             "active", "preferred"),
    ("expressed_as",     "structural",  "downward",   "cross-layer", None,             "active", "preferred"),
    ("contains",         "structural",  "any",        "any",         "part_of",        "active", "normal"),
    ("derived_from",     "structural",  "any",        "any",         "extends",        "active", "normal"),
    # layer_movement (6)
    ("realized_as",        "layer_movement", "upward",   "cross-layer", "abstracted_from", "active", "normal"),
    ("crystallized_into",  "layer_movement", "upward",   "cross-layer", None,              "active", "preferred"),
    ("abstracted_from",    "layer_movement", "downward", "cross-layer", "realized_as",     "active", "normal"),
    ("generalizes_to",     "layer_movement", "upward",   "cross-layer", None,              "active", "preferred"),
    ("constrains",         "layer_movement", "any",      "any",         None,              "active", "normal"),
    ("generates",          "layer_movement", "any",      "any",         None,              "active", "normal"),
    # diff_tracking (4)
    ("differs_in",     "diff_tracking", "horizontal", "same-layer", None,             "active", "normal"),
    ("variation_of",   "diff_tracking", "horizontal", "same-layer", None,             "active", "normal"),
    ("evolved_from",   "diff_tracking", "any",        "any",        "succeeded_by",   "active", "normal"),
    ("succeeded_by",   "diff_tracking", "any",        "any",        "evolved_from",   "active", "normal"),
    # semantic (8)
    ("supports",              "semantic", "any",        "any", "contradicts",   "active", "preferred"),
    ("contradicts",           "semantic", "any",        "any", "supports",      "active", "normal"),
    ("analogous_to",          "semantic", "horizontal", "any", None,            "active", "normal"),
    ("parallel_with",         "semantic", "horizontal", "any", None,            "active", "normal"),
    ("reinforces_mutually",   "semantic", "horizontal", "any", None,            "active", "normal"),
    ("connects_with",         "semantic", "any",        "any", None,            "active", "normal"),
    ("inspired_by",           "semantic", "any",        "any", None,            "active", "normal"),
    ("exemplifies",           "semantic", "any",        "any", None,            "active", "normal"),
    # perspective (5, 2개 deprecated)
    ("viewed_through",   "perspective", "any", "any", None, "deprecated", "deprecated"),
    ("interpreted_as",   "perspective", "any", "any", None, "deprecated", "deprecated"),
    ("questions",        "perspective", "any", "any", None, "active",     "normal"),
    ("validates",        "perspective", "any", "any", None, "active",     "normal"),
    ("contextualizes",   "perspective", "any", "any", None, "active",     "normal"),
    # temporal (4)
    ("preceded_by",        "temporal", "any", "any", None, "active", "normal"),
    ("simultaneous_with",  "temporal", "any", "any", None, "active", "normal"),
    ("born_from",          "temporal", "any", "any", None, "active", "normal"),
    ("assembles",          "temporal", "any", "any", None, "active", "normal"),
    # cross_domain (6)
    ("transfers_to",    "cross_domain", "any", "any", None, "active", "normal"),
    ("mirrors",         "cross_domain", "any", "any", None, "active", "normal"),
    ("influenced_by",   "cross_domain", "any", "any", None, "active", "normal"),
    ("showcases",       "cross_domain", "any", "any", None, "active", "normal"),
    ("correlated_with", "cross_domain", "any", "any", None, "active", "normal"),
    ("refuted_by",      "cross_domain", "any", "any", None, "active", "normal"),
]

RELATION_CORRECTIONS = {
    # old_relation -> new_relation (A-11 기반, governs 제외 — 이미 relation_defs에 추가)
    "strengthens":    "supports",
    "validated_by":   "validates",
    "extracted_from": "derived_from",
    "instance_of":    "instantiated_as",
    "evolves_from":   "evolved_from",
}


# ─── 유틸리티 ────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _log(step: int, msg: str, success: bool = True):
    status = "OK" if success else "FAIL"
    print(f"  [{step}/9] {status}: {msg}")


# ─── Step 1: action_log 테이블 ──────────────────────────────

def step1_create_action_log(conn: sqlite3.Connection) -> bool:
    """A-12 확정 스키마. action_log + 인덱스 6개."""
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL,
                session_id TEXT,
                action_type TEXT NOT NULL,
                target_type TEXT,
                target_id INTEGER,
                params TEXT DEFAULT '{}',
                result TEXT DEFAULT '{}',
                context TEXT,
                model TEXT,
                duration_ms INTEGER,
                token_cost INTEGER,
                created_at TEXT NOT NULL,
                CONSTRAINT fk_session FOREIGN KEY (session_id)
                    REFERENCES sessions(session_id)
            );

            CREATE INDEX IF NOT EXISTS idx_action_type
                ON action_log(action_type);
            CREATE INDEX IF NOT EXISTS idx_action_actor
                ON action_log(actor);
            CREATE INDEX IF NOT EXISTS idx_action_session
                ON action_log(session_id);
            CREATE INDEX IF NOT EXISTS idx_action_target
                ON action_log(target_type, target_id);
            CREATE INDEX IF NOT EXISTS idx_action_created
                ON action_log(created_at);

            -- D-5 통합: node_activated 조회 최적화 partial index
            CREATE INDEX IF NOT EXISTS idx_action_node_activated
                ON action_log(action_type, target_id, created_at DESC)
                WHERE action_type = 'node_activated';
        """)
        _log(1, "action_log 테이블 + 인덱스 6개 생성")
        return True
    except Exception as e:
        _log(1, f"action_log 생성 실패: {e}", False)
        return False


# ─── Step 2: meta 테이블 ────────────────────────────────────

def step2_create_meta_tables(conn: sqlite3.Connection) -> bool:
    """A-13 확정. type_defs + relation_defs + ontology_snapshots."""
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS type_defs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                layer INTEGER,
                super_type TEXT,
                description TEXT,
                status TEXT DEFAULT 'active',
                rank TEXT DEFAULT 'normal',
                deprecated_reason TEXT,
                replaced_by TEXT,
                deprecated_at TEXT,
                version INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS relation_defs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                category TEXT,
                direction_constraint TEXT,
                layer_constraint TEXT,
                reverse_of TEXT,
                status TEXT DEFAULT 'active',
                rank TEXT DEFAULT 'normal',
                deprecated_reason TEXT,
                replaced_by TEXT,
                deprecated_at TEXT,
                version INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ontology_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_tag TEXT UNIQUE NOT NULL,
                type_defs_json TEXT,
                relation_defs_json TEXT,
                change_summary TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_type_defs_status
                ON type_defs(status);
            CREATE INDEX IF NOT EXISTS idx_type_defs_super
                ON type_defs(super_type);
            CREATE INDEX IF NOT EXISTS idx_relation_defs_status
                ON relation_defs(status);
            CREATE INDEX IF NOT EXISTS idx_relation_defs_category
                ON relation_defs(category);
        """)
        _log(2, "type_defs + relation_defs + ontology_snapshots 생성")
        return True
    except Exception as e:
        _log(2, f"meta 테이블 생성 실패: {e}", False)
        return False


# ─── Step 3: type_defs 데이터 ───────────────────────────────

def step3_insert_type_defs(conn: sqlite3.Connection) -> bool:
    """31 활성 + 19 deprecated 타입 INSERT."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        # 이미 데이터가 있으면 스킵 (멱등성)
        count = conn.execute("SELECT COUNT(*) FROM type_defs").fetchone()[0]
        if count > 0:
            _log(3, f"type_defs 이미 {count}행 존재 — SKIP")
            return True

        for name, layer, super_type, desc, rank in ACTIVE_TYPES:
            conn.execute(
                """INSERT INTO type_defs
                   (name, layer, super_type, description, status, rank, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'active', ?, ?, ?)""",
                (name, layer, super_type, desc, rank, now, now),
            )

        for name, layer, super_type, desc, replaced_by in DEPRECATED_TYPES:
            conn.execute(
                """INSERT INTO type_defs
                   (name, layer, super_type, description, status, rank,
                    deprecated_reason, replaced_by, deprecated_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'deprecated', 'deprecated',
                           'No instances since creation', ?, ?, ?, ?)""",
                (name, layer, super_type, desc, replaced_by, now, now, now),
            )

        conn.commit()
        _log(3, f"type_defs: {len(ACTIVE_TYPES)} active + {len(DEPRECATED_TYPES)} deprecated = {len(ACTIVE_TYPES) + len(DEPRECATED_TYPES)}개 INSERT")
        return True
    except Exception as e:
        conn.rollback()
        _log(3, f"type_defs INSERT 실패: {e}", False)
        return False


# ─── Step 4: relation_defs 데이터 ───────────────────────────

def step4_insert_relation_defs(conn: sqlite3.Connection) -> bool:
    """관계 정의 INSERT."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        count = conn.execute("SELECT COUNT(*) FROM relation_defs").fetchone()[0]
        if count > 0:
            _log(4, f"relation_defs 이미 {count}행 존재 — SKIP")
            return True

        for name, cat, dir_c, lay_c, rev, status, rank in RELATION_DEFS:
            conn.execute(
                """INSERT INTO relation_defs
                   (name, category, direction_constraint, layer_constraint,
                    reverse_of, status, rank, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, cat, dir_c, lay_c, rev, status, rank, now, now),
            )

        # deprecated 관계 설명 보강
        conn.execute(
            """UPDATE relation_defs
               SET deprecated_reason = 'No instances since creation. Perspective category unused.',
                   deprecated_at = ?
               WHERE name IN ('interpreted_as', 'viewed_through')
                 AND status = 'deprecated'""",
            (now,),
        )

        conn.commit()
        active = conn.execute(
            "SELECT COUNT(*) FROM relation_defs WHERE status='active'"
        ).fetchone()[0]
        dep = conn.execute(
            "SELECT COUNT(*) FROM relation_defs WHERE status='deprecated'"
        ).fetchone()[0]
        _log(4, f"relation_defs: {active} active + {dep} deprecated INSERT")
        return True
    except Exception as e:
        conn.rollback()
        _log(4, f"relation_defs INSERT 실패: {e}", False)
        return False


# ─── Step 5: 잘못된 관계 교정 ───────────────────────────────

def step5_correct_invalid_relations(conn: sqlite3.Connection) -> bool:
    """A-11 기반: 5개 잘못된 관계 교정 + correction_log.
    governs(32)는 relation_defs에 추가 완료 → edge 유지.
    """
    now = datetime.now(timezone.utc).isoformat()
    total = 0
    try:
        for old_rel, new_rel in RELATION_CORRECTIONS.items():
            edges = conn.execute(
                "SELECT id, source_id FROM edges WHERE relation = ?", (old_rel,)
            ).fetchall()

            if not edges:
                continue

            # correction_log 기록 (UPDATE 전)
            # node_id는 NOT NULL — edge의 source_id 사용
            for edge in edges:
                conn.execute(
                    """INSERT INTO correction_log
                       (node_id, edge_id, field, old_value, new_value, reason,
                        corrected_by, created_at)
                       VALUES (?, ?, 'relation', ?, ?,
                               'A-11: invalid relation corrected (v2.1 migration)',
                               'migration', ?)""",
                    (edge["source_id"], edge["id"], old_rel, new_rel, now),
                )

            count = conn.execute(
                "UPDATE edges SET relation = ? WHERE relation = ?",
                (new_rel, old_rel),
            ).rowcount
            total += count
            print(f"    {old_rel} -> {new_rel}: {count} edges")

        conn.commit()
        _log(5, f"관계 교정 완료: {total} edges ({len(RELATION_CORRECTIONS)}개 매핑)")
        return True
    except Exception as e:
        conn.rollback()
        _log(5, f"관계 교정 실패: {e}", False)
        return False


# ─── Step 6: edges.description JSON 마이그레이션 ────────────

def step6_migrate_edge_descriptions(conn: sqlite3.Connection) -> bool:
    """B-10: 빈 문자열/NULL/비-JSON → '[]' 초기화.

    재공고화 메커니즘이 edges.description을 JSON 맥락 로그로 재사용.
    기존 텍스트 설명은 별도 보존 후 초기화.
    """
    try:
        # 1. 현재 상태 진단
        stats = conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN description IS NULL OR description = '' THEN 1 ELSE 0 END) AS empty,
                SUM(CASE WHEN description LIKE 'auto:%' THEN 1 ELSE 0 END) AS auto_desc,
                SUM(CASE WHEN description LIKE '[%' THEN 1 ELSE 0 END) AS already_json
            FROM edges
        """).fetchone()
        print(f"    진단: total={stats['total']}, empty={stats['empty']}, "
              f"auto_desc={stats['auto_desc']}, already_json={stats['already_json']}")

        # 2. 비어있거나 비-JSON → '[]'
        migrated = conn.execute("""
            UPDATE edges SET description = '[]'
            WHERE description IS NULL
               OR description = ''
               OR (length(trim(description)) > 0
                   AND NOT (description LIKE '[%' AND description LIKE '%]'))
        """).rowcount

        # 3. 이미 JSON 배열인 것 중 유효하지 않은 것 정리 (Python 레벨)
        rows = conn.execute(
            "SELECT id, description FROM edges WHERE description LIKE '[%'"
        ).fetchall()
        fixed = 0
        for row in rows:
            try:
                parsed = json.loads(row["description"])
                if not isinstance(parsed, list):
                    conn.execute(
                        "UPDATE edges SET description = '[]' WHERE id = ?",
                        (row["id"],),
                    )
                    fixed += 1
            except (json.JSONDecodeError, ValueError):
                conn.execute(
                    "UPDATE edges SET description = '[]' WHERE id = ?",
                    (row["id"],),
                )
                fixed += 1

        conn.commit()
        _log(6, f"edges.description 마이그레이션: {migrated} 초기화, {fixed} JSON 교정")
        return True
    except Exception as e:
        conn.rollback()
        _log(6, f"edges.description 마이그레이션 실패: {e}", False)
        return False


# ─── Step 7: activation_log VIEW ────────────────────────────

def step7_create_activation_view(conn: sqlite3.Connection) -> bool:
    """A-12: D-5 activation_log를 action_log VIEW로 구현."""
    try:
        conn.execute("DROP VIEW IF EXISTS activation_log")
        conn.execute("""
            CREATE VIEW activation_log AS
            SELECT
                al.id,
                al.target_id AS node_id,
                al.session_id,
                al.created_at AS activated_at,
                json_extract(al.params, '$.context_query') AS context_query,
                json_extract(al.params, '$.activation_score') AS activation_score,
                json_extract(al.params, '$.activation_rank') AS activation_rank,
                json_extract(al.params, '$.channel') AS channel,
                json_extract(al.params, '$.node_type') AS node_type,
                json_extract(al.params, '$.node_layer') AS node_layer
            FROM action_log al
            WHERE al.action_type = 'node_activated'
        """)
        _log(7, "activation_log VIEW 생성")
        return True
    except Exception as e:
        _log(7, f"activation_log VIEW 실패: {e}", False)
        return False


# ─── Step 8: 초기 스냅샷 ────────────────────────────────────

def step8_create_initial_snapshot(conn: sqlite3.Connection) -> bool:
    """A-13: v2.1-initial 스냅샷 생성."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        existing = conn.execute(
            "SELECT id FROM ontology_snapshots WHERE version_tag = 'v2.1-initial'"
        ).fetchone()
        if existing:
            _log(8, "v2.1-initial 스냅샷 이미 존재 — SKIP")
            return True

        types_json = conn.execute("""
            SELECT json_group_array(json_object(
                'name', name, 'layer', layer, 'super_type', super_type,
                'status', status, 'rank', rank, 'replaced_by', replaced_by
            )) FROM type_defs
        """).fetchone()[0]

        rels_json = conn.execute("""
            SELECT json_group_array(json_object(
                'name', name, 'category', category, 'status', status,
                'rank', rank, 'reverse_of', reverse_of
            )) FROM relation_defs
        """).fetchone()[0]

        conn.execute(
            """INSERT INTO ontology_snapshots
               (version_tag, type_defs_json, relation_defs_json, change_summary, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                "v2.1-initial",
                types_json,
                rels_json,
                "Initial v2.1 migration: 31 active + 19 deprecated types, "
                "47 active + 2 deprecated relations, "
                "5 invalid relation corrections, "
                "edges.description JSON migration",
                now,
            ),
        )
        conn.commit()
        _log(8, "ontology_snapshots v2.1-initial 생성")
        return True
    except Exception as e:
        conn.rollback()
        _log(8, f"스냅샷 생성 실패: {e}", False)
        return False


# ─── Step 9: nodes 컬럼 추가 ────────────────────────────────

def step9_add_node_columns(conn: sqlite3.Connection) -> bool:
    """B-index: BCM/UCB용 컬럼 3개 추가 (theta_m, activity_history, visit_count)."""
    columns = [
        ("theta_m",          "REAL DEFAULT 0.5"),
        ("activity_history", "TEXT DEFAULT '[]'"),
        ("visit_count",      "INTEGER DEFAULT 0"),
    ]
    added = 0
    try:
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(nodes)").fetchall()
        }
        for col_name, col_def in columns:
            if col_name in existing:
                continue
            conn.execute(f"ALTER TABLE nodes ADD COLUMN {col_name} {col_def}")
            added += 1

        conn.commit()
        if added:
            _log(9, f"nodes 컬럼 {added}개 추가: {', '.join(c for c, _ in columns if c not in existing)}")
        else:
            _log(9, "nodes 컬럼 이미 존재 — SKIP")
        return True
    except Exception as e:
        conn.rollback()
        _log(9, f"nodes 컬럼 추가 실패: {e}", False)
        return False


# ─── 메인 ───────────────────────────────────────────────────

def migrate():
    """전체 마이그레이션 실행."""
    print(f"\n{'='*60}")
    print(f"mcp-memory v2.1 Phase 0 Migration")
    print(f"DB: {DB_PATH}")
    print(f"시작: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}\n")

    conn = _connect()
    steps = [
        step1_create_action_log,
        step2_create_meta_tables,
        step3_insert_type_defs,
        step4_insert_relation_defs,
        step5_correct_invalid_relations,
        step6_migrate_edge_descriptions,
        step7_create_activation_view,
        step8_create_initial_snapshot,
        step9_add_node_columns,
    ]

    results = []
    for i, step_fn in enumerate(steps, 1):
        ok = step_fn(conn)
        results.append(ok)
        if not ok:
            print(f"\n  !! Step {i} 실패 — 후속 단계 계속 시도")

    conn.close()

    passed = sum(results)
    failed = len(results) - passed
    print(f"\n{'='*60}")
    print(f"완료: {passed}/{len(results)} 단계 성공", end="")
    if failed:
        print(f", {failed} 실패")
        failed_steps = [i+1 for i, ok in enumerate(results) if not ok]
        print(f"  실패 단계: {failed_steps}")
    else:
        print(" — 마이그레이션 완료!")
    print(f"{'='*60}\n")

    return all(results)


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
