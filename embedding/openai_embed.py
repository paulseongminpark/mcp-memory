"""OpenAI text-embedding-3-large wrapper."""

from openai import OpenAI

from config import OPENAI_API_KEY, EMBEDDING_MODEL

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY, timeout=30, max_retries=3)
    return _client


def embed_text(text: str) -> list[float]:
    try:
        resp = _get_client().embeddings.create(input=[text], model=EMBEDDING_MODEL)
        return resp.data[0].embedding
    except Exception as e:
        raise RuntimeError(f"Embedding failed: {type(e).__name__}: {e}") from e


def embed_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    try:
        resp = _get_client().embeddings.create(input=texts, model=EMBEDDING_MODEL)
        return [d.embedding for d in resp.data]
    except Exception as e:
        raise RuntimeError(f"Batch embedding failed: {type(e).__name__}: {e}") from e
