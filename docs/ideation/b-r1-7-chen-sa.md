# B-7: Chen의 SA 최적화 (SQL Recursive CTE)

> 세션 B | 2026-03-05 | 참조: `storage/hybrid.py` `traverse()`, `build_graph()`
> **성능 우선순위 1위 — NetworkX in-memory 제거, 100~500× 속도 개선**

## 설계 목표

Chen (2014): DB-optimized spreading activation이 이전 구현 대비 **500× 빠름**.
현재: `build_graph()` → NetworkX in-memory 로드 → Python BFS.
제안: SQLite Recursive CTE로 전체 교체.

---

## 현재 vs 제안 비교

| 항목 | 현재 | 제안 |
|---|---|---|
| 구현 방식 | Python NetworkX BFS | SQLite Recursive CTE |
| 속도 | 기준 | ~100~500× (Chen 2014) |
| 메모리 | `build_graph()` 전체 6,020 edges 로드 | DB 직접 쿼리 |
| 의존성 | NetworkX (in-memory graph) | SQLite (이미 존재) |
| 30K 스케일 | DeepSeek: O(k²) 유지, sub-ms | 동일 or 더 빠름 |

---

## 구현 스케치

```python
# storage/hybrid.py — traverse() 교체

def traverse_sql(conn, seed_ids: list[int], depth: int = 2) -> set[int]:
    """Chen (2014) DB-optimized spreading activation.
    SQL recursive CTE로 Python BFS 대체.

    주의: UNION (dedup) vs UNION ALL (성능) 선택.
    depth가 작을 때(2~3): UNION으로 dedup이 더 안전.
    """
    if not seed_ids:
        return set()

    ph = ','.join('?' * len(seed_ids))
    sql = f"""
    WITH RECURSIVE sa(id, hop) AS (
        -- 초기: seed 노드의 직접 이웃 (양방향 edge)
        SELECT target_id, 1 FROM edges WHERE source_id IN ({ph})
        UNION
        SELECT source_id, 1 FROM edges WHERE target_id IN ({ph})
        UNION ALL
        -- 재귀: hop 제한
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
    WHERE id NOT IN ({ph})  -- seed 자신 제외
    """
    params = seed_ids + seed_ids + [depth - 1, depth - 1] + seed_ids
    return {row[0] for row in conn.execute(sql, params).fetchall()}
```

---

## 통합 방법

```python
# hybrid_search() 수정:
# 변경 전:
# all_edges = sqlite_store.get_all_edges()
# graph = build_graph(all_edges)
# graph_neighbors = traverse(graph, seed_ids, depth=2) if seed_ids else set()

# 변경 후:
conn = sqlite_store._connect()
graph_neighbors = traverse_sql(conn, seed_ids, depth=GRAPH_MAX_HOPS) if seed_ids else set()
conn.close()

# build_graph() 호출 완전 제거 가능 — 단, UCB traverse(#3)는 NetworkX 유지
```

---

## UCB traverse와의 공존

- **단순 이웃 수집** (`GRAPH_BONUS` 계산용): `traverse_sql` 사용
- **UCB 가중치 탐색** (c값 기반): `ucb_traverse` (NetworkX 유지)

두 함수는 역할이 다름:
- `traverse_sql`: "어떤 노드가 이웃인가" → RRF 점수에 GRAPH_BONUS 가산
- `ucb_traverse`: "어떤 이웃을 탐색할 것인가" → 탐색 경로 자체를 결정

---

## 인덱스 추가 (성능 보장)

```sql
-- edges 테이블 인덱스 (이미 있을 수 있음, 없으면 추가)
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
```

Recursive CTE 성능은 이 인덱스에 크게 의존.

---

## DB 변경
없음 (인덱스만 확인/추가).

## 검증
```python
import time
# 변경 전후 hybrid_search() 응답시간 측정
start = time.perf_counter()
results = hybrid_search("포트폴리오 설계")
elapsed = time.perf_counter() - start
print(f"traverse: {elapsed*1000:.2f}ms")
```
기대: 현재 대비 50% 이상 단축 (6K edges 규모에서는 체감 낮을 수 있음, 30K에서 확실).
