# 세션 C — R3-11: promote_node.py 전체 교체 설계

> 2026-03-05 | R3 심화 | 3-gate 승격 파이프라인 최종 코드

## 설계 요약

현재 `promote_node.py`는 타입 유효성 검사만 하고 즉시 승격.
교체 후: **SWR → Bayesian → MDL** 3개 직렬 게이트를 통과해야만 승격.

```
promote_node(node_id, target_type)
  │
  ├─ [Gate 1] swr_readiness() — 구조적 준비 (vec_ratio + cross_ratio)
  │     실패 → {"status": "not_ready", "swr_score": x}
  │
  ├─ [Gate 2] promotion_probability() — Bayesian 증거 (Beta posterior)
  │     P < 0.5 → {"status": "insufficient_evidence", "p_real": x}
  │
  ├─ [Gate 3] _mdl_gate() — 의미적 중복 (embedding cosine sim > 0.75)
  │     실패 → {"status": "mdl_failed", "reason": x}
  │
  └─ 기존 승격 로직 실행 (type/layer/metadata 갱신 + realized_as edge)
```

---

## 1. tools/promote_node.py — 전체 교체

```python
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
    PROMOTION_SWR_THRESHOLD,  # 추가: config.py에 PROMOTION_SWR_THRESHOLD = 0.55
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
    conn = sqlite_store._connect()
    try:
        # vec_ratio: recall_log 소스 분포
        rows = conn.execute(
            "SELECT source, COUNT(*) FROM recall_log WHERE node_id=? GROUP BY source",
            (node_id,),
        ).fetchall()
        counts = {row[0]: row[1] for row in rows}
        fts5_hits = counts.get("fts5", 0)
        vec_hits = counts.get("vector", 0)
        total = fts5_hits + vec_hits
        vec_ratio = (vec_hits / total) if total > 0 else 0.0

        # cross_ratio: 이웃 노드의 project 다양성
        edge_rows = conn.execute(
            """SELECT source_id, target_id FROM edges
               WHERE source_id=? OR target_id=?""",
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

    finally:
        conn.close()

    readiness = 0.6 * vec_ratio + 0.4 * cross_ratio
    return readiness > PROMOTION_SWR_THRESHOLD, round(readiness, 3)


# ─────────────────────────────────────────────
# Gate 2: Bayesian P(real pattern)
# ─────────────────────────────────────────────

def _get_total_recall_count() -> int:
    """meta 테이블에서 글로벌 recall 횟수 조회."""
    conn = sqlite_store._connect()
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key='total_recall_count'"
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def promotion_probability(node: dict, total_queries: int) -> float:
    """단일 노드의 Bayesian P(real pattern).

    Prior: Beta(1, 10) — 회의적 사전 분포
    Posterior: Beta(1 + k, 10 + n - k)
    k = node frequency (recall 횟수)
    n = total_queries (전체 recall 횟수)

    Returns:
        float: 사후 분포 평균 = (1+k) / (11+n)
    """
    k = node.get("frequency") or 0
    n = max(total_queries, k)
    alpha_post = 1 + k
    beta_post = 10 + (n - k)
    return alpha_post / (alpha_post + beta_post)


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

    vecs = __import__("numpy").array(embs)
    norms = vecs / (__import__("numpy").linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
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

    # ── Gate 2: Bayesian P(real) ───────────────
    if not skip_gates:
        total_queries = _get_total_recall_count()
        p_real = promotion_probability(node, total_queries)
        if p_real < 0.5:
            return {
                "status": "insufficient_evidence",
                "p_real": round(p_real, 4),
                "frequency": node.get("frequency") or 0,
                "total_queries": total_queries,
                "message": (
                    f"Bayesian P(real)={p_real:.4f} < 0.5. "
                    "Need more recall frequency relative to total queries."
                ),
            }

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
    conn = sqlite_store._connect()
    conn.execute(
        """UPDATE nodes
           SET type = ?, layer = ?, metadata = ?, updated_at = ?
           WHERE id = ?""",
        (target_type, new_layer, json.dumps(metadata, ensure_ascii=False), now, node_id),
    )

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
        "gates_passed": [] if skip_gates else ["swr", "bayesian", "mdl"],
        "message": f"Promoted #{node_id}: {current_type} → {target_type} (L{new_layer})",
    }
```

---

## 2. tools/analyze_signals.py — _recommend_v2() 추가

현재 `_recommend()` 를 `_recommend_v2()` 로 교체. `analyze_signals()` 내부에서
`_compute_maturity()` 호출 이후 Bayesian + SPRT 데이터를 추가.

```python
# tools/analyze_signals.py 수정 요약:
#   1. _recommend() → _recommend_v2() 교체
#   2. analyze_signals() 내 results.append() 블록 수정
#   3. meta 테이블에서 total_queries 조회 추가

# ① 함수 교체
def _recommend_v2(maturity: float, bayesian_p: float, sprt_flagged: int) -> str:
    """기존 maturity + Bayesian P + SPRT flag 통합 판단.

    우선순위:
      auto_promote: maturity 매우 높음 AND Bayesian 강한 증거
      user_review: Bayesian 중간 증거 OR SPRT 2개 이상 플래그
      not_ready: 그 외
    """
    if maturity > 0.9 and bayesian_p > 0.6:
        return "auto_promote"
    if bayesian_p > 0.5 or sprt_flagged >= 2:
        return "user_review"
    if maturity > 0.6:
        return "user_review"
    return "not_ready"


# ② analyze_signals() 내부 — results.append() 블록 교체
# (min_cluster_size 이상 루프 내부)

# total_queries는 한 번만 조회 (루프 밖에서)
total_queries = _get_total_recall_count()  # promote_node.py에서 import

for cluster_ids in raw_clusters:
    if len(cluster_ids) < min_cluster_size:
        continue
    cluster_nodes = [node_map[nid] for nid in cluster_ids if nid in node_map]
    maturity = _compute_maturity(cluster_nodes)

    # Bayesian 클러스터 평균
    bayesian_p = _bayesian_cluster_score(cluster_nodes, total_queries)

    # SPRT 플래그 카운트
    sprt_flagged = sum(
        1 for n in cluster_nodes
        if n.get("promotion_candidate")
    )

    results.append({
        "node_ids": cluster_ids,
        "size": len(cluster_ids),
        "maturity": round(maturity, 2),
        "bayesian_p": round(bayesian_p, 3),       # 신규
        "sprt_flagged": sprt_flagged,              # 신규
        "recommendation": _recommend_v2(maturity, bayesian_p, sprt_flagged),
        "themes": [n.get("summary") or n["content"][:80] for n in cluster_nodes[:3]],
        "domains": _collect_domains(cluster_nodes),
        "can_promote_to": VALID_PROMOTIONS.get("Signal", []),
    })


def _bayesian_cluster_score(nodes: list[dict], total_queries: int) -> float:
    """클러스터 내 Signal들의 평균 Bayesian P(real pattern)."""
    if not nodes or total_queries <= 0:
        return 0.0
    probs = []
    for n in nodes:
        k = n.get("frequency") or 0
        n_total = max(total_queries, k)
        # Prior: Beta(1, 10)
        alpha_post = 1 + k
        beta_post = 10 + (n_total - k)
        probs.append(alpha_post / (alpha_post + beta_post))
    return sum(probs) / len(probs)
```

---

## 3. storage/hybrid.py — _sprt_check() 추가

`_bcm_update()` (또는 기존 `_hebbian_update()`) 이후, `hybrid_search()` 반환 전에 삽입.

```python
# storage/hybrid.py 추가

import json, math

# SPRT 파라미터 (config.py에 추가하거나 여기서 직접)
_SPRT_ALPHA = 0.05    # 허용 오경보율
_SPRT_BETA  = 0.20    # 허용 누락율
_SPRT_P1    = 0.70    # 진짜 Signal의 score>0.5 확률
_SPRT_P0    = 0.30    # 노이즈의 score>0.5 확률
_SPRT_MIN_OBS = 5     # 최소 관찰 횟수

_SPRT_A = math.log((1 - _SPRT_BETA) / _SPRT_ALPHA)   # 승격 임계 ≈ 2.773
_SPRT_B = math.log(_SPRT_BETA / (1 - _SPRT_ALPHA))   # 기각 임계 ≈ -1.558
_SPRT_LLR_POS = math.log(_SPRT_P1 / _SPRT_P0)        # score>0.5 시 LLR ≈ 0.847
_SPRT_LLR_NEG = math.log((1-_SPRT_P1) / (1-_SPRT_P0))  # score≤0.5 시 LLR ≈ -0.847


def _sprt_check(node: dict, score: float, conn) -> bool:
    """recall score 추가 후 SPRT 판단.

    Signal 타입 노드에만 적용.
    score_history 갱신 → SPRT 누적합 계산 → promotion_candidate 플래그.

    Returns:
        True if SPRT says "promote", False otherwise
    """
    if node.get("type") != "Signal":
        return False

    # score_history 갱신 (최대 50개)
    raw = node.get("score_history") or "[]"
    try:
        history = json.loads(raw)
        if not isinstance(history, list):
            history = []
    except (json.JSONDecodeError, ValueError):
        history = []

    history = (history + [round(score, 4)])[-50:]
    conn.execute(
        "UPDATE nodes SET score_history=? WHERE id=?",
        (json.dumps(history), node["id"]),
    )

    if len(history) < _SPRT_MIN_OBS:
        return False

    # SPRT 누적합 (전체 history 기준 — 순차 검정)
    cumulative = 0.0
    for obs in history:
        cumulative += _SPRT_LLR_POS if obs > 0.5 else _SPRT_LLR_NEG
        if cumulative >= _SPRT_A:
            return True   # "promote" 신호 도달
        if cumulative <= _SPRT_B:
            return False  # "reject" 도달
    return False  # 미결정 (중간 구간)


# hybrid_search() 내부 — _bcm_update() 호출 이후, return result 전에 삽입:
#
# conn = sqlite_store._connect()
# try:
#     for node in result:
#         if node.get("type") == "Signal":
#             if _sprt_check(node, node.get("score", 0.0), conn):
#                 conn.execute(
#                     "UPDATE nodes SET promotion_candidate=1 WHERE id=?",
#                     (node["id"],),
#                 )
#     conn.commit()
# except Exception:
#     pass
# finally:
#     conn.close()
```

---

## 4. tools/recall.py — total_recall_count 갱신

`recall()` 내 `hybrid_search()` 호출 직후에 삽입.

```python
# tools/recall.py — hybrid_search() 이후 추가

conn = sqlite_store._connect()
try:
    conn.execute(
        "UPDATE meta "
        "SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) "
        "WHERE key = 'total_recall_count'"
    )
    conn.commit()
except Exception:
    pass
finally:
    conn.close()
```

---

## 5. config.py 추가 항목

```python
# tools/promote_node.py Gate 1
PROMOTION_SWR_THRESHOLD: float = 0.55

# SPRT (storage/hybrid.py에서도 참조 가능)
SPRT_ALPHA: float = 0.05
SPRT_BETA: float = 0.20
SPRT_P1: float = 0.70
SPRT_P0: float = 0.30
SPRT_MIN_OBS: int = 5
```

---

## 파일별 변경 요약

| 파일 | 변경 내용 | 난이도 |
|---|---|---|
| `tools/promote_node.py` | 전체 교체 (3-gate 추가) | 중 |
| `tools/analyze_signals.py` | `_recommend_v2()` + `_bayesian_cluster_score()` + 결과 구조 수정 | 중 |
| `storage/hybrid.py` | `_sprt_check()` + promotion_candidate 갱신 로직 삽입 | 중 |
| `tools/recall.py` | `total_recall_count` 갱신 (4줄) | 쉬움 |
| `config.py` | `PROMOTION_SWR_THRESHOLD` + SPRT 파라미터 추가 | 쉬움 |

**선행 필수**: DB migration (recall_log, score_history, promotion_candidate, theta_m, activity_history, meta 테이블)
→ `python scripts/migrate_phase2.py` (C-11 설계대로)
