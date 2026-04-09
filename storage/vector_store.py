"""ChromaDB vector storage wrapper."""

import chromadb

from config import CHROMA_PATH, EMBEDDING_DIM
from embedding import embed_text


_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None

COLLECTION_NAME = "memories"


def _get_collection() -> chromadb.Collection:
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add(node_id: int, content: str, metadata: dict | None = None) -> None:
    coll = _get_collection()
    vector = embed_text(content)
    meta = metadata or {}
    meta = {k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))}
    coll.upsert(
        ids=[str(node_id)],
        embeddings=[vector],
        documents=[content],
        metadatas=[meta],
    )


def search(query: str, top_k: int = 5, where: dict | None = None) -> list[tuple[int, float, dict]]:
    coll = _get_collection()
    vector = embed_text(query)
    kwargs = {
        "query_embeddings": [vector],
        "n_results": min(top_k, coll.count()) if coll.count() > 0 else top_k,
    }
    if where:
        kwargs["where"] = where
    if coll.count() == 0:
        return []
    results = coll.query(**kwargs)
    output = []
    for i, id_str in enumerate(results["ids"][0]):
        distance = results["distances"][0][i] if results["distances"] else 0.0
        meta = results["metadatas"][0][i] if results["metadatas"] else {}
        output.append((int(id_str), distance, meta))
    return output


def get_node_embedding(node_id: int) -> list[float] | None:
    """ChromaDB에서 node_id의 현재 임베딩 벡터 반환.

    노드가 없거나 임베딩이 없으면 None.
    """
    try:
        coll = _get_collection()
        result = coll.get(
            ids=[str(node_id)],
            include=["embeddings"],
        )
        embeddings = result.get("embeddings")
        if embeddings and len(embeddings) > 0 and embeddings[0]:
            return list(embeddings[0])
    except Exception:
        pass
    return None
