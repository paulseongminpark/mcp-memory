# B-R3-16: build_graph + all_edges 로드 최적화 방안

> 세션 B | Round 3 | 2026-03-05
> 참조: B-11(CTE), B-12(UCB NetworkX 의존), B-13(흐름)
> 문제: 매 recall마다 6K edges 로드 + NetworkX 빌드 반복

---

## 현재 병목 분석

### 실행 경로 (Phase 1 기준)

```
hybrid_search() 매 호출마다:
  get_all_edges()       → SQLite 6,020 rows 읽기    ~6ms
  build_graph(all_edges)→ NetworkX DiGraph 빌드       ~8ms
  _bcm_update(all_edges)→ 활성 edge 탐색 (Python)    ~1ms
  ─────────────────────────────────────────────────────────
  graph 관련 소계                                    ~15ms / recall
```

### 성장 예측

| 시점 | edges 수 | get_all_edges | build_graph | 합계 |
|---|---|---|---|---|
| 현재 (2026-03) | 6,020 | ~6ms | ~8ms | ~15ms |
| 6개월 후 | ~10,000 | ~10ms | ~15ms | ~25ms |
| 1년 후 | ~18,000 | ~18ms | ~28ms | ~46ms |

recall 총 지연: 현재 ~50-80ms. graph 관련이 20~30% 차지.

### UCB의 NetworkX 의존 구조

`_ucb_traverse(graph, ...)` 가 필요로 하는 것:

```python
graph.nodes[nid].get("visit_count", 1)  # 노드 속성
graph.to_undirected(as_view=True)        # 양방향 뷰
undirected.neighbors(nid)                # 인접 노드 목록
graph.edges[nid, nbr].get("strength", 0.1)  # edge 속성
```

`build_graph()` 가 `visit_count`, `strength` 를 노드/edge 속성에 주입.
→ NetworkX 없이 UCB 구현하려면 별도 SQL 조회 필요.

### all_edges의 두 가지 역할

```
all_edges (6K rows Python list)
  ├── build_graph(all_edges)  → UCB graph 빌드용
  └── _bcm_update(all_edges)  → activated edge 탐색용
```

두 역할 모두 동일한 객체를 참조. 하나 제거 시 다른 쪽도 영향받음.

---

## 제약 조건 (제거 불가 이유)

1. **UCB는 `build_graph` 의존** — `nx.DiGraph` 구조 없이 UCB 불가
2. **`build_graph`는 `all_edges` 의존** — edges 없이 그래프 빌드 불가
3. **`_bcm_update`는 `all_edges` 의존** — Phase 2에서 SQL로 전환 가능 (B-11)
4. **`visualize.py:44`도 `build_graph` 사용** — hybrid.py와 독립적으로 유지

Phase 1에서 완전 제거는 불가. 최적화 옵션 3가지 검토.

---

## Option A: 모듈 레벨 TTL 캐싱 (즉시 적용 권장)

### 구현

```python
# storage/hybrid.py 상단에 추가 (3줄)
import time

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
        _GRAPH_CACHE = (all_edges, graph)
        _GRAPH_CACHE_TS = now
    return _GRAPH_CACHE
```

`hybrid_search()` 내 L74-75 교체:

```python
# 변경 전:
all_edges = sqlite_store.get_all_edges()
graph = build_graph(all_edges)

# 변경 후:
all_edges, graph = _get_graph()
```

### 성능 영향

```
캐시 미스 (5분마다 1회): 현재와 동일 ~15ms
캐시 히트 (5분 내 재사용): ~0ms (dict lookup + return)

5분간 10회 recall 가정:
  현재:  10 × 15ms = 150ms (graph 관련)
  캐시:  1 × 15ms + 9 × 0ms = 15ms (90% 절약)
```

### 안전성 검토

| 우려 | 분석 | 결론 |
|---|---|---|
| 새 edge가 즉시 반영 안 됨 | enrichment 배치 단위 추가, 실시간 무관 | 수용 가능 |
| visit_count 스테일 | UCB는 방향성 정확도가 중요 (절대값 X) | 수용 가능 |
| 멀티 프로세스 캐시 불일치 | MCP 서버 = 단일 프로세스 | 문제 없음 |
| 메모리 상주 | 6K edges (~1MB) + DiGraph (~2-3MB) | 수용 가능 |

### 평가: 즉시 적용 가능. 코드 변경 최소 (5줄). 위험 없음.

---

## Option B: Phase 2 — all_edges 완전 제거

B-11에서 이미 설계 완료. `_bcm_update()`를 SQL IN 조회로 전환.

```python
# _bcm_update() Phase 2 버전 (B-11 설계)
def _bcm_update(result_ids: list[int], result_scores: list[float],
                all_edges=None, query: str = ""):
    """all_edges 파라미터 무시 — SQL로 직접 activated edges 조회."""
    if not result_ids:
        return
    ph = ",".join("?" * len(result_ids))
    ...
    conn.execute(
        f"SELECT id, source_id, target_id, frequency, description "
        f"FROM edges WHERE source_id IN ({ph}) AND target_id IN ({ph})",
        result_ids + result_ids,
    ).fetchall()
```

`get_all_edges()` 제거 조건:
1. `_bcm_update()` SQL 전환 ✓ (위)
2. `build_graph()` 제거 — UCB를 SQL-only로 전환해야 함 (Option C)

단독으로는 `build_graph`가 여전히 `all_edges` 필요.
**Option B는 Option C와 함께 적용해야 완전 제거 가능.**

---

## Option C: SQL-only UCB (NetworkX 완전 제거, Phase 2)

UCB 계산을 SQL + Python 혼합으로 구현. `build_graph` 불필요.

### 구현

```python
def _ucb_traverse_sql(
    seed_ids: list[int],
    depth: int = 2,
    c: float = 1.0,
) -> set[int]:
    """SQL + Python 혼합 UCB 탐색. NetworkX 불필요.

    매 hop마다 SQL로 이웃 + strength + visit_count 조회 후
    Python에서 UCB 점수 계산, 상위 20개 선택.
    """
    if not seed_ids:
        return set()

    visited = set(seed_ids)
    frontier = list(seed_ids)
    conn = sqlite_store._connect()

    try:
        for _ in range(depth):
            if not frontier:
                break
            ph = ",".join("?" * len(frontier))

            # 양방향 이웃 + UCB 계산에 필요한 속성 조회
            rows = conn.execute(f"""
                SELECT e.target_id AS nbr, e.strength,
                       n_src.visit_count AS n_i,
                       n_tgt.visit_count AS n_j
                FROM edges e
                JOIN nodes n_src ON n_src.id = e.source_id
                JOIN nodes n_tgt ON n_tgt.id = e.target_id
                WHERE e.source_id IN ({ph})

                UNION ALL

                SELECT e.source_id AS nbr, e.strength,
                       n_tgt.visit_count AS n_i,
                       n_src.visit_count AS n_j
                FROM edges e
                JOIN nodes n_src ON n_src.id = e.source_id
                JOIN nodes n_tgt ON n_tgt.id = e.target_id
                WHERE e.target_id IN ({ph})
            """, frontier + frontier).fetchall()

            candidates: list[tuple[float, int]] = []
            for nbr, strength, n_i, n_j in rows:
                if nbr in visited:
                    continue
                w = strength or 0.1
                n_i = max(n_i or 1, 1)
                n_j = max(n_j or 1, 1)
                score = w + c * math.sqrt(math.log(n_i + 1) / (n_j + 1))
                candidates.append((score, nbr))

            candidates.sort(reverse=True)
            next_frontier = [nbr for _, nbr in candidates[:20]]
            visited.update(next_frontier)
            frontier = next_frontier

        return visited - set(seed_ids)
    finally:
        conn.close()
```

### 주의: SQLite math 함수 가용성

`math.sqrt()`, `math.log()` — Python `math` 모듈 사용 (SQL 내장 X).
SQL에서는 `sqrt()`, `log()` 사용 가능하나 SQLite 3.35+ + `SQLITE_ENABLE_MATH_FUNCTIONS` 필요.
→ Python에서 계산하는 현재 설계가 더 안전.

### Phase 2 전환 시 hybrid_search() 변경

```python
# Phase 2 — 변경 전 (Phase 1):
all_edges = sqlite_store.get_all_edges()
graph = build_graph(all_edges)
c = _auto_ucb_c(query, mode=mode)
graph_neighbors = _ucb_traverse(graph, seed_ids, ...) if seed_ids else set()

# Phase 2 — 변경 후:
c = _auto_ucb_c(query, mode=mode)
graph_neighbors = _ucb_traverse_sql(seed_ids, depth=GRAPH_MAX_HOPS, c=c) if seed_ids else set()
# all_edges 불필요 → get_all_edges() 라인 삭제
# build_graph 불필요 → import도 제거 가능
```

### Option C 성능 비교

| 항목 | 현재 (Phase 1) | Option C (Phase 2) |
|---|---|---|
| get_all_edges() | 6K rows, ~6ms | **제거** |
| build_graph() | ~8ms | **제거** |
| UCB 탐색 | Python (in-memory) | SQL + Python (DB I/O) |
| 탐색 SQL | 없음 | depth × 2 쿼리 (=4 쿼리) |
| 예상 총 비용 | ~15ms | ~5ms (SQL 조회 최적화 시) |
| 메모리 | ~3MB (edges + nx) | ~0MB (스트리밍) |

SQL 4쿼리의 실제 비용: idx_edges_source/target 인덱스 활용 시 hop당 ~1-2ms.

---

## 권고안

### Phase 1 즉시: Option A (TTL 캐싱)

```
구현 비용: 10줄 추가
위험도: 없음 (단일 프로세스, 캐시 불일치 없음)
효과: 연속 recall 시 ~90% graph 비용 절감
```

### Phase 2: Option B + C 동시 적용

```
순서:
1. _ucb_traverse_sql() 구현 + 테스트
2. hybrid_search()에서 _ucb_traverse → _ucb_traverse_sql 교체
3. get_all_edges() + build_graph() 제거
4. _bcm_update() all_edges → SQL 내부 조회로 전환
5. from graph.traversal import build_graph 제거 (visualize.py 독립 유지)

효과: ~15ms → ~5ms. 메모리 3MB 절약.
위험: SQL 쿼리 정확성 검증 필요 (양방향 UNION ALL 중복 처리)
```

---

## Phase 로드맵 정리

```
Phase 1 (지금):
  hybrid_search()
    └── get_all_edges()     [6K rows, ~6ms]
    └── build_graph()       [NetworkX, ~8ms]
    └── _ucb_traverse()     [NetworkX 의존]
    └── _bcm_update(all_edges) [Python 탐색]

Phase 1 + Option A (즉시 개선):
  hybrid_search()
    └── _get_graph()        [TTL cache: 5분 1회만 빌드]
    └── _ucb_traverse()     [동일]
    └── _bcm_update(all_edges) [동일]

Phase 2 (Option B+C):
  hybrid_search()
    └── _ucb_traverse_sql() [SQL + Python, ~5ms]
    └── _bcm_update()       [SQL IN 직접 조회, all_edges 제거]
    // get_all_edges(), build_graph() 완전 제거
```

---

## 부록: _traverse_sql() vs _ucb_traverse_sql() 차이

| 항목 | `_traverse_sql()` (B-11) | `_ucb_traverse_sql()` (신규) |
|---|---|---|
| 탐색 방식 | BFS (모든 이웃) | UCB 가중 (상위 20개/hop) |
| SQL 구조 | Recursive CTE | UNION ALL (반복 호출) |
| 탐색 범위 | depth 내 모든 노드 | UCB score 상위 노드만 |
| visit_count 활용 | 없음 | UCB 공식에 활용 |
| Phase 1 사용 | 보조 (미사용) | Phase 2 메인 |

Phase 2 전환 시 `_traverse_sql()`은 삭제하지 않고 유지 (fallback + 테스트용).
