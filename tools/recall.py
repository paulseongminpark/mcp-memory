"""recall() — 3중 하이브리드 검색으로 기억을 검색한다."""

from storage.hybrid import hybrid_search
from storage import sqlite_store
from config import DEFAULT_TOP_K, PATCH_SATURATION_THRESHOLD


def _is_patch_saturated(results: list[dict]) -> bool:
    """B-4: 결과의 75% 이상이 동일 project이면 패치 포화 판정."""
    if len(results) < 3:
        return False
    projects = [r.get("project", "") for r in results]
    dominant = max(set(projects), key=projects.count)
    return projects.count(dominant) / len(projects) >= PATCH_SATURATION_THRESHOLD


def _get_dominant_project(results: list[dict]) -> str:
    projects = [r.get("project", "") for r in results]
    return max(set(projects), key=projects.count)


def recall(
    query: str,
    type_filter: str = "",
    project: str = "",
    top_k: int = DEFAULT_TOP_K,
    mode: str = "auto",  # B-12: UCB 탐색 모드 ("focus"|"dmn"|"auto")
) -> dict:
    results = hybrid_search(
        query, type_filter=type_filter, project=project, top_k=top_k, mode=mode
    )

    # B-4: 패치 전환 (Marginal Value Theorem) — project 미지정 시에만 동작
    if not project and _is_patch_saturated(results):
        dominant = _get_dominant_project(results)
        alt = hybrid_search(
            query, type_filter=type_filter, top_k=top_k,
            excluded_project=dominant, mode=mode
        )
        results = results[: top_k // 2] + alt[: top_k - top_k // 2]
        results.sort(key=lambda r: r["score"], reverse=True)

    if not results:
        return {"results": [], "message": "No memories found."}

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
