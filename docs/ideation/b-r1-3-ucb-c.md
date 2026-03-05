# B-3: UCB c값 동적 조절

> 세션 B | 2026-03-05 | 참조: `storage/hybrid.py` `traverse()`, `config.py` `EXPLORATION_RATE`

## 설계 목표

`EXPLORATION_RATE = 0.1` (고정 ε-greedy) → UCB 기반 동적 탐색/활용 균형.

뇌과학 매핑:
- **집중 모드** (c 낮음): 강한 연결 우선, 정확한 검색
- **DMN 모드** (c 높음): 약한 연결도 탐색, 이색적 접합 (뇌 DMN 20~30% vs 현재 10%)

수식: `Score(j) = w_ij + c · √(ln(N_i) / N_j)`

---

## config.py 추가값

```python
UCB_C_FOCUS = 0.3   # 집중: 강한 연결 우선
UCB_C_AUTO  = 1.0   # 기본 (EXPLORATION_RATE 교체)
UCB_C_DMN   = 2.5   # DMN: 약한 연결도 탐색
```

---

## 구현 스케치

```python
# storage/hybrid.py — traverse() 교체

def ucb_traverse(graph, seed_ids: list[int],
                 depth: int = 2, c: float = UCB_C_AUTO) -> set[int]:
    """UCB 기반 그래프 탐색.
    c 높을수록 미탐색 이웃 우선 → DMN 모드 (이색적 접합)
    c 낮을수록 강한 연결 우선 → 집중 모드 (정확한 검색)
    """
    visited = set(seed_ids)
    frontier = set(seed_ids)

    for _ in range(depth):
        candidates: list[tuple[float, int]] = []
        for nid in frontier:
            n_i = graph.nodes[nid].get('visit_count', 1)
            for nbr in graph.neighbors(nid):
                if nbr in visited:
                    continue
                w_ij = graph[nid][nbr].get('weight', 0.1)
                n_j  = graph.nodes[nbr].get('visit_count', 1)
                score = w_ij + c * math.sqrt(math.log(n_i + 1) / (n_j + 1))
                candidates.append((score, nbr))

        candidates.sort(reverse=True)
        next_frontier = {nbr for _, nbr in candidates[:20]}  # 폭발 방지
        visited.update(next_frontier)
        frontier = next_frontier

    return visited


def auto_ucb_c(query: str, mode: str = "auto") -> float:
    """쿼리 특성으로 c 자동 결정. 사용자 명시 시 우선."""
    if mode != "auto":
        return {"focus": UCB_C_FOCUS, "dmn": UCB_C_DMN}.get(mode, UCB_C_AUTO)
    words = query.split()
    if len(words) >= 5:   # 구체적·긴 쿼리 → 집중
        return UCB_C_FOCUS
    if len(words) <= 2:   # 짧고 추상적 → DMN
        return UCB_C_DMN
    return UCB_C_AUTO


# hybrid_search() 수정:
# c = auto_ucb_c(query, mode=mode)
# graph_neighbors = ucb_traverse(graph, seed_ids, depth=GRAPH_MAX_HOPS, c=c)

# recall() 파라미터 노출:
# def recall(query, ..., mode: str = "auto"):
#     results = hybrid_search(query, ..., mode=mode)
```

---

## N_i, N_j 추적

nodes 테이블에 `visit_count INTEGER DEFAULT 0` 컬럼 추가.
`_bcm_update()` 또는 `_hebbian_update()` 실행 시 함께 갱신:

```python
for node_id in result_ids:
    conn.execute(
        "UPDATE nodes SET visit_count = COALESCE(visit_count, 0) + 1 WHERE id=?",
        (node_id,)
    )
```

---

## DeepSeek 지적: Multi-Armed Bandit

고정 ε=0.1은 장기적으로 **선형 regret** 발생.
이론적 최적: 감쇠 ε (`ε_t = 1/t`) — 시간이 지날수록 탐색 줄이고 활용 증가.

UCB는 이미 방문 횟수 기반으로 자동 감쇠 구현 → 별도 감쇠 불필요.

---

## DB 변경

| 테이블 | 컬럼 | 타입 | 기본값 |
|---|---|---|---|
| nodes | `visit_count` | INTEGER | 0 |

## 검증
`ucb_traverse(c=2.5)` vs `c=0.3` — 반환 노드의 project 분포 비교.
DMN 모드에서 cross-domain 노드 비율이 높아야 성공.
