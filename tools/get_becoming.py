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

    conn = sqlite_store._connect()
    sql = f"""SELECT * FROM nodes
              WHERE type IN ({placeholders})
              AND status = 'active'
              ORDER BY quality_score DESC NULLS LAST"""
    rows = conn.execute(sql, promotable_types).fetchall()
    conn.close()

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

    # 각 노드의 성숙도 계산
    becoming = []
    for node in nodes:
        edges = sqlite_store.get_edges(node["id"])
        qs = node.get("quality_score") or 0.5
        edge_count = len(edges)

        # 성숙도: quality 60% + edge 밀도 40%
        maturity = qs * 0.6 + min(1.0, edge_count / 10) * 0.4

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
