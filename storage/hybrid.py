"""3-way hybrid search: Vector + FTS5 + Graph traversal with RRF.

Phase 1: BCM + UCB 통합 (B-12), 재공고화 (B-10), 패치 전환 지원 (B-4).
"""

from collections import defaultdict
from datetime import datetime, timezone
import json
import logging
import math
import threading
import time

from config import (
    DEFAULT_TOP_K, RRF_K, GRAPH_BONUS,
    ENRICHMENT_QUALITY_WEIGHT, ENRICHMENT_TEMPORAL_WEIGHT,
    CONTEXT_HISTORY_LIMIT, BCM_HISTORY_WINDOW,
    UCB_C_FOCUS, UCB_C_AUTO, UCB_C_DMN,
    GRAPH_MAX_HOPS, LAYER_ETA,
    SPRT_ALPHA, SPRT_BETA, SPRT_P1, SPRT_P0, SPRT_MIN_OBS,
    TYPE_KEYWORDS, TYPE_CHANNEL_WEIGHT, TYPE_CHANNEL_WEIGHTS, MAX_TYPE_HINTS,
    COMPOSITE_WEIGHT_RRF, COMPOSITE_WEIGHT_DECAY, COMPOSITE_WEIGHT_IMPORTANCE,
    DECAY_LAMBDA, PROMOTED_MULTIPLIER, LAYER_IMPORTANCE,
)
from storage import sqlite_store, vector_store
from graph.traversal import build_graph  # traverse 제거 — UCB로 교체


# ─── TTL 캐싱 (B-16) ─────────────────────────────────────────────

_GRAPH_CACHE: tuple[list, object] | None = None  # (all_edges, nx.DiGraph)
_GRAPH_CACHE_TS: float = 0.0
_GRAPH_TTL: float = 300.0  # 5분


def _get_graph() -> tuple[list, object]:
    """all_edges + NetworkX graph 캐시 반환 (TTL=5분).

    캐시 히트 시 빌드 비용 완전 생략.
    단일 프로세스 MCP 서버 환경에서 안전.
    """
    global _GRAPH_CACHE, _GRAPH_CACHE_TS
    now = time.monotonic()
    if _GRAPH_CACHE is None or (now - _GRAPH_CACHE_TS) > _GRAPH_TTL:
        all_edges = sqlite_store.get_all_edges()
        graph = build_graph(all_edges)
        # visit_count를 DB에서 로드 → UCB 탐색에서 활용 (B-12)
        try:
            node_ids = list(graph.nodes())
            if node_ids:
                with sqlite_store._db() as conn:
                    ph = ",".join("?" * len(node_ids))
                    rows = conn.execute(
                        f"SELECT id, visit_count FROM nodes WHERE id IN ({ph})",
                        node_ids,
                    ).fetchall()
                for nid, vc in rows:
                    if nid in graph:
                        graph.nodes[nid]["visit_count"] = vc or 1
        except Exception:
            pass
        _GRAPH_CACHE = (all_edges, graph)
        _GRAPH_CACHE_TS = now
    return _GRAPH_CACHE


# ─── _traverse_sql() — B-11 (보조용, Phase 2 전환 준비) ──────────

def _traverse_sql(seed_ids: list[int], depth: int = 2) -> set[int]:
    """SQL Recursive CTE 기반 그래프 탐색. Chen (2014) DB-optimized.

    Phase 1: 직접 호출되지 않음 (UCB가 메인 탐색 경로).
    Phase 2: NetworkX 완전 제거 시 이 함수가 메인 경로로 전환.
    idx_edges_source, idx_edges_target 인덱스 활용.
    """
    if not seed_ids:
        return set()

    ph = ",".join("?" * len(seed_ids))
    sql = f"""
    WITH RECURSIVE sa(id, hop) AS (
        SELECT target_id, 1 FROM edges WHERE source_id IN ({ph})
        UNION
        SELECT source_id, 1 FROM edges WHERE target_id IN ({ph})
        UNION ALL
        SELECT e.target_id, sa.hop + 1
          FROM edges e
          JOIN sa ON e.source_id = sa.id
         WHERE sa.hop < ?
        UNION ALL
        SELECT e.source_id, sa.hop + 1
          FROM edges e
          JOIN sa ON e.target_id = sa.id
         WHERE sa.hop < ?
    )
    SELECT DISTINCT id FROM sa
    WHERE id NOT IN ({ph})
    """
    params = seed_ids + seed_ids + [depth - 1, depth - 1] + seed_ids

    try:
        with sqlite_store._db() as conn:
            rows = conn.execute(sql, params).fetchall()
            return {row[0] for row in rows}
    except Exception:
        return set()  # CTE 실패 시 그래프 보너스 없이 계속


# ─── _ucb_traverse() — B-12 ──────────────────────────────────────

def _ucb_traverse(
    graph,
    seed_ids: list[int],
    depth: int = 2,
    c: float = UCB_C_AUTO,
) -> set[int]:
    """UCB 기반 그래프 탐색 (Upper Confidence Bound).

    Score(j) = w_ij + c * sqrt(ln(N_i + 1) / (N_j + 1))
      w_ij: edge strength (연결 강도)
      N_i : 현재 노드 visit_count (탐색 기준점)
      N_j : 이웃 노드 visit_count (미탐색일수록 높은 점수)
      c   : 탐험 계수 (높을수록 미탐색 우선)

    각 hop에서 상위 20개만 탐색 (폭발 방지).
    """
    visited = set(seed_ids)
    frontier = set(seed_ids)
    undirected = graph.to_undirected(as_view=True)

    for _ in range(depth):
        candidates: list[tuple[float, int]] = []
        for nid in frontier:
            if nid not in graph:
                continue
            n_i = graph.nodes[nid].get("visit_count", 1)
            for nbr in undirected.neighbors(nid):
                if nbr in visited:
                    continue
                if graph.has_edge(nid, nbr):
                    w_ij = graph.edges[nid, nbr].get("strength", 0.1)
                elif graph.has_edge(nbr, nid):
                    w_ij = graph.edges[nbr, nid].get("strength", 0.1)
                else:
                    w_ij = 0.1
                n_j = graph.nodes[nbr].get("visit_count", 1)
                score = w_ij + c * math.sqrt(math.log(n_i + 1) / (n_j + 1))
                candidates.append((score, nbr))

        candidates.sort(reverse=True)
        next_frontier = {nbr for _, nbr in candidates[:20]}
        visited.update(next_frontier)
        frontier = next_frontier

    return visited - set(seed_ids)  # seed 자신 제외


def _auto_ucb_c(query: str, mode: str = "auto") -> float:
    """쿼리 특성으로 UCB 탐험 계수 자동 결정.

    mode 명시 시 우선 적용.
    auto 시: 단어 수 기반 (긴 쿼리=집중, 짧은 쿼리=방산)
      5단어+ → UCB_C_FOCUS (0.3): 구체적 의도, 강한 연결 우선
      3-4단어 → UCB_C_AUTO  (1.0): 균형
      2단어-  → UCB_C_DMN   (2.5): 모호한 탐색, 미탐색 우선
    """
    if mode == "focus":
        return UCB_C_FOCUS
    if mode == "dmn":
        return UCB_C_DMN
    words = query.split()
    if len(words) >= 5:
        return UCB_C_FOCUS
    if len(words) <= 2:
        return UCB_C_DMN
    return UCB_C_AUTO


# ─── _bcm_update() — B-12 + B-10 통합 ────────────────────────────

def _bcm_update(
    result_ids: list[int],
    result_scores: list[float],
    all_edges: list[dict],
    query: str = "",
):
    """BCM 학습 + 재공고화 + visit_count 갱신 (단일 트랜잭션).

    BCM 공식: dw_ij/dt = η * ν_i * (ν_i - θ_m) * ν_j
      η   : 레이어별 학습률 (LAYER_ETA)
      ν_i : 소스 노드 활성화 강도 (정규화 score)
      θ_m : 슬라이딩 윈도우 제곱평균 (runaway reinforcement 방지)
      ν_j : 타깃 노드 활성화 강도

    B-5 재공고화: activated edge의 description에 사용 맥락 JSON 추가.
    visit_count: 결과 노드 전체에 +1 (UCB 다음 탐색 시 활용).

    3N + K UPDATEs (N=활성 edge 수, K=결과 노드 수), 1 commit.
    """
    if not result_ids:
        return

    id_set = set(result_ids)
    max_score = max(result_scores) if result_scores else 1.0
    score_map = {
        rid: (s / max_score if max_score > 0 else 0.0)
        for rid, s in zip(result_ids, result_scores)
    }
    now = datetime.now(timezone.utc).isoformat()

    activated_edges = [
        e for e in all_edges
        if e.get("source_id") in id_set and e.get("target_id") in id_set
    ]

    try:
        with sqlite_store._db() as conn:
            # 1. BCM edge 강도 갱신 + θ_m 업데이트 + 재공고화
            for edge in activated_edges:
                eid = edge["id"]
                src = edge["source_id"]
                tgt = edge["target_id"]
                v_i = score_map.get(src, 0.0)
                v_j = score_map.get(tgt, 0.0)

                # 소스 노드 메타 로드 (레이어별 η, θ_m, activity_history)
                row = conn.execute(
                    "SELECT layer, theta_m, activity_history FROM nodes WHERE id=?",
                    (src,),
                ).fetchone()
                if not row:
                    continue
                layer, theta_m, hist_raw = row
                theta_m = theta_m if theta_m is not None else 0.5
                eta = LAYER_ETA.get(layer or 2, 0.010)

                try:
                    history = json.loads(hist_raw) if hist_raw else []
                    if not isinstance(history, list):
                        history = []
                except (json.JSONDecodeError, ValueError):
                    history = []

                # BCM delta_w: 양수면 강화, 음수면 약화
                delta_w = eta * v_i * (v_i - theta_m) * v_j
                new_strength = max(0.01, min(2.0, (edge.get("strength") or 1.0) + delta_w))
                new_freq = max(0.0, (edge.get("frequency") or 0) + delta_w * 10)

                # θ_m: 슬라이딩 제곱평균 갱신
                history = (history + [v_i])[-BCM_HISTORY_WINDOW:]
                new_theta = sum(h ** 2 for h in history) / len(history)

                conn.execute(
                    "UPDATE edges SET frequency=?, strength=?, last_activated=? WHERE id=?",
                    (new_freq, new_strength, now, eid),
                )
                conn.execute(
                    "UPDATE nodes SET theta_m=?, activity_history=? WHERE id=?",
                    (new_theta, json.dumps(history), src),
                )

                # B-5 재공고화: edge.description에 맥락 JSON 추가
                if query:
                    raw = edge.get("description") or ""
                    try:
                        ctx_log = json.loads(raw) if raw else []
                        if not isinstance(ctx_log, list):
                            ctx_log = []
                    except (json.JSONDecodeError, ValueError):
                        ctx_log = []
                    ctx_log.append({"q": query[:80], "t": now})
                    ctx_log = ctx_log[-CONTEXT_HISTORY_LIMIT:]
                    conn.execute(
                        "UPDATE edges SET description=? WHERE id=?",
                        (json.dumps(ctx_log, ensure_ascii=False), eid),
                    )

            # 2. visit_count + last_accessed_at 갱신 (결과 노드 전부)
            for rid in result_ids:
                conn.execute(
                    "UPDATE nodes SET "
                    "visit_count = COALESCE(visit_count, 0) + 1, "
                    "last_accessed_at = ? "
                    "WHERE id=?",
                    (now, rid),
                )

            conn.commit()
    except Exception as e:
        logging.warning("BCM update failed: %s", e)  # BCM 실패가 검색을 중단시키지 않음


# ─── _sprt_check() — C-11 SPRT 승격 판정 ─────────────────────────

_SPRT_A = math.log((1 - SPRT_BETA) / SPRT_ALPHA)       # 승격 임계 ≈ 2.773
_SPRT_B = math.log(SPRT_BETA / (1 - SPRT_ALPHA))       # 기각 임계 ≈ -1.558
_SPRT_LLR_POS = math.log(SPRT_P1 / SPRT_P0)            # score>0.5 시 LLR ≈ 0.847
_SPRT_LLR_NEG = math.log((1 - SPRT_P1) / (1 - SPRT_P0))  # score≤0.5 시 LLR ≈ -0.847


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

    if len(history) < SPRT_MIN_OBS:
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


# ─── _log_recall_activations() — A-12 ────────────────────────────

def _log_recall_activations(
    results: list[dict],
    query: str,
    session_id: str | None = None,
):
    """recall 결과를 action_log에 기록 (A-12 설계).

    1행: recall 이벤트 요약 (action_type='recall')
    N행: 개별 노드 활성화 (action_type='node_activated')
    """
    try:
        from storage import action_log
        top_ids = [r["id"] for r in results[:10]]

        action_log.record(
            action_type="recall",
            actor="claude",
            session_id=session_id,
            params=json.dumps({
                "query": query[:200],
                "result_count": len(results),
                "top_ids": top_ids,
            }),
            result=json.dumps({
                "count": len(results),
                "top_scores": [round(r.get("score", 0), 4) for r in results[:5]],
            }),
        )

        for rank, node in enumerate(results[:10], 1):
            action_log.record(
                action_type="node_activated",
                actor="system",
                session_id=session_id,
                target_type="node",
                target_id=node["id"],
                params=json.dumps({
                    "context_query": query[:200],
                    "activation_score": round(node.get("score", 0), 4),
                    "activation_rank": rank,
                    "channel": "hybrid",
                    "node_type": node.get("type", ""),
                    "node_layer": node.get("layer"),
                }),
            )
    except ImportError:
        pass  # action_log 미구현 시 graceful skip
    except Exception as e:
        logging.warning("action_log failed: %s", e)  # 로깅 실패가 검색을 중단시키지 않음


# ─── Type-aware helpers ──────────────────────────────────────────

def _detect_type_hints(query: str) -> list[str]:
    """쿼리에서 타입 키워드 감지 → 매칭된 타입 리스트 (최대 MAX_TYPE_HINTS개)."""
    hints: list[str] = []
    for node_type, keywords in TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in query:
                hints.append(node_type)
                break
        if len(hints) >= MAX_TYPE_HINTS:
            break
    return hints


def _apply_type_diversity(candidates: list[dict], top_k: int, max_same_type_ratio: float = 0.6) -> list[dict]:
    """타입 다양성 보장 re-ranking. 한 타입이 top_k의 60% 이상 차지하면 교체."""
    if len(candidates) <= top_k:
        return candidates

    top = candidates[:top_k]
    rest = candidates[top_k:]

    type_counts: dict[str, int] = {}
    for c in top:
        t = c.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    max_allowed = max(1, int(top_k * max_same_type_ratio))

    for dominant_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        if count <= max_allowed:
            continue
        excess = count - max_allowed
        for _ in range(excess):
            # top에서 dominant_type의 최하위 항목 제거
            for i in range(len(top) - 1, -1, -1):
                if top[i].get("type") == dominant_type:
                    removed = top.pop(i)
                    rest.insert(0, removed)
                    break
            # rest에서 다른 타입의 최상위 항목 추가
            for j, r in enumerate(rest):
                if r.get("type") != dominant_type:
                    top.append(rest.pop(j))
                    break

    top.sort(key=lambda n: n.get("score", 0), reverse=True)
    return top[:top_k]


# ─── hybrid_search() ─────────────────────────────────────────────

def hybrid_search(
    query: str,
    type_filter: str = "",
    project: str = "",
    excluded_project: str = "",  # B-4: 패치 전환 시 제외 project
    top_k: int = DEFAULT_TOP_K,
    mode: str = "auto",          # B-12: "auto" | "focus" | "dmn"
) -> list[dict]:
    """3-way hybrid search: Vector + FTS5 + UCB Graph.

    변경 이력:
    - Phase 1: excluded_project, mode 파라미터 추가
    - Phase 1: traverse() → _ucb_traverse() 교체
    - Phase 1: _hebbian_update() → _bcm_update() 교체
    """
    _type_hints = _detect_type_hints(query)

    # 1. 벡터 유사도 검색 (ChromaDB)
    where = {}
    if type_filter:
        where["type"] = type_filter
    if project:
        where["project"] = project
    try:
        vec_results = vector_store.search(
            query, top_k=top_k * 4, where=where if where else None
        )
    except Exception:
        vec_results = []

    # 2. FTS5 키워드 검색 (SQLite)
    fts_results = sqlite_store.search_fts(query, top_k=top_k * 4)

    # 2b. Layer A: typed vector search (type hint 감지 시 추가 채널)
    typed_vec_by_type: dict[str, list] = {}
    if _type_hints:
        for hint_type in _type_hints:
            try:
                typed_where: dict = {"type": hint_type}
                if project:
                    typed_where["project"] = project
                t_results = vector_store.search(
                    query, top_k=top_k * 2, where=typed_where
                )
                typed_vec_by_type[hint_type] = t_results
            except Exception:
                pass

    # 3. seed_ids 수집 (벡터/FTS 상위 결과)
    seed_ids = []
    for node_id, _, _ in vec_results[:3]:
        seed_ids.append(node_id)
    for node_id, _, _ in fts_results[:3]:
        seed_ids.append(node_id)

    # 4. UCB 그래프 탐색 (B-12, B-16 TTL 캐시)
    c = _auto_ucb_c(query, mode=mode)
    if seed_ids:
        if c <= UCB_C_FOCUS:
            # focus 모드: SQL CTE로 빠르게 (NetworkX 불필요)
            graph_neighbors = _traverse_sql(seed_ids, depth=GRAPH_MAX_HOPS)
        else:
            # auto/dmn 모드: UCB 필요 → NetworkX 유지 (visit_count 기반 탐험)
            all_edges, graph = _get_graph()
            graph_neighbors = _ucb_traverse(graph, seed_ids, depth=GRAPH_MAX_HOPS, c=c)
    else:
        graph_neighbors = set()

    # 5. Reciprocal Rank Fusion + source tracking
    scores: dict[int, float] = defaultdict(float)
    source_map: dict[int, set] = defaultdict(set)
    for rank, (node_id, distance, _) in enumerate(vec_results, 1):
        scores[node_id] += 1.0 / (RRF_K + rank)
        source_map[node_id].add("vector")
    for rank, (node_id, _, _) in enumerate(fts_results, 1):
        scores[node_id] += 1.0 / (RRF_K + rank)
        source_map[node_id].add("fts5")
    for node_id in graph_neighbors:
        scores[node_id] += GRAPH_BONUS
        source_map[node_id].add("graph")

    # 5b. Layer A: typed vector RRF 채널 (타입별 동적 가중치)
    for hint_type, t_results in typed_vec_by_type.items():
        w = TYPE_CHANNEL_WEIGHTS.get(hint_type, TYPE_CHANNEL_WEIGHT)
        for rank, (node_id, distance, _) in enumerate(t_results, 1):
            scores[node_id] += w / (RRF_K + rank)
            source_map[node_id].add("typed_vector")

    # 6. 필터 + composite scoring (Phase 2: RRF + decay + importance)
    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    now_utc = datetime.now(timezone.utc)
    candidates = []
    for node_id in sorted_ids[:top_k * 10]:
        node = sqlite_store.get_node(node_id)
        if not node:
            continue
        if type_filter and node["type"] != type_filter:
            continue
        if project and node["project"] != project:
            continue
        if excluded_project and node["project"] == excluded_project:
            continue  # B-4: 포화된 패치 제외
        # base RRF score (enrichment + tier 포함)
        qs = node.get("quality_score") or 0.0
        tr = node.get("temporal_relevance") or 0.0
        enrichment_bonus = (
            qs * ENRICHMENT_QUALITY_WEIGHT + tr * ENRICHMENT_TEMPORAL_WEIGHT
        )
        tier = node.get("tier", 2)
        tier_bonus = {0: 0.15, 1: 0.05, 2: 0.0}.get(tier, 0.0)
        node["_base_rrf"] = scores[node_id] + enrichment_bonus + tier_bonus
        node["_sources"] = sorted(source_map.get(node_id, set()))
        candidates.append(node)

    if not candidates:
        return []

    for node in candidates:
        base = node["_base_rrf"]

        # importance from layer
        layer = node.get("layer")
        importance = LAYER_IMPORTANCE.get(layer, 0.1)

        # decay from last access (recency bonus)
        last_access_str = node.get("last_accessed_at") or node.get("updated_at")
        if last_access_str:
            try:
                dt = datetime.fromisoformat(last_access_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                days = max(0, (now_utc - dt).days)
            except (ValueError, TypeError):
                days = 365
        else:
            days = 365
        decay = importance * math.exp(-DECAY_LAMBDA * days)

        # additive composite: base + small bonuses
        score = (base +
                 COMPOSITE_WEIGHT_DECAY * decay +
                 COMPOSITE_WEIGHT_IMPORTANCE * importance)

        # promoted multiplier (promotion_candidate 플래그)
        if node.get("promotion_candidate"):
            score *= PROMOTED_MULTIPLIER

        node["score"] = score
        del node["_base_rrf"]

    candidates.sort(key=lambda n: n["score"], reverse=True)
    result = _apply_type_diversity(candidates, top_k)

    return result


# ─── background thread 관리 ──────────────────────────────────────

_bg_threads: list[threading.Thread] = []
_bg_threads_lock = threading.Lock()


def drain_background_jobs(timeout: float = 30.0) -> None:
    """모든 pending background thread를 완료까지 대기 (테스트/종료 시 사용)."""
    with _bg_threads_lock:
        threads = list(_bg_threads)
        _bg_threads.clear()
    for t in threads:
        t.join(timeout=timeout)


# ─── post_search_learn() — query/write 분리 ─────────────────────

def post_search_learn(
    results: list[dict],
    query: str,
    session_id: str | None = None,
) -> threading.Thread | None:
    """검색 후 학습.

    - 활성화 이벤트 로깅 (A-12): 동기 실행 (action_log 즉시 기록)
    - BCM + SPRT: background thread (compute-intensive)
    """
    if not results:
        return None

    # 1. 활성화 이벤트 로깅 — 동기 (즉시 action_log 기록 보장)
    _log_recall_activations(results, query, session_id=session_id)

    # 2. BCM + SPRT — background thread
    results_copy = [dict(r) for r in results]
    t = threading.Thread(
        target=_post_search_learn_impl,
        args=(results_copy, query),
        daemon=True,
    )
    with _bg_threads_lock:
        _bg_threads.append(t)
    t.start()
    return t


def _post_search_learn_impl(
    results: list[dict],
    query: str,
):
    """BCM + SPRT 학습 로직 (background)."""
    try:
        # 1. BCM 학습 + 재공고화 (B-12 + B-10)
        all_edges, _ = _get_graph()
        _bcm_update(
            [n["id"] for n in results],
            [n["score"] for n in results],
            all_edges,
            query=query,
        )

        # 2. SPRT 승격 판정 (C-11) — score를 0-1 정규화 후 판정
        try:
            with sqlite_store._db() as sprt_conn:
                max_score = results[0]["score"] if results else 1.0
                for node in results:
                    if node.get("type") == "Signal":
                        normalized = node.get("score", 0.0) / max_score if max_score > 0 else 0.0
                        if _sprt_check(node, normalized, sprt_conn):
                            sprt_conn.execute(
                                "UPDATE nodes SET promotion_candidate=1 WHERE id=?",
                                (node["id"],),
                            )
                sprt_conn.commit()
        except Exception as e:
            logging.warning("SPRT check failed: %s", e)
    except Exception as e:
        logging.warning("Background learn failed: %s", e)
