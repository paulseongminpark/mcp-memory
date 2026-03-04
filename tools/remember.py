"""remember() — 기억을 저장하고 자동으로 관계를 생성한다."""

from config import SIMILARITY_THRESHOLD, PROMOTE_LAYER, infer_relation
from ontology.validators import validate_node_type, suggest_closest_type
from storage import sqlite_store, vector_store


def remember(
    content: str,
    type: str = "Unclassified",
    tags: str = "",
    project: str = "",
    metadata: dict | None = None,
    confidence: float = 1.0,
    source: str = "claude",
) -> dict:
    # 0. 온톨로지 타입 검증
    valid, correction = validate_node_type(type)
    if not valid:
        suggested = suggest_closest_type(content)
        type = suggested  # fallback to heuristic or Unclassified
    elif correction:
        type = correction  # 대소문자 교정

    # 0.5 provisional embedding 플래그 (S5 해결)
    metadata = dict(metadata) if metadata else {}
    metadata["embedding_provisional"] = "true"

    # 0.6 자동 tier/layer 배정
    layer = PROMOTE_LAYER.get(type)
    if layer is not None and layer >= 3:
        tier = 0  # core
    elif layer == 2:
        tier = 2  # auto (quality_score 없으니 enrichment 후 승격)
    else:
        tier = 2  # auto

    # 1. SQLite에 노드 저장
    node_id = sqlite_store.insert_node(
        type=type,
        content=content,
        metadata=metadata,
        project=project,
        tags=tags,
        confidence=confidence,
        source=source,
        layer=layer,
        tier=tier,
    )

    # 2. ChromaDB에 임베딩 저장 (provisional)
    vec_meta = {"type": type, "project": project, "tags": tags, "embedding_provisional": "true"}
    try:
        vector_store.add(node_id, content, vec_meta)
    except Exception as e:
        # ChromaDB 실패 시 SQLite 노드는 유지하되 경고 포함
        return {
            "node_id": node_id,
            "type": type,
            "project": project,
            "auto_edges": [],
            "warning": f"Stored in SQLite but embedding failed: {e}",
            "message": f"Stored as node #{node_id} (embedding failed)",
        }

    # 3. 유사 노드 검색 → 자동 edge 생성
    auto_edges = []
    try:
        similar = vector_store.search(content, top_k=5)
    except Exception:
        similar = []
    for sim_id, distance, _ in similar:
        if sim_id == node_id:
            continue
        if distance > SIMILARITY_THRESHOLD:
            continue
        sim_node = sqlite_store.get_node(sim_id)
        if not sim_node:
            continue
        # 규칙 기반 relation 추론 (α)
        relation = infer_relation(
            src_type=type,
            src_layer=layer,
            tgt_type=sim_node.get("type", ""),
            tgt_layer=sim_node.get("layer"),
            src_project=project,
            tgt_project=sim_node.get("project", ""),
        )
        strength = max(0.0, 1.0 - distance)
        edge_id = sqlite_store.insert_edge(
            source_id=node_id,
            target_id=sim_id,
            relation=relation,
            description=f"auto: similarity={1.0 - distance:.2f}",
            strength=strength,
        )
        auto_edges.append({"edge_id": edge_id, "target_id": sim_id, "relation": relation, "strength": round(strength, 2)})

    return {
        "node_id": node_id,
        "type": type,
        "project": project,
        "auto_edges": auto_edges,
        "message": f"Stored as node #{node_id} with {len(auto_edges)} auto-edge(s)",
    }
