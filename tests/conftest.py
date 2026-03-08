"""공통 pytest fixtures — DB 환경, 샘플 노드/엣지."""

import shutil
import sqlite3
import sys
import uuid
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from storage import sqlite_store


# ─── 헬퍼 ──────────────────────────────────────────────────────────


def _make_runtime_dir(prefix: str) -> Path:
    runtime_dir = ROOT / "tests" / f".runtime_{prefix}_{uuid.uuid4().hex}"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _ensure_test_schema(db_path: Path) -> None:
    """init_db()에 없는 컬럼 보완 (테스트 호환)."""
    conn = sqlite3.connect(str(db_path))
    try:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(nodes)").fetchall()
        }
        if "last_activated" not in columns:
            conn.execute("ALTER TABLE nodes ADD COLUMN last_activated TEXT")
        conn.commit()
    finally:
        conn.close()


def _reset_hybrid_cache() -> None:
    from storage import hybrid
    hybrid._GRAPH_CACHE = None
    hybrid._GRAPH_CACHE_TS = 0.0


# ─── fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def fresh_db(tmp_path):
    """임시 디렉토리에 새 DB 생성. DB_PATH 패치 + init_db() 실행.

    yield: db_path (Path)
    teardown: hybrid 캐시 리셋
    """
    db_path = tmp_path / "memory.db"

    with ExitStack() as stack:
        stack.enter_context(patch("config.DB_PATH", db_path))
        stack.enter_context(patch("storage.sqlite_store.DB_PATH", db_path))
        stack.enter_context(patch("storage.action_log.sqlite_store.DB_PATH", db_path))
        stack.enter_context(patch("utils.access_control.DB_PATH", db_path))
        sqlite_store.init_db()
        _ensure_test_schema(db_path)
        _reset_hybrid_cache()
        yield db_path
        _reset_hybrid_cache()


@pytest.fixture()
def sample_nodes(fresh_db):
    """3개 샘플 노드 생성. returns: list[int] (node_ids)"""
    contents = [
        ("Observation", "테스트 관찰 노드 alpha", 0),
        ("Insight", "테스트 인사이트 노드 beta", 2),
        ("Principle", "테스트 원칙 노드 gamma", 3),
    ]
    node_ids = []
    for type_, content, layer in contents:
        nid = sqlite_store.insert_node(
            type=type_,
            content=content,
            metadata={},
            layer=layer,
            tier=2,
        )
        node_ids.append(nid)
    _reset_hybrid_cache()
    return node_ids


@pytest.fixture()
def sample_edges(sample_nodes):
    """sample_nodes 간 2개 edge 생성. returns: list[int] (edge_ids)"""
    edge_ids = []
    edge_ids.append(sqlite_store.insert_edge(
        source_id=sample_nodes[0],
        target_id=sample_nodes[1],
        relation="connects_with",
        description="[]",
        strength=0.5,
    ))
    edge_ids.append(sqlite_store.insert_edge(
        source_id=sample_nodes[1],
        target_id=sample_nodes[2],
        relation="crystallized_into",
        description="[]",
        strength=0.8,
    ))
    _reset_hybrid_cache()
    return edge_ids
