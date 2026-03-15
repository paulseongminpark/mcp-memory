"""Type-aware vector channel 테스트 — _detect_type_hints + config 상수."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_type_config_import():
    from config import TYPE_KEYWORDS, TYPE_CHANNEL_WEIGHT, MAX_TYPE_HINTS
    assert isinstance(TYPE_KEYWORDS, dict)
    assert TYPE_CHANNEL_WEIGHT > 0
    assert MAX_TYPE_HINTS >= 1


def test_detect_workflow_as_pattern():
    """v3: Workflow deprecated → Pattern으로 흡수."""
    from storage.hybrid import _detect_type_hints
    hints = _detect_type_hints("워크플로우 자동화 절차")
    assert "Pattern" in hints


def test_detect_failure():
    from storage.hybrid import _detect_type_hints
    hints = _detect_type_hints("E14 배치 실패 원인")
    assert "Failure" in hints


def test_no_false_positive():
    from storage.hybrid import _detect_type_hints
    hints = _detect_type_hints("컨텍스트를 통화로 보는 원칙")
    assert "Failure" not in hints


def test_multiple_types():
    """v3: Agent deprecated → Tool로 흡수. '에이전트'는 Tool 키워드."""
    from storage.hybrid import _detect_type_hints
    hints = _detect_type_hints("에이전트 팀 구조 설계 프레임워크")
    assert "Tool" in hints or "Framework" in hints


def test_max_type_hints_cap():
    from config import MAX_TYPE_HINTS
    from storage.hybrid import _detect_type_hints
    # 여러 키워드가 한 쿼리에 있어도 MAX_TYPE_HINTS 이하로 제한
    hints = _detect_type_hints("워크플로우 도구 에이전트 실패 실험 결정 진화 목표 패턴")
    assert len(hints) <= MAX_TYPE_HINTS


def test_returns_list():
    from storage.hybrid import _detect_type_hints
    hints = _detect_type_hints("워크플로우 자동화")
    assert isinstance(hints, list)
