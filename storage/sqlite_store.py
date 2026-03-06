"""SQLite storage with FTS5 for keyword search."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import ALL_RELATIONS, DB_PATH


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = _connect()
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
            observation_count INTEGER DEFAULT 0
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
            layer_penalty REAL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            summary TEXT DEFAULT '',
            decisions TEXT DEFAULT '[]',
            unresolved TEXT DEFAULT '[]',
            project TEXT DEFAULT '',
            started_at TEXT NOT NULL,
            ended_at TEXT
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
            content, tags, project, summary, key_concepts,
            content='nodes',
            content_rowid='id',
            tokenize='trigram'
        );

        CREATE TRIGGER IF NOT EXISTS nodes_ai AFTER INSERT ON nodes BEGIN
            INSERT INTO nodes_fts(rowid, content, tags, project, summary, key_concepts)
            VALUES (new.id, new.content, new.tags, new.project, new.summary, new.key_concepts);
        END;

        CREATE TRIGGER IF NOT EXISTS nodes_ad AFTER DELETE ON nodes BEGIN
            INSERT INTO nodes_fts(nodes_fts, rowid, content, tags, project, summary, key_concepts)
            VALUES ('delete', old.id, old.content, old.tags, old.project, old.summary, old.key_concepts);
        END;

        CREATE TRIGGER IF NOT EXISTS nodes_au AFTER UPDATE ON nodes BEGIN
            INSERT INTO nodes_fts(nodes_fts, rowid, content, tags, project, summary, key_concepts)
            VALUES ('delete', old.id, old.content, old.tags, old.project, old.summary, old.key_concepts);
            INSERT INTO nodes_fts(rowid, content, tags, project, summary, key_concepts)
            VALUES (new.id, new.content, new.tags, new.project, new.summary, new.key_concepts);
        END;

        CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
        CREATE INDEX IF NOT EXISTS idx_nodes_project ON nodes(project);
        CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);
        CREATE INDEX IF NOT EXISTS idx_nodes_layer ON nodes(layer);
        CREATE INDEX IF NOT EXISTS idx_nodes_enriched_at ON nodes(enriched_at);
        CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
        CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
        CREATE INDEX IF NOT EXISTS idx_edges_direction ON edges(direction);
        CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);
    """)
    conn.close()


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
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO nodes (type, content, metadata, project, tags, confidence, source, layer, tier, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (type, content, json.dumps(metadata or {}), project, tags, confidence, source, layer, tier, now, now),
    )
    node_id = cur.lastrowid
    conn.commit()
    conn.close()
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
    conn = _connect()
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
    conn.close()
    return edge_id


def _escape_fts_query(query: str) -> str:
    """Escape special FTS5 characters by wrapping terms in double quotes."""
    # FTS5 special: AND OR NOT + - * ^ ~ : " ( )
    # Safest approach: quote each term individually
    terms = query.split()
    return " ".join(f'"{t}"' for t in terms if t)


def search_fts(query: str, top_k: int = 5) -> list[tuple[int, str, float]]:
    escaped = _escape_fts_query(query)
    if not escaped:
        return []
    conn = _connect()
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
    except Exception:
        conn.close()
        return []
    conn.close()
    return [(r["id"], r["content"], r["rank"]) for r in rows]


def get_node(node_id: int) -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_recent_nodes(project: str = "", limit: int = 10, type_filter: str = "") -> list[dict]:
    conn = _connect()
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
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_edges(node_id: int) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        """SELECT * FROM edges WHERE source_id = ? OR target_id = ?""",
        (node_id, node_id),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_edges() -> list[dict]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM edges").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_tiers() -> dict:
    """Tier 자동 배정: tier=0(L3+), tier=1(L2+qs>=0.8), tier=2(나머지)"""
    conn = _connect()
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
    conn.close()
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
        conn = _connect()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO correction_log "
            "(node_id, edge_id, field, old_value, new_value, reason, corrected_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (node_id or 0, edge_id, field, old_value, new_value, reason, corrected_by, now),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
