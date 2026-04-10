"""Local embedding using sentence-transformers (multilingual-e5-large).

Zero external API dependency. 1024 dimensions, excellent Korean support.
Drop-in replacement for openai_embed.py with identical interface.
"""

from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None
MODEL_NAME = "intfloat/multilingual-e5-large"

# P3: 동일 쿼리 반복 임베딩 방지
_embed_cache: dict[str, list[float]] = {}
_CACHE_MAX = 32


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_text(text: str) -> list[float]:
    """Embed a single text. Returns 1024-dim vector."""
    cached = _embed_cache.get(text)
    if cached is not None:
        return cached
    model = _get_model()
    vec = model.encode([f"query: {text}"], normalize_embeddings=True)
    result = vec[0].tolist()
    if len(_embed_cache) >= _CACHE_MAX:
        _embed_cache.clear()
    _embed_cache[text] = result
    return result


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts. Returns list of 1024-dim vectors."""
    if not texts:
        return []
    model = _get_model()
    prefixed = [f"query: {t}" for t in texts]
    vecs = model.encode(prefixed, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vecs]
