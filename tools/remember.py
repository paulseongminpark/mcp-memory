"""remember() — 기억을 저장하고 자동으로 관계를 생성한다.

v2.0: classify/store/link 3함수 분리 (A-14)
    + 방화벽 F3: L4/L5 자동 edge 금지 (A-10)
    + action_log 기록 (A-17)
외부 API(MCP tool remember) 100% 하위호환.
"""

import hashlib
import json
from dataclasses import dataclass

from config import SIMILARITY_THRESHOLD, PROMOTE_LAYER, infer_relation
from ontology.validators import validate_node_type, suggest_closest_type
from storage import sqlite_store, vector_store
from storage import action_log


# ─── 분류 결과 ──────────────────────────────────────────────

@dataclass
class ClassificationResult:
    """classify()의 반환값. DB 접촉 없는 순수 데이터."""
    type: str
    layer: int | None
    tier: int
    metadata: dict
    original_type: str  # 교정 전 원본 타입 (action_log용)


# ─── 방화벽 규칙 ────────────────────────────────────────────

# A-10 F3: L4/L5 노드에 자동 edge 생성 금지 (하드코딩)
FIREWALL_PROTECTED_LAYERS = {4, 5}


# ─── classify() — 순수 분류, DB 접촉 없음 ───────────────────

def classify(
    content: str,
    type: str = "Unclassified",
    metadata: dict | None = None,
) -> ClassificationResult:
    """온톨로지 검증 + tier/layer 배정. DB 접촉 없음.

    Returns:
        ClassificationResult — 분류 결과 (type, layer, tier, metadata, original_type)
    """
    original_type = type

    # 온톨로지 타입 검증
    valid, correction = validate_node_type(type)
    if not valid:
        suggested = suggest_closest_type(content)
        type = suggested
    elif correction:
        type = correction  # 대소문자 교정

    # provisional embedding 플래그
    metadata = dict(metadata) if metadata else {}
    metadata["embedding_provisional"] = "true"

    # 자동 tier/layer 배정
    layer = PROMOTE_LAYER.get(type)
    if layer is not None and layer >= 3:
        tier = 0  # core
    elif layer == 2:
        tier = 2  # auto (enrichment 후 승격)
    else:
        tier = 2  # auto

    return ClassificationResult(
        type=type,
        layer=layer,
        tier=tier,
        metadata=metadata,
        original_type=original_type,
    )


# ─── store() — 순수 저장 ────────────────────────────────────

def store(
    content: str,
    cls: ClassificationResult,
    tags: str = "",
    project: str = "",
    confidence: float = 1.0,
    source: str = "claude",
    content_hash: str | None = None,
    retrieval_hints: dict | None = None,
) -> dict:
    """SQLite + ChromaDB에 노드 저장.

    Returns:
        {"node_id": int, "type": str, "project": str}
        content_hash 중복 시 "duplicate" 키 포함
        ChromaDB 실패 시 "warning" 키 포함
    """
    # SQLite
    node_id = sqlite_store.insert_node(
        type=cls.type,
        content=content,
        metadata=cls.metadata,
        project=project,
        tags=tags,
        confidence=confidence,
        source=source,
        layer=cls.layer,
        tier=cls.tier,
        content_hash=content_hash,
        retrieval_hints=retrieval_hints,
    )

    # content_hash UNIQUE 제약 위반 → duplicate (concurrent race 방어)
    if isinstance(node_id, tuple) and node_id[0] == "duplicate":
        return {"status": "duplicate", "node_id": node_id[1]}

    # action_log: node_created
    action_log.record(
        action_type="node_created",
        actor="claude",
        target_type="node",
        target_id=node_id,
        params=json.dumps({
            "original_type": cls.original_type,
            "resolved_type": cls.type,
            "layer": cls.layer,
            "tier": cls.tier,
            "project": project,
            "source": source,
        }),
    )

    # ChromaDB (provisional)
    vec_meta = {
        "type": cls.type,
        "project": project,
        "tags": tags,
        "embedding_provisional": "true",
    }
    try:
        vector_store.add(node_id, content, vec_meta)
    except Exception as e:
        return {
            "node_id": node_id,
            "type": cls.type,
            "project": project,
            "warning": f"Stored in SQLite but embedding failed: {e}",
        }

    return {
        "node_id": node_id,
        "type": cls.type,
        "project": project,
    }


# ─── link() — 자동 edge 생성 + 방화벽 F3 ────────────────────

def link(
    node_id: int,
    content: str,
    type: str,
    layer: int | None,
    project: str = "",
) -> list[dict]:
    """유사 노드 검색 → 자동 edge 생성.

    방화벽 F3: L4/L5 노드에 대한 자동 edge 생성을 차단한다.
    - 새 노드가 L4/L5면: 자동 edge 전부 차단 (수동 link만 허용)
    - 유사 노드가 L4/L5면: 해당 edge만 차단
    """
    # F3-a: 새 노드 자체가 L4/L5이면 자동 edge 전체 차단
    if layer is not None and layer in FIREWALL_PROTECTED_LAYERS:
        return []

    auto_edges = []
    try:
        similar = vector_store.search(content, top_k=5)
    except Exception:
        return auto_edges

    for sim_id, distance, _ in similar:
        if sim_id == node_id:
            continue
        if distance > SIMILARITY_THRESHOLD:
            continue

        sim_node = sqlite_store.get_node(sim_id)
        if not sim_node:
            continue

        # F3-b: 유사 노드가 L4/L5이면 해당 edge 차단
        sim_layer = sim_node.get("layer")
        if sim_layer is not None and sim_layer in FIREWALL_PROTECTED_LAYERS:
            continue

        # 규칙 기반 relation 추론
        relation = infer_relation(
            src_type=type,
            src_layer=layer,
            tgt_type=sim_node.get("type", ""),
            tgt_layer=sim_layer,
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
        auto_edges.append({
            "edge_id": edge_id,
            "target_id": sim_id,
            "relation": relation,
            "strength": round(strength, 2),
        })

        # action_log: edge_auto
        action_log.record(
            action_type="edge_auto",
            actor="claude",
            target_type="edge",
            target_id=edge_id,
            params=json.dumps({
                "source_id": node_id,
                "target_id": sim_id,
                "relation": relation,
                "strength": round(strength, 2),
            }),
        )

    return auto_edges


# ─── remember() — 최상위 API (하위호환 유지) ────────────────

def remember(
    content: str,
    type: str = "Unclassified",
    tags: str = "",
    project: str = "",
    metadata: dict | None = None,
    confidence: float = 1.0,
    source: str = "claude",
    retrieval_hints: dict | None = None,
    parent_id: int | None = None,
    parent_relation: str = "contains",
) -> dict:
    """기억을 저장하고 자동으로 관계를 생성한다.

    기존 MCP API 100% 호환. 내부적으로 classify → store → link 파이프라인.

    Args:
        content: 기억할 내용
        type: 온톨로지 타입 (default: Unclassified)
        tags: 태그 (쉼표 구분)
        project: 프로젝트명
        metadata: 추가 메타데이터
        confidence: 확신도 0.0-1.0
        source: 생성 주체
        parent_id: 부모 노드 ID — 지정 시 parent→child edge 자동 생성
        parent_relation: 부모-자식 관계 타입 (default: contains)

    Returns:
        {"node_id", "type", "project", "auto_edges", "message"}
    """
    # 0. content hash 중복 검사
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    existing = sqlite_store.get_node_by_hash(content_hash)
    if existing:
        return {"status": "duplicate", "node_id": existing["id"]}

    # 1. 분류
    cls = classify(content, type=type, metadata=metadata)

    # 2. 저장 (content_hash로 DB 레벨 dedup 보장)
    store_result = store(
        content, cls,
        tags=tags, project=project,
        confidence=confidence, source=source,
        content_hash=content_hash,
        retrieval_hints=retrieval_hints,
    )

    # 2-a. DB 레벨 중복 감지 (concurrent race condition 방어)
    if store_result.get("status") == "duplicate":
        return {"status": "duplicate", "node_id": store_result.get("node_id")}

    node_id = store_result["node_id"]

    # 2-b. parent_id 명시적 edge 생성 (ChromaDB 무관, 항상 실행)
    parent_edge = None
    if parent_id is not None:
        try:
            edge_id = sqlite_store.insert_edge(
                source_id=parent_id,
                target_id=node_id,
                relation=parent_relation,
                strength=0.85,
            )
            parent_edge = {
                "edge_id": edge_id,
                "source_id": parent_id,
                "target_id": node_id,
                "relation": parent_relation,
            }
        except Exception:
            pass  # parent edge 실패가 저장을 막으면 안됨

    # 3. ChromaDB 실패 시 edge 생성 스킵
    if "warning" in store_result:
        result = {
            "node_id": node_id,
            "type": cls.type,
            "project": project,
            "auto_edges": [parent_edge] if parent_edge else [],
            "warning": store_result["warning"],
            "message": f"Stored as node #{node_id} (embedding failed)",
        }
        return result

    # 4. 자동 edge 생성 (방화벽 F3 적용)
    auto_edges = link(
        node_id, content,
        type=cls.type, layer=cls.layer, project=project,
    )
    if parent_edge:
        auto_edges.insert(0, parent_edge)

    # wiki-compiler dirty flag
    try:
        sqlite_store.mark_dirty(project, node_id)
    except Exception:
        pass  # wiki-compiler 없어도 remember()는 동작해야 함

    return {
        "node_id": node_id,
        "type": cls.type,
        "project": project,
        "auto_edges": auto_edges,
        "message": f"Stored as node #{node_id} with {len(auto_edges)} auto-edge(s)",
    }
