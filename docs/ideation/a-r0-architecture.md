# 아키텍처 & 팔란티어 벤치마크 — 아이디에이션

> mcp-memory v2.0 온톨로지 설계를 위한 8개 질문에 대한 구체적 설계안.
> 기준: 3,230 nodes, 6,020 edges, 50 types, 48 relations, 실제 코드 기반.

---

## Q1. 팔란티어 벤치마크 — 스키마/인제스트 분리, 4원소 매핑

### 현재 문제

`remember()`가 세 가지 역할을 동시에 수행한다:
1. **분류** — `validate_node_type()` + `suggest_closest_type()`으로 타입 결정
2. **저장** — SQLite `insert_node()` + ChromaDB `add()`
3. **연결** — `vector_store.search()` → `infer_relation()` → `insert_edge()`

Palantir의 핵심 교훈: **파서(분류)와 트랜스폼(저장)을 분리하면 온톨로지 진화가 파서 정의 업데이트만으로 가능해진다.** 현재 mcp-memory에서 타입을 변경하면 remember(), enrichment, validators, schema.yaml을 모두 건드려야 한다.

### Palantir 4원소 → mcp-memory 매핑

```
Palantir                    mcp-memory 현재        mcp-memory 목표
─────────────────────────────────────────────────────────────────
Object Types                nodes.type (50개)       TypeDef 테이블
Property Types              nodes.* 컬럼들          PropertyDef 테이블
Link Types                  edges.relation (48개)   LinkDef 테이블
Action Types                없음                    ActionDef 테이블
```

### 구체적 설계: 메타데이터-인스턴스 분리

**현재**: 메타데이터(타입 정의)와 인스턴스(실제 노드)가 같은 테이블에 혼재.
- `schema.yaml`이 정의, `nodes` 테이블이 인스턴스 → 이 둘 사이에 런타임 바인딩이 없다.
- `validators.py`가 매번 YAML을 파싱해서 검증 — 비효율적이고 스키마 드리프트의 원인.

**제안: 3테이블 분리**

```sql
-- 메타데이터 계층 (스키마 정의)
CREATE TABLE type_defs (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,       -- 'Pattern', 'Signal' 등
    layer INTEGER NOT NULL,          -- 0-5
    super_type TEXT,                  -- 상위 범주 (7-10개)
    description TEXT,
    status TEXT DEFAULT 'active',    -- active | deprecated | archived
    deprecated_reason TEXT,
    replaced_by TEXT,                -- deprecated 시 대체 타입
    version INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE relation_defs (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,       -- 'realized_as', 'supports' 등
    category TEXT,                    -- causal, structural, semantic 등
    direction_constraint TEXT,       -- upward | downward | horizontal | any
    layer_constraint TEXT,           -- cross-layer | same-layer | any
    status TEXT DEFAULT 'active',
    deprecated_reason TEXT,
    replaced_by TEXT,
    version INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);

-- 인스턴스 계층 (실제 데이터) — 기존 nodes/edges는 그대로 유지
-- 단, nodes.type은 type_defs.name에 FK 참조
```

### remember() 분리: classify() + store() + link()

```python
# 현재: remember() = classify + store + link (105줄 단일 함수)
# 제안: 3단계 파이프라인

def classify(content: str, hints: dict = None) -> ClassificationResult:
    """순수 분류. DB 접촉 없음."""
    # 1. 규칙 기반 (키워드 매핑)
    # 2. 온톨로지 검증 (type_defs 테이블 참조)
    # 3. fallback: suggest_closest_type()
    return ClassificationResult(type, layer, tier, confidence)

def store(content: str, classification: ClassificationResult, **kwargs) -> int:
    """순수 저장. 분류 결정을 받아서 저장만."""
    node_id = sqlite_store.insert_node(...)
    vector_store.add(node_id, content, ...)
    return node_id

def link(node_id: int, content: str) -> list[dict]:
    """자동 edge 생성. 저장 완료된 노드에 대해 실행."""
    similar = vector_store.search(content, top_k=5)
    edges = []
    for sim_id, distance, _ in similar:
        relation = infer_relation(...)
        edge_id = sqlite_store.insert_edge(...)
        edges.append(...)
    return edges

# 최상위 API는 유지 (하위 호환)
def remember(content, type="Unclassified", **kwargs):
    cls = classify(content, {"type_hint": type})
    node_id = store(content, cls, **kwargs)
    edges = link(node_id, content)
    return {"node_id": node_id, ...}
```

**이점**:
- 온톨로지 변경 시 `classify()`만 수정
- enrichment에서 `classify()`를 재호출해 재분류 가능
- `store()`와 `link()`는 분류 로직에 의존하지 않음

### Action Types — 현재 부재한 "동사"

Palantir의 Semantic(명사) vs Kinetic(동사) 이원론에서 mcp-memory에는 Kinetic 요소가 없다.

```sql
CREATE TABLE action_log (
    id INTEGER PRIMARY KEY,
    action_type TEXT NOT NULL,  -- 'recall', 'remember', 'promote', 'enrich', 'prune'
    actor TEXT DEFAULT 'claude', -- 'paul', 'claude', 'enrichment', 'system'
    target_node_id INTEGER,
    target_edge_id INTEGER,
    params TEXT,                 -- JSON: 쿼리, 필터 등
    result TEXT,                 -- JSON: 반환값 요약
    session_id TEXT,
    created_at TEXT
);
```

이것이 Prigogine의 "에너지" 추적과 직결된다 (Q7 참조).

### 규모 현실성

3,230 노드에서 Palantir 급 분리는 **과도하다**. 핵심은:
1. `type_defs` + `relation_defs` 메타 테이블만 추가 (30K 이전에 필수)
2. `remember()` 내부를 3함수로 분리 (리팩터링, API 비호환 없음)
3. `action_log`는 Q7과 합쳐서 즉시 구현 가능

---

## Q2. 검증-게이트 학습 — 현재 v2에서 치명적인가

### 현재 상태 진단

검증 부재의 **구체적 증상**:
1. `enrichment/node_enricher.py`: LLM이 생성한 summary/key_concepts/facets가 **무검증으로 DB에 기록**
2. `insert_edge()`에서 `relation not in ALL_RELATIONS` 체크만 존재 — **의미적 타당성 검증 없음**
3. `promote_node()`에서 `VALID_PROMOTIONS` 경로 체크만 — **승격 근거의 품질 검증 없음**

### 치명적인가? — "예, 하지만 단계적으로"

**즉시 치명적인 것**: 의미적 피드백 루프 (v2 문서 §2.7)
- enrichment가 환각 facet 생성 → 임베딩 오염 → 잘못된 edge → 더 많은 환각
- 이것은 **이미 발생 중**이다. `FACETS_ALLOWLIST`와 `DOMAINS_ALLOWLIST`가 부분적으로 방어하지만, summary와 key_concepts에는 필터가 없다.

**아직 치명적이지 않은 것**: Hebbian 발산
- 3,230 노드에서 recall 빈도가 낮아 실질적 발산 미발생 (DeepSeek: 921일 후 사망)
- 하지만 **능동적 사용이 시작되면** (매일 recall 10회+) 문제가 급격히 현실화

### 4차원 검증 게이트 — 구체적 구현

```python
class ValidationGate:
    """토폴로지 변경 전 4차원 검증."""

    def validate(self, change: TopologyChange) -> ValidationResult:
        scores = {
            "consistency": self._check_consistency(change),   # 기존 그래프와 모순?
            "grounding": self._check_grounding(change),       # 출처가 있는가?
            "novelty": self._check_novelty(change),           # 기존에 없는 정보?
            "alignment": self._check_alignment(change),       # Paul의 가치와 정렬?
        }
        passed = all(s >= threshold for s in scores.values())
        return ValidationResult(passed=passed, scores=scores)

    def _check_consistency(self, change):
        """기존 그래프의 contradicts 관계와 충돌하지 않는가."""
        # 신규 edge의 양쪽 노드 → 기존 contradicts edge 확인
        # 새 edge가 contradicts와 supports를 동시에 만들면 → 점수 하락

    def _check_grounding(self, change):
        """source 필드가 있는가. 'claude' 단독이면 감점."""
        # source='paul' → 1.0
        # source='claude' + session_context → 0.7
        # source='enrichment' → 0.5
        # source 없음 → 0.0

    def _check_novelty(self, change):
        """벡터 유사도로 중복 감지."""
        # 유사도 > 0.95인 기존 노드가 있으면 → 0.0 (중복)
        # 유사도 0.7-0.95 → 0.5 (관련 있지만 새로움)
        # 유사도 < 0.7 → 1.0 (참신)

    def _check_alignment(self, change):
        """L4/L5 노드와의 의미적 거리."""
        # change가 L4/L5 노드와 contradicts 관계를 형성하면 → 0.0
        # 무관하면 → 0.7
        # supports 관계면 → 1.0
```

**적용 지점**:
1. `insert_edge()` — 모든 edge 생성 전
2. `enrichment` — LLM 출력을 DB에 반영하기 전
3. `promote_node()` — 승격 전
4. `remember()` 자동 edge — link() 단계에서

**성능 고려**: consistency/novelty는 벡터 검색 1회로 해결 (< 1ms). alignment는 L4/L5 노드가 적어(~6개) 부하 무시. grounding은 메타데이터 체크만.

### 단계적 구현 제안

1. **Phase 0 (즉시)**: enrichment 결과에 `validated: false` 플래그 추가, 임베딩 반영 차단
2. **Phase 1 (1주)**: grounding + novelty 체크 구현 (LLM 불필요, 규칙 기반)
3. **Phase 2 (2주)**: consistency 체크 구현 (그래프 탐색 기반)
4. **Phase 3 (1월)**: alignment 체크 구현 (L4/L5 벡터 유사도)

---

## Q3. PKG Representation — 접근 레벨, 프로비넌스

### 현재 부재

Balog et al.(2024)의 3축에서 Representation이 약하다:
- **접근 레벨**: nodes 테이블에 없음. 모든 노드가 동일한 접근 수준.
- **프로비넌스**: `source` 필드가 있지만 `'claude'` 단일 값이 대부분. 체인 추적 불가.

### 접근 레벨 설계

```sql
-- nodes 테이블에 컬럼 추가
ALTER TABLE nodes ADD COLUMN access_level TEXT DEFAULT 'shared';
-- 'private'   : Paul만 직접 입력한 것. Claude가 임의 수정 불가.
-- 'session'   : 현재 세션에서만 유효 (임시 메모, 진행 중인 작업)
-- 'shared'    : Claude + enrichment 접근 가능 (기본값, 현재 모든 노드)
-- 'model'     : 모든 AI 모델 접근 가능 (cross-model 공유)
```

**접근 제어 규칙**:
```python
ACCESS_RULES = {
    "private": {
        "read": ["paul", "claude"],
        "write": ["paul"],           # Claude도 수정 불가
        "delete": ["paul"],
    },
    "session": {
        "read": ["paul", "claude"],
        "write": ["paul", "claude"],
        "delete": ["paul", "claude", "system"],  # 세션 종료 시 자동 정리 가능
        "ttl": "session_end",
    },
    "shared": {
        "read": ["paul", "claude", "enrichment"],
        "write": ["paul", "claude", "enrichment"],
        "delete": ["paul"],
    },
    "model": {
        "read": ["*"],
        "write": ["paul", "claude"],
        "delete": ["paul"],
    },
}
```

**remember()와의 통합**:
```python
def remember(content, ..., access_level="shared"):
    # Paul이 source='paul'로 기억하면 → private 또는 shared (명시 선택)
    # Claude가 기억하면 → shared (기본)
    # enrichment가 생성하면 → shared
    # 세션 중 임시 저장 → session
```

### 프로비넌스 체인 설계

현재 `source='claude'`만으로는 **어떤 세션에서, 어떤 맥락에서, 어떤 결정으로** 이 노드가 생겼는지 알 수 없다.

```sql
-- nodes.metadata에 구조화된 provenance 추가 (JSON)
-- 또는 별도 테이블:
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

**이점**:
- `action_log`(Q1)와 결합하면 **완전한 리니지** 구현
- "이 패턴은 언제, 어떤 대화에서, 어떤 근거로 생성되었는가" 추적 가능
- enrichment 환각 추적: "이 facet은 gpt-5-mini E4에서 생성" → 신뢰도 차등

### 규모 현실성

- `access_level` 컬럼: 단순 TEXT, 즉시 추가 가능. 마이그레이션 비용 거의 0.
- `provenance` 테이블: 매 변경마다 행 추가 → 3,230 노드에서 ~10K 행 예상. 부하 무시.
- **핵심**: remember()에 `access_level` 파라미터 추가 + insert_node()에 전달. 하위 호환 유지.

---

## Q4. 온톨로지 버전 관리 — SNOMED/GO/Wikidata 패턴

### 현재 상태

**버전 관리 0.** 타입이나 관계를 변경하면:
- `schema.yaml` 직접 수정
- `config.py`의 `RELATION_TYPES` 직접 수정
- 기존 노드/엣지가 orphan 가능
- 변경 이력 없음

`correction_log`가 최근 추가되었지만, 이것은 **인스턴스 수정 이력**이지 **스키마 변경 이력**이 아니다.

### 우리에게 맞는 패턴: Wikidata + Gene Ontology 하이브리드

SNOMED CT는 의료용으로 과도하게 엄격하다. Schema.org는 너무 느슨하다. 우리 규모에 맞는 것:

```
Wikidata의 3-rank 시스템:
  normal → preferred → deprecated (+ reason)

Gene Ontology의 obsolete 처리:
  replaced_by 태그 + 대량 Obsolete 전략

이 둘을 결합:
```

### 구체적 구현: type_defs + 버전 스냅샷

**Q1의 `type_defs` 테이블 확장**:

```sql
CREATE TABLE type_defs (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    layer INTEGER NOT NULL,
    super_type TEXT,
    description TEXT,
    -- 버전 관리 컬럼들
    status TEXT DEFAULT 'active',     -- active | deprecated | archived
    rank TEXT DEFAULT 'normal',       -- normal | preferred | deprecated (Wikidata)
    deprecated_reason TEXT,           -- "Merged into Pattern" 등
    replaced_by TEXT,                 -- deprecated 시 대체 타입명
    deprecated_at TEXT,
    version INTEGER DEFAULT 1,       -- 정의 자체의 버전
    created_at TEXT,
    updated_at TEXT,
    UNIQUE(name, version)            -- 같은 이름 여러 버전 가능
);

-- 스냅샷 (분기 또는 대규모 변경 시)
CREATE TABLE ontology_snapshots (
    id INTEGER PRIMARY KEY,
    version_tag TEXT UNIQUE NOT NULL,  -- 'v2.0', 'v2.1' 등
    type_defs_json TEXT,               -- 전체 type_defs 스냅샷
    relation_defs_json TEXT,           -- 전체 relation_defs 스냅샷
    change_summary TEXT,               -- 변경 요약
    created_at TEXT
);
```

### deprecation 워크플로우

```python
def deprecate_type(type_name: str, reason: str, replaced_by: str = None):
    """타입 deprecated 처리. 관련 노드는 유지."""
    # 1. type_defs.status = 'deprecated', rank = 'deprecated'
    # 2. type_defs.deprecated_reason = reason
    # 3. type_defs.replaced_by = replaced_by (있으면)
    # 4. 관련 노드에 metadata.deprecated_type_warning = True 추가
    # 5. validators.py가 deprecated 타입으로 새 노드 생성 시 경고
    # 6. correction_log에 스키마 변경 기록

    # 기존 노드는 삭제하지 않는다.
    # replaced_by가 있으면 마이그레이션 안내만 제공.
    # 자동 마이그레이션은 별도 명시적 호출 필요.

def migrate_type(from_type: str, to_type: str, dry_run: bool = True):
    """deprecated 타입의 노드를 새 타입으로 마이그레이션."""
    # 1. from_type 노드 조회
    # 2. 각 노드의 type → to_type, layer → 새 layer
    # 3. correction_log에 기록
    # 4. promotion_history에 기록 (타입 변경도 이력)
    # 5. dry_run이면 결과만 보고
```

### 관계 타입 정리 로드맵

현재 48개 → 목표: 활성 12-15개 + deprecated 나머지

```
Phase 1: 사용 빈도 분석
  SELECT relation, COUNT(*) FROM edges GROUP BY relation ORDER BY COUNT(*) DESC;

Phase 2: 사용 0 관계 → status='deprecated', reason='unused since creation'
  replaced_by 없이 deprecated (의미 있는 대체가 없으므로)

Phase 3: 유사 관계 병합
  예: supports + reinforces_mutually → supports (deprecated: reinforces_mutually)
  예: connects_with (catch-all) 유지, 단 새 edge에는 구체적 관계 권장

Phase 4: super-category만 UI 노출
  causal(8→3), structural(8→3), semantic(8→3), layer_movement(6→3) = ~12개 활성
```

### 버전 스냅샷 트리거

- **자동**: type_defs 또는 relation_defs에 status 변경 시
- **수동**: `ontology_review()` 도구에서 사용자 트리거
- **분기**: 3개월마다 전체 스냅샷
- 스냅샷은 JSON이므로 Git으로도 추적 가능 (schema.yaml의 히스토리와 보완)

---

## Q5. 아카이브 정책 — 삭제 vs 비활성 vs 아카이브

### 현재 상태

**아카이브 정책 0.** `nodes.status` 필드가 존재하지만 `'active'`만 사용 중.
3,230개 노드 전부가 active. 가지치기 0회.

### 3단계 생명주기

```
active ──┬──→ inactive ──→ archived ──→ (물리 삭제는 없음)
         │
         └──→ merged ──→ (원본 유지, 대표 노드에 흡수)
```

**상태 정의**:

| 상태 | 의미 | recall()에 나오나 | 복구 가능 | 저장 위치 |
|------|------|------------------|----------|----------|
| **active** | 현재 살아있는 기억 | 예 | N/A | nodes 테이블 |
| **inactive** | 유예 기간 (30-90일) | 아니오 (기본), 예 (`include_inactive=true`) | 즉시 | nodes 테이블 |
| **archived** | 장기 보관 | 아니오 | 가능 (복원 필요) | nodes 테이블 (또는 별도 archive 테이블) |
| **merged** | 다른 노드에 흡수됨 | 아니오 | 가능 (분리 필요) | nodes 테이블 + merged_into 참조 |

### 비활성화 기준 (자동)

```python
INACTIVATION_RULES = {
    "L0_observation": {
        "condition": "layer=0 AND days_since_last_activated > 180",
        "action": "inactive",
        "reason": "L0 observation unused for 6 months"
    },
    "L1_low_quality": {
        "condition": "layer=1 AND quality_score < 0.3 AND days_since_created > 90",
        "action": "inactive",
        "reason": "Low quality L1 node, 90+ days old"
    },
    "orphan_node": {
        "condition": "edge_count = 0 AND days_since_created > 60",
        "action": "inactive",
        "reason": "Orphan node (no edges) for 60+ days"
    },
    "duplicate": {
        "condition": "similarity > 0.95 with higher-quality node",
        "action": "merged",
        "reason": "Duplicate of node #{better_node_id}"
    },
}

# L3+ 노드는 자동 비활성화 불가 (인지적 방화벽, Q6)
# tier=0 노드는 자동 비활성화 불가
```

### 아카이브 기준 (자동, inactive에서)

```python
ARCHIVE_RULES = {
    "inactive_timeout": {
        "condition": "status='inactive' AND days_since_inactivated > 90",
        "action": "archived",
        "reason": "Inactive for 90+ days without reactivation"
    },
}
```

### 복구 메커니즘

```python
def reactivate_node(node_id: int, reason: str) -> dict:
    """비활성/아카이브 노드를 active로 복원."""
    # 1. status → 'active'
    # 2. correction_log에 기록
    # 3. edge 복원 (inactive edge도 reactivate)
    # 4. ChromaDB 재임베딩 (아카이브에서 제거되었을 수 있으므로)
    # 5. recall()에서 자동 발견: inactive 노드가 쿼리와 유사도 높으면 "복구 후보" 안내
```

### "recall 시 자동 발견" — 망각의 역전

Storm et al.(2008)의 발견을 구현한다: recall()이 inactive 노드와 높은 유사도를 감지하면:
```python
# hybrid_search() 내부
if include_inactive_suggestions:
    inactive_similar = vector_store.search(query, top_k=3, filter={"status": "inactive"})
    if inactive_similar and inactive_similar[0].distance < 0.2:
        result["inactive_suggestions"] = [
            {"node_id": n.id, "content": n.content[:100], "reason": "High similarity to active recall"}
        ]
```

이것은 뇌의 "재공고화" — 잊혀진 기억이 새 맥락에서 부활하는 현상의 구현이다.

### 물리 삭제 — 절대 자동으로 하지 않는다

**설계 원칙**: 아카이브 이후에도 물리 삭제는 Paul의 명시적 요청 시에만.
- 이유: "정확히 파악을 못 했기 때문에 빼기가 두렵다" (Q8의 맥락)
- 아카이브는 recall()에서 안 나올 뿐, 데이터는 영구 보존
- 3,230 노드 전부 아카이브해도 SQLite 용량 < 50MB — 물리 삭제의 실익 없음

---

## Q6. 인지적 방화벽 + 유지보수성(제4조건)

### 위협 모델

L4/L5 노드(Belief, Philosophy, Value, Axiom, Wonder, Aporia)는 Paul의 **정체성**이다. 위협:

1. **Enrichment 환각**: LLM이 L4/L5 노드의 summary를 왜곡 → 의미 변질
2. **자동 edge**: L4/L5와 모순되는 새 노드에 `supports` edge 자동 생성
3. **Hebbian 편향**: Claude가 특정 가치를 자주 recall → 다른 가치가 상대적으로 약화
4. **승격 편향**: enrichment가 Claude의 편향을 반영한 노드를 L3→L4로 승격 제안

### 방화벽 규칙 (하드코딩)

```python
COGNITIVE_FIREWALL = {
    # L4/L5 보호 규칙 — 코드에 하드코딩, 설정 변경 불가
    "rules": [
        {
            "id": "F1",
            "name": "immutable_core",
            "rule": "L4/L5 노드의 content, type 필드는 source='paul' 외 수정 불가",
            "enforcement": "insert_node/update_node에서 layer >= 4 체크",
        },
        {
            "id": "F2",
            "name": "enrichment_restriction",
            "rule": "L4/L5 노드에 대한 enrichment는 summary/key_concepts만 허용. facets/domains/secondary_types 금지",
            "enforcement": "node_enricher.py에서 layer >= 4 분기",
        },
        {
            "id": "F3",
            "name": "auto_edge_prohibition",
            "rule": "L4/L5 노드에 자동 edge 생성 불가. 수동 edge만 허용 (source='paul')",
            "enforcement": "remember()의 link() 단계에서 대상 노드 layer 체크",
        },
        {
            "id": "F4",
            "name": "promotion_human_gate",
            "rule": "L3→L4, L4→L5 승격은 Paul의 명시적 확인 필수",
            "enforcement": "promote_node()에서 target_layer >= 4일 때 confirmation 요구",
        },
        {
            "id": "F5",
            "name": "decay_immunity",
            "rule": "L4/L5 edge의 decay_rate = 0. 핵심 가치는 시간으로 약화되지 않는다",
            "enforcement": "Hebbian 갱신에서 layer >= 4 edge 제외",
        },
        {
            "id": "F6",
            "name": "deletion_prohibition",
            "rule": "L4/L5 노드는 자동 비활성화/아카이브 불가",
            "enforcement": "아카이브 정책(Q5)에서 layer >= 4 제외",
        },
    ],
}
```

### 유지보수성 (Gemini의 제4조건) — 구체적 메커니즘

Clark의 3조건(접근가능+신뢰+자동사용)에 추가:
> "AI가 사용자의 정체성/목적을 은연중에 왜곡하지 않도록 방어하는 제어/복원 능력"

```python
def integrity_check() -> dict:
    """L4/L5 노드의 무결성 검증. 주기적 실행."""
    results = {}

    # 1. L4/L5 노드 수 변동 체크
    # v2 기준 ~6개 → 급격한 증가/감소는 이상 신호
    count = count_nodes(layer_gte=4, status='active')
    results["core_count"] = {"value": count, "baseline": 6, "alert": abs(count - 6) > 3}

    # 2. L4/L5 노드의 content 해시 비교 (이전 스냅샷 대비)
    # content가 바뀌었으면 → source 확인 → paul이 아니면 경고

    # 3. L4/L5에 연결된 edge 중 source='enrichment'인 것 감지
    suspicious_edges = find_edges(layer_gte=4, source='enrichment')
    results["suspicious_edges"] = len(suspicious_edges)

    # 4. Hebbian 편향 체크: L4/L5 edge strength 분포
    # 특정 가치만 과도하게 강화되었는지 확인

    return results
```

### RBAC 구현 — 레이어별 차등 권한

```python
LAYER_PERMISSIONS = {
    # (layer, operation) → 허용 actor 목록
    (0, "create"):  ["paul", "claude", "enrichment"],
    (0, "modify"):  ["paul", "claude", "enrichment"],
    (0, "delete"):  ["paul", "claude", "system"],

    (1, "create"):  ["paul", "claude", "enrichment"],
    (1, "modify"):  ["paul", "claude", "enrichment"],
    (1, "delete"):  ["paul"],

    (2, "create"):  ["paul", "claude", "enrichment"],
    (2, "modify"):  ["paul", "claude", "enrichment"],
    (2, "delete"):  ["paul"],

    (3, "create"):  ["paul", "claude"],
    (3, "modify"):  ["paul", "claude"],
    (3, "delete"):  ["paul"],

    (4, "create"):  ["paul"],              # 방화벽: Paul만
    (4, "modify"):  ["paul"],
    (4, "delete"):  ["paul"],

    (5, "create"):  ["paul"],              # 방화벽: Paul만
    (5, "modify"):  ["paul"],
    (5, "delete"):  ["paul"],
}
```

---

## Q7. 에너지 추적 — 세션 활동 트래킹

### Prigogine의 산일 구조에서 에너지원 = Paul의 세션 활동

시스템이 자기조직화하려면 **에너지 유입**을 측정해야 한다. 현재 이 측정이 없다.

### action_log + 세션 에너지 지표

Q1에서 제안한 `action_log`를 에너지 추적의 기반으로 사용:

```python
# 모든 도구 호출에서 action_log에 기록
# remember() → action_type='remember'
# recall() → action_type='recall'
# promote_node() → action_type='promote'
# enrichment → action_type='enrich'

# 에너지 지표 계산
def calculate_session_energy(session_id: str) -> dict:
    """한 세션의 에너지(활동량) 측정."""
    actions = get_actions_by_session(session_id)

    energy = {
        "total_actions": len(actions),
        "creation_energy": count(actions, type='remember'),    # 새 기억 생성
        "retrieval_energy": count(actions, type='recall'),     # 기억 인출
        "organization_energy": count(actions, type='promote'), # 구조화
        "exploration_energy": count(actions, type='recall', unique_domains=True),  # 도메인 탐색 다양성
    }

    # 분류: 어떤 종류의 에너지인가
    if energy["creation_energy"] > energy["retrieval_energy"]:
        energy["mode"] = "generative"      # 생성 모드 (새 경험 주입)
    elif energy["exploration_energy"] > energy["retrieval_energy"] * 0.3:
        energy["mode"] = "exploratory"     # 탐색 모드 (DMN 활성)
    else:
        energy["mode"] = "consolidation"   # 공고화 모드 (기존 기억 강화)

    return energy
```

### session_context.py와의 통합

현재 `session_context.py`는 세션 시작 시 **읽기 전용**으로 컨텍스트를 제공한다. 에너지 추적을 추가하면:

```python
# session_context.py 확장
def get_context_cli(project=""):
    # 기존: 최근 노드, Signal, Decision 등 출력
    # 추가: 최근 세션 에너지 패턴

    recent_energy = get_recent_session_energies(limit=5)

    print("=== 세션 에너지 패턴 ===")
    for session in recent_energy:
        print(f"  {session['date']} [{session['mode']}] "
              f"생성:{session['creation_energy']} "
              f"인출:{session['retrieval_energy']} "
              f"탐색:{session['exploration_energy']}")

    # 에너지 트렌드 감지
    if all(s['mode'] == 'consolidation' for s in recent_energy[-3:]):
        print("  ⚠️ 최근 3세션 공고화 모드 — 새 경험 주입 권장")
    if all(s['mode'] == 'generative' for s in recent_energy[-3:]):
        print("  ⚠️ 최근 3세션 생성 모드 — 구조화/승격 시간 권장")
```

### 에너지 기반 자동 정책

```python
# daily_enrich.py에서 에너지 기반 정책 결정
def decide_enrichment_focus():
    """세션 에너지 패턴에 따라 enrichment 초점 결정."""
    weekly_energy = get_weekly_energy_summary()

    if weekly_energy["mode"] == "generative":
        # 많은 새 노드 → Phase 1 (노드 enrichment) 우선
        return {"focus": "node_enrichment", "batch_size": 50}
    elif weekly_energy["mode"] == "consolidation":
        # 기존 기억 강화 중 → Phase 2 (edge 강화) 우선
        return {"focus": "edge_enrichment", "batch_size": 30}
    elif weekly_energy["mode"] == "exploratory":
        # 탐색 중 → Phase 3 (cross-domain 발견) 우선
        return {"focus": "graph_enrichment", "batch_size": 20}
```

### 구현 우선순위

1. `action_log` 테이블 추가 (Q1과 동시)
2. remember(), recall(), promote_node()에 action_log 기록 추가 (각 3줄)
3. `calculate_session_energy()` 함수 (순수 쿼리, 50줄)
4. session_context.py에 에너지 출력 추가 (10줄)

---

## Q8. 제1원칙과 빼기 — 무엇을 먼저 파악하고, 어떤 순서로 덜어내나

### "정확히 파악을 못 했기 때문에 빼기가 두렵다"

이 두려움은 합리적이다. 빼기 전에 파악해야 할 것:

### 먼저 파악해야 할 3가지

**1. 실제 사용 분포 — "50 타입 중 몇 개가 살아있는가"**

```sql
-- 즉시 실행 가능한 진단 쿼리
SELECT type, COUNT(*) as cnt,
       AVG(quality_score) as avg_quality,
       MIN(created_at) as first_seen,
       MAX(created_at) as last_seen
FROM nodes
WHERE status = 'active'
GROUP BY type
ORDER BY cnt DESC;

-- 관계 사용 분포
SELECT relation, COUNT(*) as cnt
FROM edges
GROUP BY relation
ORDER BY cnt DESC;

-- 사용 0 타입/관계
-- 이것이 "안전하게 뺄 수 있는 것"의 첫 번째 후보
```

**2. 연결 구조 — "뭘 빼면 뭐가 끊기는가"**

```sql
-- 허브 노드 식별 (edge 수 상위 20)
SELECT n.id, n.type, n.content, COUNT(e.id) as edge_count
FROM nodes n
LEFT JOIN edges e ON n.id = e.source_id OR n.id = e.target_id
GROUP BY n.id
ORDER BY edge_count DESC
LIMIT 20;

-- 고립 노드 (edge 0)
SELECT n.id, n.type, n.content
FROM nodes n
LEFT JOIN edges e ON n.id = e.source_id OR n.id = e.target_id
WHERE e.id IS NULL;
```

**3. 실질적 검색 기여도 — "이 타입/관계가 recall 품질에 기여하는가"**

이것은 action_log(Q7) 없이는 측정 불가. 따라서:
- **action_log를 먼저 구현해야 빼기의 근거를 만들 수 있다.**
- 2-4주간 recall 데이터 수집 → 어떤 타입/관계가 실제로 반환되고 활용되는지 측정
- 이것이 DeepSeek의 "수학적 근거" vs NotebookLM의 "인지적 복잡성"의 교차점

### 덜어내는 순서 — 안전한 것부터

```
Phase 0: 데이터 수집 (1-2주)
  action_log 구현 → recall 패턴 수집 → 사용 분포 확인
  이 단계에서는 아무것도 빼지 않는다.

Phase 1: 확실한 것 제거 (1주)
  - 사용 0 관계 타입 → deprecated (삭제 아님)
  - 사용 0 노드 타입 → deprecated (삭제 아님)
  - 고립 노드(edge 0, L0/L1) → inactive
  - 중복 노드(유사도 > 0.95) → merged
  위험도: 최소. deprecated는 되돌릴 수 있다.

Phase 2: super-type 구조화 (2주)
  - 50 타입을 7-10개 super-type으로 그룹화
  - 기존 타입은 sub-type으로 유지 (삭제하지 않음)
  - recall()에서 super-type 필터 추가
  - UI/디버깅 시 super-type으로 탐색
  위험도: 낮음. 추가 구조화일 뿐, 기존 데이터 불변.

Phase 3: 관계 원시화 (2주)
  - 48 관계 → 12-15개 활성 + 나머지 deprecated
  - 유사 관계 병합 (replaced_by 포함)
  - infer_relation() 규칙 단순화
  위험도: 중간. 기존 edge.relation은 그대로. 새 edge에만 적용.

Phase 4: enrichment 단순화 (1개월)
  - 5모델 25태스크 → 확인된 가치 있는 태스크만 유지
  - action_log 데이터 기반으로 실제 기여도 측정
  - Phase 0 데이터 없이는 이 단계 진행 불가
  위험도: 높음. 충분한 데이터 후에만 진행.
```

### 핵심 원칙: "빼기"가 아니라 "비활성화"

Paul의 두려움에 대한 직접적 답:

> **물리적 삭제는 하지 않는다.** deprecated + archived로 검색에서 제외하되 데이터는 보존한다.
>
> 이것은 뇌의 시냅스 가지치기와 정확히 같다 — 시냅스를 "끊는" 것이지 뉴런을 "죽이는" 것이 아니다.
> 연결이 끊긴 뉴런은 나중에 다른 맥락에서 새 연결을 형성할 수 있다 (Storm et al., 2008: 가속화된 재학습).
>
> 구체적으로: deprecated 타입으로 분류된 노드도 `reactivate_node()`로 언제든 복구 가능.
> 아카이브된 노드도 recall()의 `include_inactive_suggestions`로 자동 발견 가능.
>
> **빼기의 본질은 "존재"를 없애는 것이 아니라 "주의"에서 제외하는 것이다.**

---

## 구현 우선순위 종합

### 즉시 (1주 이내, 코드 변경 최소)

| # | 항목 | 근거 | 영향 |
|---|------|------|------|
| 1 | `action_log` 테이블 추가 | Q1+Q7+Q8의 기반 | 모든 후속 작업의 데이터 소스 |
| 2 | `type_defs` + `relation_defs` 테이블 추가 | Q1+Q4의 기반 | 메타-인스턴스 분리 시작 |
| 3 | L4/L5 방화벽 규칙 F1-F3 하드코딩 | Q6 | 정체성 보호 즉시 시작 |
| 4 | 사용 분포 진단 쿼리 실행 | Q8 Phase 0 | 빼기의 근거 확보 |

### 단기 (2-4주)

| # | 항목 | 근거 | 영향 |
|---|------|------|------|
| 5 | remember() 3함수 분리 (classify/store/link) | Q1 | 온톨로지 진화 용이 |
| 6 | `access_level` 컬럼 + 기본 RBAC | Q3+Q6 | 접근 제어 시작 |
| 7 | `provenance` 테이블 + 기록 시작 | Q3 | 리니지 추적 시작 |
| 8 | ValidationGate Phase 1 (grounding+novelty) | Q2 | 피드백 루프 1차 차단 |
| 9 | 아카이브 정책 (inactive/archived 상태) | Q5 | 첫 가지치기 시작 |
| 10 | 세션 에너지 측정 + context 출력 | Q7 | 자기조직화 모니터링 시작 |

### 중기 (1-3개월)

| # | 항목 | 근거 |
|---|------|------|
| 11 | 사용 0 타입/관계 deprecated 처리 | Q4+Q8 Phase 1 |
| 12 | super-type 구조화 | Q8 Phase 2 |
| 13 | ValidationGate Phase 2-3 | Q2 |
| 14 | ontology_snapshots + 버전 관리 | Q4 |
| 15 | 에너지 기반 enrichment 정책 | Q7 |

---

## 설계 원칙 요약

1. **메타-인스턴스 분리**: 타입/관계 정의는 별도 테이블. 인스턴스는 기존 구조 유지.
2. **비활성화 > 삭제**: 모든 "빼기"는 deprecated/inactive/archived. 물리 삭제 금지.
3. **하드코딩된 방화벽**: L4/L5 보호는 설정이 아니라 코드. 변경 시 코드 리뷰 필수.
4. **데이터 기반 결정**: action_log 없이 빼기 결정 금지. 최소 2주 수집 후.
5. **점진적 진화**: 기존 API 하위 호환 유지. remember()는 외부 인터페이스 불변.
6. **에너지 = 활동**: Prigogine의 산일 구조를 action_log로 구현. 에너지 없으면 자기조직화 없음.

---

---

# 심화 1: action_log 중심 설계

> Q1+Q7+Q8의 공통 기반. 모든 후속 작업의 데이터 소스.

## 실제 DB 진단 결과 기반 설계 근거

```
현재 edge 출처 분포:
  other(enrichment E14 등):  6,023 (95.2%)
  orphan_fix:                  264 (4.2%)
  auto(remember):               31 (0.5%)
  enrichment(labeled):            7 (0.1%)
```

**발견**: edge의 95%가 enrichment 파이프라인에서 생성되었다. remember()의 자동 edge는 31개뿐. 이 비율 자체가 시스템의 "에너지원"이 어디인지 보여준다 — 현재는 enrichment가 에너지의 대부분을 공급하고, Paul의 직접 활동(remember/recall)은 극소량이다.

**시사점**: action_log는 이 불균형을 측정 가능하게 만드는 첫 단계다. Paul의 활동이 늘어나야 Prigogine의 산일 구조가 작동한다.

## action_log 스키마 — 정밀 설계

```sql
CREATE TABLE action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- 누가
    actor TEXT NOT NULL,              -- 'paul' | 'claude' | 'enrichment:E4' | 'system:daily_enrich'
    session_id TEXT,                  -- sessions.session_id FK (nullable: enrichment은 세션 밖)
    -- 무엇을
    action_type TEXT NOT NULL,        -- 아래 Action Taxonomy 참조
    target_type TEXT,                 -- 'node' | 'edge' | 'type_def' | 'relation_def' | 'graph'
    target_id INTEGER,               -- node_id 또는 edge_id (nullable: graph-level action)
    -- 어떻게
    params TEXT DEFAULT '{}',         -- JSON: 쿼리, 필터, 옵션 등
    result TEXT DEFAULT '{}',         -- JSON: 반환값 요약 (결과 node_ids, edge_ids 등)
    -- 맥락
    context TEXT,                     -- 어떤 대화/작업 중이었는가 (free text, 100자)
    model TEXT,                       -- 'claude-opus-4-6' | 'gpt-5-mini' | null(사람)
    -- 메타
    duration_ms INTEGER,              -- 실행 시간 (성능 추적)
    token_cost INTEGER,               -- API 토큰 사용량 (enrichment 추적)
    created_at TEXT NOT NULL,
    -- 인덱스
    CONSTRAINT fk_session FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX idx_action_type ON action_log(action_type);
CREATE INDEX idx_action_actor ON action_log(actor);
CREATE INDEX idx_action_session ON action_log(session_id);
CREATE INDEX idx_action_target ON action_log(target_type, target_id);
CREATE INDEX idx_action_created ON action_log(created_at);
```

## Action Taxonomy — 8개 카테고리, 24개 action_type

```python
ACTION_TAXONOMY = {
    # 1. 기억 생성 (Creation)
    "remember":         "새 노드 생성 (remember() 호출)",
    "auto_link":        "remember() 내 자동 edge 생성",

    # 2. 기억 인출 (Retrieval)
    "recall":           "hybrid_search 실행",
    "get_context":      "세션 컨텍스트 조회",
    "inspect":          "노드 상세 조회",

    # 3. 기억 조직화 (Organization)
    "promote":          "노드 승격 (promote_node)",
    "merge":            "노드 병합",
    "classify":         "타입 재분류",

    # 4. 기억 강화 (Strengthening)
    "hebbian_update":   "recall 시 edge 강화",
    "edge_create":      "수동 edge 생성",
    "edge_modify":      "edge 속성 변경",

    # 5. 기억 약화 (Weakening)
    "inactivate":       "노드 inactive 전환",
    "archive":          "노드 archive 전환",
    "reactivate":       "노드 재활성화",
    "deprecate":        "타입/관계 deprecated",

    # 6. 품질 관리 (Quality)
    "enrich":           "enrichment 태스크 실행 (E1-E25)",
    "validate":         "검증 게이트 실행",
    "integrity_check":  "L4/L5 무결성 검증",

    # 7. 스키마 관리 (Schema)
    "type_create":      "새 타입 정의",
    "type_modify":      "타입 정의 변경",
    "relation_create":  "새 관계 정의",
    "relation_modify":  "관계 정의 변경",
    "snapshot":         "온톨로지 스냅샷 생성",

    # 8. 분석 (Analysis)
    "analyze_signals":  "Signal 분석",
    "dashboard":        "대시보드 조회",
}
```

## 삽입 지점 — 코드 내 정확한 위치

### remember.py (tools/remember.py:39-49)
```python
# 현재: insert_node() 호출 후 바로 ChromaDB
# 추가: insert_node() 직후
action_log.record(
    action_type="remember",
    actor=source,  # remember()의 source 파라미터 재활용
    target_type="node",
    target_id=node_id,
    params=json.dumps({"type": type, "project": project}),
    result=json.dumps({"node_id": node_id}),
)

# 자동 edge 생성 후 (tools/remember.py:90-97)
action_log.record(
    action_type="auto_link",
    actor="system",
    target_type="edge",
    target_id=edge_id,
    params=json.dumps({"source_node": node_id, "target_node": sim_id, "relation": relation}),
)
```

### hybrid.py (storage/hybrid.py — _hebbian_update)
```python
# _hebbian_update() 내부
# 현재: edge.frequency += 1, last_activated 갱신
# 추가: 갱신 후
action_log.record(
    action_type="hebbian_update",
    actor="system",
    target_type="edge",
    target_id=edge_id,
    params=json.dumps({"query": query_text, "result_ids": result_ids}),
)
```

### recall (tools/recall.py)
```python
# recall() 반환 직전
action_log.record(
    action_type="recall",
    actor="claude",  # 현재는 항상 claude
    params=json.dumps({"query": query, "type_filter": type_filter, "project": project}),
    result=json.dumps({"count": len(results), "top_ids": [r["id"] for r in results[:5]]}),
)
```

### promote_node.py (tools/promote_node.py)
```python
# 승격 완료 후
action_log.record(
    action_type="promote",
    actor="claude",
    target_type="node",
    target_id=node_id,
    params=json.dumps({"from_type": old_type, "to_type": target_type, "reason": reason}),
)
```

### enrichment (scripts/enrich/node_enricher.py)
```python
# 각 E 태스크 완료 후
action_log.record(
    action_type="enrich",
    actor=f"enrichment:{task_id}",  # 'enrichment:E4' 등
    target_type="node",
    target_id=node_id,
    model=model_name,
    token_cost=tokens_used,
    params=json.dumps({"task": task_id, "fields_updated": fields}),
)
```

## action_log 기반 record() 함수 구현

```python
# storage/action_log.py (신규 파일)
import json
import sqlite3
from datetime import datetime, timezone
from config import DB_PATH

def record(
    action_type: str,
    actor: str = "claude",
    session_id: str = None,
    target_type: str = None,
    target_id: int = None,
    params: str = "{}",
    result: str = "{}",
    context: str = None,
    model: str = None,
    duration_ms: int = None,
    token_cost: int = None,
) -> int:
    """action_log에 기록. 실패해도 main flow 중단하지 않는다."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.execute(
            """INSERT INTO action_log
               (actor, session_id, action_type, target_type, target_id,
                params, result, context, model, duration_ms, token_cost, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (actor, session_id, action_type, target_type, target_id,
             params, result, context, model, duration_ms, token_cost, now),
        )
        log_id = cur.lastrowid
        conn.commit()
        conn.close()
        return log_id
    except Exception:
        return -1  # 로깅 실패는 무시

def get_session_actions(session_id: str) -> list[dict]:
    """한 세션의 모든 action 조회."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM action_log WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recent_actions(limit: int = 50, action_type: str = None) -> list[dict]:
    """최근 action 조회."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM action_log"
    params = []
    if action_type:
        sql += " WHERE action_type = ?"
        params.append(action_type)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

## 세션 에너지 계산 — 구현체

```python
# storage/action_log.py 에 추가

def calculate_session_energy(session_id: str) -> dict:
    """한 세션의 에너지(활동량) 측정."""
    actions = get_session_actions(session_id)
    if not actions:
        return {"mode": "idle", "total": 0}

    creation = sum(1 for a in actions if a["action_type"] in ("remember", "auto_link"))
    retrieval = sum(1 for a in actions if a["action_type"] in ("recall", "get_context", "inspect"))
    organization = sum(1 for a in actions if a["action_type"] in ("promote", "merge", "classify"))
    strengthening = sum(1 for a in actions if a["action_type"] in ("hebbian_update", "edge_create"))

    # 도메인 다양성 = recall 쿼리의 고유 project 수
    recall_actions = [a for a in actions if a["action_type"] == "recall"]
    domains = set()
    for a in recall_actions:
        try:
            p = json.loads(a.get("params", "{}"))
            if p.get("project"):
                domains.add(p["project"])
        except Exception:
            pass
    exploration = len(domains)

    # 모드 판정
    total = creation + retrieval + organization + strengthening
    if total == 0:
        mode = "idle"
    elif creation > retrieval:
        mode = "generative"
    elif exploration >= 3 or (exploration > 0 and exploration / max(retrieval, 1) > 0.3):
        mode = "exploratory"
    elif organization > 0:
        mode = "organizing"
    else:
        mode = "consolidation"

    return {
        "mode": mode,
        "total": total,
        "creation": creation,
        "retrieval": retrieval,
        "organization": organization,
        "strengthening": strengthening,
        "exploration_domains": exploration,
        "session_id": session_id,
    }

def get_energy_trend(limit: int = 10) -> list[dict]:
    """최근 N 세션의 에너지 패턴."""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    sessions = conn.execute(
        "SELECT DISTINCT session_id FROM action_log ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [calculate_session_energy(s["session_id"]) for s in sessions if s["session_id"]]
```

## action_log + provenance 통합: 리니지 그래프

action_log와 provenance 테이블의 관계:

```
action_log: "무엇이 일어났는가" (이벤트 로그)
provenance: "왜, 어떤 맥락에서 일어났는가" (인과 추적)

action_log.id → provenance.action_id (1:N)
하나의 action이 여러 provenance 기록을 생성할 수 있다.
예: enrichment E13이 5개 edge를 생성 → action_log 1행 + provenance 5행
```

provenance는 action_log의 확장이므로, **action_log 먼저 구현 → 안정화 후 provenance 추가**가 올바른 순서다. action_log 만으로도 Q7(에너지), Q8(빼기 근거)의 기능을 즉시 제공한다.

---

# 심화 2: 인지적 방화벽 — 실제 코드 삽입 지점

## 실제 L4/L5 노드 현황 (DB 진단 결과)

```
L4/L5 총 6개 노드. 전부 orphan (edge 0).

#4161 L4 [Belief]     q=0.92 src=user
  "모든 현상을 다차원으로 해석하는 것이 사고의 본질이다"
#4162 L4 [Philosophy]  q=0.78 src=user
  "기억과 연결이 동시에, 의식하지 않아도 자동으로 일어난다"
#4165 L4 [Philosophy]  q=0.92 src=user
  "의지에 의존하지 않고 환경과 규칙을 설계해서 관찰->분해->구조화->검증"
#4163 L4 [Value]       q=0.95 src=user
  "뇌의 다차원적 연결을 외부화하고 싶다는 욕구. 더, 더, 더!"
#4166 L4 [Value]       q=0.92 src=user
  "이색적 접합 - 서로 다른 도메인의 개념을 연결해서 새로운 의미"
#4164 L5 [Axiom]       q=0.85 src=user
  "'가고 싶은 지점'과 '가야만 하는 지점' - 이 둘의 수렴과 분기 추적"
```

**치명적 발견**: L4/L5 노드에 edge가 하나도 없다.
- recall()에서 이 노드들이 반환되려면 벡터 유사도에만 의존
- 그래프 보너스(GRAPH_BONUS=0.3) 전혀 못 받음
- Hebbian 강화도 없음 (edge가 없으므로)
- **Paul의 핵심 가치가 시스템에서 사실상 유리(遊離)되어 있다**

**방화벽 이전에 L4/L5 연결을 먼저 구축해야 한다.** 하지만 자동 edge가 아닌 수동 edge로.

## F1: immutable_core — 삽입 지점

### sqlite_store.py의 모든 UPDATE/DELETE 경로에 가드

```python
# storage/sqlite_store.py — 신규 함수
def _check_firewall(node_id: int, actor: str, operation: str) -> bool:
    """L4/L5 노드에 대한 방화벽 체크. False면 차단."""
    conn = _connect()
    row = conn.execute("SELECT layer FROM nodes WHERE id = ?", (node_id,)).fetchone()
    conn.close()
    if not row or row["layer"] is None:
        return True  # layer 없으면 통과
    if row["layer"] < 4:
        return True  # L0-L3은 통과

    # L4/L5 도달 — actor 체크
    if operation in ("modify_content", "modify_type", "delete"):
        return actor == "paul"  # Paul만 허용
    if operation == "modify_metadata":
        return actor in ("paul", "claude")  # 메타데이터는 Claude도 가능
    if operation == "enrich":
        return True  # enrichment는 summary/key_concepts만 (별도 제한)
    return True
```

### 삽입 지점 1: update_node (현재 미존재 — 추가 필요)

현재 `sqlite_store.py`에 `update_node()` 함수가 없다. enrichment가 직접 SQL로 UPDATE한다. 이것이 방화벽 우회의 근본 원인.

```python
# storage/sqlite_store.py — 신규 함수
def update_node(node_id: int, updates: dict, actor: str = "system") -> bool:
    """노드 업데이트. 방화벽 적용."""
    # 방화벽 체크
    content_fields = {"content", "type"}
    has_content_change = bool(content_fields & set(updates.keys()))
    if has_content_change and not _check_firewall(node_id, actor, "modify_content"):
        raise PermissionError(f"F1 violation: L4/L5 content/type modification requires actor='paul', got '{actor}'")

    # 허용된 경우 UPDATE 실행
    # ...
```

### 삽입 지점 2: enrichment node_enricher.py

```python
# scripts/enrich/node_enricher.py — enrich_node_combined() 내부
# 현재: layer 체크 없이 모든 필드 업데이트

# 추가: layer >= 4 분기
if node.get("layer") is not None and node["layer"] >= 4:
    # F2: L4/L5는 summary, key_concepts만 enrichment 허용
    allowed_fields = {"summary", "key_concepts", "quality_score"}
    updates = {k: v for k, v in updates.items() if k in allowed_fields}
    # facets, domains, secondary_types 제거
```

## F3: auto_edge_prohibition — 삽입 지점

### tools/remember.py:72-97 (자동 edge 생성 루프)

```python
# 현재:
for sim_id, distance, _ in similar:
    if sim_id == node_id:
        continue
    if distance > SIMILARITY_THRESHOLD:
        continue
    # ... edge 생성

# 변경:
for sim_id, distance, _ in similar:
    if sim_id == node_id:
        continue
    if distance > SIMILARITY_THRESHOLD:
        continue
    sim_node = sqlite_store.get_node(sim_id)
    if not sim_node:
        continue
    # F3: L4/L5 대상 자동 edge 금지
    sim_layer = sim_node.get("layer")
    if sim_layer is not None and sim_layer >= 4:
        continue  # 방화벽: 자동 edge로 L4/L5에 접근 불가
    # ... edge 생성
```

### enrichment E13 (scripts/enrich/relation_extractor.py — 새 edge 발견)

```python
# E13에서도 동일 가드 필요
# 새 edge 생성 전:
if target_layer >= 4 or source_layer >= 4:
    continue  # F3: enrichment가 L4/L5에 edge 생성 불가
```

## F4: promotion_human_gate — 삽입 지점

### tools/promote_node.py

```python
# 현재: VALID_PROMOTIONS 경로 체크만
# 추가: target_layer >= 4 시 human gate

target_layer = PROMOTE_LAYER.get(target_type)
if target_layer is not None and target_layer >= 4:
    # F4: L3->L4, L4->L5 승격은 source='paul' 필수
    if source != "paul":
        return {
            "error": f"F4 violation: Promotion to L4/L5 requires human confirmation.",
            "node_id": node_id,
            "requested_type": target_type,
            "action": "blocked"
        }
```

## F5: decay_immunity — 삽입 지점

### storage/hybrid.py — _hebbian_update()

```python
# 현재: 모든 edge에 frequency += 1
# 변경: L4/L5 edge 제외

for edge in matching_edges:
    # F5: L4/L5 edge는 decay/Hebbian 갱신 제외
    source_node = sqlite_store.get_node(edge["source_id"])
    target_node = sqlite_store.get_node(edge["target_id"])
    src_layer = source_node.get("layer") if source_node else None
    tgt_layer = target_node.get("layer") if target_node else None
    if (src_layer is not None and src_layer >= 4) or (tgt_layer is not None and tgt_layer >= 4):
        continue  # L4/L5 edge는 시간에 의해 변하지 않는다
    # ... 기존 Hebbian 갱신
```

**성능 주의**: 현재 _hebbian_update()에서 매 edge마다 get_node() 2번 호출은 비효율. 최적화:
```python
# edge 테이블에 source_layer, target_layer 캐시 컬럼 추가
# 또는: recall 결과 노드의 layer를 미리 조회해서 set으로 전달
```

## F6: deletion_prohibition — 삽입 지점

Q5의 아카이브 정책과 통합:

```python
INACTIVATION_RULES = {
    # ... 기존 규칙들 ...
}

# F6: 모든 자동 비활성화 규칙에 글로벌 예외
FIREWALL_EXCEPTIONS = {
    "layer_gte_4": "L4/L5 노드는 자동 비활성화/아카이브 불가",
    "tier_0_manual": "tier=0(core) 노드는 자동 비활성화 시 경고",
}
```

## integrity_check() — 구현체

```python
# tools/integrity.py (신규 파일)
import hashlib
import json
from storage import sqlite_store

# L4/L5 baseline (최초 실행 시 기록, 이후 비교)
INTEGRITY_BASELINE_KEY = "l4l5_integrity_baseline"

def integrity_check() -> dict:
    """L4/L5 노드의 무결성 검증."""
    conn = sqlite_store._connect()

    # 1. L4/L5 노드 현황
    l4l5 = conn.execute(
        "SELECT id, type, layer, content, source, quality_score FROM nodes WHERE layer >= 4 AND status = 'active'"
    ).fetchall()

    results = {
        "core_count": len(l4l5),
        "baseline_count": 6,  # 현재 기준
        "count_alert": abs(len(l4l5) - 6) > 2,
        "nodes": [],
        "violations": [],
    }

    for node in l4l5:
        node_info = {
            "id": node["id"],
            "type": node["type"],
            "layer": node["layer"],
            "source": node["source"],
            "content_hash": hashlib.sha256(node["content"].encode()).hexdigest()[:16],
        }

        # 2. source != 'user'/'paul' 체크
        if node["source"] not in ("user", "paul"):
            results["violations"].append({
                "rule": "F1",
                "node_id": node["id"],
                "detail": f"L{node['layer']} node created by '{node['source']}', not 'paul'",
            })

        # 3. edge 체크: enrichment가 만든 L4/L5 edge 탐지
        edges = conn.execute(
            """SELECT e.*, e.description FROM edges e
               WHERE (e.source_id = ? OR e.target_id = ?)""",
            (node["id"], node["id"]),
        ).fetchall()

        for e in edges:
            if "enrichment" in (e["description"] or "").lower() or "E13" in (e["description"] or ""):
                results["violations"].append({
                    "rule": "F3",
                    "node_id": node["id"],
                    "edge_id": e["id"],
                    "detail": f"Enrichment-created edge touching L{node['layer']} node",
                })

        node_info["edge_count"] = len(edges)
        results["nodes"].append(node_info)

    conn.close()
    return results
```

## L4/L5 연결 복구 — 방화벽 이전의 선행 작업

현재 L4/L5 노드가 전부 orphan이므로, 방화벽을 설치하기 전에 **수동 edge를 먼저 만들어야** 한다.

제안하는 연결 구조:

```
L5 Axiom (#4164: 수렴/분기 추적)
  ├── crystallized_into ← L4 Value (#4163: 더, 더, 더)
  ├── crystallized_into ← L4 Value (#4166: 이색적 접합)
  └── governs ← L4 Belief (#4161: 다차원 해석)

L4 Value (#4163: 외부화 욕구)
  ├── expressed_as → L3 Principle: 컨텍스트 효율성
  └── expressed_as → L3 Principle: 확장된 인지 시스템

L4 Value (#4166: 이색적 접합)
  ├── expressed_as → L2 Pattern: DMN/EXPLORATION_RATE
  └── expressed_as → L3 Principle: 연결 자동화

L4 Philosophy (#4162: 자동 기억+연결)
  ├── expressed_as → L3 Principle: Hebbian 학습
  └── governs → L2 Pattern: recall 시 자동 강화

L4 Philosophy (#4165: 환경/규칙 설계)
  ├── expressed_as → L3 Principle: 의지 아닌 시스템
  └── governs → L2 Framework: 오케스트레이션

L4 Belief (#4161: 다차원 해석)
  ├── expressed_as → L3 Principle: 다각도 분석
  └── governs → L2 Pattern: 크로스 도메인 연결
```

이 연결은 **Paul이 직접 확인/승인**해야 한다 (F3 규칙에 의해 자동 생성 불가). 구현 세션에서 Paul에게 각 연결을 제안하고 승인받는 형태로 진행.

---

# 심화 3: 빼기 실행 계획 — 실제 데이터 기반

## 실제 분포 진단 — 핵심 발견

### 타입 분포 (31/50 사용중)

```
===== 사용중 타입 (31개) =====
Tier A (100+ 노드, 핵심):
  Workflow(567), Insight(331), Principle(284), Decision(274),
  Narrative(193), Tool(173), Framework(159), Skill(140),
  Project(133), Goal(131), Agent(130), Pattern(128), SystemVersion(122)
  → 13개 타입이 전체 3,268의 86%

Tier B (10-100 노드, 보조):
  Conversation(89), Failure(85), Experiment(72), Breakthrough(58),
  Identity(44), Unclassified(38), Evolution(28), Connection(24),
  Tension(20), Question(11), Observation(11)
  → 11개

Tier C (1-10 노드, 소수):
  Preference(7), Signal(5), AntiPattern(5), Value(2),
  Philosophy(2), Belief(1), Axiom(1)
  → 7개 (L4/L5 포함)

===== 미사용 타입 (19개) =====
schema.yaml에만 존재, DB 인스턴스 0:
  Evidence, Trigger, Context, Plan, Ritual, Constraint, Assumption,
  Heuristic, Trade-off, Metaphor, Concept,
  Boundary, Vision, Paradox, Commitment,
  Mental Model, Lens,
  Wonder, Aporia
```

### 관계 분포 (51개 in DB, 48개 정의)

```
===== Top 10 관계 (전체의 91.7%) =====
  supports         1,475 (23.3%)
  part_of            961 (15.2%)
  expressed_as       741 (11.7%)
  generalizes_to     606 (9.6%)
  instantiated_as    455 (7.2%)
  led_to             259 (4.1%)
  enabled_by         254 (4.0%)
  parallel_with      187 (3.0%)
  assembles          167 (2.6%)
  contains           166 (2.6%)

===== 6개 잘못된 관계 (ALL_RELATIONS에 없음) =====
  strengthens, extracted_from, governs, instance_of, evolves_from, validated_by
  → enrichment E14가 ALL_RELATIONS 목록 밖의 관계를 생성한 결과
  → correction_log에 기록되어 있어야 하나, connects_with로 폴백되지 않은 것도 있음

===== 3개 미사용 유효 관계 =====
  interpreted_as, questions, viewed_through
  → perspective 카테고리의 3개 관계 모두 미사용
```

### 구조적 발견

```
레이어 분포:
  L?(None): 55 (1.7%) — 분류 안 된 노드
  L0:      293 (9.0%)
  L1:    1,913 (58.5%) — 압도적
  L2:      673 (20.6%)
  L3:      328 (10.0%)
  L4:        5 (0.15%)
  L5:        1 (0.03%)

Tier 분포:
  tier=0 (core):  334 (10.2%)
  tier=1 (verified): 402 (12.3%)
  tier=2 (auto):  2,532 (77.5%) — 미검증 압도적

Orphan 노드: 26개 (전체의 0.8%)
  L4/L5 6개 + Failure/Decision/Insight/Connection 등 20개
```

## Phase 0 결론 — 데이터가 말하는 것

### 1. 19개 미사용 타입은 즉시 deprecated 가능

schema.yaml에만 존재하고 인스턴스가 0인 타입들. deprecated 처리해도 기존 데이터에 영향 0.

```
즉시 deprecated 후보 (인스턴스 0):
  L0: Evidence, Trigger, Context
  L1: Plan, Ritual, Constraint, Assumption
  L2: Heuristic, Trade-off, Metaphor, Concept
  L3: Boundary, Vision, Paradox, Commitment
  L4: Mental Model, Lens
  L5: Wonder, Aporia

deprecated 이유: "No instances since system creation. Can be reactivated if needed."
replaced_by: 각각 가장 가까운 활성 타입 지정
  Evidence → Observation
  Trigger → Signal
  Context → Conversation
  Plan → Goal
  Ritual → Workflow
  Constraint → Principle
  Assumption → Belief
  Heuristic → Pattern
  Trade-off → Tension
  Metaphor → Connection
  Concept → Insight
  Boundary → Principle
  Vision → Goal
  Paradox → Tension
  Commitment → Decision
  Mental Model → Framework
  Lens → Framework
  Wonder → Question
  Aporia → Question
```

### 2. 잘못된 관계 6개는 정리 필요

enrichment가 생성한 invalid relation들. correction_log 확인 후:
- `governs`: 실제로는 `governed_by`의 역방향으로 의도된 것. 이미 31개 edge 존재. **ALL_RELATIONS에 추가**하는 것이 삭제보다 나음.
- `strengthens`, `validated_by`: `supports`, `validates`의 변형. → 기존 edge의 relation을 교정.
- `extracted_from`, `instance_of`, `evolves_from`: 각각 `derived_from`, `instantiated_as`, `evolved_from`의 변형. → 교정.

### 3. perspective 카테고리(3개 관계) 전체 미사용

`interpreted_as`, `questions`, `viewed_through` 모두 사용 0.
→ deprecated 후보. 하지만 `questions`는 Question 타입의 자연스러운 관계이므로 유보.

### 4. super-type 구조 제안 (31개 활성 → 8개 super-type)

```
Super-type 1: Experience (L0)
  Observation, Conversation, Narrative, Preference
  → 원시 경험/입력

Super-type 2: Action (L1)
  Decision, Experiment, Failure, Breakthrough, Evolution
  → 행동과 결과

Super-type 3: System (L1)
  Workflow, Tool, Skill, Agent, Project, Goal, SystemVersion
  → 시스템 구성요소

Super-type 4: Signal (L1)
  Signal, Question, AntiPattern
  → 관찰 중인 패턴

Super-type 5: Concept (L2)
  Pattern, Insight, Framework, Connection, Tension
  → 추상화된 지식

Super-type 6: Identity (L3)
  Principle, Identity
  → 핵심 정체성

Super-type 7: Worldview (L4)
  Belief, Philosophy, Value
  → 세계관

Super-type 8: Axiom (L5)
  Axiom
  → 근본 공리

+ Unclassified (메타)
```

### 5. L1 과밀(58.5%) 문제

1,913개 노드가 L1에 몰려 있다. 승격이 거의 안 일어나고 있다는 증거.
- Signal → Pattern 승격: Signal이 5개밖에 없음 (대부분 L1에서 Pattern으로 직접 기록)
- 자동 승격 메커니즘 필요성 재확인

### 6. tier=2(77.5%) — 검증 미달

2,532개 노드가 미검증 상태. enrichment가 quality_score를 부여하지만 이것 자체가 LLM 생성값이므로 검증된 것이 아니다.

## Phase 1 실행 계획 (확실한 것)

```
Step 1: type_defs 테이블 생성 + 31개 활성 타입 마이그레이션
Step 2: 19개 미사용 타입 → deprecated 처리
Step 3: relation_defs 테이블 생성 + 48개 활성 관계 마이그레이션
Step 4: 6개 잘못된 관계 교정 (edge.relation UPDATE)
  governs → ALL_RELATIONS에 추가 (역방향 관계로 정당성 있음)
  strengthens → supports
  validated_by → validates
  extracted_from → derived_from
  instance_of → instantiated_as
  evolves_from → evolved_from
Step 5: 3개 미사용 관계 중 interpreted_as, viewed_through → deprecated
  questions는 유보 (Question 타입과 자연스러운 쌍)
Step 6: 26개 orphan 노드 검토
  L4/L5 6개 → 수동 edge 연결 (Paul 확인 필요)
  나머지 20개 → 내용 확인 후 inactive 또는 edge 생성
Step 7: L?(None) 55개 노드 → layer 배정
```

## Phase 2: 위험도별 "빼기" 매트릭스

| 빼기 대상 | 위험도 | 되돌리기 | 데이터 근거 |
|-----------|--------|---------|-----------|
| 19 미사용 타입 deprecated | 0 | 즉시 | 인스턴스 0 |
| 2 미사용 관계 deprecated | 0 | 즉시 | 사용 0 |
| 6 잘못된 관계 교정 | 낮음 | correction_log | 명확한 변형 |
| 20 orphan(비L4) inactive | 낮음 | reactivate | edge 0 |
| super-type 추가 | 0 | 제거 | 추가만, 삭제 없음 |
| L1 승격 촉진 | 낮음 | 되돌리기 가능 | L1 과밀 58.5% |
| 유사 관계 병합 | 중간 | replaced_by 추적 | 빈도 분석 필요 |
| enrichment 태스크 축소 | 높음 | 재활성화 | action_log 필요 |

---

*이 문서는 아이디에이션이다. 코드 수정은 포함하지 않는다.*
*실제 DB 진단 데이터(2026-03-05 시점)에 기반한 구체적 설계안.*
*각 설계안의 구현은 별도 세션에서 진행한다.*
