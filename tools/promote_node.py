"""promote_node() — 3-gate 승격 파이프라인 + 이력 보존.

Gates (직렬):
  1. SWR readiness: 구조적 성숙도 (B-2)
  2. Bayesian P(real): 통계적 증거 (C-7)
  3. MDL gate: 의미적 중복도 (C-7)
"""

import json
import math
from datetime import datetime, timezone

from config import (
    VALID_PROMOTIONS,
    PROMOTE_LAYER,
    PROMOTION_SWR_THRESHOLD,
)
from storage import sqlite_store


# ─────────────────────────────────────────────
# Gate 1: SWR Readiness (B-2)
# ─────────────────────────────────────────────

def swr_readiness(node_id: int) -> tuple[bool, float]:
    """구조적 성숙도 판단.

    지표 1 — vec_ratio (가중치 0.6):
        recall_log에서 vector vs FTS5 비율.
        vec_ratio > 0.6 → 의미적 연결 우세 (해마→신피질 전이 준비)

    지표 2 — cross_ratio (가중치 0.4):
        이웃 노드가 여러 project에 걸쳐 있는가.
        피질간 연결성 proxy (Slow Oscillation 게이트)

    Returns:
        (ready: bool, readiness_score: float)
    """
    with sqlite_store._db() as conn:
        # vec_ratio: recall_log sources JSON에서 vector/fts5 비율
        try:
            rows = conn.execute(
                "SELECT sources FROM recall_log WHERE node_id=? AND sources IS NOT NULL AND sources != '[]'",
                (node_id,),
            ).fetchall()
            vec_hits = sum(1 for r in rows if '"vector"' in (r[0] or ""))
            fts_hits = sum(1 for r in rows if '"fts5"' in (r[0] or ""))
            total = vec_hits + fts_hits
            # sources 데이터 없으면 neutral fallback (데이터 부재로 페널티 주지 않음)
            vec_ratio = (vec_hits / total) if total > 0 else 0.5
        except Exception:
            vec_ratio = 0.5  # recall_log 테이블 미존재 시 neutral fallback

        # cross_ratio: 이웃 노드의 project 다양성
        edge_rows = conn.execute(
            """SELECT source_id, target_id FROM edges
               WHERE (source_id=? OR target_id=?) AND status='active'""",
            (node_id, node_id),
        ).fetchall()
        if not edge_rows:
            cross_ratio = 0.0
        else:
            neighbor_ids = set()
            for src, tgt in edge_rows:
                neighbor_ids.add(tgt if src == node_id else src)
            projects = set()
            for nbr_id in neighbor_ids:
                row = conn.execute(
                    "SELECT project FROM nodes WHERE id=?", (nbr_id,)
                ).fetchone()
                if row and row[0]:
                    projects.add(row[0])
            cross_ratio = len(projects) / max(len(edge_rows), 1)

    readiness = 0.6 * vec_ratio + 0.4 * cross_ratio
    return readiness > PROMOTION_SWR_THRESHOLD, round(readiness, 3)


# ─────────────────────────────────────────────
# Gate 2: Bayesian P(real pattern)
# ─────────────────────────────────────────────

PROMOTION_VISIT_THRESHOLD = 10  # visit_count >= 이 값이면 Gate 2 통과


def promotion_frequency_check(node: dict) -> tuple[bool, int]:
    """Gate 2: 노드의 recall 빈도 검증.

    v3: Bayesian Beta(1,10)에서 visit_count 직접 threshold로 교체.
    사유: Beta(1,10) prior는 total_queries=401 규모에서 수학적으로 통과 불가.
    visit_count는 post_search_learn()에서 recall마다 +1 갱신됨.

    Returns:
        (passed: bool, visit_count: int)
    """
    vc = node.get("visit_count") or 0
    return vc >= PROMOTION_VISIT_THRESHOLD, vc


# ─────────────────────────────────────────────
# Gate 3: MDL (Minimum Description Length)
# ─────────────────────────────────────────────

def _mdl_gate(node: dict, related_nodes: list[dict]) -> tuple[bool, str]:
    """MDL 기준 승격 정당성 검증.

    avg cosine similarity > 0.75 → 신호들이 의미적으로 중복
    → Pattern으로 통합 시 설명 길이 감소 → MDL 정당화

    데이터 부족 또는 임베딩 없으면 통과 처리 (보수적).

    Returns:
        (ok: bool, reason: str)
    """
    if not related_nodes or len(related_nodes) < 2:
        return True, "not_enough_signals"

    try:
        import numpy as np
        from storage import vector_store

        coll = vector_store._get_collection()
        ids = [str(n["id"]) for n in related_nodes]
        result = coll.get(ids=ids, include=["embeddings"])
        embs = result.get("embeddings") or []
    except Exception as e:
        return True, f"embedding_unavailable:{e}"

    if len(embs) < 2:
        return True, "embedding_unavailable"

    vecs = np.array(embs)
    norms = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
    sim_matrix = norms @ norms.T
    n = len(vecs)
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    avg_sim = sum(sim_matrix[i, j] for i, j in pairs) / len(pairs)

    if avg_sim > 0.75:
        return True, f"high_similarity={avg_sim:.3f}"
    return False, f"low_similarity={avg_sim:.3f}_mdl_failed"


# ─────────────────────────────────────────────
# 메인: promote_node()
# ─────────────────────────────────────────────

def promote_node(
    node_id: int,
    target_type: str,
    reason: str = "",
    related_ids: list[int] | None = None,
    skip_gates: bool = False,  # 관리자 강제 승격용
) -> dict:
    """노드 타입을 3-gate 검증 후 승격한다.

    Args:
        node_id: 승격할 노드 ID
        target_type: 목표 타입 (예: Pattern, Principle)
        reason: 승격 사유
        related_ids: 같은 클러스터의 다른 노드 ID (realized_as edge 생성 + MDL 검증)
        skip_gates: True면 게이트 우회 (관리자 전용)
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

    gates_passed: list[str] = []

    # ── Gate 1: SWR readiness ──────────────────
    if not skip_gates:
        ready, swr_score = swr_readiness(node_id)
        if not ready:
            return {
                "status": "not_ready",
                "swr_score": swr_score,
                "threshold": PROMOTION_SWR_THRESHOLD,
                "message": (
                    f"SWR readiness {swr_score:.3f} < {PROMOTION_SWR_THRESHOLD}. "
                    "Need more vector recalls or cross-domain neighbors."
                ),
            }
        gates_passed.append("swr")

    # ── Gate 2: Recall frequency ───────────────
    if not skip_gates:
        freq_ok, visit_count = promotion_frequency_check(node)
        if not freq_ok:
            return {
                "status": "insufficient_evidence",
                "visit_count": visit_count,
                "threshold": PROMOTION_VISIT_THRESHOLD,
                "message": (
                    f"visit_count={visit_count} < {PROMOTION_VISIT_THRESHOLD}. "
                    "Need more recall frequency."
                ),
            }
        gates_passed.append("frequency")

    # ── Gate 3: MDL ────────────────────────────
    if not skip_gates and related_ids:
        related_nodes = [
            sqlite_store.get_node(rid)
            for rid in related_ids
            if rid != node_id
        ]
        related_nodes = [n for n in related_nodes if n]
        mdl_ok, mdl_reason = _mdl_gate(node, related_nodes)
        if not mdl_ok:
            return {
                "status": "mdl_failed",
                "reason": mdl_reason,
                "message": f"MDL gate rejected: signals not semantically similar enough. {mdl_reason}",
            }
        gates_passed.append("mdl")

    # ── 승격 실행 ───────────────────────────────
    now = datetime.now(timezone.utc).isoformat()

    metadata = json.loads(node.get("metadata") or "{}")
    history = metadata.get("promotion_history", [])
    history.append({
        "from": current_type,
        "to": target_type,
        "reason": reason,
        "promoted_at": now,
        "gates_skipped": skip_gates,
    })
    metadata["promotion_history"] = history
    metadata.pop("embedding_provisional", None)

    new_layer = PROMOTE_LAYER.get(target_type, node.get("layer"))
    edge_ids = []
    with sqlite_store._db() as conn:
        conn.execute(
            """UPDATE nodes
               SET type = ?, layer = ?, metadata = ?, updated_at = ?
               WHERE id = ?""",
            (target_type, new_layer, json.dumps(metadata, ensure_ascii=False), now, node_id),
        )

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

    # ── action_log 기록 ─────────────────────────
    try:
        from storage import action_log
        action_log.record(
            action_type="node_promoted",
            actor="claude",
            target_type="node",
            target_id=node_id,
            params=json.dumps({
                "from_type": current_type,
                "to_type": target_type,
                "reason": reason,
                "skip_gates": skip_gates,
                "gates_passed": gates_passed,
            }),
            result=json.dumps({
                "new_layer": new_layer,
                "realized_as_edges": edge_ids,
            }),
        )
    except Exception:
        pass

    return {
        "node_id": node_id,
        "previous_type": current_type,
        "new_type": target_type,
        "new_layer": new_layer,
        "realized_as_edges": edge_ids,
        "promotion_count": len(history),
        "gates_passed": gates_passed,
        "message": f"Promoted #{node_id}: {current_type} → {target_type} (L{new_layer})",
    }
