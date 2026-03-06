# B-13: recall() 전체 흐름 다이어그램

> 세션 B | 2026-03-05
> B-4 패치 전환 + B-5 재공고화 + B-6 Pruning이 recall() 한 번 호출에서 일어나는 순서

## 현재 vs 목표 흐름

### 현재 (변경 전)

```
recall(query)
└── hybrid_search(query)
    ├── [READ] vector_store.search()          ChromaDB
    ├── [READ] sqlite_store.search_fts()      SQLite FTS5
    ├── [READ] sqlite_store.get_all_edges()   SQLite 6K rows
    ├── [CPU]  build_graph(all_edges)          NetworkX DiGraph 빌드
    ├── [CPU]  traverse(graph, seed_ids)       Python BFS
    ├── [READ] get_node() × top_k*2           SQLite ×10
    ├── [CPU]  RRF + enrichment 가중치
    └── [WRITE] _hebbian_update()             SQLite 1 conn, N edges
        └── frequency+1, last_activated
```

DB 쓰기: 1 트랜잭션, N updates (N ≈ 5~15 활성 edge)

---

### 목표 (B-4, B-5, B-7, UCB 적용 후)

```
recall(query, mode="auto")
│
├── hybrid_search(query, mode="auto")
│   ├── [READ]  vector_store.search()              ChromaDB
│   ├── [READ]  sqlite_store.search_fts()          FTS5
│   ├── [READ]  sqlite_store.get_all_edges()       SQLite 6K rows  ← Phase2에서 제거
│   ├── [CPU]   build_graph(all_edges)             NetworkX         ← UCB 위해 유지
│   ├── [CPU]   _auto_ucb_c(query, mode)           c값 결정
│   ├── [CPU]   _ucb_traverse(graph, seed_ids, c)  UCB BFS (B-3)
│   ├── [READ]  get_node() × top_k*2              SQLite ×10
│   ├── [CPU]   RRF + enrichment + tier 가중치
│   ├── [WRITE] _bcm_update(result, scores, edges, query)  ← 핵심 변경
│   │   ├── BCM: edge frequency 갱신 (B-1)
│   │   ├── BCM: theta_m + activity_history 갱신 (B-1)
│   │   ├── 재공고화: edges.description 맥락 추가 (B-5)
│   │   └── visit_count +1 per result node (B-3)
│   └── return result
│
├── [CPU] _is_patch_saturated(results)?            (B-4) 포화 체크
│
├── [선택적] hybrid_search() 2회차               (B-4) 포화 시만
│   └── (위 흐름 전체 반복, excluded_project 필터 추가)
│
└── [CPU] format results → return
```

---

## DB 쓰기 횟수 상세

### 정상 경로 (포화 없음)

| 단계 | SQL | 횟수 | 설명 |
|---|---|---|---|
| _bcm_update: edge frequency | UPDATE edges | N | 활성 edge 수 (보통 5~15) |
| _bcm_update: edge description | UPDATE edges | N | 재공고화 (B-5) |
| _bcm_update: node theta_m | UPDATE nodes | N | BCM θ_m (B-1) |
| _bcm_update: node visit_count | UPDATE nodes | K | 결과 노드 수 (=top_k, 보통 5) |
| **총 쓰기** | | **3N + K** | N≈10, K=5 → ~35 UPDATEs |
| **트랜잭션** | | **1** | 단일 conn.commit() |

### 포화 경로 (B-4 트리거)

```
정상 경로 × 2 (hybrid_search 2회 = 모든 쓰기 2배)
+ 패치 전환 후 재정렬 CPU 비용
```

포화 빈도: `project` 미지정 쿼리에서만 발생. 실제 발생률 낮음 (10~20% 예상).

---

## B-6 Pruning은 recall()에서 실행하지 않음

Pruning은 **daily_enrich.py 스케줄 작업**에서만 실행.
recall() 내 실행 이유 없음:
- 쓰기 비용 높음 (전체 edge 순회)
- 실시간 검색 응답 지연
- recall()은 읽기 중심 작업

Pruning 실행 시점: 매일 09:30 KST (daily_enrich.py Phase 6)

---

## 완전한 recall() 코드 스케치

```python
# tools/recall.py — 전체 교체 스케치

from storage.hybrid import hybrid_search
from storage import sqlite_store
from config import DEFAULT_TOP_K, PATCH_SATURATION_THRESHOLD


def recall(
    query: str,
    type_filter: str = "",
    project: str = "",
    top_k: int = DEFAULT_TOP_K,
    mode: str = "auto",   # "auto" | "focus" | "dmn"
) -> dict:
    # 1차 검색
    results = hybrid_search(
        query, type_filter=type_filter, project=project,
        top_k=top_k, mode=mode
    )

    if not results:
        return {"results": [], "message": "No memories found."}

    # B-4: 패치 전환 (포화 체크)
    if not project and _is_patch_saturated(results):
        dominant = _dominant_project(results)
        alt = hybrid_search(
            query, top_k=top_k, mode=mode,
            excluded_project=dominant
        )
        results = results[:top_k // 2] + alt[:top_k - top_k // 2]
        results.sort(key=lambda r: r["score"], reverse=True)

    # 포매팅 (기존 L19-37 유지)
    formatted = []
    for r in results:
        edges = sqlite_store.get_edges(r["id"])
        related = [
            f"{e['relation']}→#{e['target_id'] if e['source_id'] == r['id'] else e['source_id']}"
            for e in edges[:3]
        ]
        formatted.append({
            "id": r["id"],
            "type": r["type"],
            "content": r["content"][:200],
            "project": r["project"],
            "tags": r["tags"],
            "score": round(r["score"], 3),
            "created_at": r["created_at"],
            "related": related,
        })

    return {
        "results": formatted,
        "count": len(formatted),
        "message": f"Found {len(formatted)} memory(ies) for '{query}'",
    }


def _is_patch_saturated(results: list[dict]) -> bool:
    if len(results) < 3:
        return False
    projects = [r.get("project", "") for r in results]
    dominant = max(set(projects), key=projects.count)
    return projects.count(dominant) / len(projects) >= PATCH_SATURATION_THRESHOLD


def _dominant_project(results: list[dict]) -> str:
    projects = [r.get("project", "") for r in results]
    return max(set(projects), key=projects.count)
```

---

## 성능 영향 총평

| 항목 | 현재 | 목표 | 차이 |
|---|---|---|---|
| ChromaDB READ | 1회 | 1회 | 동일 |
| FTS5 READ | 1회 | 1회 | 동일 |
| all_edges READ | 1회 (6K) | 1회 (6K) | Phase2에서 제거 |
| 그래프 빌드 | 1회 (NetworkX) | 1회 (UCB용 유지) | 동일 |
| 그래프 탐색 | Python BFS | UCB BFS (최대 20노드/hop) | 더 제한적 |
| DB READ (nodes) | ×10 | ×10 | 동일 |
| DB WRITE | 1 트랜잭션, N × 2 col | 1 트랜잭션, N × 4 col + K | ~2배 쓰기 |
| 포화 시 2차 검색 | 없음 | 전체 흐름 반복 | 드물게 발생 |

**결론**: 쓰기 증가는 미미 (N≈10 × 2 UPDATE 추가). 읽기는 변화 없음.
UCB의 탐색 제한(top 20)으로 기존 무제한 BFS보다 안정적.

---

## 단계별 우선순위 재확인

```
Phase 1 구현 순서:
1. B-10 (재공고화): _hebbian_update() 수정 1회 + config 1줄 + 마이그레이션
2. B-11 Phase1 (CTE): hybrid.py L75-76 교체 + import 수정
3. B-4 (패치 전환): recall.py에 _is_patch_saturated + hybrid_search에 excluded_project
4. B-12 (BCM+UCB): DB 마이그레이션 + _bcm_update() + _ucb_traverse() 추가
```
