"""Type diversity re-ranking 테스트."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from storage.hybrid import _apply_type_diversity


def test_diversity_breaks_monopoly():
    candidates = [
        {"id": i, "type": "Principle", "score": 1.0 - i * 0.01}
        for i in range(8)
    ] + [
        {"id": 100, "type": "Workflow", "score": 0.5},
        {"id": 101, "type": "Failure", "score": 0.4},
    ]
    result = _apply_type_diversity(candidates, top_k=5)
    types = [r["type"] for r in result]
    assert types.count("Principle") <= 3  # 60% of 5


def test_diversity_preserves_good_results():
    candidates = [
        {"id": 1, "type": "Principle", "score": 1.0},
        {"id": 2, "type": "Workflow", "score": 0.9},
        {"id": 3, "type": "Failure", "score": 0.8},
        {"id": 4, "type": "Pattern", "score": 0.7},
        {"id": 5, "type": "Tool", "score": 0.6},
    ]
    result = _apply_type_diversity(candidates, top_k=5)
    assert len(result) == 5
    assert result[0]["id"] == 1


def test_diversity_no_change_when_diverse():
    candidates = [
        {"id": i, "type": f"Type{i}", "score": 1.0 - i * 0.1}
        for i in range(10)
    ]
    result = _apply_type_diversity(candidates, top_k=5)
    assert [r["id"] for r in result] == [0, 1, 2, 3, 4]
