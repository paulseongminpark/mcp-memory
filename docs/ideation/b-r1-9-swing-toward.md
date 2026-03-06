# B-9: Swing-toward 재연결

> 세션 B | 2026-03-05 | 참조: `daily_enrich.py`
> **PyTorch 불필요 — NetworkX로 충분. daily_enrich 마지막 단계.**

## 설계 목표

차수 보존하면서 클러스터링 계수를 높이는 알고리즘.
고립된 노드들이 군집을 형성하도록 edge를 재배선 → 지식 클러스터 강화.

뇌과학 매핑:
- 사용 안 하는 시냅스 제거 + 관련 시냅스 강화 = 시냅스 가지치기 + 재조직
- 클러스터링 계수 증가 = 같은 도메인 내 개념들이 더 촘촘히 연결

---

## PyTorch 필요? → **불필요**

| 옵션 | 속도 | 복잡도 | 결론 |
|---|---|---|---|
| NetworkX (로컬 CC) | ms 수준 | 낮음 | **선택** |
| NetworkX (전체 CC) | 초 수준 | 낮음 | 너무 느림 |
| PyTorch geometric | ms 수준 | 높음 | 과잉 |

로컬 CC (영향받는 4노드만) 계산 → 전체 CC 재계산 불필요.

---

## 구현 스케치

```python
# storage/graph_ops.py (신규)

import networkx as nx
import random
from typing import list

def local_clustering_delta(graph: nx.Graph, a: int, b: int,
                            c: int, d: int) -> float:
    """swap (a-b, c-d) → (a-c, b-d) 시 로컬 CC 변화량.
    영향받는 4노드만 계산 → 전체 CC 재계산 대비 훨씬 빠름.
    """
    affected = {a, b, c, d}
    before = sum(nx.clustering(graph, n) for n in affected)

    # 임시 swap
    graph.remove_edge(a, b); graph.remove_edge(c, d)
    graph.add_edge(a, c);    graph.add_edge(b, d)
    after = sum(nx.clustering(graph, n) for n in affected)

    # 반드시 롤백
    graph.remove_edge(a, c); graph.remove_edge(b, d)
    graph.add_edge(a, b);    graph.add_edge(c, d)

    return after - before


def swing_toward(graph: nx.Graph, n_rounds: int = 200) -> list[tuple]:
    """Maslov-Sneppen 변형: 차수 보존 + 클러스터링 증가.
    개선되는 swap만 수용 (hill-climbing).

    Returns:
        applied: DB에 반영할 edge 변경 목록
                 [((a, b), (c, d)), ...]  — (a-b), (c-d) 제거 → (a-c), (b-d) 추가
    """
    edges = list(graph.edges())
    applied = []

    for _ in range(n_rounds):
        if len(edges) < 2:
            break

        e1, e2 = random.sample(edges, 2)
        a, b = e1; c, d = e2

        # 유효성 검사
        if len({a, b, c, d}) < 4:                        # 노드 중복 방지
            continue
        if graph.has_edge(a, c) or graph.has_edge(b, d):  # 멀티엣지 방지
            continue

        # 클러스터링 개선 시에만 swap 수용
        if local_clustering_delta(graph, a, b, c, d) >= 0:
            graph.remove_edge(a, b); graph.remove_edge(c, d)
            graph.add_edge(a, c);    graph.add_edge(b, d)
            # edges 목록 동기화
            edges.remove(e1); edges.remove(e2)
            edges += [(a, c), (b, d)]
            applied.append((e1, e2))  # 제거된 pair 기록

    return applied
```

---

## DB 반영

```python
# daily_enrich.py 마지막 단계에서:

def apply_swing_toward_to_db(conn, applied_swaps: list[tuple]):
    """swing_toward() 결과를 SQLite edges에 반영.
    실제 edge ID 조회 후 source/target 업데이트.
    """
    for (a, b), (c, d) in applied_swaps:
        # a-b edge를 a-c로 수정
        conn.execute(
            "UPDATE edges SET target_id=? WHERE source_id=? AND target_id=?",
            (c, a, b)
        )
        # c-d edge를 b-d로 수정
        conn.execute(
            "UPDATE edges SET source_id=? WHERE source_id=? AND target_id=?",
            (b, c, d)
        )
    conn.commit()
```

---

## 실행 시점

`daily_enrich.py` 마지막 단계 (B-6 Pruning 이후):
```python
# daily_enrich.py Phase 7 (신규):
graph = build_graph(sqlite_store.get_all_edges())
applied = swing_toward(graph, n_rounds=200)
apply_swing_toward_to_db(conn, applied)
log.info(f"swing_toward: {len(applied)} swaps applied")
```

---

## 한계 및 고려사항

1. **edge 속성 손실**: swap 시 edge의 relation type, frequency 등 보존 필요
   → `UPDATE edges SET source_id=?, target_id=?` 대신 relation도 함께 검토
2. **directed vs undirected**: edges 테이블이 방향 있음. 양방향 처리 주의
3. **n_rounds 조절**: 6K edges에서 200 rounds는 소수만 영향. 더 많이 해도 무방

---

## DB 변경
없음.

## 검증
```python
cc_before = nx.average_clustering(graph_before)
cc_after  = nx.average_clustering(graph_after)
print(f"CC: {cc_before:.4f} → {cc_after:.4f} (+{cc_after-cc_before:.4f})")
```
기대: 0.001~0.01 수준 미세 개선. 200 rounds에서 10~30 swaps 정도 적용됨.
