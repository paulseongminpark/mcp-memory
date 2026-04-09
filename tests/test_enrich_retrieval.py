import sqlite3
from pathlib import Path

from scripts.enrich_retrieval import get_remaining


def test_get_remaining_includes_null_empty_and_array_missing():
    db = Path(__file__).resolve().parent / "_tmp_enrich_retrieval.db"
    if db.exists():
        db.unlink()
    try:
        conn = sqlite3.connect(db)
        conn.execute(
            """
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY,
                type TEXT,
                content TEXT,
                summary TEXT,
                key_concepts TEXT,
                project TEXT,
                status TEXT,
                retrieval_queries TEXT,
                atomic_claims TEXT
            )
            """
        )
        rows = [
            (1, "Pattern", "a", "s", "[]", "mcp-memory", "active", None, None),
            (2, "Pattern", "b", "s", "[]", "mcp-memory", "active", "", "[]"),
            (3, "Pattern", "c", "s", "[]", "mcp-memory", "active", "[]", "[\"c1\"]"),
            (4, "Pattern", "d", "s", "[]", "mcp-memory", "active", "[\"q1\"]", ""),
            (5, "Pattern", "e", "s", "[]", "mcp-memory", "active", "[\"q1\"]", "[\"c1\"]"),
            (6, "Pattern", "f", "s", "[]", "mcp-memory", "archived", None, None),
        ]
        conn.executemany("INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        conn.commit()
        conn.close()

        remaining = get_remaining(db)
        assert [row["id"] for row in remaining] == [1, 2, 3, 4]
    finally:
        if db.exists():
            db.unlink()
