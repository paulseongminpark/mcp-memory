"""get_becoming() — Becoming 중인 노드들 (Signal, Pattern) 현황."""

import json

from config import VALID_PROMOTIONS
from storage import sqlite_store
from utils.growth import compute_growth_score


def get_becoming(
    domain: str = "",
    top_k: int = 10,
) -> dict:
    """성장 중인 노드들의 현황을 growth_score 순으로 반환한다.

    Signal, Pattern, Observation 등 승격 가능 타입만 조회.
    growth_score = quality(30%) + edges(20%) + visits(20%) + diversity(20%) + recency(10%)
    """
    promotable_types = list(VALID_PROMOTIONS.keys())
    placeholders = ",".join("?" * len(promotable_types))

    sql = f"""SELECT * FROM nodes
              WHERE type IN ({placeholders})
              AND status = 'active'
              ORDER BY quality_score DESC NULLS LAST"""
    with sqlite_store._db() as conn:
        rows = conn.execute(sql, promotable_types).fetchall()

    nodes = [dict(r) for r in rows]

    # 도메인 필터 (JSON 파싱 후 정확 매칭)
    if domain:
        filtered = []
        for n in nodes:
            try:
                doms = json.loads(n.get("domains") or "[]")
                if isinstance(doms, list) and domain in doms:
                    filtered.append(n)
            except (json.JSONDecodeError, TypeError):
                pass
        nodes = filtered

    becoming = []
    for node in nodes:
        edges = sqlite_store.get_edges(node["id"])
        active_edges = [e for e in edges if e.get("status") == "active"]
        edge_count = len(active_edges)

        # cross-project diversity
        neighbor_projects = set()
        for e in active_edges:
            nid = e["target_id"] if e["source_id"] == node["id"] else e["source_id"]
            n = sqlite_store.get_node(nid)
            if n and n.get("project"):
                neighbor_projects.add(n["project"])

        has_contradiction = any(
            e.get("relation") == "contradicts" for e in active_edges
        )

        score = compute_growth_score(
            quality_score=node.get("quality_score"),
            active_edge_count=edge_count,
            visit_count=node.get("visit_count"),
            neighbor_project_count=len(neighbor_projects),
            created_at=node.get("created_at", ""),
            has_contradiction=has_contradiction,
        )

        targets = VALID_PROMOTIONS.get(node["type"], [])

        try:
            domains = json.loads(node.get("domains") or "[]")
        except (json.JSONDecodeError, TypeError):
            domains = []

        becoming.append({
            "id": node["id"],
            "type": node["type"],
            "layer": node.get("layer"),
            "summary": node.get("summary") or node["content"][:100],
            "quality_score": node.get("quality_score"),
            "edge_count": edge_count,
            "visit_count": node.get("visit_count") or 0,
            "diversity": round(min(1.0, len(neighbor_projects) / 3), 2),
            "growth_score": round(score, 2),
            "can_promote_to": targets,
            "domains": domains if isinstance(domains, list) else [],
            "tags": node.get("tags", ""),
        })

    becoming.sort(key=lambda b: b["growth_score"], reverse=True)

    ready = sum(1 for b in becoming if b["growth_score"] > 0.6)
    return {
        "nodes": becoming[:top_k],
        "total_becoming": len(becoming),
        "ready_count": ready,
        "message": f"{len(becoming)} node(s) in becoming state, {ready} ready for review.",
    }
