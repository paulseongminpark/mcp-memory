# Q1. 팔란티어 벤치마크 — 스키마/인제스트 분리, 4원소 매핑

## 현재 문제

`remember()`가 세 가지 역할을 동시에 수행한다:
1. **분류** — `validate_node_type()` + `suggest_closest_type()`으로 타입 결정
2. **저장** — SQLite `insert_node()` + ChromaDB `add()`
3. **연결** — `vector_store.search()` → `infer_relation()` → `insert_edge()`

Palantir의 핵심 교훈: **파서(분류)와 트랜스폼(저장)을 분리하면 온톨로지 진화가 파서 정의 업데이트만으로 가능해진다.** 현재 mcp-memory에서 타입을 변경하면 remember(), enrichment, validators, schema.yaml을 모두 건드려야 한다.

## Palantir 4원소 매핑

```
Palantir                    mcp-memory 현재        mcp-memory 목표
───────────────────────────────────────────────────────────────
Object Types                nodes.type (50개)       TypeDef 테이블
Property Types              nodes.* 컬럼들          PropertyDef 테이블
Link Types                  edges.relation (48개)   LinkDef 테이블
Action Types                없음                    ActionDef 테이블
```

## 메타데이터-인스턴스 분리 — 3테이블 설계

```sql
CREATE TABLE type_defs (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    layer INTEGER NOT NULL,
    super_type TEXT,
    description TEXT,
    status TEXT DEFAULT 'active',
    deprecated_reason TEXT,
    replaced_by TEXT,
    version INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE relation_defs (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    category TEXT,
    direction_constraint TEXT,
    layer_constraint TEXT,
    status TEXT DEFAULT 'active',
    deprecated_reason TEXT,
    replaced_by TEXT,
    version INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);
```

## remember() 분리: classify() + store() + link()

```python
def classify(content: str, hints: dict = None) -> ClassificationResult:
    """순수 분류. DB 접촉 없음."""
    return ClassificationResult(type, layer, tier, confidence)

def store(content: str, classification: ClassificationResult, **kwargs) -> int:
    """순수 저장. 분류 결정을 받아서 저장만."""
    node_id = sqlite_store.insert_node(...)
    vector_store.add(node_id, content, ...)
    return node_id

def link(node_id: int, content: str) -> list[dict]:
    """자동 edge 생성. 저장 완료된 노드에 대해 실행."""
    similar = vector_store.search(content, top_k=5)
    # ... edge 생성
    return edges

# 최상위 API 유지 (하위 호환)
def remember(content, type="Unclassified", **kwargs):
    cls = classify(content, {"type_hint": type})
    node_id = store(content, cls, **kwargs)
    edges = link(node_id, content)
    return {"node_id": node_id, ...}
```

## Action Types — action_log 테이블

```sql
CREATE TABLE action_log (
    id INTEGER PRIMARY KEY,
    action_type TEXT NOT NULL,
    actor TEXT DEFAULT 'claude',
    target_node_id INTEGER,
    target_edge_id INTEGER,
    params TEXT,
    result TEXT,
    session_id TEXT,
    created_at TEXT
);
```

→ 심화 설계: [a-arch-9-action-log-deep.md](a-arch-9-action-log-deep.md)

## 규모 현실성

3,230 노드에서 Palantir 급 분리는 과도하다. 핵심:
1. `type_defs` + `relation_defs` 메타 테이블만 추가 (30K 이전에 필수)
2. `remember()` 내부를 3함수로 분리 (리팩터링, API 비호환 없음)
3. `action_log`는 Q7과 합쳐서 즉시 구현 가능
