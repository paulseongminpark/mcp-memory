"""3-way hybrid search: Vector + FTS5 + Graph traversal with RRF."""

from collections import defaultdict
from datetime import datetime, timezone

from config import (
    DEFAULT_TOP_K, RRF_K, GRAPH_BONUS,
    ENRICHMENT_QUALITY_WEIGHT, ENRICHMENT_TEMPORAL_WEIGHT,
)
from storage import sqlite_store, vector_store
from graph.traversal import build_graph, traverse


def _hebbian_update(result_ids: list[int], all_edges: list[dict]):
    """헤비안 학습: recall 결과에 관여한 edge의 frequency +1, last_activated 갱신.

    05-blueprint Part 6, Part 9 핵심 메커니즘.
    """
    if not result_ids:
        return
    id_set = set(result_ids)
    now = datetime.now(timezone.utc).isoformat()
    activated = []
    for edge in all_edges:
        src = edge.get("source_id")
        tgt = edge.get("target_id")
        if src in id_set and tgt in id_set:
            activated.append(edge.get("id"))
    if activated:
        conn = None
        try:
            conn = sqlite_store._connect()
            for eid in activated:
                conn.execute(
                    "UPDATE edges SET frequency = COALESCE(frequency, 0) + 1, "
                    "last_activated = ? WHERE id = ?",
                    (now, eid),
                )
            conn.commit()
        except Exception:
            pass  # 헤비안 실패가 검색을 중단시키지 않음
        finally:
            if conn:
                conn.close()


def hybrid_search(
    query: str,
    type_filter: str = "",
    project: str = "",
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:
    # 1. 벡터 유사도 검색 (ChromaDB 실패 시 graceful fallback)
    where = {}
    if type_filter:
        where["type"] = type_filter
    if project:
        where["project"] = project
    try:
        vec_results = vector_store.search(query, top_k=top_k * 2, where=where if where else None)
    except Exception:
        vec_results = []

    # 2. FTS5 키워드 검색
    fts_results = sqlite_store.search_fts(query, top_k=top_k * 2)

    # 3. 그래프 탐색 — 벡터/FTS 상위 결과의 이웃
    seed_ids = []
    for node_id, _, _ in vec_results[:3]:
        seed_ids.append(node_id)
    for node_id, _, _ in fts_results[:3]:
        seed_ids.append(node_id)

    all_edges = sqlite_store.get_all_edges()
    graph = build_graph(all_edges)
    graph_neighbors = traverse(graph, seed_ids, depth=2) if seed_ids else set()

    # 4. Reciprocal Rank Fusion
    scores: dict[int, float] = defaultdict(float)

    for rank, (node_id, distance, _) in enumerate(vec_results, 1):
        scores[node_id] += 1.0 / (RRF_K + rank)

    for rank, (node_id, _, _) in enumerate(fts_results, 1):
        scores[node_id] += 1.0 / (RRF_K + rank)

    for node_id in graph_neighbors:
        scores[node_id] += GRAPH_BONUS

    # 5. 타입/프로젝트 필터 적용 + enrichment 가중치 + 노드 정보 조회
    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    candidates = []
    for node_id in sorted_ids[:top_k * 2]:
        node = sqlite_store.get_node(node_id)
        if not node:
            continue
        if type_filter and node["type"] != type_filter:
            continue
        if project and node["project"] != project:
            continue
        # enrichment 가중치 (S5 해결)
        qs = node.get("quality_score") or 0.0
        tr = node.get("temporal_relevance") or 0.0
        enrichment_bonus = qs * ENRICHMENT_QUALITY_WEIGHT + tr * ENRICHMENT_TEMPORAL_WEIGHT
        node["score"] = scores[node_id] + enrichment_bonus
        candidates.append(node)

    # enrichment 반영 후 재정렬
    candidates.sort(key=lambda n: n["score"], reverse=True)
    result = candidates[:top_k]

    # 6. 헤비안 학습: 결과에 관여한 edge 강화 (05-blueprint Part 6)
    _hebbian_update([n["id"] for n in result], all_edges)

    return result
