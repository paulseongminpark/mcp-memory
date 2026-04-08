"""storage/reranker.py — sentence-transformers cross-encoder reranker.

ms-marco-MiniLM-L-6-v2 (22MB) 사용. 빠르고 Windows 호환.
조건부 실행: RRF 상위 점수 차이가 작을 때만 rerank.
"""

import logging

logger = logging.getLogger(__name__)

# lazy-loaded singleton
_model = None
_load_attempted = False

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _load_model():
    """CrossEncoder 모델을 lazy-load한다."""
    global _model, _load_attempted
    _load_attempted = True

    try:
        from sentence_transformers import CrossEncoder
        _model = CrossEncoder(MODEL_NAME)
        logger.info(f"Reranker loaded: {MODEL_NAME}")
    except ImportError:
        logger.warning("sentence-transformers not installed. Reranker disabled.")
    except Exception as e:
        logger.warning(f"Reranker load failed: {e}")


def rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    """cross-encoder로 후보를 re-score한다.

    Args:
        query: 검색 쿼리
        candidates: hybrid_search에서 나온 후보 리스트 (각각 'score', 'content' 키 포함)
        top_k: 최종 반환 개수

    Returns:
        rerank된 후보 리스트 (top_k개)
    """
    global _model, _load_attempted

    if not _load_attempted:
        _load_model()

    if _model is None:
        return candidates[:top_k]

    # cross-encoder 입력 쌍 구성
    pairs = [
        (query, (c.get("content", "") or "")[:300])
        for c in candidates
    ]

    try:
        ce_scores = _model.predict(pairs).tolist()
    except Exception:
        return candidates[:top_k]

    # normalize ce_scores to [0, 1]
    min_s, max_s = min(ce_scores), max(ce_scores)
    span = max_s - min_s if max_s > min_s else 1.0
    ce_norm = [(s - min_s) / span for s in ce_scores]

    # blend: RRF score * (1 - weight) + CE score * weight
    from config import RERANKER_WEIGHT
    for c, ce in zip(candidates, ce_norm):
        c["score"] = c["score"] * (1 - RERANKER_WEIGHT) + ce * RERANKER_WEIGHT

    candidates.sort(key=lambda n: n["score"], reverse=True)
    return candidates[:top_k]


def should_rerank(candidates: list[dict], threshold: float) -> bool:
    """상위 결과 간 점수 차이가 작으면 True (rerank 필요)."""
    if len(candidates) < 2:
        return False
    gap = candidates[0]["score"] - candidates[1]["score"]
    return gap < threshold
