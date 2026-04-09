import sqlite3

from scripts.archive_stale_obsidian_history import apply_archive, collect_candidates


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE nodes (
            id INTEGER PRIMARY KEY,
            source TEXT,
            type TEXT,
            project TEXT,
            content TEXT,
            status TEXT,
            visit_count INTEGER,
            created_at TEXT,
            updated_at TEXT,
            node_role TEXT,
            epistemic_status TEXT
        )
        """
    )
    rows = [
        (1, r"obsidian:01_projects\01_orchestration\_history\plans\a.md#1", "Decision", "orchestration", "old history", "active", 0, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", "knowledge_candidate", "provisional"),
        (2, r"obsidian:01_projects\01_orchestration\_archived\docs\b.md#1", "Principle", "orchestration", "old archived", "active", 0, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", "knowledge_candidate", "provisional"),
        (3, r"obsidian:01_projects\01_orchestration\CHANGELOG.md#1", "Observation", "orchestration", "old changelog", "active", 0, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", "knowledge_candidate", "provisional"),
        (4, r"obsidian:01_projects\01_orchestration\_history\plans\keep.md#1", "Decision", "orchestration", "recent history", "active", 0, "2099-01-01T00:00:00+00:00", "2099-01-01T00:00:00+00:00", "knowledge_candidate", "provisional"),
        (5, r"obsidian:01_projects\01_orchestration\_history\plans\core.md#1", "Decision", "orchestration", "core history", "active", 0, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", "knowledge_core", "provisional"),
        (6, r"obsidian:01_projects\01_orchestration\_history\plans\validated.md#1", "Decision", "orchestration", "validated history", "active", 0, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", "knowledge_candidate", "validated"),
        (7, r"obsidian:01_projects\02_portfolio\docs\plans\plan.md#1", "Decision", "portfolio", "normal plan", "active", 0, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", "knowledge_candidate", "provisional"),
        (8, r"obsidian:01_projects\01_orchestration\_history\plans\visited.md#1", "Decision", "orchestration", "visited history", "active", 3, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", "knowledge_candidate", "provisional"),
    ]
    conn.executemany(
        "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return conn


def test_collect_candidates_filters_conservatively():
    conn = _make_conn()
    try:
        result = collect_candidates(conn, days=30, sample_limit=10)
    finally:
        conn.close()

    assert result["candidate_count"] == 3
    assert result["by_rule"] == {
        "obsidian_history": 1,
        "obsidian_archived": 1,
        "obsidian_changelog": 1,
    }
    assert [sample["id"] for sample in result["samples"]] == [1, 2, 3]


def test_apply_archive_updates_status():
    conn = _make_conn()
    try:
        result = apply_archive(conn, days=30)
        statuses = {
            row["id"]: row["status"]
            for row in conn.execute("SELECT id, status FROM nodes").fetchall()
        }
    finally:
        conn.close()

    assert result["archived_count"] == 3
    assert statuses[1] == "archived"
    assert statuses[2] == "archived"
    assert statuses[3] == "archived"
    assert statuses[4] == "active"
    assert statuses[5] == "active"
    assert statuses[6] == "active"
    assert statuses[7] == "active"
    assert statuses[8] == "active"
