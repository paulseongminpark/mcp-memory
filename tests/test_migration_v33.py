from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


def _load_script(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migrate_v33_adds_required_columns(tmp_path):
    db_path = tmp_path / "memory.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE nodes (
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
        CREATE TABLE edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
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
        CREATE TABLE recall_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT
        );
        """
    )
    conn.commit()
    conn.close()

    migrate_v33 = _load_script(ROOT / "scripts" / "migrate_v33.py", "migrate_v33_test")

    with patch("config.DB_PATH", db_path), patch("storage.sqlite_store.DB_PATH", db_path):
        assert migrate_v33.main(["--apply"]) == 0

    conn = sqlite3.connect(str(db_path))
    node_columns = {row[1] for row in conn.execute("PRAGMA table_info(nodes)").fetchall()}
    edge_columns = {row[1] for row in conn.execute("PRAGMA table_info(edges)").fetchall()}
    conn.close()

    assert {"source_kind", "source_ref", "node_role", "epistemic_status"} <= node_columns
    assert "generation_method" in edge_columns
