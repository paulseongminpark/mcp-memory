"""save_session low-signal suppression tests."""

from contextlib import ExitStack
from pathlib import Path
import shutil
import sys
import uuid
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from storage import sqlite_store
from tools.save_session import classify_session_item_role, save_session


def _make_runtime_dir() -> Path:
    runtime_dir = ROOT / "tests" / f".runtime_save_session_{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


@pytest.fixture()
def session_db():
    runtime_dir = _make_runtime_dir()
    db_path = runtime_dir / "memory.db"

    with ExitStack() as stack:
        stack.enter_context(patch("config.DB_PATH", db_path))
        stack.enter_context(patch("storage.sqlite_store.DB_PATH", db_path))
        stack.enter_context(patch("storage.action_log.sqlite_store.DB_PATH", db_path))
        stack.enter_context(patch("utils.access_control.DB_PATH", db_path))
        sqlite_store.init_db()
        yield db_path

    shutil.rmtree(runtime_dir, ignore_errors=True)


@patch("storage.vector_store.add", return_value=None)
@patch("storage.vector_store.search", return_value=[])
def test_save_session_skips_short_work_items(mock_search, mock_add, session_db):
    result = save_session(
        session_id="sess-short",
        summary="session summary",
        decisions=["짧다", "이 결정은 충분히 길고 구체적이어서 durable memory로 남기고 이후 검색에서도 재사용해야 한다."],
        unresolved=["짧은 질문", "이 unresolved question은 충분히 길고 구체적이어서 durable memory로 남겨 다음 세션에서도 이어가야 한다."],
        project="mcp-memory",
    )

    with sqlite_store._db() as conn:
        rows = conn.execute(
            """
            SELECT type, content, node_role
            FROM nodes
            WHERE source = 'save_session' AND status = 'active'
            ORDER BY id
            """
        ).fetchall()
        edges = conn.execute(
            """
            SELECT relation, generation_method
            FROM edges
            WHERE generation_method = 'session_anchor'
            ORDER BY id
            """
        ).fetchall()

    typed = [(r["type"], r["content"], r["node_role"]) for r in rows]

    assert result["nodes_created"]["narrative"] == 1
    assert result["nodes_created"]["decisions"] == 1
    assert result["nodes_created"]["questions"] == 1
    assert result["skipped_low_signal"] == {"decisions": 1, "questions": 1}

    assert ("Decision", "짧다", "work_item") not in typed
    assert ("Question", "짧은 질문", "work_item") not in typed
    assert any(r[0] == "Decision" and "durable memory" in r[1] for r in typed)
    assert any(r[0] == "Question" and "durable memory" in r[1] for r in typed)
    assert len(edges) == 2


def test_classify_session_item_role_filters_taskish_but_keeps_durable_items():
    assert classify_session_item_role(
        "textAnchor SVG 속성 center→middle 수정 (TS 빌드 에러)",
        "Decision",
    ) == "work_item"
    assert classify_session_item_role(
        "findings/ untracked 파일 25개 커밋 여부 (커버 이미지·HTML)",
        "Question",
    ) == "work_item"
    assert classify_session_item_role(
        "병렬 파일 쓰기 금지: 에이전트 4개가 같은 JSON 동시 수정 시 충돌 발생 확인",
        "Decision",
    ) == "knowledge_candidate"
    assert classify_session_item_role(
        "checkpoint 역할 재검토: Layer A 전용 축소 vs 폐기 vs 현행 유지 (v6 세션에서 판단)",
        "Question",
    ) == "knowledge_candidate"
    assert classify_session_item_role(
        "typed vector TYPE_CHANNEL_WEIGHTS 동적 가중치 적용 (Pattern/Decision=1.0)",
        "Decision",
    ) == "knowledge_candidate"
    assert classify_session_item_role(
        "SWR 점수 자연 축적 확인 (Pre-flight Recall 정착 후)",
        "Question",
    ) == "knowledge_candidate"
    assert classify_session_item_role(
        "YouTube AP 미완 2건: 'How Anthropic Employees ACTUALLY Use Claude Code', 'Without Palantir' — 크레딧 충전 후 재실행",
        "Question",
    ) == "work_item"
    assert classify_session_item_role(
        "CE 다이어그램 Gemini 작성분 유지 vs Primitive 기반 재작성",
        "Question",
    ) == "work_item"
    assert classify_session_item_role(
        "run-daily-v3.py: pull --rebase + push returncode 체크 추가 (silent failure 방지)",
        "Decision",
    ) == "work_item"
    assert classify_session_item_role(
        "MCP_MEMORY_DETAIL_KO.md에 Paul 리라이트 텍스트 반영 필요",
        "Question",
    ) == "work_item"
    assert classify_session_item_role(
        "recall() min_score 0.3 + quality signals",
        "Decision",
    ) == "knowledge_candidate"
    assert classify_session_item_role(
        ".impeccable.md로 디자인 컨텍스트 관리 (브랜드 깊이·절제·친근, 토큰, 레퍼런스)",
        "Decision",
    ) == "knowledge_candidate"
    assert classify_session_item_role(
        "split 마커 시스템 도입: v3.md에 <!-- split --> 추가하면 left/right 페이지 정확히 분할. md 단일 소스로 레이아웃 제어",
        "Decision",
    ) == "knowledge_candidate"
