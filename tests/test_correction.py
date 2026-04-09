"""P2-W2-03: Correction 타입 테스트.

- Correction 노드 생성 → recall 시 최상위 노출 (top-inject)
- Correction 0개 시 기존 동작 동일
- schema/PROMOTE_LAYER 등록 확인
"""

from unittest.mock import patch, MagicMock
import pytest


# ─── Correction 타입 등록 검증 ────────────────────────────────────────────


def test_correction_in_promote_layer():
    """v3: Correction → Failure로 merge. Failure는 layer 1."""
    from config import PROMOTE_LAYER
    assert "Failure" in PROMOTE_LAYER
    assert PROMOTE_LAYER["Failure"] == 1


def test_correction_in_schema():
    """schema.yaml node_types에 Correction 등록."""
    import yaml
    from pathlib import Path
    schema_path = Path(__file__).resolve().parent.parent / "ontology" / "schema.yaml"
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    assert "Correction" in schema["node_types"]
    assert schema["node_types"]["Correction"]["layer"] == 3


# ─── Correction top-inject 동작 ───────────────────────────────────────────


def _make_node(id: int, type: str, score: float = 0.9, project: str = "") -> dict:
    return {
        "id": id, "type": type, "content": f"node-{id}",
        "project": project, "tags": "", "score": score,
        "created_at": "2026-03-08",
    }


@patch("tools.recall._increment_recall_count")
@patch("tools.recall._log_recall_results")
@patch("tools.recall.post_search_learn")
@patch("tools.recall.sqlite_store")
@patch("tools.recall.hybrid_search")
def test_correction_top_inject(mock_hs, mock_sqls, mock_psl, mock_log, mock_inc):
    """correction mode에서만 Correction 노드가 결과 맨 앞에 삽입된다."""
    regular = [_make_node(1, "Observation"), _make_node(2, "Signal")]
    correction = [_make_node(99, "Correction", score=0.85)]

    # 1차: 일반 검색 결과, 2차: Correction 검색 결과
    mock_hs.side_effect = [regular, correction]
    mock_sqls.get_edges.return_value = []

    from tools.recall import recall
    result = recall("Paul의 데이터베이스", mode="correction")

    assert result["results"][0]["type"] == "Correction"
    assert result["results"][0]["id"] == 99


@patch("tools.recall._increment_recall_count")
@patch("tools.recall._log_recall_results")
@patch("tools.recall.post_search_learn")
@patch("tools.recall.sqlite_store")
@patch("tools.recall.hybrid_search")
def test_correction_dedup(mock_hs, mock_sqls, mock_psl, mock_log, mock_inc):
    """correction mode에서 기존 결과에 이미 있는 Correction은 중복 삽입되지 않는다."""
    correction_node = _make_node(99, "Correction", score=0.85)
    regular = [_make_node(1, "Observation"), correction_node]
    correction = [correction_node]  # 동일 id=99

    mock_hs.side_effect = [regular, correction]
    mock_sqls.get_edges.return_value = []

    from tools.recall import recall
    result = recall("테스트 중복 제거", mode="correction")

    ids = [r["id"] for r in result["results"]]
    assert ids.count(99) == 1  # 중복 없음


@patch("tools.recall._increment_recall_count")
@patch("tools.recall._log_recall_results")
@patch("tools.recall.post_search_learn")
@patch("tools.recall.sqlite_store")
@patch("tools.recall.hybrid_search")
def test_no_correction_same_behavior(mock_hs, mock_sqls, mock_psl, mock_log, mock_inc):
    """generic mode에서는 Correction top-inject를 시도하지 않는다."""
    regular = [_make_node(1, "Observation", score=0.9),
               _make_node(2, "Signal", score=0.8)]

    mock_hs.return_value = regular
    mock_sqls.get_edges.return_value = []

    from tools.recall import recall
    result = recall("기존 동작 확인")

    ids = [r["id"] for r in result["results"]]
    assert ids == [1, 2]  # 원래 순서 유지
    assert mock_hs.call_count == 1


@patch("tools.recall._increment_recall_count")
@patch("tools.recall._log_recall_results")
@patch("tools.recall.post_search_learn")
@patch("tools.recall.sqlite_store")
@patch("tools.recall.hybrid_search")
def test_correction_low_score_filtered(mock_hs, mock_sqls, mock_psl, mock_log, mock_inc):
    """correction mode에서 score 낮은 Correction은 top-inject 제외."""
    regular = [_make_node(1, "Observation", score=0.9)]
    correction_low = [_make_node(99, "Correction", score=0.3)]  # 낮은 score

    mock_hs.side_effect = [regular, correction_low]
    mock_sqls.get_edges.return_value = []

    from tools.recall import recall
    result = recall("낮은 score 테스트", mode="correction")

    assert result["results"][0]["id"] == 1  # Correction 삽입 안 됨
    assert len(result["results"]) == 1
