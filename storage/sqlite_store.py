"""SQLite storage with FTS5 for keyword search."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import DB_PATH


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
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
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL REFERENCES nodes(id),
            target_id INTEGER NOT NULL REFERENCES nodes(id),
            relation TEXT NOT NULL,
            description TEXT DEFAULT '',
            strength REAL DEFAULT 1.0,
            created_at TEXT NOT NULL
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

        CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
            content, tags, project,
            content='nodes',
            content_rowid='id',
            tokenize='trigram'
        );

        CREATE TRIGGER IF NOT EXISTS nodes_ai AFTER INSERT ON nodes BEGIN
            INSERT INTO nodes_fts(rowid, content, tags, project)
            VALUES (new.id, new.content, new.tags, new.project);
        END;

        CREATE TRIGGER IF NOT EXISTS nodes_ad AFTER DELETE ON nodes BEGIN
            INSERT INTO nodes_fts(nodes_fts, rowid, content, tags, project)
            VALUES ('delete', old.id, old.content, old.tags, old.project);
        END;

        CREATE TRIGGER IF NOT EXISTS nodes_au AFTER UPDATE ON nodes BEGIN
            INSERT INTO nodes_fts(nodes_fts, rowid, content, tags, project)
            VALUES ('delete', old.id, old.content, old.tags, old.project);
            INSERT INTO nodes_fts(rowid, content, tags, project)
            VALUES (new.id, new.content, new.tags, new.project);
        END;

        CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
        CREATE INDEX IF NOT EXISTS idx_nodes_project ON nodes(project);
        CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);
        CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
        CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
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
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO nodes (type, content, metadata, project, tags, confidence, source, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (type, content, json.dumps(metadata or {}), project, tags, confidence, source, now, now),
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
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO edges (source_id, target_id, relation, description, strength, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (source_id, target_id, relation, description, strength, now),
    )
    edge_id = cur.lastrowid
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
