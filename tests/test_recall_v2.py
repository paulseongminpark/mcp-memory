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
            top_k=15,  # overfetch: top_k(5) * 3
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
        """project 명시 시 패치 전환 없음 → 추가 검색 없음."""
        pf_results = _make_results(["pf", "pf", "pf", "pf", "pf"])
        mock_hs.return_value = pf_results
        mock_sqls.get_edges.return_value = []

        from tools.recall import recall
        recall("포트폴리오", project="portfolio")
        assert mock_hs.call_count == 1

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.post_search_learn")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_patch_switch_on_saturation(self, mock_hs, mock_sqls, mock_psl, mock_inc):
        """100% 포화 → hybrid_search 2회 호출 (원래 + 2차 패치)."""
        saturated = _make_results(["pf"] * 5)
        alt = _make_results(["orch", "mcp", "tr"])
        mock_hs.side_effect = [saturated, alt]
        mock_sqls.get_edges.return_value = []

        from tools.recall import recall
        result = recall("포트폴리오")
        assert mock_hs.call_count == 2
        # 2차 호출에 excluded_project 전달 확인
        _, kwargs2 = mock_hs.call_args_list[1]
        assert kwargs2.get("excluded_project") == "pf"

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.post_search_learn")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_patch_switch_deduplicates_same_node_ids(self, mock_hs, mock_sqls, mock_psl, mock_inc):
        saturated = _make_results(["pf"] * 5)
        alt = [
            {
                "id": 1, "type": "Observation", "content": "dup",
                "project": "orch", "tags": "", "score": 0.99,
                "created_at": "2026-03-05",
            },
            {
                "id": 9, "type": "Observation", "content": "new",
                "project": "mcp", "tags": "", "score": 0.88,
                "created_at": "2026-03-05",
            },
        ]
        mock_hs.side_effect = [saturated, alt]
        mock_sqls.get_edges.return_value = []

        from tools.recall import recall
        result = recall("포트폴리오")
        ids = [r["id"] for r in result["results"]]

        assert ids.count(1) == 1
        assert 9 in ids
        assert len(ids) == len(set(ids))

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.post_search_learn")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_patch_no_switch_top_k_2(self, mock_hs, mock_sqls, mock_psl, mock_inc):
        """top_k=2 → 결과 < 3 → 포화 판단 불가 → 추가 검색 없음."""
        results = _make_results(["pf", "pf"])
        mock_hs.return_value = results
        mock_sqls.get_edges.return_value = []

        from tools.recall import recall
        recall("포트폴리오", top_k=2)
        assert mock_hs.call_count == 1

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

    @patch("tools.recall._log_recall_results")
    @patch("tools.recall._record_edge_contribution")
    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.post_search_learn")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_mutate_false_skips_all_writebacks(
        self, mock_hs, mock_sqls, mock_psl, mock_inc, mock_edge, mock_log
    ):
        """mutate=False면 학습/통계 write-back 전부 생략."""
        mock_hs.return_value = [(
            {
                "id": 1, "type": "Observation", "content": "테스트 내용",
                "project": "mcp-memory", "tags": "", "score": 0.9,
                "created_at": "2026-03-05",
            }
        )]
        mock_sqls.get_edges.return_value = []

        from tools.recall import recall
        result = recall("테스트", mutate=False)

        assert result["count"] == 1
        mock_psl.assert_not_called()
        mock_inc.assert_not_called()
        mock_edge.assert_not_called()
        mock_log.assert_not_called()

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.post_search_learn")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_patch_switch_applies_role_filter_to_alt_results(self, mock_hs, mock_sqls, mock_psl, mock_inc):
        """패치 전환 결과도 intent role 필터를 다시 거친다."""
        saturated = _make_results(["pf"] * 5)
        alt = [
            {
                "id": 10, "type": "Observation", "content": "noise",
                "project": "orch", "tags": "", "score": 0.95,
                "created_at": "2026-03-05", "node_role": "work_item",
            },
            {
                "id": 11, "type": "Observation", "content": "keep",
                "project": "mcp", "tags": "", "score": 0.85,
                "created_at": "2026-03-05", "node_role": "knowledge_candidate",
            },
        ]
        mock_hs.side_effect = [saturated, alt]
        mock_sqls.get_edges.return_value = []

        from tools.recall import recall
        result = recall("포트폴리오")
        ids = [r["id"] for r in result["results"]]

        assert 10 not in ids
        assert 11 in ids

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.post_search_learn")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_generic_filters_pdr_and_precompact_noise(self, mock_hs, mock_sqls, mock_psl, mock_inc):
        mock_hs.return_value = [
            {
                "id": 1, "type": "Narrative", "content": "pdr anchor",
                "project": "mcp-memory", "tags": "", "score": 0.9,
                "created_at": "2026-03-05", "node_role": "session_anchor",
                "source": "pdr",
            },
            {
                "id": 2, "type": "Observation", "content": "pdr observation",
                "project": "mcp-memory", "tags": "", "score": 0.8,
                "created_at": "2026-03-05", "node_role": "knowledge_candidate",
                "source": "pdr",
            },
            {
                "id": 3, "type": "Narrative", "content": "relay snapshot",
                "project": "mcp-memory", "tags": "", "score": 0.7,
                "created_at": "2026-03-05", "node_role": "knowledge_candidate",
                "source": "hook:PreCompact:relay",
            },
            {
                "id": 4, "type": "Failure", "content": "keep me",
                "project": "mcp-memory", "tags": "", "score": 0.6,
                "created_at": "2026-03-05", "node_role": "knowledge_candidate",
                "source": "pdr",
            },
        ]
        mock_sqls.get_edges.return_value = []

        from tools.recall import recall
        result = recall("테스트", mode="generic")
        ids = [r["id"] for r in result["results"]]

        assert ids == [4]

    @patch("tools.recall._increment_recall_count")
    @patch("tools.recall.post_search_learn")
    @patch("tools.recall.sqlite_store")
    @patch("tools.recall.hybrid_search")
    def test_recollection_keeps_pdr_narrative(self, mock_hs, mock_sqls, mock_psl, mock_inc):
        mock_hs.return_value = [
            {
                "id": 1, "type": "Narrative", "content": "pdr anchor",
                "project": "mcp-memory", "tags": "", "score": 0.9,
                "created_at": "2026-03-05", "node_role": "session_anchor",
                "source": "pdr",
            },
            {
                "id": 2, "type": "Observation", "content": "normal",
                "project": "mcp-memory", "tags": "", "score": 0.8,
                "created_at": "2026-03-05", "node_role": "knowledge_candidate",
                "source": "claude",
            },
        ]
        mock_sqls.get_edges.return_value = []

        from tools.recall import recall
        result = recall("회고", mode="recollection")
        ids = [r["id"] for r in result["results"]]

        assert ids == [1, 2]

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
        assert len(result["results"][0]["context"]) <= 5


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
