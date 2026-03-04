"""recall() — 3중 하이브리드 검색으로 기억을 검색한다."""

from storage.hybrid import hybrid_search
from storage import sqlite_store
from graph.traversal import build_graph, get_relation_path
from config import DEFAULT_TOP_K


def recall(
    query: str,
    type_filter: str = "",
    project: str = "",
    top_k: int = DEFAULT_TOP_K,
) -> dict:
    results = hybrid_search(query, type_filter=type_filter, project=project, top_k=top_k)

    if not results:
        return {"results": [], "message": "No memories found."}

    # 관계 경로 추가
    all_edges = sqlite_store.get_all_edges()
    graph = build_graph(all_edges)
    result_ids = [r["id"] for r in results]

    formatted = []
    for r in results:
        content_preview = r["content"][:200]
        edges = sqlite_store.get_edges(r["id"])
        related = []
        for e in edges[:3]:
            other_id = e["target_id"] if e["source_id"] == r["id"] else e["source_id"]
            related.append(f"{e['relation']}→#{other_id}")

        formatted.append({
            "id": r["id"],
            "type": r["type"],
            "content": content_preview,
            "project": r["project"],
            "tags": r["tags"],
            "score": round(r["score"], 3),
            "created_at": r["created_at"],
            "related": related,
        })

    return {
        "results": formatted,
        "count": len(formatted),
        "message": f"Found {len(formatted)} memory(ies) for '{query}'",
    }
