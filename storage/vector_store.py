"""Numpy-based vector storage in SQLite. ChromaDB replacement (1-Store).

All embeddings stored as BLOB in nodes.embedding column.
In-memory numpy cache for fast cosine similarity search.
"""

import logging
import struct
import threading

import numpy as np

from config import DB_PATH, EMBEDDING_DIM
from embedding import embed_text

logger = logging.getLogger(__name__)

# ─── In-memory cache ─────────────────────────────────────────────
# _cache_ids[i] corresponds to _cache_matrix[i]
_cache_ids: list[int] = []
_cache_matrix: np.ndarray | None = None  # shape (N, EMBEDDING_DIM), float32
_cache_lock = threading.Lock()
_cache_loaded = False


def _blob_to_vector(blob: bytes) -> np.ndarray:
    """BLOB (little-endian float32 array) -> numpy 1-D array."""
    return np.frombuffer(blob, dtype=np.float32).copy()


def _vector_to_blob(vec: list[float] | np.ndarray) -> bytes:
    """numpy array or list -> BLOB bytes."""
    return np.asarray(vec, dtype=np.float32).tobytes()


def _load_cache() -> None:
    """Load all active node embeddings into memory. Called once at first use."""
    global _cache_ids, _cache_matrix, _cache_loaded
    import sqlite3

    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT id, embedding FROM nodes WHERE status='active' AND embedding IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        _cache_ids = []
        _cache_matrix = np.empty((0, EMBEDDING_DIM), dtype=np.float32)
        _cache_loaded = True
        logger.info("Vector cache loaded: 0 vectors")
        return

    ids = []
    vecs = []
    for row_id, blob in rows:
        try:
            vec = _blob_to_vector(blob)
            if vec.shape[0] == EMBEDDING_DIM:
                ids.append(row_id)
                vecs.append(vec)
        except Exception:
            continue

    _cache_ids = ids
    _cache_matrix = np.vstack(vecs).astype(np.float32) if vecs else np.empty((0, EMBEDDING_DIM), dtype=np.float32)
    _cache_loaded = True
    logger.info("Vector cache loaded: %d vectors", len(_cache_ids))


def _ensure_cache() -> None:
    """Ensure cache is loaded (thread-safe, one-time init)."""
    global _cache_loaded
    if not _cache_loaded:
        with _cache_lock:
            if not _cache_loaded:
                _load_cache()


# ─── Public API (same interface as old ChromaDB vector_store) ────


def add(node_id: int, content: str, metadata: dict | None = None) -> None:
    """Embed content and store vector in SQLite + update cache."""
    import sqlite3

    vector = embed_text(content)
    blob = _vector_to_blob(vector)

    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("UPDATE nodes SET embedding = ? WHERE id = ?", (blob, node_id))
        conn.commit()
    finally:
        conn.close()

    # Update cache
    _ensure_cache()
    vec_np = np.asarray(vector, dtype=np.float32)
    with _cache_lock:
        global _cache_ids, _cache_matrix
        if node_id in _cache_ids:
            idx = _cache_ids.index(node_id)
            _cache_matrix[idx] = vec_np
        else:
            _cache_ids.append(node_id)
            if _cache_matrix is not None and _cache_matrix.shape[0] > 0:
                _cache_matrix = np.vstack([_cache_matrix, vec_np.reshape(1, -1)])
            else:
                _cache_matrix = vec_np.reshape(1, -1)


def search(query: str, top_k: int = 5, where: dict | None = None) -> list[tuple[int, float, dict]]:
    """Embed query and find top_k nearest neighbors by cosine distance.

    Returns list of (node_id, distance, metadata_dict).
    distance = 1 - cosine_similarity (0 = identical, 2 = opposite).
    Compatible with ChromaDB's cosine distance output.
    """
    _ensure_cache()

    if _cache_matrix is None or _cache_matrix.shape[0] == 0:
        return []

    query_vec = np.asarray(embed_text(query), dtype=np.float32)

    with _cache_lock:
        ids = list(_cache_ids)
        matrix = _cache_matrix.copy()

    # Apply where filter by fetching matching node_ids from SQLite
    if where:
        filtered_ids = _filter_by_where(where)
        if not filtered_ids:
            return []
        mask = np.array([nid in filtered_ids for nid in ids], dtype=bool)
        ids = [nid for nid, m in zip(ids, mask) if m]
        matrix = matrix[mask]
        if matrix.shape[0] == 0:
            return []

    # Cosine similarity: dot(q, M^T) / (|q| * |M|)
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return []
    matrix_norms = np.linalg.norm(matrix, axis=1)
    # Avoid division by zero
    valid = matrix_norms > 0
    similarities = np.zeros(matrix.shape[0], dtype=np.float32)
    if valid.any():
        similarities[valid] = (matrix[valid] @ query_vec) / (matrix_norms[valid] * query_norm)

    # Convert to cosine distance (1 - similarity) to match ChromaDB convention
    distances = 1.0 - similarities

    # Get top_k indices (smallest distance = most similar)
    k = min(top_k, len(ids))
    top_indices = np.argpartition(distances, k)[:k]
    top_indices = top_indices[np.argsort(distances[top_indices])]

    results = []
    for idx in top_indices:
        results.append((ids[idx], float(distances[idx]), {}))

    return results


def _filter_by_where(where: dict) -> set[int]:
    """Translate ChromaDB-style where filter to SQLite query."""
    import sqlite3

    conditions = []
    params = []
    for key, value in where.items():
        if key in ("type", "project", "tags"):
            conditions.append(f"{key} = ?")
            params.append(value)

    if not conditions:
        return set()  # unknown filter keys

    sql = f"SELECT id FROM nodes WHERE status='active' AND {' AND '.join(conditions)}"
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return {row[0] for row in rows}


def get_node_embedding(node_id: int) -> list[float] | None:
    """Get embedding vector for a node from SQLite."""
    import sqlite3

    conn = sqlite3.connect(str(DB_PATH))
    try:
        row = conn.execute(
            "SELECT embedding FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
    finally:
        conn.close()

    if row and row[0]:
        try:
            vec = _blob_to_vector(row[0])
            return list(vec)
        except Exception:
            pass
    return None


def remove_from_cache(node_id: int) -> None:
    """Remove a node from the in-memory cache (e.g., on archive)."""
    _ensure_cache()
    with _cache_lock:
        global _cache_ids, _cache_matrix
        if node_id in _cache_ids:
            idx = _cache_ids.index(node_id)
            _cache_ids.pop(idx)
            if _cache_matrix is not None and _cache_matrix.shape[0] > 0:
                _cache_matrix = np.delete(_cache_matrix, idx, axis=0)


def reload_cache() -> None:
    """Force reload the entire cache from SQLite. Use after bulk operations."""
    global _cache_loaded
    with _cache_lock:
        _cache_loaded = False
    _load_cache()


def cache_stats() -> dict:
    """Return cache statistics for diagnostics."""
    _ensure_cache()
    with _cache_lock:
        return {
            "cached_vectors": len(_cache_ids),
            "matrix_shape": list(_cache_matrix.shape) if _cache_matrix is not None else None,
            "memory_bytes": _cache_matrix.nbytes if _cache_matrix is not None else 0,
        }
