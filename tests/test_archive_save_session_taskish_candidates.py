"""archive_save_session_taskish_candidates script tests."""

from pathlib import Path
import json
import shutil
import sqlite3
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.archive_save_session_taskish_candidates import main


def _make_runtime_dir() -> Path:
    runtime_dir = ROOT / "tests" / f".runtime_archive_taskish_{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _init_test_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY,
                type TEXT,
                project TEXT,
                status TEXT,
                source TEXT,
                node_role TEXT,
                content TEXT,
                updated_at TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO nodes (id, type, project, status, source, node_role, content, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            [
                (1, "Decision", "portfolio", "active", "save_session", "knowledge_candidate", "textAnchor SVG 속성 center→middle 수정 (TS 빌드 에러)"),
                (2, "Question", "portfolio", "active", "save_session", "knowledge_candidate", "findings/ untracked 파일 25개 커밋 여부 (커버 이미지·HTML)"),
                (3, "Decision", "tech-review", "active", "save_session", "knowledge_candidate", "병렬 파일 쓰기 금지: 에이전트 4개가 같은 JSON 동시 수정 시 충돌 발생 확인"),
                (4, "Question", "mcp-memory", "active", "save_session", "knowledge_candidate", "checkpoint 역할 재검토: Layer A 전용 축소 vs 폐기 vs 현행 유지 (v6 세션에서 판단)"),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_archive_save_session_taskish_candidates_apply():
    runtime_dir = _make_runtime_dir()
    try:
        db_path = runtime_dir / "memory.db"
        report_path = runtime_dir / "report.json"
        _init_test_db(db_path)

        rc = main(["--db", str(db_path), "--report", str(report_path)])
        assert rc == 0

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["candidates"]["candidate_count"] == 2

        rc = main(["--db", str(db_path), "--apply", "--report", str(report_path)])
        assert rc == 0

        conn = sqlite3.connect(str(db_path))
        try:
            statuses = conn.execute("SELECT id, status FROM nodes ORDER BY id").fetchall()
        finally:
            conn.close()

        assert statuses == [
            (1, "archived"),
            (2, "archived"),
            (3, "active"),
            (4, "active"),
        ]
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)
