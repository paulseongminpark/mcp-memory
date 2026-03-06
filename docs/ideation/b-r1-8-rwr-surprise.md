# B-8: RWR + 놀라움 지수

> 세션 B | 2026-03-05 | 참조: `storage/hybrid.py` `hybrid_search()`
> **복잡도 높음 — scipy.sparse 최적화 또는 truncated RWR 필요**

## 설계 목표

확산 활성화에서 "예상치 못한" 노드에 보너스 부여.
DMN의 "이색적 접합"을 spreading activation 수준에서 구현.

핵심 개념:
- **RWR (Random Walk with Restart)**: PageRank의 개인화 버전. seed로 돌아오는 편향.
- **놀라움 지수**: `rwr_score / baseline_score - 1.0` (초과분)
  - baseline = 차수 기반 기대 활성화 확률
  - 차수 낮은 노드가 높은 RWR 점수 → "뜻밖의 연결" = 높은 놀라움

---

## 구현 스케치

```python
# storage/rwr.py (신규)

def random_walk_with_restart(graph, seed_id: int,
                              alpha: float = 0.15,
                              max_iter: int = 30) -> dict[int, float]:
    """RWR: 각 노드의 최종 활성화 확률 계산.
    alpha = restart 확률 (0.15 = PageRank damping factor 0.85에 대응).
    수렴 기준: max_iter 대신 delta < 1e-6 조건 추가 권장.
    """
    nodes = list(graph.nodes())
    r = {n: (1.0 if n == seed_id else 0.0) for n in nodes}

    for _ in range(max_iter):
        new_r = {}
        for node in nodes:
            nbrs = list(graph.neighbors(node))
            incoming = sum(
                r[nbr] * graph[nbr][node].get('weight', 1.0) /
                max(sum(graph[nbr][n].get('weight', 1.0)
                        for n in graph.neighbors(nbr)), 1e-9)
                for nbr in nbrs
            )
            new_r[node] = (
                (1 - alpha) * incoming
                + alpha * (1.0 if node == seed_id else 0.0)
            )
        r = new_r
    return r


def compute_baseline(graph) -> dict[int, float]:
    """차수 기반 기대 활성화 확률 (degree-normalized).
    허브 노드(높은 차수)는 당연히 자주 활성화됨 → baseline 높음.
    """
    degrees = dict(graph.degree(weight='weight'))
    total = sum(degrees.values()) or 1.0
    return {n: degrees[n] / total for n in graph.nodes()}


def surprise_score(rwr_score: float, baseline_score: float) -> float:
    """놀라움 = RWR가 기대(baseline)를 얼마나 초과했나.
    0 이상의 초과분만 반환 (기대 이하는 0).
    """
    if baseline_score < 1e-9:
        return 0.0
    return max(0.0, rwr_score / baseline_score - 1.0)
```

---

## hybrid_search() 통합

```python
# config.py 추가:
RWR_SURPRISE_WEIGHT = 0.1  # 놀라움 보너스 가중치
RWR_ALPHA = 0.15
RWR_MAX_ITER = 30

# hybrid_search() 수정 (4번 RRF 이후):
if seed_ids and len(graph.nodes()) > 0:
    rwr_r    = random_walk_with_restart(graph, seed_ids[0],
                                         alpha=RWR_ALPHA, max_iter=RWR_MAX_ITER)
    baseline = compute_baseline(graph)
    for node_id in scores:
        s = surprise_score(rwr_r.get(node_id, 0.0), baseline.get(node_id, 1e-9))
        scores[node_id] += RWR_SURPRISE_WEIGHT * s
```

---

## 성능 최적화 방안

### 문제
Python 반복 구현: 30K 노드 × 30 iter = 9M 연산 → 느림.

### 옵션 1: scipy.sparse (추천)
```python
import scipy.sparse as sp
import numpy as np

def rwr_sparse(adj_matrix: sp.csr_matrix, seed_idx: int,
               alpha: float = 0.15, max_iter: int = 30) -> np.ndarray:
    """행렬 곱 기반 RWR — 100x 이상 빠름."""
    n = adj_matrix.shape[0]
    # 열 정규화 (전이 행렬)
    col_sum = np.array(adj_matrix.sum(axis=0)).flatten()
    col_sum[col_sum == 0] = 1
    P = adj_matrix / col_sum

    r = np.zeros(n)
    r[seed_idx] = 1.0
    e = np.zeros(n)
    e[seed_idx] = 1.0

    for _ in range(max_iter):
        r = (1 - alpha) * P.dot(r) + alpha * e
    return r
```

### 옵션 2: Truncated RWR (간단)
전체 그래프 대신 seed 주변 2-hop 서브그래프에서만 계산:
```python
neighbors = traverse_sql(conn, seed_ids, depth=2)
subgraph = graph.subgraph(neighbors | set(seed_ids))
rwr_r = random_walk_with_restart(subgraph, seed_ids[0])
```
정확도는 약간 낮지만 속도 100x 개선. 현재 규모(3K 노드)에서는 충분.

---

## DB 변경
없음. 순수 계산 로직.

## 검증
놀라움 보너스가 붙은 노드의 type 분포 확인.
기대: Insight, Breakthrough 등 고가치 타입이 상위에 올라와야 함.
`RWR_SURPRISE_WEIGHT`가 너무 높으면 관련 없는 노드가 상위 진입 → 0.05로 낮추기.
