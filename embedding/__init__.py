"""Embedding module — automatic provider selection.

EMBEDDING_PROVIDER=local  -> sentence-transformers (no API, 1024 dim)
EMBEDDING_PROVIDER=openai -> OpenAI API (3072 dim)
"""

from config import EMBEDDING_PROVIDER

if EMBEDDING_PROVIDER == "local":
    from embedding.local_embed import embed_text, embed_batch
else:
    from embedding.openai_embed import embed_text, embed_batch

__all__ = ["embed_text", "embed_batch"]
