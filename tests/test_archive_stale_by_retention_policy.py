import sqlite3

from scripts.archive_stale_by_retention_policy import apply_archive, collect_candidates


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
            r"checkpoint",
            "Decision",
            "mcp-memory",
            "checkpoint keep",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            2,
            r"claude",
            "Insight",
            "orchestration",
            "claude keep",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            3,
            r"obsidian:01_projects\04_monet-lab\docs\plans\2026-02-22-page-12-implementation.md#8013135c7cf3f600",
            "Tool",
            "monet-lab",
            "tmux new-session -s dev",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            4,
            r"obsidian:01_projects\04_monet-lab\docs\plans\2026-02-22-page-12-implementation.md#8013135c7cf3f600",
            "Pattern",
            "monet-lab",
            "workflow principle",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            5,
            r"obsidian:01_projects\03_tech-review\blog\docs\plans\2026-02-18-daily-digest-impl.md#dc443a29d25fa44f",
            "Insight",
            "tech-review",
            "dated digest",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
        (
            6,
            r"obsidian:01_projects\06_mcp-memory\docs\01-design.md#e80ba3c9035a2785",
            "Tool",
            "mcp-memory",
            "canonical doc keep",
            "active",
            0,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "knowledge_candidate",
            "provisional",
        ),
    ]
    conn.executemany(
        "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return conn


def test_collect_candidates_respects_keep_and_archive_planes():
    conn = _make_conn()
    try:
        result = collect_candidates(conn, days=30, sample_limit=10)
    finally:
        conn.close()

    assert result["candidate_count"] == 2
    assert result["by_rule"] == {
        "dated_digest_impl": 1,
        "page12_command_cookbook": 1,
    }
    assert {sample["id"] for sample in result["samples"]} == {3, 5}


def test_apply_archive_only_marks_archive_plane_candidates():
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
    assert statuses[2] == "active"
    assert statuses[3] == "archived"
    assert statuses[4] == "active"
    assert statuses[5] == "archived"
    assert statuses[6] == "active"
