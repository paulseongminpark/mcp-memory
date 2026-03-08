"""Type boost 키워드 감지 테스트."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_type_keywords_import():
    from config import TYPE_KEYWORDS, TYPE_BOOST
    assert isinstance(TYPE_KEYWORDS, dict)
    assert TYPE_BOOST > 0


def test_detect_workflow():
    from storage.hybrid import _detect_type_hints
    hints = _detect_type_hints("워크플로우 자동화 절차")
    assert "Workflow" in hints


def test_detect_failure():
    from storage.hybrid import _detect_type_hints
    hints = _detect_type_hints("E14 배치 실패 원인")
    assert "Failure" in hints


def test_no_false_positive():
    from storage.hybrid import _detect_type_hints
    hints = _detect_type_hints("컨텍스트를 통화로 보는 원칙")
    assert "Workflow" not in hints
    assert "Failure" not in hints


def test_multiple_types():
    from storage.hybrid import _detect_type_hints
    hints = _detect_type_hints("에이전트 팀 구조 설계 프레임워크")
    assert "Agent" in hints
    assert "Framework" in hints
