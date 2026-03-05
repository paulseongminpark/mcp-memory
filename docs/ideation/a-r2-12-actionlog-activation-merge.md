# 심화 4: action_log + activation_log 통합 설계

> A-9 action_log(확정 1순위) + D-5 activation_log → 단일 테이블 통합
> 원칙: activation_log는 action_log의 VIEW/subset으로 구현

---

## D-5가 원하는 것

D-5의 `activation_log`는 recall() 결과의 **개별 노드 활성화 이력**을 추적한다:

```
node_id, session_id, context_query, activation_score, activation_rank, channel
```

이것은 action_log의 `action_type='recall'` 레코드에서 **파생 가능한 데이터**다.

---

## 통합 전략: params/result JSON 내장 + VIEW

### 방안 비교

| 방안 | 장점 | 단점 |
|------|------|------|
| A. 별도 테이블 유지 | 쿼리 단순 | 스키마 중복, 동기화 필요 |
| B. action_log params/result에 내장 | 단일 테이블 | JSON 쿼리 성능 |
| C. action_log + 노드별 분해 행 | 정규화 | 행 수 폭발 |

**결론: 방안 B+C 하이브리드.**
- recall 1회 = action_log **1행** (요약 + top_ids)
- recall 결과의 **개별 노드 활성화** = action_log **N행** (`action_type='node_activated'`)
- activation_log = `WHERE action_type='node_activated'` VIEW

### action_log 스키마 (A-9 확정 + D-5 통합)

```sql
-- A-9에서 확정된 스키마 그대로 유지
CREATE TABLE action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    session_id TEXT,
    action_type TEXT NOT NULL,
    target_type TEXT,
    target_id INTEGER,
    params TEXT DEFAULT '{}',
    result TEXT DEFAULT '{}',
    context TEXT,
    model TEXT,
    duration_ms INTEGER,
    token_cost INTEGER,
    created_at TEXT NOT NULL,
    CONSTRAINT fk_session FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- A-9 인덱스
CREATE INDEX idx_action_type ON action_log(action_type);
CREATE INDEX idx_action_actor ON action_log(actor);
CREATE INDEX idx_action_session ON action_log(session_id);
CREATE INDEX idx_action_target ON action_log(target_type, target_id);
CREATE INDEX idx_action_created ON action_log(created_at);

-- D-5 통합용 추가 인덱스 (node_activated 조회 최적화)
CREATE INDEX idx_action_node_activated ON action_log(action_type, target_id, created_at DESC)
    WHERE action_type = 'node_activated';
```

### Action Taxonomy 확장 (A-9 + D-5)

```python
# A-9의 24개 + D-5 통합 1개 = 25개
ACTION_TAXONOMY = {
    # ... A-9의 기존 24개 그대로 ...

    # D-5 통합: 개별 노드 활성화 (recall의 하위 이벤트)
    "node_activated":   "recall 결과로 반환된 개별 노드의 활성화 기록",
}
```

---

## 기록 구조: recall 1회 → action_log N+1행

### hybrid.py 삽입 — recall 결과 기록

```python
# storage/hybrid.py — hybrid_search() 반환 직전

def _log_recall_activations(results: list[dict], query: str,
                             session_id: str | None = None):
    """recall 결과를 action_log에 기록.

    1행: recall 이벤트 요약 (action_type='recall')
    N행: 개별 노드 활성화 (action_type='node_activated')
    """
    import json
    from storage import action_log

    now = datetime.now(timezone.utc).isoformat()
    top_ids = [r["id"] for r in results[:10]]

    # 1. recall 요약 (1행)
    action_log.record(
        action_type="recall",
        actor="claude",
        session_id=session_id,
        params=json.dumps({
            "query": query[:200],
            "result_count": len(results),
            "top_ids": top_ids,
        }),
        result=json.dumps({
            "count": len(results),
            "top_scores": [round(r.get("score", 0), 4) for r in results[:5]],
        }),
    )

    # 2. 개별 노드 활성화 (N행, 상위 10개)
    for rank, node in enumerate(results[:10], 1):
        # channel 판별: score 구성 분석
        # (현재 hybrid_search에서 channel 정보를 직접 제공하지 않으므로
        #  향후 hybrid_search가 source 정보를 반환하도록 확장 시 활용)
        action_log.record(
            action_type="node_activated",
            actor="system",
            session_id=session_id,
            target_type="node",
            target_id=node["id"],
            params=json.dumps({
                "context_query": query[:200],
                "activation_score": round(node.get("score", 0), 4),
                "activation_rank": rank,
                "channel": "hybrid",  # 향후: vector/fts/graph 분리
                "node_type": node.get("type", ""),
                "node_layer": node.get("layer"),
            }),
        )

    # 3. nodes.last_activated 갱신 (기존 동작 유지)
    try:
        conn = sqlite_store._connect()
        for nid in top_ids:
            conn.execute(
                "UPDATE nodes SET last_activated=? WHERE id=?", (now, nid)
            )
        conn.commit()
        conn.close()
    except Exception:
        pass
```

### 삽입 지점

```python
# storage/hybrid.py:116 — return result 직전

    # 6. 헤비안 학습
    _hebbian_update([n["id"] for n in result], all_edges)

    # 7. 활성화 기록 (D-5 통합)
    _log_recall_activations(result, query)      # <-- 추가

    return result
```

---

## activation_log VIEW 정의

```sql
-- D-5가 원하는 activation_log를 VIEW로 구현
CREATE VIEW activation_log AS
SELECT
    al.id,
    al.target_id AS node_id,
    al.session_id,
    al.created_at AS activated_at,
    json_extract(al.params, '$.context_query') AS context_query,
    json_extract(al.params, '$.activation_score') AS activation_score,
    json_extract(al.params, '$.activation_rank') AS activation_rank,
    json_extract(al.params, '$.channel') AS channel,
    json_extract(al.params, '$.node_type') AS node_type,
    json_extract(al.params, '$.node_layer') AS node_layer
FROM action_log al
WHERE al.action_type = 'node_activated';
```

### VIEW 쿼리 성능

SQLite의 `json_extract()`는 **인덱스를 활용할 수 없다**. 하지만:

1. **partial index** (`WHERE action_type = 'node_activated'`)가 대상 행을 먼저 필터
2. 월간 recall 10회/일 × 10노드 = ~3,000행/월 → 1년 ~36,000행
3. `json_extract`는 이 규모에서 < 10ms (SQLite JSON1 확장)

성능이 문제가 되는 시점(10만행+)에서 **Generated Columns**으로 마이그레이션:

```sql
-- 향후 성능 최적화 (필요 시)
ALTER TABLE action_log ADD COLUMN _activation_score REAL
    GENERATED ALWAYS AS (
        CASE WHEN action_type = 'node_activated'
             THEN json_extract(params, '$.activation_score')
        END
    ) STORED;

CREATE INDEX idx_activation_score ON action_log(_activation_score)
    WHERE action_type = 'node_activated';
```

---

## D-5 분석 쿼리 → VIEW 기반 재작성

### 최근 7일 가장 많이 recall된 노드 Top 10

```sql
SELECT
    n.content,
    n.type,
    n.layer,
    COUNT(al.id) AS activation_count,
    AVG(al.activation_score) AS avg_score,
    MIN(al.activation_rank) AS best_rank
FROM activation_log al
JOIN nodes n ON n.id = al.node_id
WHERE al.activated_at >= datetime('now', '-7 days')
GROUP BY al.node_id
ORDER BY activation_count DESC
LIMIT 10;
```

### 특정 세션의 활성화 타임라인

```sql
SELECT
    al.activated_at,
    n.content,
    al.context_query,
    al.activation_rank
FROM activation_log al
JOIN nodes n ON n.id = al.node_id
WHERE al.session_id = ?
ORDER BY al.activated_at;
```

### 90일 비활성 노드 (pruning 후보)

```sql
SELECT n.id, n.content, n.type, n.layer, n.quality_score
FROM nodes n
LEFT JOIN activation_log al ON al.node_id = n.id
    AND al.activated_at >= datetime('now', '-90 days')
WHERE al.id IS NULL
  AND n.status = 'active'
ORDER BY n.created_at ASC
LIMIT 50;
```

---

## D-5 temporal_search와의 관계

D-5의 `temporal_search()`는 action_log와 **독립적으로 동작** 가능:
- `since_days` 필터: `nodes.last_activated` 기반 (action_log 불필요)
- `recency_boost`: `nodes.last_activated` 기반

하지만 action_log가 있으면 **더 정밀한 temporal_search** 가능:
- "이 노드가 최근 7일간 몇 번 활성화되었는가" → `activation_log` COUNT
- "어떤 맥락에서 활성화되었는가" → `context_query` 패턴 분석

```python
def temporal_search_v2(query, since_days=None, top_k=10):
    """action_log 기반 확장 temporal search."""
    results = hybrid_search(query, top_k=top_k * 3)

    # activation_log에서 최근 활성화 횟수 조회
    conn = sqlite_store._connect()
    for r in results:
        count = conn.execute(
            "SELECT COUNT(*) FROM activation_log "
            "WHERE node_id = ? AND activated_at >= datetime('now', ?)",
            (r["id"], f"-{since_days} days" if since_days else "-30 days")
        ).fetchone()[0]
        r["recent_activation_count"] = count
        # 활성화 빈도 보너스
        r["score"] += min(count * 0.02, 0.1)  # 최대 0.1 보너스

    results.sort(key=lambda x: -x["score"])
    conn.close()
    return results[:top_k]
```

---

## 통합 요약

| D-5 원래 설계 | 통합 후 |
|--------------|---------|
| `activation_log` 별도 테이블 | `action_log WHERE action_type='node_activated'` |
| `_log_activations()` 함수 | `_log_recall_activations()` (action_log.record 호출) |
| 전용 인덱스 3개 | partial index 1개 (`idx_action_node_activated`) |
| `temporal_search()` | 독립 유지, activation_log VIEW 활용 가능 |
| `compute_temporal_relevance()` | 독립 유지, action_log 무관 |

**이점**: 테이블 1개 관리, 스키마 단순화, 모든 시스템 활동이 단일 로그에 집중.
