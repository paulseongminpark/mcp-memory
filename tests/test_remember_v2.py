"""P1-W2-03: remember.py v2 테스트 — classify/store/link/F3/action_log."""

from unittest.mock import MagicMock, patch
import pytest

from tools.remember import (
    ClassificationResult,
    classify,
    link,
    FIREWALL_PROTECTED_LAYERS,
)


# ─── 헬퍼 ─────────────────────────────────────────────────────────────

def _make_cls(type="Observation", layer=0, tier=2, metadata=None, original_type=None):
    return ClassificationResult(
        type=type,
        layer=layer,
        tier=tier,
        metadata=metadata or {},
        original_type=original_type or type,
    )


# ─── classify() 테스트 (DB 없음 — validate_node_type mock) ──────────

class TestClassify:
    @patch("tools.remember.validate_node_type", return_value=(True, None))
    def test_classify_no_db(self, _mock):
        """classify()가 DB 없이 동작하는지 + Principle layer/tier 확인."""
        cls = classify("시스템 설계 원칙", type="Principle")
        assert cls.type == "Principle"
        assert cls.layer == 3       # PROMOTE_LAYER["Principle"] = 3
        assert cls.tier == 0        # layer >= 3 → core
        assert cls.original_type == "Principle"
        assert cls.metadata.get("embedding_provisional") == "true"

    @patch("tools.remember.validate_node_type", return_value=(False, None))
    @patch("tools.remember.suggest_closest_type", return_value="Pattern")
    def test_classify_type_correction_deprecated(self, _mock_suggest, _mock_valid):
        """잘못된 타입 → suggest_closest_type 결과로 교정."""
        cls = classify("경험 법칙", type="Heuristic")
        assert cls.type == "Pattern"          # suggest 결과
        assert cls.original_type == "Heuristic"

    @patch("tools.remember.validate_node_type", return_value=(True, "Pattern"))
    def test_classify_case_correction(self, _mock):
        """소문자 → canonical 대소문자 교정."""
        cls = classify("패턴 발견", type="pattern")
        assert cls.type == "Pattern"
        assert cls.original_type == "pattern"

    @patch("tools.remember.validate_node_type", return_value=(True, None))
    def test_classify_principle_layer3(self, _mock):
        """v3: Principle → layer=3."""
        cls = classify("핵심 원칙", type="Principle")
        assert cls.layer == 3

    @patch("tools.remember.validate_node_type", return_value=(True, None))
    def test_classify_observation_tier2(self, _mock):
        """Observation → layer=0, tier=2 (auto)."""
        cls = classify("관찰 내용", type="Observation")
        assert cls.layer == 0
        assert cls.tier == 2

    @patch("tools.remember.validate_node_type", return_value=(True, None))
    def test_classify_unknown_type_no_layer(self, _mock):
        """PROMOTE_LAYER에 layer 미배정 타입(Unclassified) → layer=None, tier=2."""
        cls = classify("임의 내용", type="Unclassified")
        assert cls.layer is None
        assert cls.tier == 2


# ─── link() F3 방화벽 테스트 ─────────────────────────────────────────

class TestLinkFirewall:
    def test_f3a_l4_no_auto_edges(self):
        """F3-a: layer=4 노드는 자동 edge 0개."""
        edges = link(node_id=9999, content="핵심 가치", type="Value", layer=4)
        assert edges == []

    def test_f3a_l5_no_auto_edges(self):
        """F3-a: layer=5 노드는 자동 edge 0개."""
        edges = link(node_id=9999, content="근본 공리", type="Axiom", layer=5)
        assert edges == []

    def test_f3_protected_layers_constant(self):
        """FIREWALL_PROTECTED_LAYERS = {4, 5}."""
        assert FIREWALL_PROTECTED_LAYERS == {4, 5}

    @patch("tools.remember.vector_store")
    def test_f3b_skips_l4_similar_node(self, mock_vstore):
        """F3-b: 유사 노드가 L4이면 해당 edge만 스킵."""
        # vector_store.search → L4 노드(id=100) + L0 노드(id=200) 반환
        mock_vstore.search.return_value = [
            (100, 0.1, {}),   # distance < threshold → 후보
            (200, 0.1, {}),   # distance < threshold → 후보
        ]
        with patch("tools.remember.sqlite_store") as mock_store:
            mock_store.get_node.side_effect = lambda nid: {
                100: {"layer": 4, "type": "Value", "project": ""},
                200: {"layer": 0, "type": "Observation", "project": ""},
            }.get(nid)
            mock_store.insert_edge.return_value = 1

            edges = link(node_id=9999, content="테스트", type="Observation", layer=0)

        # id=100(L4)은 스킵, id=200만 edge 생성
        assert len(edges) == 1
        assert edges[0]["target_id"] == 200

    @patch("tools.remember.vector_store")
    def test_link_vector_failure_returns_empty(self, mock_vstore):
        """vector_store.search 예외 시 빈 리스트 반환."""
        mock_vstore.search.side_effect = Exception("ChromaDB down")
        edges = link(node_id=9999, content="테스트", type="Observation", layer=0)
        assert edges == []


# ─── remember() 통합 테스트 (mock) ───────────────────────────────────

class TestRemember:
    @patch("tools.remember.validate_node_type", return_value=(True, None))
    @patch("tools.remember.action_log")
    @patch("tools.remember.vector_store")
    @patch("tools.remember.sqlite_store")
    def test_basic_return_format(self, mock_sqls, mock_vs, mock_alog, _mock_valid):
        """반환 형태: node_id, type, project, auto_edges, message 필수."""
        mock_sqls.get_node_by_hash.return_value = None
        mock_sqls.insert_node.return_value = 42
        mock_vs.add.return_value = None
        mock_vs.search.return_value = []

        from tools.remember import remember
        result = remember("테스트 기억", type="Observation", project="mcp-memory")

        required = {"node_id", "type", "project", "auto_edges", "message"}
        assert required.issubset(set(result.keys()))
        assert result["node_id"] == 42
        assert result["type"] == "Observation"
        assert result["project"] == "mcp-memory"
        assert isinstance(result["auto_edges"], list)

    @patch("tools.remember.validate_node_type", return_value=(False, None))
    @patch("tools.remember.suggest_closest_type", return_value="Insight")
    @patch("tools.remember.action_log")
    @patch("tools.remember.vector_store")
    @patch("tools.remember.sqlite_store")
    def test_invalid_type_correction(self, mock_sqls, mock_vs, mock_alog, _s, _v):
        """잘못된 타입 → 교정된 타입으로 저장."""
        mock_sqls.get_node_by_hash.return_value = None
        mock_sqls.insert_node.return_value = 43
        mock_vs.add.return_value = None
        mock_vs.search.return_value = []

        from tools.remember import remember
        result = remember("테스트", type="NonExistentType")
        assert result["type"] == "Insight"   # suggest 결과

    @patch("tools.remember.validate_node_type", return_value=(True, None))
    @patch("tools.remember.action_log")
    @patch("tools.remember.vector_store")
    @patch("tools.remember.sqlite_store")
    def test_chromadb_failure_graceful(self, mock_sqls, mock_vs, mock_alog, _v):
        """ChromaDB 실패 시 SQLite 노드 생성 + warning + auto_edges=[]."""
        mock_sqls.get_node_by_hash.return_value = None
        mock_sqls.insert_node.return_value = 44
        mock_vs.add.side_effect = Exception("ChromaDB down")

        from tools.remember import remember
        result = remember("테스트", type="Observation")
        assert result["node_id"] == 44
        assert "warning" in result
        assert result["auto_edges"] == []

    @patch("tools.remember.validate_node_type", return_value=(True, None))
    @patch("tools.remember.action_log")
    @patch("tools.remember.vector_store")
    @patch("tools.remember.sqlite_store")
    def test_action_log_node_created(self, mock_sqls, mock_vs, mock_alog, _v):
        """store() 호출 시 action_log.record('node_created') 호출 확인."""
        mock_sqls.get_node_by_hash.return_value = None
        mock_sqls.insert_node.return_value = 45
        mock_vs.add.return_value = None
        mock_vs.search.return_value = []

        from tools.remember import remember
        remember("action_log 테스트", type="Observation")

        calls = [c.kwargs.get("action_type") or c.args[0]
                 for c in mock_alog.record.call_args_list]
        assert "node_created" in calls

    @patch("tools.remember.validate_node_type", return_value=(True, None))
    @patch("tools.remember.action_log")
    @patch("tools.remember.vector_store")
    @patch("tools.remember.sqlite_store")
    def test_action_log_edge_auto(self, mock_sqls, mock_vs, mock_alog, _v):
        """자동 edge 생성 시 action_log.record('edge_auto') 호출 확인."""
        mock_sqls.get_node_by_hash.return_value = None
        mock_sqls.insert_node.return_value = 46
        mock_sqls.get_node.return_value = {"layer": 1, "type": "Signal", "project": ""}
        mock_sqls.insert_edge.return_value = 10
        mock_vs.add.return_value = None
        mock_vs.search.return_value = [(99, 0.1, {})]   # 유사 노드 1개

        from tools.remember import remember
        remember("edge_auto 테스트", type="Observation")

        calls = [c.kwargs.get("action_type") or c.args[0]
                 for c in mock_alog.record.call_args_list]
        assert "edge_auto" in calls

    @patch("tools.remember.validate_node_type", return_value=(True, None))
    @patch("tools.remember.action_log")
    @patch("tools.remember.vector_store")
    @patch("tools.remember.sqlite_store")
    def test_store_independent(self, mock_sqls, mock_vs, mock_alog, _v):
        """store()가 ClassificationResult만으로 동작하는지."""
        mock_sqls.insert_node.return_value = 47
        mock_vs.add.return_value = None

        from tools.remember import store
        cls = _make_cls(type="Pattern", layer=2, tier=2)
        result = store("패턴 인식", cls, project="mcp-memory")
        assert "node_id" in result
        assert result["node_id"] == 47

    def test_link_returns_list(self):
        """link()가 항상 list를 반환하는지."""
        with patch("tools.remember.vector_store") as mock_vs:
            mock_vs.search.return_value = []
            from tools.remember import link
            edges = link(node_id=9999, content="테스트", type="Observation", layer=0)
        assert isinstance(edges, list)
