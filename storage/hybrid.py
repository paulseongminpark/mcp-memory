"""3-way hybrid search: Vector + FTS5 + Graph traversal with RRF."""

import json
import math
from collections import defaultdict
from datetime import datetime, timezone

from config import (
    DEFAULT_TOP_K, RRF_K, GRAPH_BONUS,
    ENRICHMENT_QUALITY_WEIGHT, ENRICHMENT_TEMPORAL_WEIGHT,
    CONTEXT_HISTORY_LIMIT, LAYER_ETA, BCM_HISTORY_WINDOW,
    UCB_C_FOCUS, UCB_C_AUTO, UCB_C_DMN,
)
from storage import sqlite_store, vector_store


def _traverse_sql(seed_ids: list[int], depth: int = 2) -> set[int]:
    """B-11: SQLite Recursive CTE로 그래프 이웃 탐색 (Chen 2014).

    NetworkX BFS 대비 ~100-500x 빠름. idx_edges_source/target 인덱스 활용.
    """
    if not seed_ids:
        return set()
    conn = None
    try:
        conn = sqlite_store._connect()
        ph = ",".join("?" * len(seed_ids))
        sql = f"""
        WITH RECURSIVE sa(id, hop) AS (
            SELECT target_id, 1 FROM edges WHERE source_id IN ({ph})
            UNION
            SELECT source_id, 1 FROM edges WHERE target_id IN ({ph})
            UNION ALL
            SELECT e.target_id, sa.hop + 1
              FROM edges e JOIN sa ON e.source_id = sa.id WHERE sa.hop < ?
            UNION ALL
            SELECT e.source_id, sa.hop + 1
              FROM edges e JOIN sa ON e.target_id = sa.id WHERE sa.hop < ?
        )
        SELECT DISTINCT id FROM sa WHERE id NOT IN ({ph})
        """
        params = seed_ids + seed_ids + [depth - 1, depth - 1] + seed_ids
        rows = conn.execute(sql, params).fetchall()
        return {row[0] for row in rows}
    except Exception:
        return set()
    finally:
        if conn:
            conn.close()


def _auto_ucb_c(query: str, mode: str = "auto") -> float:
    """B-12: 쿼리 길이/모드로 UCB c값 자동 결정."""
    if mode == "focus":
        return UCB_C_FOCUS
    if mode == "dmn":
        return UCB_C_DMN
    words = query.split()
    if len(words) >= 5:
        return UCB_C_FOCUS  # 구체적 쿼리 → 집중
    if len(words) <= 2:
        return UCB_C_DMN    # 추상적 쿼리 → DMN
    return UCB_C_AUTO


def _ucb_traverse(seed_ids: list[int], depth: int = 2, c: float = UCB_C_AUTO) -> set[int]:
    """B-12: UCB 기반 그래프 탐색. Score(j) = w_ij + c·√(ln(N_i)/N_j).

    visit_count가 적은 노드(탐험 미개척)를 c값에 따라 더 적극적으로 탐색.
    """
    if not seed_ids:
        return set()
    conn = None
    try:
        conn = sqlite_store._connect()

        # seed_ids의 visit_count 조회
        ph = ",".join("?" * len(seed_ids))
        rows = conn.execute(
            f"SELECT id, visit_count FROM nodes WHERE id IN ({ph})", seed_ids
        ).fetchall()
        visit_map: dict[int, int] = {r[0]: (r[1] or 1) for r in rows}

        # 1-hop 이웃 + edge 가중치 조회
        rows = conn.execute(
            f"""SELECT source_id, target_id, COALESCE(frequency, 0) + 1.0 AS w
                FROM edges WHERE source_id IN ({ph}) OR target_id IN ({ph})""",
            seed_ids + seed_ids,
        ).fetchall()

        visited = set(seed_ids)
        frontier = set(seed_ids)

        for _ in range(depth):
            candidates: list[tuple[float, int]] = []
            for src, tgt, w in rows:
                nid = src if tgt in frontier else tgt if src in frontier else None
                if nid is None or nid in visited:
                    continue
                n_i = visit_map.get(src if tgt == nid else tgt, 1)
                n_j = visit_map.get(nid, 1)
                score = w + c * math.sqrt(math.log(n_i + 1) / (n_j + 1))
                candidates.append((score, nid))

            candidates.sort(reverse=True)
            next_frontier = {nid for _, nid in candidates[:30]}
            visited.update(next_frontier)
            frontier = next_frontier

            if next_frontier:
                ph2 = ",".join("?" * len(next_frontier))
                new_rows = conn.execute(
                    f"""SELECT source_id, target_id, COALESCE(frequency, 0) + 1.0 AS w
                        FROM edges WHERE source_id IN ({ph2}) OR target_id IN ({ph2})""",
                    list(next_frontier) + list(next_frontier),
                ).fetchall()
                rows = new_rows

        visited -= set(seed_ids)
        return visited
    except Exception:
        return set()
    finally:
        if conn:
            conn.close()


def _bcm_update(result_ids: list[int], result_scores: list[float],
                all_edges: list[dict], query: str = ""):
    """B-12: BCM 규칙 + B-10 재공고화 통합.

    dw_ij/dt = η · ν_i · (ν_i - θ_m) · ν_j
    θ_m: 슬라이딩 제곱평균 임계값 (runaway reinforcement 방지)
    """
    if not result_ids:
        return
    score_map = dict(zip(result_ids, result_scores))
    id_set = set(result_ids)
    now = datetime.now(timezone.utc).isoformat()

    activated_edges = [
        e for e in all_edges
        if e.get("source_id") in id_set and e.get("target_id") in id_set
    ]
    if not activated_edges:
        return

    conn = None
    try:
        conn = sqlite_store._connect()

        for edge in activated_edges:
            eid = edge.get("id")
            src = edge.get("source_id")
            v_i = score_map.get(src, 0.5)
            v_j = score_map.get(edge.get("target_id"), 0.5)

            # 노드 정보 (theta_m, activity_history, layer)
            node_row = conn.execute(
                "SELECT layer, theta_m, activity_history FROM nodes WHERE id = ?", (src,)
            ).fetchone()
            if node_row:
                layer = node_row[0] if node_row[0] is not None else 2
                theta_m = node_row[1] if node_row[1] is not None else 0.5
                try:
                    history = json.loads(node_row[2] or "[]")
                    if not isinstance(history, list):
                        history = []
                except (json.JSONDecodeError, TypeError):
                    history = []
            else:
                layer, theta_m, history = 2, 0.5, []

            eta = LAYER_ETA.get(layer, 0.01)
            delta_w = eta * v_i * (v_i - theta_m) * v_j
            new_freq = max(0.0, (edge.get("frequency") or 0) + delta_w * 10)

            # θ_m 슬라이딩 제곱평균 갱신
            history = (history + [v_i])[-BCM_HISTORY_WINDOW:]
            new_theta = sum(h ** 2 for h in history) / len(history)

            # 맥락 로그 (B-10 재공고화)
            if query:
                try:
                    ctx_log = json.loads(edge.get("description") or "[]")
                    if not isinstance(ctx_log, list):
                        ctx_log = []
                except (json.JSONDecodeError, TypeError):
                    ctx_log = []
                ctx_log.append({"q": query[:80], "t": now})
                ctx_log = ctx_log[-CONTEXT_HISTORY_LIMIT:]
                new_desc = json.dumps(ctx_log, ensure_ascii=False)
                conn.execute(
                    "UPDATE edges SET frequency = ?, last_activated = ?, description = ? WHERE id = ?",
                    (new_freq, now, new_desc, eid),
                )
            else:
                conn.execute(
                    "UPDATE edges SET frequency = ?, last_activated = ? WHERE id = ?",
                    (new_freq, now, eid),
                )

            conn.execute(
                "UPDATE nodes SET theta_m = ?, activity_history = ?, "
                "visit_count = COALESCE(visit_count, 0) + 1 WHERE id = ?",
                (new_theta, json.dumps(history), src),
            )

        conn.commit()
    except Exception:
        pass
    finally:
        if conn:
            conn.close()


def hybrid_search(
    query: str,
    type_filter: str = "",
    project: str = "",
    top_k: int = DEFAULT_TOP_K,
    excluded_project: str = "",  # B-4: 패치 전환 — 이 project 제외
    mode: str = "auto",          # B-12: UCB 탐색 모드 ("focus"|"dmn"|"auto")
) -> list[dict]:
    # 1. 벡터 유사도 검색 (ChromaDB 실패 시 graceful fallback)
    where = {}
    if type_filter:
        where["type"] = type_filter
    if project:
        where["project"] = project
    try:
        vec_results = vector_store.search(query, top_k=top_k * 2, where=where if where else None)
    except Exception:
        vec_results = []

    # 2. FTS5 키워드 검색
    fts_results = sqlite_store.search_fts(query, top_k=top_k * 2)

    # 3. 그래프 탐색 — 벡터/FTS 상위 결과의 이웃
    seed_ids = []
    for node_id, _, _ in vec_results[:3]:
        seed_ids.append(node_id)
    for node_id, _, _ in fts_results[:3]:
        seed_ids.append(node_id)

    all_edges = sqlite_store.get_all_edges()
    ucb_c = _auto_ucb_c(query, mode)
    graph_neighbors = _ucb_traverse(seed_ids, depth=2, c=ucb_c) if seed_ids else set()  # B-12: UCB

    # 4. Reciprocal Rank Fusion
    scores: dict[int, float] = defaultdict(float)

    for rank, (node_id, distance, _) in enumerate(vec_results, 1):
        scores[node_id] += 1.0 / (RRF_K + rank)

    for rank, (node_id, _, _) in enumerate(fts_results, 1):
        scores[node_id] += 1.0 / (RRF_K + rank)

    for node_id in graph_neighbors:
        scores[node_id] += GRAPH_BONUS

    # 5. 타입/프로젝트 필터 적용 + enrichment 가중치 + 노드 정보 조회
    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    candidates = []
    for node_id in sorted_ids[:top_k * 2]:
        node = sqlite_store.get_node(node_id)
        if not node:
            continue
        if type_filter and node["type"] != type_filter:
            continue
        if project and node["project"] != project:
            continue
        if excluded_project and node["project"] == excluded_project:  # B-4
            continue
        # enrichment 가중치 (S5 해결)
        qs = node.get("quality_score") or 0.0
        tr = node.get("temporal_relevance") or 0.0
        enrichment_bonus = qs * ENRICHMENT_QUALITY_WEIGHT + tr * ENRICHMENT_TEMPORAL_WEIGHT
        # tier 보너스: 상위 tier 노드 우선 (tier=0: L3+, tier=1: L2+고품질)
        tier = node.get("tier", 2)
        tier_bonus = {0: 0.15, 1: 0.05, 2: 0.0}.get(tier, 0.0)
        node["score"] = scores[node_id] + enrichment_bonus + tier_bonus
        candidates.append(node)

    # enrichment 반영 후 재정렬
    candidates.sort(key=lambda n: n["score"], reverse=True)
    result = candidates[:top_k]

    # 6. BCM 학습 + 맥락 재공고화 (B-12 + B-10)
    scores_for_bcm = [n.get("score", 0.5) for n in result]
    _bcm_update([n["id"] for n in result], scores_for_bcm, all_edges, query)

    return result
