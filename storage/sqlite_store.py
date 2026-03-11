"""SQLite storage with FTS5 for keyword search."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from config import ALL_RELATIONS, DB_PATH, PROMOTE_LAYER


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def _db():
    """DB 연결 context manager. 자동으로 conn.close() 보장."""
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


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
            retrieval_hints TEXT DEFAULT NULL
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
            status TEXT DEFAULT 'active'
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
) -> int | tuple[str, int | None]:
    """노드 삽입. content_hash UNIQUE 제약 위반 시 "duplicate" 반환.

    v3: retrieval_hints (H4) — {"when_needed", "related_queries", "context_keys"}
    """
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
                """INSERT INTO nodes (type, content, metadata, project, tags, confidence, source, layer, tier, content_hash, retrieval_hints, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (type, content, json.dumps(metadata or {}), project, tags, confidence, source, layer, tier, content_hash, hints_json, now, now),
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
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    original_relation = relation
    if relation not in ALL_RELATIONS:
        # 미정의 relation → connects_with fallback + correction_log 기록
        relation = "connects_with"
    with _db() as conn:
        cur = conn.execute(
            """INSERT INTO edges (source_id, target_id, relation, description, strength, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source_id, target_id, relation, description, strength, now),
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


def get_node(node_id: int) -> dict | None:
    with _db() as conn:
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


def get_edges(node_id: int) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            """SELECT * FROM edges WHERE source_id = ? OR target_id = ?""",
            (node_id, node_id),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_edges() -> list[dict]:
    with _db() as conn:
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
