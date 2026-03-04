"""inspect() — 노드 상세 조회 (전체 메타, 연결, 승격 이력)."""

import json

from storage import sqlite_store


def _parse_json(val) -> list | dict:
    if not val:
        return []
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val


def inspect_node(node_id: int) -> dict:
    """노드의 전체 메타데이터, 연결, enrichment 상태, 승격 이력을 반환한다."""
    node = sqlite_store.get_node(node_id)
    if not node:
        return {"error": f"Node #{node_id} not found.", "message": "Node not found."}

    # edge 조회 + incoming/outgoing 분류
    edges = sqlite_store.get_edges(node_id)
    incoming = []
    outgoing = []
    for e in edges:
        info = {
            "edge_id": e["id"],
            "relation": e["relation"],
            "description": e.get("description", ""),
            "strength": e.get("strength", 1.0),
            "created_at": e.get("created_at", ""),
        }
        if e["source_id"] == node_id:
            other = sqlite_store.get_node(e["target_id"])
            info["target_id"] = e["target_id"]
            info["target_type"] = other["type"] if other else "?"
            info["target_summary"] = (
                (other.get("summary") or other.get("content", "")[:80]) if other else ""
            )
            outgoing.append(info)
        else:
            other = sqlite_store.get_node(e["source_id"])
            info["source_id"] = e["source_id"]
            info["source_type"] = other["type"] if other else "?"
            info["source_summary"] = (
                (other.get("summary") or other.get("content", "")[:80]) if other else ""
            )
            incoming.append(info)

    metadata = _parse_json(node.get("metadata"))
    enrichment_status = _parse_json(node.get("enrichment_status"))
    promotion_history = metadata.get("promotion_history", []) if isinstance(metadata, dict) else []

    return {
        "id": node["id"],
        "type": node["type"],
        "layer": node.get("layer"),
        "status": node.get("status"),
        "content": node["content"],
        "summary": node.get("summary"),
        "key_concepts": _parse_json(node.get("key_concepts")),
        "tags": node.get("tags"),
        "project": node.get("project"),
        "facets": _parse_json(node.get("facets")),
        "domains": _parse_json(node.get("domains")),
        "secondary_types": _parse_json(node.get("secondary_types")),
        "quality_score": node.get("quality_score"),
        "abstraction_level": node.get("abstraction_level"),
        "temporal_relevance": node.get("temporal_relevance"),
        "actionability": node.get("actionability"),
        "confidence": node.get("confidence"),
        "source": node.get("source"),
        "metadata": metadata,
        "enrichment_status": enrichment_status,
        "enriched_at": node.get("enriched_at"),
        "created_at": node.get("created_at"),
        "updated_at": node.get("updated_at"),
        "promotion_history": promotion_history,
        "outgoing_edges": outgoing,
        "incoming_edges": incoming,
        "edge_count": len(edges),
        "message": (
            f"Node #{node['id']} ({node['type']}, L{node.get('layer', '?')}): "
            f"{len(outgoing)} outgoing, {len(incoming)} incoming edge(s)."
        ),
    }
