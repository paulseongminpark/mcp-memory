# D-10: activation_log ↔ action_log 통합 설계

> 세션 D | 2026-03-05
> A-9 action_log(24 타입) 상위 설계 전제 하에 activation 데이터 통합

---

## 현재 상태

- `action_log`: **미존재** (A 세션 설계만, 미구현)
- `activation_log`: **미존재** (D-5 설계만, 미구현)
- `correction_log`: **존재** (수정 이력 추적)

---

## A-9 action_log 24 타입 전제

A 세션 설계에서 action_log는 24개 action_type을 가진 통합 이벤트 로그:

```
추정 타입 (A 세션 문서 미확인이므로 context 기반 추론):
  - remember, recall, promote, demote, prune, archive
  - enrich_start, enrich_complete, enrich_fail
  - edge_create, edge_delete, edge_strengthen
  - hub_alert, drift_detected, validation_fail
  - session_start, session_end
  - ... (총 24개)
```

**가정:** `recall` 타입이 있음 → recall 이벤트 = activation.

---

## 설계 결정: 통합 vs 분리

### 옵션 A: action_log 단일 테이블 (A 설계 따름)

```sql
CREATE TABLE action_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type  TEXT NOT NULL,  -- 'recall', 'remember', 'enrich', ...
    node_id      INTEGER REFERENCES nodes(id),
    session_id   TEXT,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- recall 전용 필드 (nullable)
    context_query    TEXT,
    activation_score REAL,
    activation_rank  INTEGER,
    channel          TEXT,   -- 'vector' | 'fts' | 'graph'
    -- 기타 action 전용 필드
    metadata     TEXT   -- JSON 직렬화 (타입별 추가 데이터)
);

CREATE INDEX idx_action_type_node ON action_log(action_type, node_id, created_at DESC);
CREATE INDEX idx_action_session   ON action_log(session_id, created_at DESC);
CREATE INDEX idx_action_time      ON action_log(created_at DESC);
```

**장점:** 단일 이력 소스, A 설계와 일치, JOIN 없이 전체 이벤트 조회
**단점:** recall 전용 컬럼이 NULL로 낭비, 타입별 스키마 강제 불가

### 옵션 B: activation_log 별도 유지 + action_log와 FK

```sql
-- action_log: 경량 이벤트 허브
CREATE TABLE action_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL,
    node_id     INTEGER REFERENCES nodes(id),
    session_id  TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata    TEXT   -- JSON
);

-- activation_log: recall 이벤트 상세 (action_log와 1:1)
CREATE TABLE activation_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    action_log_id    INTEGER REFERENCES action_log(id),
    node_id          INTEGER NOT NULL REFERENCES nodes(id),
    session_id       TEXT,
    activated_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    context_query    TEXT,
    activation_score REAL,
    activation_rank  INTEGER,
    channel          TEXT
);
```

**장점:** 타입별 정규화, activation 특화 인덱스
**단점:** 2-테이블 JOIN 필요, A 설계와 불일치 가능

### 옵션 C: activation_log = action_log WHERE recall VIEW

```sql
-- 뷰로 처리 (테이블 추가 없음)
CREATE VIEW activation_log AS
SELECT
    id,
    node_id,
    session_id,
    created_at AS activated_at,
    json_extract(metadata, '$.query')  AS context_query,
    json_extract(metadata, '$.score')  AS activation_score,
    json_extract(metadata, '$.rank')   AS activation_rank,
    json_extract(metadata, '$.channel') AS channel
FROM action_log
WHERE action_type = 'recall';
```

**장점:** 완전 통합, 테이블 추가 없음
**단점:** JSON 직렬화/역직렬화, 인덱스 못 씀 (뷰이므로)

---

## 권장안: 옵션 A (action_log 통합) + 마이그레이션 경로

**이유:**
- A 세션이 상위 설계 → D는 따름
- 24 타입이 이미 정의됐다면 recall도 그 중 하나
- 뷰(옵션 C)는 JSON 검색이 느림
- 분리(옵션 B)는 불필요한 복잡도

```sql
-- action_log 최종 설계 (A-9 기반 + D-10 보완)
CREATE TABLE IF NOT EXISTS action_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type  TEXT    NOT NULL,    -- 'recall' | 'remember' | 'enrich' | ...
    node_id      INTEGER REFERENCES nodes(id),
    edge_id      INTEGER REFERENCES edges(id),
    session_id   TEXT,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- recall 전용
    context_query    TEXT,
    activation_score REAL,
    activation_rank  INTEGER,
    channel          TEXT,
    -- 범용
    metadata         TEXT    -- JSON
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_alog_recall
    ON action_log(action_type, node_id, created_at DESC)
    WHERE action_type = 'recall';

CREATE INDEX IF NOT EXISTS idx_alog_session
    ON action_log(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alog_time
    ON action_log(created_at DESC);
```

---

## temporal_search() → action_log 직접 쿼리

### D-5의 temporal_search() 수정 SQL

**기존 (activation_log 기준):**
```python
results = [r for r in results
           if r["last_activated"] and r["last_activated"] >= cutoff]
```

**수정 (action_log 기준):**
```python
def _get_recently_activated_node_ids(since_cutoff: str, conn) -> set[int]:
    """action_log에서 최근 recall된 node_id 집합"""
    rows = conn.execute(
        "SELECT DISTINCT node_id FROM action_log "
        "WHERE action_type='recall' "
        "  AND created_at >= ? "
        "  AND node_id IS NOT NULL",
        (since_cutoff,)
    ).fetchall()
    return {r[0] for r in rows}
```

**temporal_search() 수정본:**
```python
def temporal_search(
    query: str,
    since_days: int | None = None,
    until_date: str | None = None,
    top_k: int = 10,
    recency_halflife: float = 30.0,
    conn=None,
) -> list[dict]:
    from datetime import datetime, timedelta, timezone
    import math

    results = hybrid_search(query, top_k=top_k * 3)
    now = datetime.now(timezone.utc)

    # 시간 필터 (action_log 기반)
    if since_days and conn:
        cutoff = (now - timedelta(days=since_days)).isoformat()
        recent_ids = _get_recently_activated_node_ids(cutoff, conn)

        # last_activated fallback도 병행 (action_log 미기록분 대비)
        results = [
            r for r in results
            if r["id"] in recent_ids
               or (r.get("last_activated") and
                   _parse_dt(r["last_activated"]) >= now - timedelta(days=since_days))
        ]

    # Recency boost: action_log에서 최근 recall 빈도 기반
    if conn:
        for r in results:
            node_id = r["id"]
            # 최근 30일 내 recall 횟수
            recall_count = conn.execute(
                "SELECT COUNT(*) FROM action_log "
                "WHERE action_type='recall' AND node_id=? "
                "  AND created_at >= datetime('now', '-30 days')",
                (node_id,)
            ).fetchone()[0]

            # log1p 스케일 boost (0회: 0, 5회: ~0.79, 10회: ~1.04)
            recency_boost = math.log1p(recall_count) * 0.3
            r["score"] = r.get("score", 0) * (1 + recency_boost)

    results.sort(key=lambda x: -x["score"])
    return results[:top_k]
```

---

## action_log 기록 함수 (hybrid.py에 삽입)

```python
# storage/hybrid.py _hebbian_update() 근방에 추가

def _log_recall_event(
    results: list[dict],
    query: str,
    session_id: str,
    conn,
):
    """
    recall 이벤트를 action_log에 기록.
    hybrid_search() 반환 직전에 호출.
    """
    now_str = datetime.utcnow().isoformat()
    for rank, node in enumerate(results[:10], 1):
        conn.execute(
            "INSERT INTO action_log "
            "(action_type, node_id, session_id, created_at, "
            " context_query, activation_score, activation_rank) "
            "VALUES ('recall', ?, ?, ?, ?, ?, ?)",
            (
                node["id"],
                session_id,
                now_str,
                query[:200],
                round(node.get("score", 0), 4),
                rank,
            )
        )
        # nodes.last_activated 갱신 (기존 동작 유지)
        conn.execute(
            "UPDATE nodes SET last_activated=? WHERE id=?",
            (now_str, node["id"])
        )
    conn.commit()
```

---

## 마이그레이션 경로

### D가 먼저 구현할 경우 (A 미구현 상태)

```python
# 임시: activation_log를 독립 테이블로 먼저 구현
# → A-9 구현 후 action_log로 데이터 이전 + 뷰 생성

# 이전 스크립트 (나중에 사용):
def migrate_activation_to_action(conn):
    """activation_log → action_log 데이터 이전"""
    conn.execute("""
        INSERT INTO action_log
            (action_type, node_id, session_id, created_at,
             context_query, activation_score, activation_rank)
        SELECT
            'recall', node_id, session_id, activated_at,
            context_query, activation_score, activation_rank
        FROM activation_log
    """)
    conn.commit()
    print("activation_log → action_log 이전 완료")
```

### A-9 먼저 구현할 경우 (권장)

A-9에서 action_log 구현 → D-10은 recall 타입만 사용하도록 연결.

---

## 결론 및 다음 스텝

| 상황 | 조치 |
|------|------|
| A-9 미구현 | activation_log 독립 테이블로 임시 구현 (D-5 설계) |
| A-9 구현 완료 | action_log에 recall 타입으로 통합, activation_log 제거 |
| 통합 후 | `temporal_search()`를 action_log 직접 쿼리로 전환 |

**A와 D 간 인터페이스 합의 필요:**
- `action_type='recall'` 타입명 확정
- `session_id` 포맷 통일 (UUID vs 날짜 기반)
- `metadata` JSON 키 네이밍 규칙
