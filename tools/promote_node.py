"""promote_node() — 타입 승격 실행 + realized_as edge + 이력 보존."""

import json
from datetime import datetime, timezone

from config import VALID_PROMOTIONS, PROMOTE_LAYER
from storage import sqlite_store


def promote_node(
    node_id: int,
    target_type: str,
    reason: str = "",
    related_ids: list[int] | None = None,
) -> dict:
    """노드 타입을 승격하고 이력을 보존한다.

    Args:
        node_id: 승격할 노드 ID
        target_type: 목표 타입 (예: Pattern, Principle)
        reason: 승격 사유
        related_ids: 같은 클러스터의 다른 노드 ID (realized_as edge 생성)
    """
    node = sqlite_store.get_node(node_id)
    if not node:
        return {"error": f"Node #{node_id} not found.", "message": "Promotion failed."}

    current_type = node["type"]
    valid_targets = VALID_PROMOTIONS.get(current_type, [])
    if target_type not in valid_targets:
        return {
            "error": f"Invalid promotion: {current_type} → {target_type}",
            "valid_targets": valid_targets,
            "message": f"Cannot promote {current_type} to {target_type}. Valid: {valid_targets}",
        }

    now = datetime.now(timezone.utc).isoformat()

    # 승격 이력 구성
    metadata = json.loads(node.get("metadata") or "{}")
    history = metadata.get("promotion_history", [])
    history.append({
        "from": current_type,
        "to": target_type,
        "reason": reason,
        "promoted_at": now,
    })
    metadata["promotion_history"] = history
    metadata.pop("embedding_provisional", None)  # 승격 시 재임베딩 필요 표시 제거

    # DB 업데이트: type, layer, metadata
    new_layer = PROMOTE_LAYER.get(target_type, node.get("layer"))
    conn = sqlite_store._connect()
    conn.execute(
        """UPDATE nodes
           SET type = ?, layer = ?, metadata = ?, updated_at = ?
           WHERE id = ?""",
        (target_type, new_layer, json.dumps(metadata, ensure_ascii=False), now, node_id),
    )

    # realized_as edge: 관련 노드들 → 승격된 노드
    edge_ids = []
    for rid in (related_ids or []):
        if rid == node_id:
            continue
        try:
            cur = conn.execute(
                """INSERT INTO edges (source_id, target_id, relation, description, strength, created_at)
                   VALUES (?, ?, 'realized_as', ?, 1.0, ?)""",
                (rid, node_id, f"{current_type}→{target_type}: {reason}", now),
            )
            edge_ids.append(cur.lastrowid)
        except Exception:
            pass

    conn.commit()
    conn.close()

    return {
        "node_id": node_id,
        "previous_type": current_type,
        "new_type": target_type,
        "new_layer": new_layer,
        "realized_as_edges": edge_ids,
        "promotion_count": len(history),
        "message": f"Promoted #{node_id}: {current_type} → {target_type} (L{new_layer})",
    }
