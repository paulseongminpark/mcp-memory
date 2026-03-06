# B-12: BCM + UCB 통합 설계

> 세션 B | 2026-03-05 | 오케스트레이터 확정: BCM 직행 (D세션 tanh 단계 없음)
> 참조: `storage/hybrid.py`, `graph/traversal.py`

## 실행 순서 (recall() 전체 흐름에서)

```
hybrid_search(query, mode="auto")
├── 1. 벡터 검색 (ChromaDB)
├── 2. FTS5 검색 (SQLite)
├── 3. seed_ids 수집
├── 4. [UCB] ucb_traverse(graph, seed_ids, c=auto_ucb_c(query)) ← UCB 탐색
├── 5. RRF 점수 통합
├── 6. 노드 필터 + enrichment 가중치 + 정렬
└── 7. [BCM] _bcm_update(result, all_edges, query)               ← BCM + 재공고화
    └── visit_count 갱신도 여기서 함께
```

UCB는 탐색 경로 결정 (어떤 이웃을 볼지).
BCM은 학습 결과 반영 (어떤 edge를 강화/약화할지).

---

## UCB traverse 구현

### 전제
`build_graph(all_edges)` 호출은 UCB traverse 때문에 유지.
(SQL CTE는 단순 이웃 수집용, UCB는 가중치 기반 경로 결정용)

```python
# storage/hybrid.py에 추가

import math
from config import UCB_C_FOCUS, UCB_C_AUTO, UCB_C_DMN  # config.py에 추가

def _ucb_traverse(graph: "nx.DiGraph", seed_ids: list[int],
                  depth: int = 2, c: float = UCB_C_AUTO) -> set[int]:
    """UCB 기반 그래프 탐색.
    Score(j) = w_ij + c · √(ln(N_i + 1) / (N_j + 1))
    c 높음 → 미탐색 이웃 우선 (DMN 모드)
    c 낮음 → 강한 연결 우선 (집중 모드)
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
                # edge 강도 (양방향 중 존재하는 쪽)
                if graph.has_edge(nid, nbr):
                    w_ij = graph.edges[nid, nbr].get("strength", 0.1)
                elif graph.has_edge(nbr, nid):
                    w_ij = graph.edges[nbr, nid].get("strength", 0.1)
                else:
                    w_ij = 0.1
                n_j = graph.nodes[nbr].get("visit_count", 1)
                score = w_ij + c * math.sqrt(math.log(n_i + 1) / (n_j + 1))
                candidates.append((score, nbr))

        # 상위 20개만 탐색 (폭발 방지)
        candidates.sort(reverse=True)
        next_frontier = {nbr for _, nbr in candidates[:20]}
        visited.update(next_frontier)
        frontier = next_frontier

    return visited - set(seed_ids)  # seed 자신 제외


def _auto_ucb_c(query: str, mode: str = "auto") -> float:
    """쿼리 특성으로 c 자동 결정."""
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
```

### hybrid_search() 수정 (L75-76)

```python
# 현재 L75-76:
graph = build_graph(all_edges)
graph_neighbors = traverse(graph, seed_ids, depth=2) if seed_ids else set()

# 변경 후 (UCB 적용, mode 파라미터 추가):
graph = build_graph(all_edges)
c = _auto_ucb_c(query, mode=mode)
graph_neighbors = _ucb_traverse(graph, seed_ids, depth=GRAPH_MAX_HOPS, c=c) if seed_ids else set()

# hybrid_search() 시그니처에 mode 추가:
def hybrid_search(query: str, type_filter: str = "", project: str = "",
                  top_k: int = DEFAULT_TOP_K, mode: str = "auto") -> list[dict]:
```

---

## BCM 구현

### 전제: DB 마이그레이션

```sql
-- nodes 테이블 컬럼 추가
ALTER TABLE nodes ADD COLUMN theta_m REAL DEFAULT 0.5;
ALTER TABLE nodes ADD COLUMN activity_history TEXT DEFAULT '[]';
ALTER TABLE nodes ADD COLUMN visit_count INTEGER DEFAULT 0;

-- 기존 3,230 노드: θ_m=0.5, activity_history='[]', visit_count=0 자동 적용
-- (ALTER TABLE DEFAULT가 기존 행에 적용됨 — SQLite 동작 확인됨)
```

**컬럼명**: `θ_m`은 SQLite에서 유니코드 허용이나, 안전하게 `theta_m` 사용.

### BCM 구현 코드

```python
# storage/hybrid.py — _hebbian_update() 교체 (B-10 통합 버전)

LAYER_ETA: dict[int, float] = {
    0: 0.020,   # L0 Observation: 빠른 변화
    1: 0.015,   # L1 Signal
    2: 0.010,   # L2 Pattern/Insight/Framework (기본)
    3: 0.005,   # L3 Principle
    4: 0.001,   # L4 Belief/Philosophy
    5: 0.0001,  # L5 Value: 거의 고정
}
BCM_HISTORY_WINDOW = 20

def _bcm_update(result_ids: list[int], result_scores: list[float],
                all_edges: list[dict], query: str = ""):
    """BCM 학습 + 재공고화 + visit_count 갱신 (단일 트랜잭션).

    dw_ij/dt = η · ν_i · (ν_i - θ_m) · ν_j
    θ_m: 슬라이딩 윈도우 제곱평균 (runaway reinforcement 방지)
    """
    if not result_ids:
        return
    id_set = set(result_ids)
    # score 정규화 (0~1)
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

    conn = None
    try:
        conn = sqlite_store._connect()

        # 1. BCM: edge 강도 갱신
        for edge in activated_edges:
            eid = edge["id"]
            src = edge["source_id"]
            tgt = edge["target_id"]
            ν_i = score_map.get(src, 0.0)
            ν_j = score_map.get(tgt, 0.0)

            # 소스 노드 메타 로드
            row = conn.execute(
                "SELECT layer, theta_m, activity_history FROM nodes WHERE id=?",
                (src,)
            ).fetchone()
            if not row:
                continue
            layer, θ_m, hist_raw = row
            θ_m = θ_m if θ_m is not None else 0.5
            η = LAYER_ETA.get(layer or 2, 0.010)

            try:
                history = json.loads(hist_raw) if hist_raw else []
                if not isinstance(history, list):
                    history = []
            except (json.JSONDecodeError, ValueError):
                history = []

            # BCM delta
            delta_w = η * ν_i * (ν_i - θ_m) * ν_j
            new_freq = max(0.0, (edge.get("frequency") or 0) + delta_w * 10)

            # θ_m 업데이트: 슬라이딩 제곱평균
            history = (history + [ν_i])[-BCM_HISTORY_WINDOW:]
            new_θ = sum(h ** 2 for h in history) / len(history)

            conn.execute(
                "UPDATE edges SET frequency=?, last_activated=? WHERE id=?",
                (new_freq, now, eid),
            )
            conn.execute(
                "UPDATE nodes SET theta_m=?, activity_history=? WHERE id=?",
                (new_θ, json.dumps(history), src),
            )

            # B-5 재공고화: description 맥락 추가
            if query:
                raw = edge.get("description") or ""
                try:
                    ctx_log = json.loads(raw) if raw and raw != "" else []
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

        # 2. visit_count 갱신 (결과 노드 전부)
        for rid in result_ids:
            conn.execute(
                "UPDATE nodes SET visit_count = COALESCE(visit_count, 0) + 1 WHERE id=?",
                (rid,),
            )

        conn.commit()
    except Exception:
        pass
    finally:
        if conn:
            conn.close()
```

---

## θ_m 초기값 마이그레이션 (기존 3,230 노드)

```sql
-- SQLite: ALTER TABLE ADD COLUMN은 DEFAULT를 기존 행에 즉시 적용하지 않음
-- (값은 NULL로 저장, SELECT 시 DEFAULT 반환)
-- 실제 값으로 채우려면:

UPDATE nodes SET theta_m = 0.5 WHERE theta_m IS NULL;
UPDATE nodes SET activity_history = '[]' WHERE activity_history IS NULL;
UPDATE nodes SET visit_count = 0 WHERE visit_count IS NULL;
```

**SQLite의 ALTER TABLE 동작**: DEFAULT는 새 행에만 적용. 기존 행은 NULL.
위 UPDATE로 명시적 초기화 필요.

---

## hybrid_search() 최종 변경 요약

```python
def hybrid_search(query: str, type_filter: str = "", project: str = "",
                  top_k: int = DEFAULT_TOP_K, mode: str = "auto") -> list[dict]:
    # ... (L53-73 동일)

    all_edges = sqlite_store.get_all_edges()          # L74 유지
    graph = build_graph(all_edges)                    # L75 유지 (UCB 필요)
    c = _auto_ucb_c(query, mode=mode)                 # 신규
    graph_neighbors = (                               # L76 교체
        _ucb_traverse(graph, seed_ids, depth=GRAPH_MAX_HOPS, c=c)
        if seed_ids else set()
    )

    # ... (L78-113 동일)

    _bcm_update(                                      # L116 교체
        [n["id"] for n in result],
        [n["score"] for n in result],
        all_edges,
        query=query,
    )

    return result
```

---

## visit_count 갱신 위치 결정

**결론**: `_bcm_update()` 내부에서 함께 갱신.
이유:
- 같은 트랜잭션이므로 원자적 처리
- edge 갱신 시 노드도 함께 접근하므로 추가 비용 없음
- 별도 함수로 분리하면 conn 2회 열기 필요

---

## config.py 추가값 전체

```python
# UCB 탐색 모드
UCB_C_FOCUS = 0.3
UCB_C_AUTO  = 1.0
UCB_C_DMN   = 2.5

# BCM 학습
BCM_HISTORY_WINDOW = 20   # θ_m 계산용 슬라이딩 윈도우

# 재공고화 (B-5)
CONTEXT_HISTORY_LIMIT = 5
```
