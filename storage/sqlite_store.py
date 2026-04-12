"""SQLite storage with FTS5 for keyword search."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from config import ALL_RELATIONS, DB_PATH, PROMOTE_LAYER, canonicalize_relation_for_storage


_local = threading.local()


def _connect() -> sqlite3.Connection:
    """새 연결 생성. 직접 lifecycle 관리하는 호출자용."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-20000")
    return conn


@contextmanager
def _db():
    """Thread-local cached connection. DB_PATH 변경 시 자동 무효화."""
    conn = getattr(_local, '_conn', None)
    cached_path = getattr(_local, '_conn_path', None)
    current_path = str(DB_PATH)
    if conn is None or cached_path != current_path:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        conn = _connect()
        _local._conn = conn
        _local._conn_path = current_path
    try:
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception:
            _local._conn = None
            _local._conn_path = None
        raise


def init_db() -> None:
    with _db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL DEFAULT 'Unclassified',
            content TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            project TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            confidence REAL DEFAULT 1.0,
            source TEXT DEFAULT 'claude',
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            layer INTEGER,
            summary TEXT,
            key_concepts TEXT,
            facets TEXT,
            domains TEXT,
            secondary_types TEXT,
            quality_score REAL,
            abstraction_level REAL,
            temporal_relevance REAL,
            actionability REAL,
            enrichment_status TEXT DEFAULT '{}',
            enriched_at TEXT,
            tier INTEGER DEFAULT 2,
            maturity REAL DEFAULT 0.0,
            observation_count INTEGER DEFAULT 0,
            theta_m REAL DEFAULT 0.5,
            activity_history TEXT DEFAULT '[]',
            visit_count INTEGER DEFAULT 0,
            score_history TEXT DEFAULT '[]',
            promotion_candidate INTEGER DEFAULT 0,
            content_hash TEXT,
            last_accessed_at TEXT,
            retrieval_hints TEXT DEFAULT NULL,
            source_kind TEXT DEFAULT '',
            source_ref TEXT DEFAULT '',
            node_role TEXT DEFAULT '',
            epistemic_status TEXT DEFAULT 'provisional'
        );

        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL REFERENCES nodes(id),
            target_id INTEGER NOT NULL REFERENCES nodes(id),
            relation TEXT NOT NULL,
            description TEXT DEFAULT '',
            strength REAL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            direction TEXT,
            reason TEXT,
            updated_at TEXT,
            base_strength REAL,
            frequency INTEGER DEFAULT 0,
            last_activated TEXT,
            decay_rate REAL DEFAULT 0.005,
            layer_distance INTEGER,
            layer_penalty REAL,
            status TEXT DEFAULT 'active',
            generation_method TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            summary TEXT DEFAULT '',
            decisions TEXT DEFAULT '[]',
            unresolved TEXT DEFAULT '[]',
            project TEXT DEFAULT '',
            started_at TEXT NOT NULL,
            ended_at TEXT,
            active_pipeline TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS correction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id INTEGER REFERENCES nodes(id),
            edge_id INTEGER REFERENCES edges(id),
            field TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            reason TEXT DEFAULT '',
            corrected_by TEXT DEFAULT 'system',
            created_at TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
            content, tags, project, summary, key_concepts, domains, facets,
            content='nodes',
            content_rowid='id',
            tokenize='trigram'
        );

        CREATE TRIGGER IF NOT EXISTS nodes_ai AFTER INSERT ON nodes BEGIN
            INSERT INTO nodes_fts(rowid, content, tags, project, summary, key_concepts, domains, facets)
            VALUES (new.id, new.content, new.tags, new.project, new.summary, new.key_concepts, new.domains, new.facets);
        END;

        CREATE TRIGGER IF NOT EXISTS nodes_ad AFTER DELETE ON nodes BEGIN
            INSERT INTO nodes_fts(nodes_fts, rowid, content, tags, project, summary, key_concepts, domains, facets)
            VALUES ('delete', old.id, old.content, old.tags, old.project, old.summary, old.key_concepts, old.domains, old.facets);
        END;

        CREATE TRIGGER IF NOT EXISTS nodes_au AFTER UPDATE ON nodes BEGIN
            INSERT INTO nodes_fts(nodes_fts, rowid, content, tags, project, summary, key_concepts, domains, facets)
            VALUES ('delete', old.id, old.content, old.tags, old.project, old.summary, old.key_concepts, old.domains, old.facets);
            INSERT INTO nodes_fts(rowid, content, tags, project, summary, key_concepts, domains, facets)
            VALUES (new.id, new.content, new.tags, new.project, new.summary, new.key_concepts, new.domains, new.facets);
        END;

        CREATE UNIQUE INDEX IF NOT EXISTS idx_nodes_content_hash
            ON nodes(content_hash) WHERE content_hash IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
        CREATE INDEX IF NOT EXISTS idx_nodes_project ON nodes(project);
        CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);
        CREATE INDEX IF NOT EXISTS idx_nodes_layer ON nodes(layer);
        CREATE INDEX IF NOT EXISTS idx_nodes_enriched_at ON nodes(enriched_at);
        CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
        CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
        CREATE INDEX IF NOT EXISTS idx_edges_direction ON edges(direction);
        CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);

        -- v2.1: action_log (A-12)
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

        CREATE INDEX IF NOT EXISTS idx_action_type ON action_log(action_type);
        CREATE INDEX IF NOT EXISTS idx_action_actor ON action_log(actor);
        CREATE INDEX IF NOT EXISTS idx_action_session ON action_log(session_id);
        CREATE INDEX IF NOT EXISTS idx_action_target ON action_log(target_type, target_id);
        CREATE INDEX IF NOT EXISTS idx_action_created ON action_log(created_at);
        CREATE INDEX IF NOT EXISTS idx_action_node_activated
            ON action_log(action_type, target_id, created_at DESC)
            WHERE action_type = 'node_activated';

        -- v2.1: meta tables (A-13)
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
            description TEXT,
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

        CREATE INDEX IF NOT EXISTS idx_type_defs_status ON type_defs(status);
        CREATE INDEX IF NOT EXISTS idx_type_defs_super ON type_defs(super_type);
        CREATE INDEX IF NOT EXISTS idx_relation_defs_status ON relation_defs(status);
        CREATE INDEX IF NOT EXISTS idx_relation_defs_category ON relation_defs(category);

        -- v2.1: meta key-value store (recall counter, SPRT stats)
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        );

        -- v2.1: recall_log (Gate 1 SWR input)
        CREATE TABLE IF NOT EXISTS recall_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            node_id TEXT,
            rank INTEGER,
            score REAL,
            mode TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- v2.1.3: verification_log
        CREATE TABLE IF NOT EXISTS verification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            check_name TEXT NOT NULL,
            category TEXT,
            score REAL,
            threshold REAL,
            status TEXT NOT NULL,
            details TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_vlog_run ON verification_log(run_id);
        CREATE INDEX IF NOT EXISTS idx_vlog_check ON verification_log(check_name);

        -- v2.1: activation_log VIEW (A-12, D-5)
        CREATE VIEW IF NOT EXISTS activation_log AS
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
        WHERE al.action_type = 'node_activated';
    """)

    # 기존 edges 테이블에 status 컬럼 없을 경우 migration (v2.1.3)
    with _db() as _mig:
        try:
            _mig.execute("ALTER TABLE edges ADD COLUMN status TEXT DEFAULT 'active'")
            _mig.execute("CREATE INDEX IF NOT EXISTS idx_edges_status ON edges(status)")
            _mig.commit()
        except Exception:
            pass  # 이미 존재하면 무시

    # nodes 테이블에 last_accessed_at 컬럼 추가 (Phase 2, composite scoring)
    with _db() as _mig:
        try:
            _mig.execute("ALTER TABLE nodes ADD COLUMN last_accessed_at TEXT")
            _mig.execute("UPDATE nodes SET last_accessed_at = updated_at WHERE last_accessed_at IS NULL")
            _mig.commit()
        except Exception:
            pass  # 이미 존재하면 무시

    # v3 Step 0: nodes.retrieval_hints (V3-05)
    with _db() as _mig:
        try:
            _mig.execute("ALTER TABLE nodes ADD COLUMN retrieval_hints TEXT DEFAULT NULL")
            _mig.commit()
        except Exception:
            pass

    # v3.3: nodes source provenance / role / epistemic status
    with _db() as _mig:
        for sql in (
            "ALTER TABLE nodes ADD COLUMN source_kind TEXT DEFAULT ''",
            "ALTER TABLE nodes ADD COLUMN source_ref TEXT DEFAULT ''",
            "ALTER TABLE nodes ADD COLUMN node_role TEXT DEFAULT ''",
            "ALTER TABLE nodes ADD COLUMN epistemic_status TEXT DEFAULT 'provisional'",
        ):
            try:
                _mig.execute(sql)
                _mig.commit()
            except Exception:
                pass

    # v3.3: edges generation_method
    with _db() as _mig:
        try:
            _mig.execute("ALTER TABLE edges ADD COLUMN generation_method TEXT DEFAULT ''")
            _mig.commit()
        except Exception:
            pass

    # v3 Step 0: recall_log.recall_id (H2)
    with _db() as _mig:
        try:
            _mig.execute("ALTER TABLE recall_log ADD COLUMN recall_id TEXT DEFAULT NULL")
            _mig.commit()
        except Exception:
            pass

    # v3 Step 0: recall_log 인덱스 (M3)
    with _db() as _mig:
        try:
            _mig.execute("CREATE INDEX IF NOT EXISTS idx_recall_log_recall_id ON recall_log(recall_id)")
            _mig.execute("CREATE INDEX IF NOT EXISTS idx_recall_log_query_ts ON recall_log(query, timestamp)")
            _mig.commit()
        except Exception:
            pass

    # v3 Step 0: edges 복합 인덱스 (H3)
    with _db() as _mig:
        try:
            _mig.execute("CREATE INDEX IF NOT EXISTS idx_edges_source_target ON edges(source_id, target_id)")
            _mig.commit()
        except Exception:
            pass

    # v6.0: session_events 테이블 (Event Journal)
    with _db() as _mig:
        try:
            _mig.execute("""
                CREATE TABLE IF NOT EXISTS session_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    session_id TEXT NOT NULL,
                    project TEXT DEFAULT '',
                    event_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT DEFAULT 'ACTIVE',
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            _mig.execute("CREATE INDEX IF NOT EXISTS idx_sevt_session ON session_events(session_id)")
            _mig.execute("CREATE INDEX IF NOT EXISTS idx_sevt_status ON session_events(status)")
            _mig.execute("CREATE INDEX IF NOT EXISTS idx_sevt_created ON session_events(created_at)")
            _mig.execute("CREATE INDEX IF NOT EXISTS idx_sevt_type ON session_events(event_type)")
            _mig.commit()
        except Exception:
            pass

    # v6.1: session_events에 target + task_id 칼럼 추가 (Gas Town)
    with _db() as _mig:
        try:
            _mig.execute("ALTER TABLE session_events ADD COLUMN target TEXT DEFAULT ''")
            _mig.commit()
        except Exception:
            pass
    with _db() as _mig:
        try:
            _mig.execute("ALTER TABLE session_events ADD COLUMN task_id TEXT DEFAULT ''")
            _mig.commit()
        except Exception:
            pass
    with _db() as _mig:
        try:
            _mig.execute("CREATE INDEX IF NOT EXISTS idx_sevt_target ON session_events(target)")
            _mig.commit()
        except Exception:
            pass

    # v7: nodes.embedding BLOB (1-Store: ChromaDB → SQLite)
    with _db() as _mig:
        try:
            _mig.execute("ALTER TABLE nodes ADD COLUMN embedding BLOB")
            _mig.commit()
        except Exception:
            pass  # already exists

    # --- dirty_topics (wiki-compiler 연동) ---
    with _db() as conn:
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dirty_topics (
                    topic TEXT PRIMARY KEY,
                    dirty_since TEXT NOT NULL,
                    node_ids TEXT NOT NULL DEFAULT '[]'
                )
            """)
            conn.commit()
        except Exception:
            pass

    # --- v8 Ontology Redesign (2026-04-12, Build R1 Day 1) ---
    # SoT: 07_ontology-redesign_0410/30_build-r1/03_impl-plan.md
    # Phase 0 — SQLite 위에서 5-Plane 증명 (7 신규 테이블)
    # Migration Contract (principles.md R1-R10): UUID v7 독립 id 공간, concepts(=nodes)와 loose link
    with _db() as conn:
        try:
            conn.executescript("""
            -- ============================================================
            -- Evidence Plane: captures (append-only 원문 보존, 불변식 1)
            -- ============================================================
            CREATE TABLE IF NOT EXISTS captures (
                id TEXT PRIMARY KEY,                 -- UUID v7
                source_type TEXT NOT NULL,           -- 'user_message' | 'file_change' | 'checkpoint' | 'manual'
                actor TEXT NOT NULL,                 -- 'paul' | 'claude' | 'system'
                content TEXT NOT NULL,               -- 원문 (수정 금지)
                project TEXT DEFAULT '',
                session_id TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_captures_actor ON captures(actor);
            CREATE INDEX IF NOT EXISTS idx_captures_session ON captures(session_id);
            CREATE INDEX IF NOT EXISTS idx_captures_created ON captures(created_at);
            CREATE INDEX IF NOT EXISTS idx_captures_source_type ON captures(source_type);

            -- 불변식 1 물리 강제: captures는 append-only
            CREATE TRIGGER IF NOT EXISTS captures_no_update BEFORE UPDATE ON captures
            BEGIN
                SELECT RAISE(FAIL, 'captures is append-only (invariant 1)');
            END;
            CREATE TRIGGER IF NOT EXISTS captures_no_delete BEFORE DELETE ON captures
            BEGIN
                SELECT RAISE(FAIL, 'captures is append-only (invariant 1)');
            END;

            -- ============================================================
            -- Evidence Plane: feedback_events (polymorphic target, D3-2)
            -- ============================================================
            CREATE TABLE IF NOT EXISTS feedback_events (
                id TEXT PRIMARY KEY,                 -- UUID v7
                target_type TEXT NOT NULL,           -- 'claim' | 'trait' | 'concept' | 'policy_rule'
                target_id TEXT NOT NULL,             -- polymorphic (D3-2, FK 없음)
                feedback_type TEXT NOT NULL,         -- 'reject' | 'approve' | 'correct' | 'flag'
                content TEXT DEFAULT '',             -- Paul 코멘트
                actor TEXT NOT NULL DEFAULT 'paul',
                created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_feedback_target ON feedback_events(target_type, target_id);
            CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback_events(feedback_type);
            CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback_events(created_at);

            -- ============================================================
            -- Epistemic Plane: claims (capture 해석, 불변식 2: FK NOT NULL)
            -- ============================================================
            CREATE TABLE IF NOT EXISTS claims (
                id TEXT PRIMARY KEY,                 -- UUID v7
                capture_id TEXT NOT NULL,            -- loose link to captures.id (shortcut 차단)
                text TEXT NOT NULL,
                claim_type TEXT DEFAULT '',          -- 'observation' | 'preference' | 'decision' | ...
                confidence REAL DEFAULT 0.5,
                extractor_model TEXT DEFAULT '',     -- 'qwen2.5-7b-instruct-q4_K_M'
                extracted_at TEXT NOT NULL,
                status TEXT DEFAULT 'provisional',   -- Migration Contract enum
                metadata TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_claims_capture ON claims(capture_id);
            CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(status);
            CREATE INDEX IF NOT EXISTS idx_claims_extracted ON claims(extracted_at);

            -- 불변식 2 물리 강제: capture_id는 captures 테이블에 존재해야 함
            CREATE TRIGGER IF NOT EXISTS claims_capture_fk BEFORE INSERT ON claims
            BEGIN
                SELECT CASE
                    WHEN NEW.capture_id NOT IN (SELECT id FROM captures)
                    THEN RAISE(FAIL, 'Invariant 2: capture_id must reference existing capture')
                END;
            END;

            -- ============================================================
            -- Self Model Plane: traits (D3 물리 분리)
            -- ============================================================
            CREATE TABLE IF NOT EXISTS self_model_traits (
                id TEXT PRIMARY KEY,                 -- UUID v7
                dimension TEXT NOT NULL,             -- 8차원 중 하나
                content TEXT NOT NULL,
                status TEXT DEFAULT 'provisional',   -- provisional|verified|protected|dormant|archived
                approval TEXT DEFAULT 'pending',     -- pending|approved|rejected|expired
                created_at TEXT NOT NULL,
                verified_at TEXT,
                metadata TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_traits_dimension ON self_model_traits(dimension);
            CREATE INDEX IF NOT EXISTS idx_traits_status ON self_model_traits(status);
            CREATE INDEX IF NOT EXISTS idx_traits_approval ON self_model_traits(approval);

            -- ============================================================
            -- Self Model Plane: evidence bridge (D20 — 유일한 Self↔Epistemic 경로)
            -- ============================================================
            CREATE TABLE IF NOT EXISTS self_trait_evidence (
                id TEXT PRIMARY KEY,                 -- UUID v7
                trait_id TEXT NOT NULL,              -- → self_model_traits.id (loose link)
                claim_id TEXT NOT NULL,              -- → claims.id (불변식 9: 직결 금지, claim 경유)
                strength REAL DEFAULT 1.0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_trevidence_trait ON self_trait_evidence(trait_id);
            CREATE INDEX IF NOT EXISTS idx_trevidence_claim ON self_trait_evidence(claim_id);

            -- D20 evidence bridge 물리 강제: claim_id는 claims 테이블에 존재해야 함
            CREATE TRIGGER IF NOT EXISTS trevidence_claim_fk BEFORE INSERT ON self_trait_evidence
            BEGIN
                SELECT CASE
                    WHEN NEW.claim_id NOT IN (SELECT id FROM claims)
                    THEN RAISE(FAIL, 'D20: claim_id must reference existing claim')
                END;
            END;
            -- D20 UPDATE 경로도 보호 (W2)
            CREATE TRIGGER IF NOT EXISTS trevidence_claim_fk_update
            BEFORE UPDATE ON self_trait_evidence
            WHEN NEW.claim_id != OLD.claim_id
            BEGIN
                SELECT CASE
                    WHEN NEW.claim_id NOT IN (SELECT id FROM claims)
                    THEN RAISE(FAIL, 'D20: claim_id must reference existing claim')
                END;
            END;

            -- ============================================================
            -- Self Model Plane: conflicts (Paul 교정 + 모순 기록)
            -- ============================================================
            CREATE TABLE IF NOT EXISTS self_trait_conflicts (
                id TEXT PRIMARY KEY,                 -- UUID v7
                trait_id TEXT NOT NULL,
                conflicting_source_type TEXT,        -- 'claim' | 'feedback' | 'correction'
                conflicting_source_id TEXT,
                description TEXT,
                resolved INTEGER DEFAULT 0,          -- 0 | 1
                created_at TEXT NOT NULL,
                resolved_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_trconflicts_trait ON self_trait_conflicts(trait_id);
            CREATE INDEX IF NOT EXISTS idx_trconflicts_resolved ON self_trait_conflicts(resolved);

            -- ============================================================
            -- Governance Plane: retrieval_logs (context_pack + cross-domain + feedback 연결)
            -- ============================================================
            CREATE TABLE IF NOT EXISTS retrieval_logs (
                id TEXT PRIMARY KEY,                 -- UUID v7
                session_id TEXT DEFAULT '',
                query TEXT DEFAULT '',
                context_pack_id TEXT DEFAULT '',     -- 어떤 pack으로 retrieve했는지
                returned_ids TEXT NOT NULL DEFAULT '[]',  -- JSON array of concept ids
                slot_distribution TEXT DEFAULT '{}', -- JSON: {task_frame: N, episodes: N, ...}
                cross_domain INTEGER DEFAULT 0,
                feedback_linked INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_rlogs_session ON retrieval_logs(session_id);
            CREATE INDEX IF NOT EXISTS idx_rlogs_created ON retrieval_logs(created_at);
            CREATE INDEX IF NOT EXISTS idx_rlogs_context_pack ON retrieval_logs(context_pack_id);
            """)
            conn.commit()
        except Exception as e:
            import traceback
            print(f"[WARN] v8 schema init: {e}", file=sys.stderr)

    # v8 테이블/트리거 존재 검증 (Finding 5: fail-open 방지)
    with _db() as conn:
        required_tables = {
            'captures', 'claims', 'self_model_traits', 'self_trait_evidence',
            'self_trait_conflicts', 'feedback_events', 'retrieval_logs',
        }
        found = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        missing = required_tables - found
        if missing:
            raise RuntimeError(f"v8 critical tables missing after init: {missing}")

        required_triggers = {
            'captures_no_update', 'captures_no_delete',
            'trevidence_claim_fk', 'trevidence_claim_fk_update',
            'claims_capture_fk',
        }
        triggers = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()}
        missing_triggers = required_triggers - triggers
        if missing_triggers:
            raise RuntimeError(f"v8 critical triggers missing: {missing_triggers}")


def mark_dirty(project: str, node_id: int) -> None:
    """wiki-compiler용: 토픽을 dirty로 마킹한다."""
    import json
    topic = project.strip().lower() if project else "uncategorized"
    with _db() as conn:
        existing = conn.execute(
            "SELECT node_ids FROM dirty_topics WHERE topic = ?", (topic,)
        ).fetchone()
        if existing:
            ids = json.loads(existing[0])
            if node_id not in ids:
                ids.append(node_id)
            conn.execute(
                "UPDATE dirty_topics SET node_ids = ?, dirty_since = datetime('now') WHERE topic = ?",
                (json.dumps(ids), topic),
            )
        else:
            conn.execute(
                "INSERT INTO dirty_topics (topic, dirty_since, node_ids) VALUES (?, datetime('now'), ?)",
                (topic, json.dumps([node_id])),
            )
        conn.commit()


def get_dirty_topics() -> list[dict]:
    """dirty 토픽 목록을 반환한다."""
    import json
    with _db() as conn:
        rows = conn.execute("SELECT topic, dirty_since, node_ids FROM dirty_topics").fetchall()
    return [{"topic": r[0], "dirty_since": r[1], "node_ids": json.loads(r[2])} for r in rows]


def clear_dirty_topics(topics: list[str] | None = None) -> int:
    """dirty 토픽을 클리어한다. topics=None이면 전부."""
    with _db() as conn:
        if topics:
            placeholders = ",".join("?" for _ in topics)
            conn.execute(f"DELETE FROM dirty_topics WHERE topic IN ({placeholders})", topics)
        else:
            conn.execute("DELETE FROM dirty_topics")
        conn.commit()
        return conn.total_changes


def insert_node(
    type: str,
    content: str,
    metadata: dict | None = None,
    project: str = "",
    tags: str = "",
    confidence: float = 1.0,
    source: str = "claude",
    layer: int | None = None,
    tier: int = 2,
    content_hash: str | None = None,
    retrieval_hints: dict | None = None,
    source_kind: str = "",
    source_ref: str = "",
    node_role: str = "",
    epistemic_status: str = "provisional",
) -> int | tuple[str, int | None]:
    """노드 삽입. content_hash UNIQUE 제약 위반 시 "duplicate" 반환.

    v3: retrieval_hints (H4) — {"when_needed", "related_queries", "context_keys"}
    v3.3: source_kind, source_ref, node_role, epistemic_status 추가
    """
    # WS-2.1: 중앙 write-layer normalize — 모든 ingress의 최종 방어선
    if not node_role:
        node_role = "knowledge_candidate"
    if not epistemic_status:
        epistemic_status = "provisional"

    # PROMOTE_LAYER fallback: caller가 layer 미전달 시 타입 기반 자동 배정
    if layer is None:
        layer = PROMOTE_LAYER.get(type)  # Unclassified → None (의도적)
    now = datetime.now(timezone.utc).isoformat()

    # H4: retrieval_hints JSON 직렬화
    hints_json = None
    if retrieval_hints and isinstance(retrieval_hints, dict):
        hints_json = json.dumps(retrieval_hints, ensure_ascii=False)

    with _db() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO nodes (type, content, metadata, project, tags, confidence, source, layer, tier, content_hash, retrieval_hints, source_kind, source_ref, node_role, epistemic_status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (type, content, json.dumps(metadata or {}), project, tags, confidence, source, layer, tier, content_hash, hints_json, source_kind, source_ref, node_role, epistemic_status, now, now),
            )
            node_id = cur.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            # content_hash UNIQUE 제약 위반 — 기존 노드 ID를 같은 conn에서 조회
            existing_id = None
            if content_hash:
                row = conn.execute(
                    "SELECT id FROM nodes WHERE content_hash = ?", (content_hash,)
                ).fetchone()
                if row:
                    existing_id = row[0]
            return ("duplicate", existing_id)
    return node_id


def insert_edge(
    source_id: int,
    target_id: int,
    relation: str,
    description: str = "",
    strength: float = 1.0,
    generation_method: str = "",
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    original_relation = relation
    relation = canonicalize_relation_for_storage(relation)
    if relation not in ALL_RELATIONS:
        # 미정의 relation → connects_with fallback + correction_log 기록
        relation = "connects_with"
    with _db() as conn:
        cur = conn.execute(
            """INSERT INTO edges (source_id, target_id, relation, description, strength, generation_method, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (source_id, target_id, relation, description, strength, generation_method, now),
        )
        edge_id = cur.lastrowid
        if original_relation != relation:
            conn.execute(
                """INSERT INTO correction_log (node_id, edge_id, field, old_value, new_value, reason, corrected_by, created_at)
                   VALUES (?, ?, 'relation', ?, ?, 'relation not in ALL_RELATIONS', 'system', ?)""",
                (source_id, edge_id, original_relation, relation, now),
            )
        conn.commit()
    return edge_id


def _strip_korean_particles(term: str) -> str:
    """한국어 조사/어미 제거. 어근만 남긴다."""
    import re
    # 긴 패턴부터 매칭 (에서, 으로, 하는 등)
    suffixes = (
        "에서", "으로", "하는", "해서", "하고", "에게", "처럼", "까지",
        "부터", "만큼", "라는", "라고", "이라", "에는",
        "을", "를", "의", "이", "가", "은", "는", "에", "로", "와", "과",
        "도", "만", "며", "고", "면", "서", "나", "든",
    )
    for s in suffixes:
        if len(term) > len(s) + 1 and term.endswith(s):
            return term[:-len(s)]
    return term


def _escape_fts_query(query: str) -> str:
    """Escape FTS5 query: 조사 제거 + 3글자+ OR 매칭.

    trigram 토크나이저는 3글자 미만 매칭 불가이므로
    3글자+ 단어만 FTS5에 보내고, 2글자는 search_fts()의 LIKE 보조에 맡긴다.
    OR 매칭으로 부분 일치도 허용 (RRF가 최종 랭킹 담당).
    """
    terms = query.split()
    cleaned = []
    for t in terms:
        t = t.replace('"', '""')
        stripped = _strip_korean_particles(t)
        if stripped and len(stripped) >= 3:  # 3글자+ → FTS5 trigram
            cleaned.append('"' + stripped + '"')
    if not cleaned:
        return ""
    return " OR ".join(cleaned)


def search_fts(query: str, top_k: int = 5) -> list[tuple[int, str, float]]:
    """FTS5 trigram + 2글자 LIKE 보조 검색.

    trigram 토크나이저는 3글자 미만 매칭 불가 → 한국어 2글자 단어를
    SQL LIKE로 보조 검색하여 다중 매칭 노드를 상위에 배치한다.
    """
    escaped = _escape_fts_query(query)

    # 1. FTS5 trigram 검색 (3글자+ 단어)
    fts_results: list[tuple[int, str, float]] = []
    if escaped:
        with _db() as conn:
            try:
                rows = conn.execute(
                    """SELECT n.id, n.content, rank
                       FROM nodes_fts f
                       JOIN nodes n ON n.id = f.rowid
                       WHERE nodes_fts MATCH ?
                         AND n.status = 'active'
                       ORDER BY rank
                       LIMIT ?""",
                    (escaped, top_k),
                ).fetchall()
                fts_results = [(r["id"], r["content"], r["rank"]) for r in rows]
            except sqlite3.OperationalError:
                rows = conn.execute(
                    """SELECT n.id, n.content, rank
                       FROM nodes_fts f
                       JOIN nodes n ON n.id = f.rowid
                       WHERE nodes_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (escaped, top_k),
                ).fetchall()
                fts_results = [(r["id"], r["content"], r["rank"]) for r in rows]
            except Exception:
                pass

    # 2. 2글자 한국어 보조 LIKE 검색 (trigram 한계 보완)
    terms = query.split()
    short_terms = []
    for t in terms:
        stripped = _strip_korean_particles(t)
        if stripped and len(stripped) == 2:
            short_terms.append(stripped)

    if short_terms:
        # 다중 매칭 → 높은 랭크: 3개 용어 매칭 노드가 1개 매칭보다 상위
        like_match_count: dict[int, int] = {}
        like_content: dict[int, str] = {}
        with _db() as conn:
            for term in short_terms[:5]:
                try:
                    rows = conn.execute(
                        """SELECT id, content FROM nodes
                           WHERE status = 'active'
                             AND (content LIKE ? OR summary LIKE ?
                                  OR key_concepts LIKE ? OR domains LIKE ?
                                  OR facets LIKE ?)
                           LIMIT ?""",
                        (f"%{term}%", f"%{term}%", f"%{term}%", f"%{term}%", f"%{term}%", top_k),
                    ).fetchall()
                    for r in rows:
                        like_match_count[r["id"]] = like_match_count.get(r["id"], 0) + 1
                        like_content[r["id"]] = r["content"]
                except Exception:
                    pass

        # 다중 매칭 상위 → 과반수 이상 매칭 시 BM25 앞에 삽입 (RRF 상위 부스트)
        # 과반수 미달 → FTS 결과 뒤에 추가 (기존 동작)
        high_thresh = max(2, len(short_terms) // 2)  # 최소 2개, 50% 이상
        seen_ids = {r[0] for r in fts_results}
        like_ranked = sorted(like_match_count, key=like_match_count.get, reverse=True)
        high_boost: list[tuple[int, str, float]] = []
        low_append: list[tuple[int, str, float]] = []
        for nid in like_ranked:
            if nid not in seen_ids:
                cnt = like_match_count[nid]
                if cnt >= high_thresh and len(high_boost) < 2:  # ← cap 2개
                    high_boost.append((nid, like_content[nid], -float(cnt) * 10))
                else:
                    low_append.append((nid, like_content[nid], -float(cnt)))
                seen_ids.add(nid)
        # high_boost 노드: BM25 결과보다 앞에 배치 → RRF 상위 랭크 확보
        fts_results = high_boost + fts_results + low_append

    return fts_results


def get_node(node_id: int, active_only: bool = True) -> dict | None:
    with _db() as conn:
        try:
            if active_only:
                row = conn.execute(
                    "SELECT * FROM nodes WHERE id = ? AND status = 'active'",
                    (node_id,),
                ).fetchone()
            else:
                row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        except sqlite3.OperationalError:
            row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    return dict(row) if row else None


def get_node_by_hash(content_hash: str) -> dict | None:
    """content_hash 인덱스로 기존 노드 검색. 중복 저장 방지용."""
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM nodes WHERE content_hash = ? AND status = 'active'",
            (content_hash,),
        ).fetchone()
    return dict(row) if row else None


def get_recent_nodes(project: str = "", limit: int = 10, type_filter: str = "") -> list[dict]:
    sql = "SELECT * FROM nodes WHERE status = 'active'"
    params: list = []
    if project:
        sql += " AND project = ?"
        params.append(project)
    if type_filter:
        sql += " AND type = ?"
        params.append(type_filter)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_edges(node_id: int, active_only: bool = True) -> list[dict]:
    with _db() as conn:
        try:
            if active_only:
                rows = conn.execute(
                    """SELECT e.*
                       FROM edges e
                       JOIN nodes s ON s.id = e.source_id
                       JOIN nodes t ON t.id = e.target_id
                       WHERE e.status = 'active'
                         AND s.status = 'active'
                         AND t.status = 'active'
                         AND (e.source_id = ? OR e.target_id = ?)""",
                    (node_id, node_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM edges WHERE source_id = ? OR target_id = ?""",
                    (node_id, node_id),
                ).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                """SELECT * FROM edges WHERE source_id = ? OR target_id = ?""",
                (node_id, node_id),
            ).fetchall()
    return [dict(r) for r in rows]


def get_contradicted_node_ids(node_ids: list[int]) -> set[int]:
    """node_ids 중 contradicts 관계가 있는 노드 ID 집합 반환 (P1: N+1 제거)."""
    if not node_ids:
        return set()
    ph = ",".join("?" * len(node_ids))
    with _db() as conn:
        rows = conn.execute(f"""
            SELECT DISTINCT e.source_id FROM edges e
            JOIN nodes s ON s.id = e.source_id AND s.status = 'active'
            JOIN nodes t ON t.id = e.target_id AND t.status = 'active'
            WHERE e.relation = 'contradicts' AND e.status = 'active'
              AND e.source_id IN ({ph})
            UNION
            SELECT DISTINCT e.target_id FROM edges e
            JOIN nodes s ON s.id = e.source_id AND s.status = 'active'
            JOIN nodes t ON t.id = e.target_id AND t.status = 'active'
            WHERE e.relation = 'contradicts' AND e.status = 'active'
              AND e.target_id IN ({ph})
        """, node_ids + node_ids).fetchall()
    return {r[0] for r in rows}


def get_all_edges(active_only: bool = True) -> list[dict]:
    with _db() as conn:
        try:
            if active_only:
                rows = conn.execute(
                    """SELECT e.*
                       FROM edges e
                       JOIN nodes s ON s.id = e.source_id
                       JOIN nodes t ON t.id = e.target_id
                       WHERE e.status = 'active'
                         AND s.status = 'active'
                         AND t.status = 'active'"""
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM edges").fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute("SELECT * FROM edges").fetchall()
    return [dict(r) for r in rows]


def update_tiers() -> dict:
    """Tier 자동 배정: tier=0(L3+), tier=1(L2+qs>=0.8), tier=2(나머지)"""
    with _db() as conn:
        # tier=0: layer >= 3
        r0 = conn.execute(
            "UPDATE nodes SET tier = 0 WHERE status = 'active' AND layer >= 3"
        ).rowcount
        # tier=1: layer == 2 AND quality_score >= 0.8
        r1 = conn.execute(
            "UPDATE nodes SET tier = 1 WHERE status = 'active' AND layer = 2 AND quality_score >= 0.8"
        ).rowcount
        # tier=2: 나머지 (이미 default 2이지만 명시)
        r2 = conn.execute(
            "UPDATE nodes SET tier = 2 WHERE status = 'active' AND tier NOT IN (0, 1)"
        ).rowcount
        conn.commit()
    return {"tier_0": r0, "tier_1": r1, "tier_2": r2}


def log_correction(
    node_id: int | None = None,
    edge_id: int | None = None,
    field: str = "",
    old_value: str = "",
    new_value: str = "",
    reason: str = "",
    corrected_by: str = "system",
) -> None:
    """correction_log 기록. 실패해도 main flow 중단 안 함."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        with _db() as conn:
            conn.execute(
                "INSERT INTO correction_log "
                "(node_id, edge_id, field, old_value, new_value, reason, corrected_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (node_id or 0, edge_id, field, old_value, new_value, reason, corrected_by, now),
            )
            conn.commit()
    except Exception:
        pass


def get_meta(key: str) -> str | None:
    """meta 테이블에서 값 조회. 없거나 에러 시 None."""
    try:
        with _db() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            return row[0] if row else None
    except Exception:
        return None


def upsert_meta(key: str, value: str) -> None:
    """meta 테이블 UPSERT. 에러 시 graceful skip."""
    try:
        with _db() as conn:
            conn.execute(
                """INSERT INTO meta(key, value, updated_at)
                       VALUES(?, ?, datetime('now'))
                   ON CONFLICT(key) DO UPDATE SET
                       value = excluded.value,
                       updated_at = datetime('now')""",
                (key, value),
            )
            conn.commit()
    except Exception:
        pass


def sync_schema() -> dict:
    """schema.yaml → type_defs/relation_defs 테이블 동기화.

    서버 시작 시 호출. schema.yaml이 SoT(Single Source of Truth).
    새 타입/관계는 추가, 제거된 것은 deprecated 처리.
    """
    import logging
    import yaml
    schema_path = Path(__file__).parent.parent / "ontology" / "schema.yaml"
    if not schema_path.exists():
        return {"error": "schema.yaml not found"}

    with open(schema_path, encoding="utf-8") as f:
        schema = yaml.safe_load(f)

    node_types = schema.get("node_types", {})
    relation_types = schema.get("relation_types", {})
    now = datetime.now(timezone.utc).isoformat()
    result = {"types_synced": 0, "relations_synced": 0, "deprecated": 0}

    with _db() as conn:
        # 1. node_types → type_defs
        for name, info in node_types.items():
            layer = info.get("layer")
            desc = info.get("description", "")
            existing = conn.execute(
                "SELECT id, status FROM type_defs WHERE name=?", (name,)
            ).fetchone()
            if existing:
                # C1 fix: deprecated 타입은 건드리지 않음 — active로 되돌리지 않는다
                if existing["status"] == "deprecated":
                    continue
                conn.execute(
                    """UPDATE type_defs SET layer=?, description=?,
                       updated_at=? WHERE name=? AND status='active'""",
                    (layer, desc, now, name),
                )
            else:
                conn.execute(
                    """INSERT INTO type_defs (name, layer, description, status, created_at, updated_at)
                       VALUES (?, ?, ?, 'active', ?, ?)""",
                    (name, layer, desc, now, now),
                )
            result["types_synced"] += 1

        # deprecated: type_defs에 있지만 schema.yaml에 없는 것
        schema_type_names = set(node_types.keys())
        db_types = conn.execute("SELECT name FROM type_defs WHERE status='active'").fetchall()
        for row in db_types:
            if row[0] not in schema_type_names:
                conn.execute(
                    "UPDATE type_defs SET status='deprecated', deprecated_at=?, updated_at=? WHERE name=?",
                    (now, now, row[0]),
                )
                result["deprecated"] += 1

        # 2. relation_types → relation_defs
        # relation_types는 카테고리별로 그룹화됨: {name: {description, inverse, ...}}
        # config.py의 RELATION_TYPES 카테고리 정보 활용
        from config import RELATION_TYPES as rel_categories
        name_to_category = {}
        for cat, rels in rel_categories.items():
            for rel in rels:
                name_to_category[rel] = cat

        for name, info in relation_types.items():
            desc = info.get("description", "")
            inverse = info.get("inverse")
            category = name_to_category.get(name, "")
            existing = conn.execute(
                "SELECT id FROM relation_defs WHERE name=?", (name,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE relation_defs SET description=?, category=?,
                       reverse_of=?, status='active', updated_at=? WHERE name=?""",
                    (desc, category, inverse, now, name),
                )
            else:
                conn.execute(
                    """INSERT INTO relation_defs (name, category, description, reverse_of, status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, 'active', ?, ?)""",
                    (name, category, desc, inverse, now, now),
                )
            result["relations_synced"] += 1

        # deprecated: relation_defs에 있지만 schema.yaml에 없는 것
        schema_rel_names = set(relation_types.keys())
        db_rels = conn.execute("SELECT name FROM relation_defs WHERE status='active'").fetchall()
        for row in db_rels:
            if row[0] not in schema_rel_names:
                conn.execute(
                    "UPDATE relation_defs SET status='deprecated', deprecated_at=?, updated_at=? WHERE name=?",
                    (now, now, row[0]),
                )
                result["deprecated"] += 1

        # 3. 스냅샷 저장
        version = schema.get("version", "unknown")
        conn.execute(
            """INSERT OR IGNORE INTO ontology_snapshots (version_tag, type_defs_json, relation_defs_json, change_summary, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (f"sync-{version}-{now[:10]}", json.dumps(list(node_types.keys())),
             json.dumps(list(relation_types.keys())), f"auto-sync {result}", now),
        )

        conn.commit()

    logging.info("schema sync: %s", result)
    return result


# ── v6.0 Session Events (Event Journal) ──────────────────────────


def insert_session_event(
    event_id: str,
    session_id: str,
    event_type: str,
    summary: str,
    project: str = "",
    metadata: dict | None = None,
    target: str = "",
    task_id: str = "",
) -> dict:
    """Idempotent upsert — 동일 event_id는 무시."""
    now = datetime.now(timezone.utc).isoformat()
    with _db() as conn:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO session_events
                   (event_id, session_id, project, event_type, summary, status, created_at, metadata, target, task_id)
                   VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?)""",
                (event_id, session_id, project, event_type, summary, now,
                 json.dumps(metadata or {}), target, task_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT id FROM session_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            return {"event_id": event_id, "id": row["id"] if row else None, "status": "created"}
        except Exception:
            return {"event_id": event_id, "status": "duplicate"}


def query_session_events(
    exclude_session: str = "",
    since: str = "",
    status: str = "ACTIVE",
    limit: int = 50,
    target: str = "",
    event_type: str = "",
) -> list[dict]:
    """다른 세션의 이벤트 조회 (polling용). target으로 inbox 필터링."""
    with _db() as conn:
        conditions = ["status = ?"]
        params: list = [status]
        if exclude_session:
            conditions.append("session_id != ?")
            params.append(exclude_session)
        if since:
            conditions.append("created_at > ?")
            params.append(since)
        if target:
            conditions.append("target = ?")
            params.append(target)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        params.append(limit)
        rows = conn.execute(
            f"SELECT * FROM session_events WHERE {' AND '.join(conditions)} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def resolve_session_event(event_id: str) -> bool:
    """이벤트를 RESOLVED로 전환."""
    now = datetime.now(timezone.utc).isoformat()
    with _db() as conn:
        cur = conn.execute(
            "UPDATE session_events SET status = 'RESOLVED', resolved_at = ? WHERE event_id = ? AND status = 'ACTIVE'",
            (now, event_id),
        )
        conn.commit()
        return cur.rowcount > 0


def export_ontology(
    types: list[str] | None = None,
    project: str = "",
    since: str = "",
    changed_only: bool = False,
) -> dict:
    """전체 온톨로지 export (노드+엣지 JSON). 주간 3-way 풀스캔용."""
    with _db() as conn:
        # nodes
        node_conditions = ["status = 'active'"]
        node_params: list = []
        if types:
            placeholders = ",".join("?" * len(types))
            node_conditions.append(f"type IN ({placeholders})")
            node_params.extend(types)
        if project:
            node_conditions.append("project = ?")
            node_params.append(project)
        if since:
            col = "updated_at" if changed_only else "created_at"
            node_conditions.append(f"{col} > ?")
            node_params.append(since)

        nodes = conn.execute(
            f"SELECT id, type, content, project, tags, confidence, source, created_at, updated_at, layer, score_history "
            f"FROM nodes WHERE {' AND '.join(node_conditions)}",
            node_params,
        ).fetchall()

        node_ids = {r["id"] for r in nodes}

        # edges (양쪽 노드가 결과에 포함된 것만)
        edges = conn.execute(
            "SELECT id, source_id, target_id, relation, strength, created_at "
            "FROM edges WHERE status = 'active'"
        ).fetchall()
        filtered_edges = [
            dict(e) for e in edges
            if e["source_id"] in node_ids and e["target_id"] in node_ids
        ]

        return {
            "meta": {
                "exported": datetime.now(timezone.utc).isoformat(),
                "nodes": len(nodes),
                "edges": len(filtered_edges),
                "filters": {"types": types, "project": project, "since": since, "changed_only": changed_only},
            },
            "nodes": [dict(n) for n in nodes],
            "edges": filtered_edges,
        }
