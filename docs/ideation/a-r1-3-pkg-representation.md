# Q3. PKG Representation — 접근 레벨, 프로비넌스

## 현재 부재

Balog et al.(2024)의 3축에서 Representation이 약하다:
- **접근 레벨**: nodes 테이블에 없음. 모든 노드가 동일한 접근 수준.
- **프로비넌스**: `source` 필드가 있지만 `'claude'` 단일 값이 대부분. 체인 추적 불가.

## 접근 레벨 설계

```sql
ALTER TABLE nodes ADD COLUMN access_level TEXT DEFAULT 'shared';
-- 'private'  : Paul만 직접 입력. Claude 수정 불가.
-- 'session'  : 현재 세션에서만 유효 (임시)
-- 'shared'   : Claude + enrichment 접근 가능 (기본값)
-- 'model'    : 모든 AI 모델 접근 가능 (cross-model)
```

## 접근 제어 규칙

```python
ACCESS_RULES = {
    "private": {"read": ["paul", "claude"], "write": ["paul"], "delete": ["paul"]},
    "session": {"read": ["paul", "claude"], "write": ["paul", "claude"], "delete": ["paul", "claude", "system"], "ttl": "session_end"},
    "shared":  {"read": ["paul", "claude", "enrichment"], "write": ["paul", "claude", "enrichment"], "delete": ["paul"]},
    "model":   {"read": ["*"], "write": ["paul", "claude"], "delete": ["paul"]},
}
```

## 프로비넌스 체인

```sql
CREATE TABLE provenance (
    id INTEGER PRIMARY KEY,
    node_id INTEGER REFERENCES nodes(id),
    edge_id INTEGER REFERENCES edges(id),
    event_type TEXT,          -- 'created', 'modified', 'promoted', 'enriched'
    actor TEXT,               -- 'paul', 'claude', 'enrichment:E4', 'system'
    session_id TEXT,
    context TEXT,             -- 어떤 대화/작업 중이었는가
    evidence TEXT,            -- 근거 (다른 node_id 참조 등)
    tool TEXT,                -- 'remember', 'promote_node', 'enrichment'
    model TEXT,               -- 'claude-opus-4-6', 'gpt-5-mini' 등
    created_at TEXT
);
```

## 이점

- `action_log`(Q1)와 결합하면 **완전한 리니지** 구현
- "이 패턴은 언제, 어떤 대화에서, 어떤 근거로 생성되었는가" 추적
- enrichment 환각 추적: "이 facet은 gpt-5-mini E4에서 생성" -> 신뢰도 차등

## 규모 현실성

- `access_level` 컬럼: 단순 TEXT, 즉시 추가. 마이그레이션 비용 ~0.
- `provenance` 테이블: ~10K 행 예상. 부하 무시.
- 핵심: remember()에 `access_level` 파라미터 추가. 하위 호환 유지.
