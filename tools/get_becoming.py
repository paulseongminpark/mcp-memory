"""get_becoming() — Becoming 중인 노드들 (Signal, Pattern) 현황."""

import json

from config import VALID_PROMOTIONS
from storage import sqlite_store


def get_becoming(
    domain: str = "",
    top_k: int = 10,
) -> dict:
    """성장 중인 노드들의 현황을 성숙도 순으로 반환한다.

    Signal, Pattern, Observation 등 승격 가능 타입만 조회.
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

    # 각 노드의 성숙도 계산 — v3.3: 다차원 maturity
    becoming = []
    for node in nodes:
        edges = sqlite_store.get_edges(node["id"])
        # v3.3: active edge만 카운트
        active_edges = [e for e in edges if e.get("status") == "active"]
        qs = node.get("quality_score") or 0.5
        edge_count = len(active_edges)
        visit_count = node.get("visit_count") or 0

        # cross-project diversity: 이웃 프로젝트 다양성
        neighbor_projects = set()
        for e in active_edges:
            nid = e["target_id"] if e["source_id"] == node["id"] else e["source_id"]
            n = sqlite_store.get_node(nid)
            if n and n.get("project"):
                neighbor_projects.add(n["project"])
        diversity = min(1.0, len(neighbor_projects) / 3)  # 3+ projects = 1.0

        # contradiction check
        has_contradiction = any(
            e.get("relation") == "contradicts" for e in active_edges
        )
        contra_penalty = -0.2 if has_contradiction else 0.0

        # v3.3 maturity: quality 30% + edges 20% + visits 20% + diversity 20% + recency 10%
        edge_density = min(1.0, edge_count / 10)
        visit_norm = min(1.0, visit_count / 10)
        # recency: 최근 30일 내 생성이면 1.0, 90일+ 이면 0.0
        from datetime import datetime, timezone, timedelta
        created = node.get("created_at", "")
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            days_old = (datetime.now(timezone.utc) - created_dt).days
            recency = max(0.0, 1.0 - days_old / 90)
        except Exception:
            recency = 0.5

        maturity = (
            qs * 0.3
            + edge_density * 0.2
            + visit_norm * 0.2
            + diversity * 0.2
            + recency * 0.1
            + contra_penalty
        )
        maturity = max(0.0, min(1.0, maturity))

        targets = VALID_PROMOTIONS.get(node["type"], [])

        # 도메인 파싱
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
            "visit_count": visit_count,
            "diversity": round(diversity, 2),
            "maturity": round(maturity, 2),
            "can_promote_to": targets,
            "domains": domains if isinstance(domains, list) else [],
            "tags": node.get("tags", ""),
        })

    becoming.sort(key=lambda b: b["maturity"], reverse=True)

    ready = sum(1 for b in becoming if b["maturity"] > 0.6)
    return {
        "nodes": becoming[:top_k],
        "total_becoming": len(becoming),
        "ready_count": ready,
        "message": f"{len(becoming)} node(s) in becoming state, {ready} ready for review.",
    }
