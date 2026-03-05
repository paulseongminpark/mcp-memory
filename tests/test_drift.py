"""tests/test_drift.py — drift 탐지 + summary 길이 검증 테스트.

설계: d-r3-12
커버리지:
  TD01 cosine_similarity == 1.0 (동일 벡터)
  TD02 cosine_similarity == 0.0 (직교)
  TD03 cosine_similarity == 0.0 (길이 불일치)
  TD04 cosine_similarity 정상 범위 (-1~1)
  TD05 _get_summary_median_length — 샘플 부족 → None
  TD06 _get_summary_median_length — 충분한 샘플 → 중앙값 반환
  TD07 _validate_summary_length — 정상 길이
  TD08 _validate_summary_length — 이상치 (2배 초과)
  TD09 _validate_summary_length — 샘플 부족 시 무조건 통과
  TD10 _apply E7 drift_detected → vector_store.add 미호출
  TD11 _apply E7 drift 없을 때 → vector_store.add 호출
  TD12 _apply E7 old_embedding 없을 때 → 무조건 add 호출
  TD13 _apply E1 정상 summary → updates 반영
  TD14 _apply E1 이상치 summary → updates 미반영, correction_log 기록
  TD15 enrich_node_combined E1 이상치 → 기존 summary 유지
"""
from __future__ import annotations

import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.similarity import cosine_similarity


# ── TD01-TD04: cosine_similarity ──────────────────────────────────────────────

def test_td01_identical_vectors():
    """TD01: 동일 벡터 → 1.0."""
    assert cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(1.0)


def test_td02_orthogonal_vectors():
    """TD02: 직교 벡터 → 0.0."""
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_td03_mismatched_length():
    """TD03: 길이 불일치 → 0.0."""
    assert cosine_similarity([1.0, 0.0], [1.0]) == 0.0


def test_td04_similarity_range():
    """TD04: 유사도는 -1 ~ 1 범위."""
    a = [0.3, 0.7, -0.2]
    b = [-0.1, 0.5, 0.8]
    sim = cosine_similarity(a, b)
    assert -1.0 <= sim <= 1.0


def test_td04_opposite_vectors():
    """TD04b: 반대 방향 벡터 → -1.0."""
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


# ── Fixtures for NodeEnricher ─────────────────────────────────────────────────

def _make_enricher_conn(
    nodes: list[tuple] | None = None,
) -> tuple:
    """in-memory DB + NodeEnricher 생성.
    nodes: [(id, type, layer, summary, enriched_at), ...]
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE nodes (
            id INTEGER PRIMARY KEY,
            type TEXT, layer INTEGER DEFAULT 0,
            content TEXT DEFAULT 'test content',
            summary TEXT, key_concepts TEXT, tags TEXT,
            facets TEXT, domains TEXT, secondary_types TEXT,
            quality_score REAL, abstraction_level REAL,
            temporal_relevance REAL, actionability REAL,
            project TEXT DEFAULT '', status TEXT DEFAULT 'active',
            enrichment_status TEXT DEFAULT '{}',
            enriched_at TEXT, created_at TEXT DEFAULT '2026-01-01',
            updated_at TEXT
        );
        CREATE TABLE correction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id INTEGER, edge_id INTEGER,
            field TEXT, old_value TEXT, new_value TEXT,
            reason TEXT, corrected_by TEXT, created_at TEXT
        );
        CREATE TABLE hub_snapshots (
            node_id INTEGER, snapshot_date TEXT, ihs_score REAL
        );
    """)
    if nodes:
        conn.executemany(
            "INSERT INTO nodes (id, type, layer, summary, enriched_at) VALUES (?,?,?,?,?)",
            nodes,
        )
    conn.commit()

    # NodeEnricher mock: conn만 교체
    from scripts.enrich.node_enricher import NodeEnricher
    enricher = NodeEnricher.__new__(NodeEnricher)
    enricher.conn = conn
    enricher.dry_run = False
    enricher.stats = {"processed": 0, "skipped": 0, "errors": 0}
    return enricher, conn


# ── TD05-TD09: summary 길이 검증 ──────────────────────────────────────────────

def test_td05_median_length_insufficient_sample():
    """TD05: SUMMARY_LENGTH_MIN_SAMPLE(10) 미만 → None."""
    enricher, _ = _make_enricher_conn(nodes=[
        (i + 1, "Principle", 0, "짧은 요약", "2026-01-01") for i in range(3)
    ])
    result = enricher._get_summary_median_length("Principle")
    assert result is None


def test_td06_median_length_sufficient_sample():
    """TD06: 10개 이상 샘플 → 중앙값 반환."""
    # 길이 10 × 10개 → 중앙값 10
    summaries = [
        (i + 1, "Pattern", 0, "x" * 10, "2026-01-01")
        for i in range(10)
    ]
    enricher, _ = _make_enricher_conn(nodes=summaries)
    median = enricher._get_summary_median_length("Pattern")
    assert median == pytest.approx(10.0)


def test_td07_validate_summary_normal():
    """TD07: 정상 길이 summary → (True, None)."""
    # 중앙값 10, 한도 20 → 15자는 정상
    summaries = [(i + 1, "Insight", 0, "x" * 10, "2026-01-01") for i in range(10)]
    enricher, _ = _make_enricher_conn(nodes=summaries)
    ok, reason = enricher._validate_summary_length("x" * 15, "Insight")
    assert ok is True
    assert reason is None


def test_td08_validate_summary_anomaly():
    """TD08: 중앙값 2배 초과 → (False, reason)."""
    # 중앙값 10, 한도 20 → 25자는 이상치
    summaries = [(i + 1, "Insight", 0, "x" * 10, "2026-01-01") for i in range(10)]
    enricher, _ = _make_enricher_conn(nodes=summaries)
    ok, reason = enricher._validate_summary_length("x" * 25, "Insight")
    assert ok is False
    assert reason is not None
    assert "length_anomaly" in reason


def test_td09_validate_summary_no_sample():
    """TD09: 샘플 부족 → 무조건 (True, None)."""
    enricher, _ = _make_enricher_conn(nodes=[])
    ok, reason = enricher._validate_summary_length("아무 텍스트나", "UnknownType")
    assert ok is True
    assert reason is None


# ── TD10-TD14: _apply E7/E1 ───────────────────────────────────────────────────

def test_td10_e7_drift_blocks_chroma_update():
    """TD10: drift_detected → vector_store.add 미호출."""
    enricher, conn = _make_enricher_conn(nodes=[(1, "Principle", 4, None, None)])
    node = {"id": 1, "type": "Principle", "layer": 4, "project": "", "tags": ""}
    updates = {}

    with patch("utils.access_control.check_access", return_value=True), \
         patch("storage.vector_store.get_node_embedding") as mock_get, \
         patch("utils.similarity.cosine_similarity", return_value=0.1) as mock_cos, \
         patch("embedding.openai_embed.embed_text", return_value=[0.1] * 3) as mock_embed, \
         patch("storage.vector_store.add") as mock_add, \
         patch("storage.sqlite_store.log_correction") as mock_log:

        mock_get.return_value = [1.0, 0.0, 0.0]  # old embedding 존재

        enricher._apply("E7", "embedding text", node, updates)

        mock_add.assert_not_called()
        mock_log.assert_called_once()
        args = mock_log.call_args[1]
        assert "semantic_drift" in args["reason"]


def test_td11_e7_no_drift_updates_chroma():
    """TD11: 드리프트 없을 때 → vector_store.add 호출."""
    enricher, conn = _make_enricher_conn(nodes=[(1, "Pattern", 2, None, None)])
    node = {"id": 1, "type": "Pattern", "layer": 2, "project": "", "tags": ""}
    updates = {}

    with patch("utils.access_control.check_access", return_value=True), \
         patch("storage.vector_store.get_node_embedding") as mock_get, \
         patch("utils.similarity.cosine_similarity", return_value=0.99) as mock_cos, \
         patch("embedding.openai_embed.embed_text", return_value=[0.9] * 3) as mock_embed, \
         patch("storage.vector_store.add") as mock_add, \
         patch("storage.sqlite_store.log_correction") as mock_log:

        mock_get.return_value = [1.0, 0.0, 0.0]  # old embedding 존재

        enricher._apply("E7", "embedding text", node, updates)

        mock_add.assert_called_once()
        mock_log.assert_not_called()


def test_td12_e7_no_old_embedding_always_updates():
    """TD12: old_embedding 없을 때 → drift 탐지 없이 바로 add."""
    enricher, conn = _make_enricher_conn(nodes=[(1, "Pattern", 2, None, None)])
    node = {"id": 1, "type": "Pattern", "layer": 2, "project": "", "tags": ""}
    updates = {}

    with patch("utils.access_control.check_access", return_value=True), \
         patch("storage.vector_store.get_node_embedding", return_value=None), \
         patch("storage.vector_store.add") as mock_add, \
         patch("storage.sqlite_store.log_correction") as mock_log:

        enricher._apply("E7", "embedding text", node, updates)

        mock_add.assert_called_once()
        mock_log.assert_not_called()


def test_td13_e1_normal_summary_applied():
    """TD13: 정상 길이 summary → updates["summary"] 설정."""
    # 충분한 샘플 없음 → 길이 검증 skip → 무조건 통과
    enricher, _ = _make_enricher_conn(nodes=[(1, "Insight", 2, None, None)])
    node = {"id": 1, "type": "Insight", "summary": None}
    updates = {}

    # check_access mock: 실제 DB 조회 우회 (테스트는 summary 검증만 확인)
    with patch("utils.access_control.check_access", return_value=True):
        enricher._apply("E1", "정상 요약 텍스트", node, updates)

    assert updates.get("summary") == "정상 요약 텍스트"


def test_td14_e1_anomaly_summary_not_applied():
    """TD14: 이상치 summary → updates 미반영, correction_log 기록."""
    # 샘플 10개 길이 10 → 중앙값 10, 한도 20. 50자는 이상치
    summaries = [(i + 1, "Insight", 0, "x" * 10, "2026-01-01") for i in range(10)]
    enricher, _ = _make_enricher_conn(nodes=summaries + [(20, "Insight", 0, None, None)])
    node = {"id": 20, "type": "Insight", "summary": "기존 요약"}
    updates = {}

    # check_access mock: 실제 DB 조회 우회 (테스트는 summary 검증만 확인)
    with patch("utils.access_control.check_access", return_value=True), \
         patch("storage.sqlite_store.log_correction") as mock_log:
        enricher._apply("E1", "x" * 50, node, updates)

    assert "summary" not in updates  # 기존 summary 유지
    mock_log.assert_called_once()
    kw = mock_log.call_args[1]
    assert kw["field"] == "summary"
    assert kw["corrected_by"] == "summary_length_validator"


# ── TD15: enrich_node_combined E1 이상치 ─────────────────────────────────────

def test_td15_combined_e1_anomaly_keeps_old_summary():
    """TD15: enrich_node_combined E1 이상치 → 기존 summary 유지."""
    summaries = [(i + 1, "Pattern", 0, "x" * 10, "2026-01-01") for i in range(10)]
    enricher, conn = _make_enricher_conn(nodes=summaries)
    # 테스트 노드: 기존 summary = "기존 요약"
    conn.execute(
        "INSERT INTO nodes (id, type, layer, content, summary, status, enrichment_status) "
        "VALUES (100, 'Pattern', 2, 'content here', '기존 요약', 'active', '{}')"
    )
    conn.commit()

    enricher.dry_run = True  # DB 쓰기 방지

    # API 응답 mock: summary가 매우 긴 이상치
    mock_response = {
        "summary": "x" * 100,  # 100자 → 중앙값(10)의 10배, 한도(20) 초과
        "concepts": ["a"], "tags": ["b"], "facets": [], "domains": [],
        "quality_score": 0.8, "abstraction_level": 0.5,
        "temporal_relevance": 0.7, "actionability": 0.6,
    }

    with patch.object(enricher, "_call_json", return_value=mock_response), \
         patch.object(enricher, "_get_node") as mock_get_node, \
         patch("storage.sqlite_store.log_correction") as mock_log:

        mock_get_node.return_value = {
            "id": 100, "type": "Pattern", "layer": 2,
            "content": "content here", "summary": "기존 요약",
            "tags": "", "enrichment_status": "{}",
        }

        result = enricher.enrich_node_combined(100)

    # E1이 이상치이므로 결과에 없거나 correction_log 기록
    assert "E1" not in result or mock_log.called
