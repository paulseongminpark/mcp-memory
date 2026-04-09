import sqlite3

from scripts.archive_stale_tech_review_impl_tasks import apply_archive, collect_candidates


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
            r"obsidian:01_projects\03_tech-review\design\2026-02-17-tech-review-impl.md#1",
            "Tool",
            "tech-review",
            "## Task 1\n**Files:**\n- Create: `tech-review/_config.yml`\n```bash\ngh repo create\n```",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            2,
            r"obsidian:01_projects\03_tech-review\design\2026-02-18-tech-review-design.md#1",
            "Framework",
            "tech-review",
            "## 시스템 흐름\n설계 문서 요약",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            3,
            r"obsidian:01_projects\03_tech-review\blog\docs\plans\2026-02-18-daily-digest-impl.md#1",
            "Insight",
            "tech-review",
            "오늘의 핵심 요약",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            4,
            r"obsidian:01_projects\03_tech-review\design\2026-02-17-tech-review-impl.md#2",
            "Tool",
            "tech-review",
            "## Task 2\n**Files:**\n- Modify: `foo`\n**Step 1** do it",
            "active",
            1,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            5,
            r"obsidian:01_projects\03_tech-review\design\2026-02-17-tech-review-impl.md#3",
            "Tool",
            "tech-review",
            "## Task 3\n**Files:**\n- Create: `bar`",
            "active",
            0,
            "2099-01-01T00:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            6,
            r"obsidian:01_projects\03_tech-review\design\2026-02-17-tech-review-impl.md#4",
            "Tool",
            "tech-review",
            "## Task 4\n**Files:**\n- Create: `baz`",
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


def test_collect_candidates_matches_only_stale_tech_review_impl_task_nodes():
    conn = _make_conn()
    try:
        result = collect_candidates(conn, days=30, sample_limit=10)
    finally:
        conn.close()

    assert result["candidate_count"] == 1
    assert [sample["id"] for sample in result["samples"]] == [1]


def test_apply_archive_marks_only_taskish_impl_candidates():
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
