# Q5. 아카이브 정책 — 삭제 vs 비활성 vs 아카이브

## 현재 상태

**아카이브 정책 0.** `nodes.status`가 존재하지만 `'active'`만 사용 중.
3,230개 노드 전부 active. 가지치기 0회.

## 3단계 생명주기

```
active --+---> inactive ---> archived ---> (물리 삭제 없음)
         |
         +---> merged ---> (원본 유지, 대표 노드에 흡수)
```

| 상태 | recall()에 나오나 | 복구 가능 |
|------|------------------|----------|
| **active** | 예 | N/A |
| **inactive** | 아니오 (기본), 예 (`include_inactive=true`) | 즉시 |
| **archived** | 아니오 | 가능 (복원 필요) |
| **merged** | 아니오 | 가능 (분리 필요) |

## 비활성화 기준 (자동)

```python
INACTIVATION_RULES = {
    "L0_observation": {
        "condition": "layer=0 AND days_since_last_activated > 180",
        "action": "inactive",
    },
    "L1_low_quality": {
        "condition": "layer=1 AND quality_score < 0.3 AND days_since_created > 90",
        "action": "inactive",
    },
    "orphan_node": {
        "condition": "edge_count = 0 AND days_since_created > 60",
        "action": "inactive",
    },
    "duplicate": {
        "condition": "similarity > 0.95 with higher-quality node",
        "action": "merged",
    },
}
# L3+ 노드는 자동 비활성화 불가 (인지적 방화벽, Q6)
# tier=0 노드는 자동 비활성화 불가
```

## 아카이브 기준

```python
ARCHIVE_RULES = {
    "inactive_timeout": {
        "condition": "status='inactive' AND days_since_inactivated > 90",
        "action": "archived",
    },
}
```

## 복구 메커니즘

```python
def reactivate_node(node_id: int, reason: str) -> dict:
    # 1. status -> 'active'
    # 2. correction_log 기록
    # 3. edge 복원
    # 4. ChromaDB 재임베딩
    # 5. recall()에서 자동 발견
```

## "recall 시 자동 발견" — 망각의 역전

Storm et al.(2008): recall()이 inactive 노드와 높은 유사도 감지 시:
```python
if include_inactive_suggestions:
    inactive_similar = vector_store.search(query, top_k=3, filter={"status": "inactive"})
    if inactive_similar and inactive_similar[0].distance < 0.2:
        result["inactive_suggestions"] = [...]
```

## 물리 삭제 금지

아카이브 이후에도 물리 삭제는 Paul의 명시적 요청 시에만.
3,230 노드 전부 아카이브해도 SQLite < 50MB. 물리 삭제의 실익 없음.
