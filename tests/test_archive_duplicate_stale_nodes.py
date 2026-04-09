import sqlite3

from scripts.archive_duplicate_stale_nodes import apply_archive, collect_candidates


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
        (
            1,
            r"obsidian:01_projects\04_monet-lab\src\experiments\page-11\content\A.md#1",
            "Insight",
            "monet-lab",
            "same content",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            2,
            r"obsidian:01_projects\04_monet-lab\src\experiments\page-11-v2\content\A.md#1",
            "Insight",
            "monet-lab",
            "same   content",
            "active",
            0,
            "2026-01-02T00:00:00+00:00",
            "2026-01-02T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            3,
            r"obsidian:01_projects\04_monet-lab\src\experiments\page-11-v3\content\A.md#1",
            "Insight",
            "monet-lab",
            "same content",
            "active",
            0,
            "2026-01-03T00:00:00+00:00",
            "2026-01-03T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            4,
            r"obsidian:01_projects\04_monet-lab\src\experiments\page-11\content\B.md#1",
            "Insight",
            "monet-lab",
            "unique content",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            5,
            r"obsidian:AGENTS.md#1",
            "Project",
            "orchestration",
            "shared rule content",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            6,
            r"obsidian:GEMINI.md#1",
            "Project",
            "orchestration",
            "shared rule content",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            7,
            r"obsidian:01_projects\02_portfolio\docs\plans\plan.md#1",
            "Pattern",
            "portfolio",
            "same content",
            "active",
            1,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            8,
            r"obsidian:01_projects\02_portfolio\docs\plans\plan.md#2",
            "Pattern",
            "portfolio",
            "same content",
            "active",
            0,
            "2099-01-01T00:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            9,
            r"obsidian:01_projects\02_portfolio\docs\plans\plan.md#3",
            "Pattern",
            "portfolio",
            "same content",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_core",
            "provisional",
        ),
    ]
    conn.executemany(
        "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return conn


def test_collect_candidates_keeps_single_canonical_and_excludes_foundation_docs():
    conn = _make_conn()
    try:
        result = collect_candidates(conn, days=30, sample_limit=10)
    finally:
        conn.close()

    assert result["group_count"] == 1
    assert result["candidate_count"] == 2
    group = result["sample_groups"][0]
    assert group["keeper"]["id"] == 1
    assert group["archive_ids"] == [2, 3]


def test_apply_archive_marks_only_duplicate_candidates():
    conn = _make_conn()
    try:
        result = apply_archive(conn, days=30)
        statuses = {
            row["id"]: row["status"]
            for row in conn.execute("SELECT id, status FROM nodes").fetchall()
        }
    finally:
        conn.close()

    assert result["archived_count"] == 2
    assert statuses[1] == "active"
    assert statuses[2] == "archived"
    assert statuses[3] == "archived"
    assert statuses[4] == "active"
    assert statuses[5] == "active"
    assert statuses[6] == "active"
    assert statuses[7] == "active"
    assert statuses[8] == "active"
    assert statuses[9] == "active"
