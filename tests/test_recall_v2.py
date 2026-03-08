"""P1-W2-04: recall.py v2 테스트 — mode/패치전환/포매팅/graceful."""

from unittest.mock import MagicMock, patch, call
import pytest

from tools.recall import _is_patch_saturated, _dominant_project


# ─── 헬퍼 ─────────────────────────────────────────────────────────────

def _make_results(projects: list[str], score: float = 0.9) -> list[dict]:
    """테스트용 recall 결과 목록 생성."""
    return [
        {"id": i + 1, "type": "Observation", "content": f"c{i}",
         "project": p, "tags": "", "score": score - i * 0.01,
         "created_at": "2026-03-05"}
        for i, p in enumerate(projects)
    ]


# ─── _is_patch_saturated 단위 테스트 ──────────────────────────────────

class TestIsPatchSaturated:
    def test_less_than_3_results(self):
        """결과 3개 미만 → 항상 False."""
        results = _make_results(["pf", "pf"])
        assert _is_patch_saturated(results) is False

    def test_exact_75_percent(self):
        """75% 정확히 → 포화 (>=0.75)."""
        results = _make_results(["pf", "pf", "pf", "orch"])
        # 3/4 = 0.75 → 포화
        assert _is_patch_saturated(results) is True

    def test_below_75_not_saturated(self):
        """74% 이하 → 미포화."""
        results = _make_results(["pf", "pf", "orch", "orch", "mcp"])
        # pf=2/5=40% → 미포화
        assert _is_patch_saturated(results) is False

    def test_100_percent_saturated(self):
        """100% 동일 project → 포화."""
        results = _make_results(["pf", "pf", "pf", "pf", "pf"])
        assert _is_patch_saturated(results) is True

    def test_empty_project_counted(self):
        """빈 project("")도 포화 계산에 포함."""
        results = _make_results(["", "", "", "pf"])
        # "": 3/4 = 75% → 포화
        assert _is_patch_saturated(results) is True


# ─── _dominant_project 단위 테스트 ────────────────────────────────────

class TestDominantProject:
    def test_dominant(self):
        results = _make_results(["pf", "pf", "orch", "pf"])
        assert _dominant_project(results) == "pf"

    def test_single_project(self):
        results = _make_results(["mcp"])
        assert _dominant_project(results) == "mcp"


# ─── recall() 통합 테스트 ─────────────────────────────────────────────

class TestRecall:
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_empty_results(self, mock_hs, mock_sqls):
        """결과 없음 → {"results": [], "message": ...}."""
        mock_hs.return_value = []

        from tools.recall import recall
        result = recall("없는 내용")
        assert result["results"] == []
        assert "No memories found" in result["message"]

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.post_search_learn")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_basic_format(self, mock_hs, mock_sqls, mock_psl, mock_inc):
        """기본 반환 형태 확인."""
        mock_hs.return_value = [{
            "id": 1, "type": "Observation", "content": "테스트 내용",
            "project": "mcp-memory", "tags": "", "score": 0.9,
            "created_at": "2026-03-05",
        }]
        mock_sqls.get_edges.return_value = []

        from tools.recall import recall
        result = recall("테스트")
        assert "results" in result
        assert "count" in result
        assert "message" in result
        assert result["count"] == 1
        assert result["results"][0]["id"] == 1

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_mode_passed_to_hybrid(self, mock_hs, mock_sqls, mock_inc):
        """mode 파라미터가 hybrid_search로 전달되는지."""
        mock_hs.return_value = []

        from tools.recall import recall
        recall("테스트", mode="focus")
        mock_hs.assert_called_once_with(
            "테스트",
            type_filter="",
            project="",
            top_k=5,
            mode="focus",
        )

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_mode_dmn_passed(self, mock_hs, mock_sqls, mock_inc):
        """mode='dmn' 정상 전달."""
        mock_hs.return_value = []

        from tools.recall import recall
        recall("기억", mode="dmn")
        args, kwargs = mock_hs.call_args
        assert kwargs.get("mode") == "dmn"

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.post_search_learn")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_no_patch_when_project_specified(self, mock_hs, mock_sqls, mock_psl, mock_inc):
        """project 명시 시 패치 전환 없음 → 패치 검색 추가 없이 Correction 검색만."""
        pf_results = _make_results(["pf", "pf", "pf", "pf", "pf"])
        # 1차: 원래 검색, 2차: Correction top-inject (score 낮게 → 필터 통과 안 됨)
        mock_hs.side_effect = [pf_results, _make_results([], score=0.0)]
        mock_sqls.get_edges.return_value = []

        from tools.recall import recall
        recall("포트폴리오", project="portfolio")
        assert mock_hs.call_count == 2  # 원래 검색 1 + Correction top-inject 1

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.post_search_learn")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_patch_switch_on_saturation(self, mock_hs, mock_sqls, mock_psl, mock_inc):
        """100% 포화 → hybrid_search 3회 호출 (원래 + 2차 패치 + Correction top-inject)."""
        saturated = _make_results(["pf"] * 5)
        alt = _make_results(["orch", "mcp", "tr"])
        mock_hs.side_effect = [saturated, alt, []]  # 3차: Correction (없음)
        mock_sqls.get_edges.return_value = []

        from tools.recall import recall
        result = recall("포트폴리오")
        assert mock_hs.call_count == 3
        # 2차 호출에 excluded_project 전달 확인
        _, kwargs2 = mock_hs.call_args_list[1]
        assert kwargs2.get("excluded_project") == "pf"

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.post_search_learn")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_patch_no_switch_top_k_2(self, mock_hs, mock_sqls, mock_psl, mock_inc):
        """top_k=2 → 결과 < 3 → 포화 판단 불가 → 패치 전환 없음 (Correction 검색만 추가)."""
        results = _make_results(["pf", "pf"])
        mock_hs.side_effect = [results, []]  # 2차: Correction (없음)
        mock_sqls.get_edges.return_value = []

        from tools.recall import recall
        recall("포트폴리오", top_k=2)
        assert mock_hs.call_count == 2  # 원래 검색 1 + Correction top-inject 1

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.post_search_learn")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_increment_recall_called(self, mock_hs, mock_sqls, mock_psl, mock_inc):
        """_increment_recall_count() 매 recall 호출마다 실행."""
        mock_hs.return_value = _make_results(["pf"])
        mock_sqls.get_edges.return_value = []

        from tools.recall import recall
        recall("테스트")
        mock_inc.assert_called_once()

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.post_search_learn")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_content_truncated_200(self, mock_hs, mock_sqls, mock_psl, mock_inc):
        """content 200자 초과 시 잘림."""
        long_content = "x" * 300
        mock_hs.return_value = [{
            "id": 1, "type": "Observation", "content": long_content,
            "project": "", "tags": "", "score": 0.9, "created_at": "2026-03-05",
        }]
        mock_sqls.get_edges.return_value = []

        from tools.recall import recall
        result = recall("x")
        assert len(result["results"][0]["content"]) == 200

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.post_search_learn")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_related_edges_max_3(self, mock_hs, mock_sqls, mock_psl, mock_inc):
        """related는 최대 3개."""
        mock_hs.return_value = [{
            "id": 1, "type": "Observation", "content": "c",
            "project": "", "tags": "", "score": 0.9, "created_at": "2026-03-05",
        }]
        mock_sqls.get_edges.return_value = [
            {"source_id": 1, "target_id": 2, "relation": "relates_to"},
            {"source_id": 1, "target_id": 3, "relation": "supports"},
            {"source_id": 1, "target_id": 4, "relation": "connects_with"},
            {"source_id": 1, "target_id": 5, "relation": "leads_to"},
        ]

        from tools.recall import recall
        result = recall("테스트")
        assert len(result["results"][0]["related"]) == 3


# ─── _increment_recall_count graceful skip ────────────────────────────

class TestIncrementRecallCount:
    def test_graceful_skip_on_exception(self):
        """meta 테이블 없으면 예외 없이 통과."""
        with patch("tools.recall.sqlite_store") as mock_sqls:
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = Exception("no such table: meta")
            mock_sqls._connect.return_value = mock_conn

            from tools.recall import _increment_recall_count
            _increment_recall_count()  # 예외 발생 없어야 함
