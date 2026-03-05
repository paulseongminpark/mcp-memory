# B-11: B-7 SQL CTE — 실제 교체 코드

> 세션 B | 2026-03-05 | 오케스트레이터 확정: 성능 1순위
> 참조: `storage/hybrid.py` L74-76, `graph/traversal.py`, `storage/sqlite_store.py`

## 결론 요약

| 항목 | 결정 |
|---|---|
| 교체 대상 | `hybrid.py` L75-76: `build_graph` + `traverse` → `traverse_sql` |
| `all_edges` | 유지 (L74) — `_hebbian_update` 의존, Phase 2에서 제거 |
| `build_graph` 완전 제거 | 불가 — `visualize.py:44`에서 사용 |
| 인덱스 | `idx_edges_source`, `idx_edges_target` 이미 존재 ✓ |

---

## 현재 코드 (교체 대상: hybrid.py L74-76)

```python
# hybrid.py L74-76 — 현재
all_edges = sqlite_store.get_all_edges()      # L74: 전체 edges 로드
graph = build_graph(all_edges)                 # L75: NetworkX 그래프 빌드
graph_neighbors = traverse(graph, seed_ids, depth=2) if seed_ids else set()  # L76: Python BFS
```

---

## build_graph 호출처 전체

| 파일 | 줄 | 처리 |
|---|---|---|
| `storage/hybrid.py:75` | L75 | **교체** (traverse_sql로) |
| `tools/visualize.py:44` | L44 | **유지** (그래프 시각화용) |
| `graph/traversal.py:11` | L11 | 정의 — 유지 |

→ `graph/traversal.py`의 `build_graph`, `traverse` 함수 **삭제 불가**.

---

## 인덱스 확인

```sql
-- 실행 확인용:
SELECT name, sql FROM sqlite_master
WHERE type = 'index' AND tbl_name = 'edges'
ORDER BY name;

-- 기대 결과 (sqlite_store.py에서 확인됨):
-- idx_edges_source : CREATE INDEX ... ON edges(source_id)
-- idx_edges_target : CREATE INDEX ... ON edges(target_id)
-- idx_edges_direction, idx_edges_relation 도 존재
```

**CTE 성능의 핵심**: `source_id`, `target_id` 인덱스 존재로 recursive join이 빠름. ✓

---

## traverse_sql() 구현

```python
# storage/hybrid.py에 추가 — _hebbian_update() 위에 삽입

def _traverse_sql(seed_ids: list[int], depth: int = 2) -> set[int]:
    """SQL Recursive CTE 기반 그래프 탐색. Chen (2014) DB-optimized SA.

    build_graph() + NetworkX BFS를 SQL로 대체.
    idx_edges_source, idx_edges_target 인덱스 활용.

    Args:
        seed_ids: 시작 노드 ID 목록
        depth: 탐색 깊이 (기본 GRAPH_MAX_HOPS=2)

    Returns:
        seed 제외, 도달 가능한 모든 이웃 노드 ID 집합
    """
    if not seed_ids:
        return set()

    ph = ",".join("?" * len(seed_ids))
    sql = f"""
    WITH RECURSIVE sa(id, hop) AS (
        -- 초기: seed 노드의 직접 이웃 (양방향)
        SELECT target_id, 1 FROM edges WHERE source_id IN ({ph})
        UNION
        SELECT source_id, 1 FROM edges WHERE target_id IN ({ph})
        UNION ALL
        -- 재귀: hop 제한 (depth-1 이하인 frontier에서 확장)
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
    # 파라미터: seed×2(초기 양방향) + depth-1×2(재귀 제한) + seed(seed 제외)
    params = seed_ids + seed_ids + [depth - 1, depth - 1] + seed_ids

    conn = None
    try:
        conn = sqlite_store._connect()
        rows = conn.execute(sql, params).fetchall()
        return {row[0] for row in rows}
    except Exception:
        return set()  # CTE 실패 시 빈 집합 (그래프 보너스 없이 계속)
    finally:
        if conn:
            conn.close()
```

---

## hybrid_search() 수정 (Phase 1 — 최소 변경)

```python
# storage/hybrid.py L74-76 교체

# === 변경 전 ===
all_edges = sqlite_store.get_all_edges()                                    # L74
graph = build_graph(all_edges)                                              # L75
graph_neighbors = traverse(graph, seed_ids, depth=2) if seed_ids else set() # L76

# === 변경 후 ===
all_edges = sqlite_store.get_all_edges()                  # L74: 유지 (_hebbian_update 의존)
graph_neighbors = _traverse_sql(seed_ids, depth=GRAPH_MAX_HOPS)  # L75-76 → 1줄로

# import 수정 (L11):
# 변경 전: from graph.traversal import build_graph, traverse
# 변경 후: (import 제거 또는 유지 — visualize.py는 별도 import)
# hybrid.py에서만 제거:
# L11 삭제
```

**변경 줄 수**: L75-76 삭제 후 1줄 추가 + L11 import 수정 = 3줄.

---

## Phase 2 (선택적 최적화): all_edges 제거

`_hebbian_update()`를 SQL IN 절로 리팩토링하면 `all_edges` 불필요:

```python
# Phase 2: _hebbian_update() 내부에서 직접 SQL 조회

def _hebbian_update(result_ids: list[int], all_edges: list[dict] = None,
                    query: str = ""):
    """Phase 2: all_edges 파라미터 무시, SQL로 직접 조회."""
    if not result_ids:
        return
    id_set = set(result_ids)
    ph = ",".join("?" * len(result_ids))
    now = datetime.now(timezone.utc).isoformat()

    conn = None
    try:
        conn = sqlite_store._connect()

        # 활성 edge 조회 (Python 순회 대신 SQL)
        rows = conn.execute(
            f"SELECT id, description FROM edges "
            f"WHERE source_id IN ({ph}) AND target_id IN ({ph})",
            result_ids + result_ids,
        ).fetchall()

        for eid, raw_desc in rows:
            conn.execute(
                "UPDATE edges SET frequency = COALESCE(frequency, 0) + 1, "
                "last_activated = ? WHERE id = ?",
                (now, eid),
            )
            if query:
                # 재공고화 맥락 (B-5)
                try:
                    ctx_log = json.loads(raw_desc) if raw_desc and raw_desc != '' else []
                    if not isinstance(ctx_log, list):
                        ctx_log = []
                except (json.JSONDecodeError, ValueError):
                    ctx_log = []
                ctx_log.append({"q": query[:80], "t": now})
                ctx_log = ctx_log[-CONTEXT_HISTORY_LIMIT:]
                conn.execute(
                    "UPDATE edges SET description = ? WHERE id = ?",
                    (json.dumps(ctx_log, ensure_ascii=False), eid),
                )

        conn.commit()
    except Exception:
        pass
    finally:
        if conn:
            conn.close()

# Phase 2 적용 시 hybrid_search() L74 제거:
# all_edges = sqlite_store.get_all_edges()  ← 삭제
# _hebbian_update([n["id"] for n in result], query=query)  ← all_edges 인수 제거
```

Phase 2 효과: `get_all_edges()` 제거 → 6,020 rows 메모리 로드 없음.

---

## 성능 비교

| 단계 | 현재 | Phase 1 | Phase 2 |
|---|---|---|---|
| all_edges 로드 | O(6K) | O(6K) 유지 | **제거** |
| 그래프 빌드 | O(6K) NetworkX | **제거** | **제거** |
| 이웃 탐색 | Python BFS O(k²) | SQL CTE (인덱스) | SQL CTE |
| 메모리 | 6K edges + nx.DiGraph | 6K edges only | **최소** |

---

## 검증

```python
import time

# Phase 1 전후 비교:
start = time.perf_counter()
results = hybrid_search("포트폴리오 설계")
print(f"elapsed: {(time.perf_counter()-start)*1000:.2f}ms")

# CTE 결과 직접 확인:
neighbors = _traverse_sql([100, 200, 300], depth=2)
print(f"neighbors: {len(neighbors)} nodes")
# 기대: 현재 traverse() 결과와 동일 (또는 유사)
```

**주의**: CTE UNION은 dedup 포함이므로 중복 없음.
현재 `traverse()`의 EXPLORATION_RATE 랜덤 탐험은 CTE에서 미구현.
→ UCB traverse (B-3)가 이를 대체하므로 생략 가능.
