import sqlite3

from scripts.archive_stale_plan_task_nodes import apply_archive, collect_candidates


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
            r"obsidian:01_projects\02_portfolio\docs\plans\a.md#1",
            "Tool",
            "portfolio",
            "## Task 1\n**Files:**\n- Create: `C:\\dev\\01_projects\\02_portfolio\\a.ts`",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            2,
            r"obsidian:01_projects\02_portfolio\docs\plans\b.md#1",
            "Pattern",
            "portfolio",
            "## 설계 원칙\n컨텍스트를 먼저 줄이고 구조를 남긴다.",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            3,
            r"obsidian:01_projects\02_portfolio\docs\plans\c.md#1",
            "Tool",
            "portfolio",
            "## Task 2\n**Step 1**\n- Modify: foo",
            "active",
            2,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            4,
            r"obsidian:01_projects\02_portfolio\docs\plans\d.md#1",
            "Tool",
            "portfolio",
            "## Task 3\n**Files:**\n- Create: `C:\\dev\\01_projects\\02_portfolio\\b.ts`",
            "active",
            0,
            "2099-01-01T00:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            5,
            r"obsidian:01_projects\02_portfolio\docs\plans\e.md#1",
            "Tool",
            "portfolio",
            "## Task 4\n**Files:**\n- Create: `C:\\dev\\01_projects\\02_portfolio\\c.ts`",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_core",
            "provisional",
        ),
        (
            6,
            r"obsidian:01_projects\02_portfolio\docs\plans\f.md#1",
            "Tool",
            "portfolio",
            "## Task 5\n**Files:**\n- Create: `C:\\dev\\01_projects\\02_portfolio\\d.ts`",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "validated",
        ),
    ]
    conn.executemany(
        "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return conn


def test_collect_candidates_matches_only_taskish_stale_plan_nodes():
    conn = _make_conn()
    try:
        result = collect_candidates(conn, days=30, sample_limit=10)
    finally:
        conn.close()

    assert result["candidate_count"] == 1
    assert [sample["id"] for sample in result["samples"]] == [1]


def test_apply_archive_marks_only_taskish_candidates():
    conn = _make_conn()
    try:
        result = apply_archive(conn, days=30)
        statuses = {
            row["id"]: row["status"]
            for row in conn.execute("SELECT id, status FROM nodes").fetchall()
        }
    finally:
        conn.close()

    assert result["archived_count"] == 1
    assert statuses[1] == "archived"
    assert statuses[2] == "active"
    assert statuses[3] == "active"
    assert statuses[4] == "active"
    assert statuses[5] == "active"
    assert statuses[6] == "active"
