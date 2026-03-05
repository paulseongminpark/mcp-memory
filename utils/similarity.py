"""utils/similarity.py — 벡터 유사도 계산 유틸리티.

외부 의존성: numpy (optional — 없으면 순수 Python fallback)
설계: d-r3-12
"""
from __future__ import annotations

try:
    import numpy as np

    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """
        두 벡터의 코사인 유사도 [-1.0, 1.0].
        동일 벡터 → 1.0 / 직교 → 0.0 / 반대 → -1.0

        Args:
            vec_a, vec_b: 동일 차원의 float 리스트
        Returns:
            0.0 if either vector is zero or mismatched length
        """
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        a = np.array(vec_a, dtype=np.float64)
        b = np.array(vec_b, dtype=np.float64)
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / denom) if denom > 0 else 0.0

except ImportError:
    import math

    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:  # type: ignore[misc]
        """numpy 없을 때 순수 Python fallback."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(x * x for x in vec_a))
        norm_b = math.sqrt(sum(x * x for x in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)
