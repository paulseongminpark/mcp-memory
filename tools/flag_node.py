"""flag_node() — 노드 피드백 (잘못된 결과 신고 / 신뢰도 조정).

v3.2: Claude가 recall 결과에 대해 피드백할 수 있게 하는 경량 도구.
Correction 노드 생성 + 원본 confidence 하락 + contradicts edge.
"""

from storage import sqlite_store
from tools.remember import remember


def flag_node(
    node_id: int,
    reason: str,
    action: str = "inaccurate",  # "inaccurate" | "outdated" | "irrelevant"
) -> dict:
    """노드에 대한 피드백 — 부정확/구식/무관함 신고.

    Args:
        node_id: 대상 노드 ID
        reason: 왜 잘못되었는지 설명
        action: 신고 유형 (inaccurate, outdated, irrelevant)
    """
    node = sqlite_store.get_node(node_id)
    if not node:
        return {"error": f"Node {node_id} not found"}
    if node.get("status") != "active":
        return {"error": f"Node {node_id} is not active (status={node.get('status')})"}

    # 1. 원본 confidence 하락
    penalty = {"inaccurate": 0.2, "outdated": 0.15, "irrelevant": 0.1}.get(action, 0.1)
    old_conf = node.get("confidence") or 0.5
    new_conf = max(0.1, old_conf - penalty)

    with sqlite_store._db() as conn:
        conn.execute(
            "UPDATE nodes SET confidence = ?, updated_at = datetime('now') WHERE id = ?",
            (new_conf, node_id),
        )
        conn.commit()

    # 2. 원본 노드 epistemic_status 갱신
    with sqlite_store._db() as conn:
        conn.execute(
            "UPDATE nodes SET epistemic_status = ? WHERE id = ?",
            ("flagged" if action == "inaccurate" else action, node_id),
        )
        conn.commit()

    # 3. Correction 노드 생성 (system type — validators bypass 필요)
    correction = remember(
        content=f"[Correction] Node #{node_id} flagged as {action}: {reason}",
        type="Correction",
        project=node.get("project", ""),
        source="flag_node",
        confidence=0.8,
        source_kind="claude",
        source_ref=f"flag_node:{node_id}",
        node_role="correction",
        epistemic_status="validated",
    )

    # 4. contradicts edge 생성
    corr_id = correction.get("node_id")
    if corr_id:
        sqlite_store.insert_edge(
            source_id=corr_id,
            target_id=node_id,
            relation="contradicts",
            description=reason[:200],
            strength=0.9,
            generation_method="rule",
        )

    return {
        "node_id": node_id,
        "action": action,
        "confidence": f"{old_conf:.2f} → {new_conf:.2f}",
        "epistemic_status": "flagged" if action == "inaccurate" else action,
        "correction_id": corr_id,
        "message": f"Node #{node_id} flagged as {action}. Confidence {old_conf:.2f}→{new_conf:.2f}. Correction #{corr_id} created.",
    }
