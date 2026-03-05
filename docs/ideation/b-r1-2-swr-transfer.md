# B-2: SWR-SO-Spindle 조건부 전이

> 세션 B | 2026-03-05 | 참조: `tools/promote.py`

## 설계 목표

"이 Signal이 Pattern으로 전이될 준비가 되었는가"를 수치로 판단.
현재 **"3회 반복이면 Pattern"** 규칙 → `swr_readiness()` 교체.

뇌과학 매핑:
- **SWR (Sharp-Wave Ripples)**: 해마 재생 버스트 → 벡터 검색 히트율 증가
- **Slow Oscillations**: 신피질 게이트 → cross-domain 연결 강도
- **Spindles**: 쓰기 윈도우 → `swr_readiness()` 임계값 통과 시점

---

## 전제: recall_log 테이블 추가 필요

```sql
CREATE TABLE recall_log (
    id INTEGER PRIMARY KEY,
    node_id INTEGER,
    source TEXT,     -- 'vector' | 'fts5' | 'graph'
    query_hash TEXT, -- 중복 쿼리 집약 (MD5 앞 8자)
    recalled_at TEXT
);
```

`hybrid_search()` 내부에서 각 결과의 기여 소스를 로그로 기록:
```python
# hybrid_search() 결과 결합 후 추가:
for rank, (node_id, _, _) in enumerate(vec_results, 1):
    recall_log.insert(node_id, source='vector', query_hash=hash_query(query))
for rank, (node_id, _, _) in enumerate(fts_results, 1):
    recall_log.insert(node_id, source='fts5', query_hash=hash_query(query))
```

---

## 구현 스케치

```python
# tools/promote.py 내 (또는 storage/promotion.py 신규)
# config.py 추가: PROMOTION_SWR_THRESHOLD = 0.55

def swr_readiness(node_id: int) -> tuple[bool, float]:
    """
    지표 1 — vec_ratio (60% 가중치)
        FTS5 → ChromaDB 의존도 전환점 (Gemini 제안)
        vec_ratio > 0.6 → 의미적 연결 우세 → "신피질 전이 준비"
        텍스트 매칭 → 의미적 매칭으로 전환 = 해마→신피질 전이 시작점

    지표 2 — cross_ratio (40% 가중치)
        이웃 노드가 여러 project에 걸쳐 있는가
        피질간 연결성 proxy (Slow Oscillation의 "게이트" 역할)
    """
    # 지표 1
    rows = conn.execute(
        "SELECT source, COUNT(*) FROM recall_log WHERE node_id=? GROUP BY source",
        (node_id,)
    ).fetchall()
    counts = {row[0]: row[1] for row in rows}
    fts5_hits = counts.get('fts5', 0)
    vec_hits  = counts.get('vector', 0)
    total = fts5_hits + vec_hits
    vec_ratio = (vec_hits / total) if total > 0 else 0.0

    # 지표 2
    edges = sqlite_store.get_edges(node_id)
    neighbor_projects = {
        sqlite_store.get_node(
            e['target_id'] if e['source_id'] == node_id else e['source_id']
        )['project']
        for e in edges
    }
    cross_ratio = len(neighbor_projects) / max(len(edges), 1)

    readiness = 0.6 * vec_ratio + 0.4 * cross_ratio
    return readiness > PROMOTION_SWR_THRESHOLD, round(readiness, 3)


# promote_node() 내부 수정:
def promote_node(node_id: int, target_type: str) -> dict:
    ready, score = swr_readiness(node_id)
    if not ready:
        return {"status": "not_ready", "readiness_score": score}
    # ... 기존 승격 로직
```

---

## DB 변경

| 테이블 | 변경 | 용도 |
|---|---|---|
| (신규) recall_log | 4개 컬럼 | SWR 지표 1 (vec_ratio) |

## 검증
`swr_readiness(node_id)` 반환값 로그 → 임계값 0.55가 적절한지 3개월 후 검토.
false negative(준비됐는데 거부)가 많으면 임계값 낮추기.
