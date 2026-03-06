# D-5: 시간축 보완

> 세션 D | 2026-03-05
> Rewind 모델 + 활성화 이력 + 동적 decay

---

## 현재 상태 점검

### 보유 필드 (nodes 테이블)

| 필드 | 의미 | 문제 |
|------|------|------|
| `created_at` | 생성 시각 | OK |
| `updated_at` | 마지막 수정 | OK |
| `last_activated` | 마지막 recall 시각 | 단일값 → 이력 손실 |
| `enriched_at` | enrichment 완료 시각 | OK |
| `temporal_relevance` | 시간 관련성 float | 정적 값, 시간 미반영 |

### 보유 필드 (edges 테이블)

| 필드 | 의미 | 문제 |
|------|------|------|
| `last_activated` | 마지막 활성화 | 단일값 |
| `decay_rate` | 감쇠율 | 있으나 **미적용** |

### 부족한 것

1. **시간 범위 검색:** "2주 전 기억" 검색 불가
2. **decay 적용:** `decay_rate` 컬럼 존재하나 hybrid.py에서 사용 안 함
3. **활성화 이력:** `last_activated` 단일 필드 → 타임라인 재구성 불가
4. **동적 temporal_relevance:** 정적 저장값이라 시간이 지나도 갱신 안 됨

---

## 1. activation_log 테이블 (신규)

```sql
-- storage/sqlite_store.py init_db() 또는 _apply_v2_migrations() 에 추가

CREATE TABLE IF NOT EXISTS activation_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id          TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    session_id       TEXT,
    activated_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    context_query    TEXT,           -- 어떤 쿼리로 활성화됐는지
    activation_score REAL,           -- recall 당시 RRF 점수
    activation_rank  INTEGER,        -- 검색 결과에서의 순위
    channel          TEXT            -- 'vector' | 'fts' | 'graph'
);

CREATE INDEX idx_actlog_node    ON activation_log(node_id, activated_at DESC);
CREATE INDEX idx_actlog_session ON activation_log(session_id, activated_at DESC);
CREATE INDEX idx_actlog_time    ON activation_log(activated_at DESC);
```

**기록 위치 (storage/hybrid.py):**
```python
# hybrid_search() 반환 직전에 추가
def _log_activations(results: list, query: str, session_id: str, conn):
    """검색 결과 상위 K개의 활성화 이력 기록"""
    now = datetime.utcnow().isoformat()
    for rank, node in enumerate(results[:10], 1):
        conn.execute(
            "INSERT INTO activation_log "
            "(node_id, session_id, activated_at, context_query, activation_score, activation_rank) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (node["id"], session_id, now, query[:200], node.get("score", 0), rank)
        )
        # nodes.last_activated 갱신
        conn.execute(
            "UPDATE nodes SET last_activated=? WHERE id=?", (now, node["id"])
        )
    conn.commit()
```

---

## 2. temporal_search (Rewind 모델)

```python
# storage/hybrid.py 에 추가 (신규 함수)

from datetime import datetime, timedelta, timezone

def temporal_search(
    query: str,
    since_days: int | None = None,
    until_date: str | None = None,  # 'YYYY-MM-DD'
    top_k: int = 10,
    recency_boost_halflife: float = 30.0,  # 30일 반감기
) -> list[dict]:
    """
    시간 범위 기반 기억 검색 (Rewind 모델).

    동작:
      1. hybrid_search로 기본 검색
      2. since_days / until_date 필터 적용
      3. last_activated 최신일수록 score 부스트
    """
    # 기본 검색
    results = hybrid_search(query, top_k=top_k * 3)  # 필터 후 top_k 확보용 여유

    now = datetime.now(timezone.utc)

    # 시간 필터
    if since_days:
        cutoff = now - timedelta(days=since_days)
        results = [
            r for r in results
            if r.get("last_activated") and
               _parse_dt(r["last_activated"]) >= cutoff
        ]

    if until_date:
        until_dt = datetime.fromisoformat(until_date).replace(tzinfo=timezone.utc)
        results = [
            r for r in results
            if r.get("created_at") and
               _parse_dt(r["created_at"]) <= until_dt
        ]

    # Recency Boost: 최신 활성화일수록 score 증폭
    # boost = exp(-days_since_activation / halflife)
    # 오늘 활성화: boost=1.0 / 30일 전: boost=0.5 / 90일 전: boost=0.05
    for r in results:
        last_act = r.get("last_activated")
        if last_act:
            days_ago = (now - _parse_dt(last_act)).total_seconds() / 86400
            recency_boost = math.exp(-days_ago * math.log(2) / recency_boost_halflife)
        else:
            recency_boost = 0.1  # 한 번도 recall 안 된 노드

        r["score"] = r.get("score", 0) * (1 + recency_boost * 0.5)

    # 재정렬
    results.sort(key=lambda x: -x["score"])
    return results[:top_k]


def _parse_dt(dt_str: str) -> datetime:
    """ISO 형식 datetime 파싱 (타임존 처리)"""
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
```

**사용 예:**
```python
# "최근 7일 내 orchestration 관련 기억"
results = temporal_search("컨텍스트 관리", since_days=7)

# "2주 전부터 오늘까지 portfolio 결정"
results = temporal_search("섹션 구조", since_days=14)

# "특정 날짜 이전의 기억"
results = temporal_search("v2 설계", until_date="2026-02-01")
```

---

## 3. temporal_relevance 동적 계산

**현재 문제:** `temporal_relevance`는 enrichment 시 LLM이 생성한 정적 float. 시간이 지나도 갱신 안 됨.

```python
# storage/hybrid.py 또는 utils/temporal.py 에 추가

import math
from datetime import datetime, timezone

def compute_temporal_relevance(node: dict, current_time: datetime | None = None) -> float:
    """
    정적 저장값 대신 동적 계산.

    공식:
      base = max(0, 1 - age_days / 365)          # 1년 선형 감쇠
      recency_boost = exp(-recency_days / 30)     # 30일 반감기
      final = min(1.0, base + recency_boost * 0.5)

    의미:
      - 오늘 활성화된 1년 된 노드: base=0 + boost=0.5 * 0.5 = 0.25
      - 오늘 생성된 노드: base=1 + boost=0.5 = 1.0 (클램프)
      - 3년 된 + 90일 비활성: base=0 + boost≈0.025 = 0.012
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)

    # 생성 기반 감쇠
    created_at = node.get("created_at")
    if created_at:
        created_dt = _parse_dt(created_at)
        age_days = (current_time - created_dt).total_seconds() / 86400
        base = max(0.0, 1.0 - age_days / 365)
    else:
        base = 0.5  # 알 수 없는 경우 중간값

    # 최근 활성화 기반 boost
    last_activated = node.get("last_activated")
    if last_activated:
        last_dt = _parse_dt(last_activated)
        recency_days = (current_time - last_dt).total_seconds() / 86400
        boost = math.exp(-recency_days * math.log(2) / 30)  # 30일 반감기
        return min(1.0, base + boost * 0.5)

    return base
```

**적용 위치:** hybrid.py의 enrichment 가중치 계산 시 `node["temporal_relevance"]` 대신 호출.

---

## 4. 활성화 이력 분석 쿼리

```sql
-- 최근 7일 내 가장 많이 recall된 노드 Top 10
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

-- 특정 세션의 활성화 타임라인
SELECT
    al.activated_at,
    n.content,
    al.context_query,
    al.activation_rank
FROM activation_log al
JOIN nodes n ON n.id = al.node_id
WHERE al.session_id = 'SESSION_ID_HERE'
ORDER BY al.activated_at;

-- 90일 이상 비활성 노드 (pruning 후보 예비 탐색)
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

## 5. 타임라인 검색 MCP 도구 확장 (설계)

```python
# mcp_server.py 에 신규 도구 추가

@mcp.tool()
def recall_temporal(
    query: str,
    since_days: int | None = None,
    until_date: str | None = None,
    top_k: int = 10,
) -> dict:
    """
    시간 범위 기반 기억 검색.

    Args:
        query: 검색 쿼리
        since_days: 최근 N일 내 활성화된 기억만
        until_date: 특정 날짜 이전 생성된 기억 (YYYY-MM-DD)
        top_k: 반환 개수

    Examples:
        recall_temporal("컨텍스트 관리", since_days=7)
        recall_temporal("v2 설계 결정", until_date="2026-02-01")
    """
    results = temporal_search(query, since_days=since_days,
                               until_date=until_date, top_k=top_k)
    return {
        "results": results,
        "filter": {"since_days": since_days, "until_date": until_date},
        "count": len(results),
    }
```

---

## 구현 우선순위

| 순위 | 항목 | 소요 | 의존성 |
|-----|------|------|-------|
| 1 | activation_log 테이블 생성 | 30분 | 없음 |
| 2 | _log_activations() 추가 (hybrid.py) | 1시간 | activation_log |
| 3 | decay 적용 (_effective_strength) | 1시간 | d-2-consensus.md |
| 4 | temporal_search() 구현 | 2시간 | activation_log |
| 5 | compute_temporal_relevance() | 1시간 | 없음 |
| 6 | recall_temporal MCP 도구 | 1시간 | temporal_search |
