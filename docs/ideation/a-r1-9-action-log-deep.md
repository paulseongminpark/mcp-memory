# 심화 1: action_log 중심 설계

> Q1+Q7+Q8의 공통 기반. 모든 후속 작업의 데이터 소스.

## 실제 DB 진단 결과

```
현재 edge 출처 분포:
  other(enrichment E14 등):  6,023 (95.2%)
  orphan_fix:                  264 (4.2%)
  auto(remember):               31 (0.5%)
  enrichment(labeled):            7 (0.1%)
```

**발견**: edge의 95%가 enrichment에서 생성. remember() 자동 edge는 31개뿐.
현재 enrichment가 에너지의 대부분을 공급하고, Paul의 직접 활동은 극소량.
action_log는 이 불균형을 측정 가능하게 만드는 첫 단계다.

## action_log 스키마

```sql
CREATE TABLE action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,              -- 'paul' | 'claude' | 'enrichment:E4' | 'system:daily_enrich'
    session_id TEXT,                  -- sessions.session_id FK
    action_type TEXT NOT NULL,        -- Action Taxonomy 참조
    target_type TEXT,                 -- 'node' | 'edge' | 'type_def' | 'relation_def' | 'graph'
    target_id INTEGER,
    params TEXT DEFAULT '{}',         -- JSON
    result TEXT DEFAULT '{}',         -- JSON
    context TEXT,
    model TEXT,
    duration_ms INTEGER,
    token_cost INTEGER,
    created_at TEXT NOT NULL,
    CONSTRAINT fk_session FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX idx_action_type ON action_log(action_type);
CREATE INDEX idx_action_actor ON action_log(actor);
CREATE INDEX idx_action_session ON action_log(session_id);
CREATE INDEX idx_action_target ON action_log(target_type, target_id);
CREATE INDEX idx_action_created ON action_log(created_at);
```

## Action Taxonomy — 8 카테고리, 24 타입

```python
ACTION_TAXONOMY = {
    # 1. Creation
    "remember": "새 노드 생성",
    "auto_link": "remember() 자동 edge",
    # 2. Retrieval
    "recall": "hybrid_search",
    "get_context": "세션 컨텍스트 조회",
    "inspect": "노드 상세 조회",
    # 3. Organization
    "promote": "노드 승격",
    "merge": "노드 병합",
    "classify": "타입 재분류",
    # 4. Strengthening
    "hebbian_update": "recall 시 edge 강화",
    "edge_create": "수동 edge 생성",
    "edge_modify": "edge 속성 변경",
    # 5. Weakening
    "inactivate": "노드 inactive",
    "archive": "노드 archive",
    "reactivate": "노드 재활성화",
    "deprecate": "타입/관계 deprecated",
    # 6. Quality
    "enrich": "enrichment 태스크 (E1-E25)",
    "validate": "검증 게이트",
    "integrity_check": "L4/L5 무결성 검증",
    # 7. Schema
    "type_create": "새 타입 정의",
    "type_modify": "타입 정의 변경",
    "relation_create": "새 관계 정의",
    "relation_modify": "관계 정의 변경",
    "snapshot": "온톨로지 스냅샷",
    # 8. Analysis
    "analyze_signals": "Signal 분석",
    "dashboard": "대시보드 조회",
}
```

## 코드 삽입 지점

### tools/remember.py:39-49 (insert_node 직후)
```python
action_log.record(action_type="remember", actor=source,
    target_type="node", target_id=node_id,
    params=json.dumps({"type": type, "project": project}))
```

### tools/remember.py:90-97 (자동 edge 생성 후)
```python
action_log.record(action_type="auto_link", actor="system",
    target_type="edge", target_id=edge_id,
    params=json.dumps({"source_node": node_id, "target_node": sim_id}))
```

### storage/hybrid.py (_hebbian_update 내부)
```python
action_log.record(action_type="hebbian_update", actor="system",
    target_type="edge", target_id=edge_id,
    params=json.dumps({"query": query_text, "result_ids": result_ids}))
```

### tools/recall.py (반환 직전)
```python
action_log.record(action_type="recall", actor="claude",
    params=json.dumps({"query": query, "type_filter": type_filter}),
    result=json.dumps({"count": len(results), "top_ids": top_ids}))
```

### tools/promote_node.py (승격 완료 후)
```python
action_log.record(action_type="promote", actor="claude",
    target_type="node", target_id=node_id,
    params=json.dumps({"from": old_type, "to": target_type}))
```

### scripts/enrich/node_enricher.py (E 태스크 완료 후)
```python
action_log.record(action_type="enrich", actor=f"enrichment:{task_id}",
    target_type="node", target_id=node_id,
    model=model_name, token_cost=tokens_used)
```

## record() 구현

```python
# storage/action_log.py
def record(action_type, actor="claude", session_id=None, target_type=None,
           target_id=None, params="{}", result="{}", context=None,
           model=None, duration_ms=None, token_cost=None) -> int:
    """action_log에 기록. 실패해도 main flow 중단 안 함."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.execute(
            """INSERT INTO action_log (actor, session_id, action_type, target_type,
               target_id, params, result, context, model, duration_ms, token_cost, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (actor, session_id, action_type, target_type, target_id,
             params, result, context, model, duration_ms, token_cost, now))
        log_id = cur.lastrowid
        conn.commit(); conn.close()
        return log_id
    except Exception:
        return -1
```

## 세션 에너지 계산

```python
def calculate_session_energy(session_id):
    actions = get_session_actions(session_id)
    creation = sum(1 for a in actions if a["action_type"] in ("remember", "auto_link"))
    retrieval = sum(1 for a in actions if a["action_type"] in ("recall", "get_context"))
    organization = sum(1 for a in actions if a["action_type"] in ("promote", "merge"))

    domains = set()
    for a in actions:
        if a["action_type"] == "recall":
            p = json.loads(a.get("params", "{}"))
            if p.get("project"): domains.add(p["project"])

    total = creation + retrieval + organization
    if total == 0: mode = "idle"
    elif creation > retrieval: mode = "generative"
    elif len(domains) >= 3: mode = "exploratory"
    elif organization > 0: mode = "organizing"
    else: mode = "consolidation"

    return {"mode": mode, "total": total, "creation": creation,
            "retrieval": retrieval, "organization": organization,
            "exploration_domains": len(domains)}
```

## provenance 통합 로드맵

```
action_log: "무엇이 일어났는가" (이벤트 로그)
provenance: "왜, 어떤 맥락에서" (인과 추적)
action_log.id -> provenance.action_id (1:N)
```

action_log 먼저 -> 안정화 후 provenance 추가. action_log만으로도 Q7(에너지), Q8(빼기 근거) 즉시 제공.
