# T2-C-03 — Utils/Ontology Layer Architecture Review

> **Round**: 2 (Architecture)
> **Reviewer**: rv-c2 (Claude Opus)
> **Scope**: ontology/validators.py, ontology/schema.yaml, config.py, utils/access_control.py, utils/similarity.py
> **Key Question**: "이것이 잘 설계되었는가?"
> **Focus**: Validator extensibility, config organization, schema evolution strategy, type system design quality

---

## Executive Summary

온톨로지 레이어는 50 node types + 48 relation types를 3개 소스(schema.yaml, config.py, DB type_defs/relation_defs)로 관리한다. 타입 검증의 deprecation 지원과 다중 fallback은 우수하나, **진실의 원천(Source of Truth)이 3곳에 분산**되어 동기화 드리프트 위험이 존재한다. config.py에 비즈니스 로직(`infer_relation()`)이 혼재되어 있고, access_control.py는 config.py와 독립적으로 하드코딩된 권한 테이블을 유지한다.

**발견 사항**: HIGH 2 / MEDIUM 4 / LOW 3 / INFO 3

---

## Findings

### H-01: Triple Source of Truth — Schema Drift Risk

**Severity**: HIGH
**Files**: schema.yaml, config.py, DB type_defs/relation_defs

노드/관계 타입이 3곳에 정의되어 있으며 자동 동기화 메커니즘이 없다:

```
schema.yaml (50 node types, 48 relation types)
    ↓ 수동 동기화
config.py (RELATION_RULES, VALID_PROMOTIONS, PROMOTE_LAYER, ALL_RELATIONS)
    ↓ 수동 동기화
DB type_defs / relation_defs 테이블
    ↓ 마이그레이션 스크립트
validators.py (검증 시 type_defs 우선, schema.yaml fallback)
```

**구체적 드리프트 시나리오**:
1. schema.yaml에 새 타입 추가 → config.py PROMOTE_LAYER 미반영 → promote_node KeyError
2. DB type_defs에 deprecated 설정 → schema.yaml에는 여전히 active → fallback 시 검증 불일치
3. config.py에 관계 규칙 추가 → schema.yaml relation_types에 미등록 → validate_relation 실패

**현재 완화**: validators.py의 이중 검증(DB → schema.yaml fallback)이 부분적 보호를 제공하지만, 근본적으로 어떤 소스가 canonical인지 명확하지 않다.

**권장**:
- schema.yaml을 **유일한 선언적 소스**로 지정
- 시작 시 schema.yaml → DB type_defs/relation_defs 자동 동기화
- config.py의 타입 관련 상수는 schema.yaml에서 파싱하여 생성

---

### H-02: Business Logic in config.py — `infer_relation()` (Config Organization)

**Severity**: HIGH
**File**: config.py (Lines 197-240)

config.py에 44줄의 비즈니스 로직 함수가 위치한다:

```python
def infer_relation(src_type, src_layer, tgt_type, tgt_layer,
                   src_project, tgt_project) -> str:
    # 4-stage fallback: exact match → reverse → layer-based → "connects_with"
```

이 함수는:
- 타입 쌍 매칭 (`RELATION_RULES` dict lookup)
- 역방향 관계 추론 (`reverse_map`)
- 레이어 기반 관계 추론 (src_layer < tgt_layer → "generalizes_to")
- 프로젝트 교차 관계 (cross_project → "transfers_to")

**문제점**:
1. config.py의 책임: 상수 정의 vs 관계 추론 로직 — 관심사 혼재
2. remember.py가 `from config import infer_relation`으로 import — config가 tool의 의존성
3. 단위 테스트가 config.py에 대한 의존으로 복잡해짐

**권장**: `infer_relation()`을 `ontology/inference.py` 또는 `ontology/validators.py`로 이동. config.py에는 RELATION_RULES dict만 남김.

---

### M-01: access_control.py Hardcoded Constants (Config Organization)

**Severity**: MEDIUM
**File**: utils/access_control.py

access_control.py는 config.py를 import하지 않고 모든 상수를 자체 하드코딩한다:

```python
# access_control.py 내부
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "memory.db"

LAYER_PERMISSIONS = {
    0: {"read": ["all"], "write": ["paul", "claude", "system", "enrichment"], ...},
    1: {"read": ["all"], "write": ["paul", "claude", "system", "enrichment"], ...},
    # ... L0-L5 전체 하드코딩
}
```

**비교**: config.py에도 `DB_PATH`가 정의되어 있음. 두 곳의 경로가 독립적으로 계산되어 불일치 가능.

**문제점**:
1. DB 경로 변경 시 두 파일 동시 수정 필요
2. LAYER_PERMISSIONS이 schema.yaml의 계층 정의와 독립 — 레이어 추가/변경 시 동기화 누락 위험
3. Actor 목록(`"paul"`, `"claude"`, `"system"`, `"enrichment"`)이 문자열 리터럴 — enum/constant 없음

**권장**: `DB_PATH`는 config.py에서 import. LAYER_PERMISSIONS는 성격상 access_control에 유지하되, Actor 이름을 상수로 정의.

---

### M-02: suggest_closest_type() Hardcoded Hints — Not Synced with type_defs (Extensibility)

**Severity**: MEDIUM
**File**: ontology/validators.py (Lines ~80-120)

```python
hints: dict[str, list[str]] = {
    "Decision":    ["결정", "decided", "decision", ...],
    "Failure":     ["실패", "fail", "error", ...],
    # ... 12 types only
}
```

50개 노드 타입 중 **12개만** 키워드 힌트가 정의되어 있다. 나머지 38개 타입(특히 L3-L5의 Identity, Boundary, Vision, Paradox, Axiom, Wonder 등)은 힌트가 없어 suggest가 불가능하다.

**문제점**:
1. 새 타입 추가 시 hints dict 업데이트를 잊기 쉬움 (type_defs 테이블과 별도 관리)
2. L3-L5 고계층 타입이 누락 — 고계층일수록 올바른 분류가 중요
3. 키워드 기반 분류의 한계 — 동일 키워드가 여러 타입에 해당 가능

**권장**: schema.yaml에 `keywords` 필드를 추가하여 타입별 힌트를 선언적으로 관리. suggest_closest_type()가 이를 파싱.

---

### M-03: config.py Mixed Concerns — Flat Structure (Config Organization)

**Severity**: MEDIUM
**File**: config.py (259 lines)

config.py가 7개 이상의 관심사를 단일 파일에 평면적으로 관리한다:

| Concern | Lines | Examples |
|---------|-------|---------|
| Path/env setup | 1-15 | BASE_DIR, DB_PATH, OPENAI_API_KEY |
| Search parameters | 18-26 | DEFAULT_TOP_K, RRF_K, GRAPH_BONUS |
| BCM/UCB math | 28-34 | UCB_C_FOCUS, BCM_HISTORY_WINDOW, LAYER_ETA |
| SPRT parameters | 39-45 | SPRT_ALPHA, SPRT_BETA, SPRT_P1 |
| Drift detection | 47-50 | DRIFT_THRESHOLD |
| Enrichment API | 52-93 | API_PROVIDER, ENRICHMENT_MODELS, TOKEN_BUDGETS |
| Ontology definitions | 100-258 | RELATION_TYPES, RELATION_RULES, VALID_PROMOTIONS |

**현재**: 주석 블록으로만 섹션 구분. import 시 전체 모듈 로드.

**권장**: 현재 규모(259줄)에서는 분리가 과도할 수 있으나, 최소한:
- `infer_relation()` 함수를 ontology 모듈로 이동 (H-02)
- 향후 성장 시 `config/search.py`, `config/enrichment.py` 분리 고려

---

### M-04: No Schema Evolution Strategy — Required Fields All Empty (Type System)

**Severity**: MEDIUM
**File**: ontology/schema.yaml

schema.yaml의 모든 50개 노드 타입에서 `required_fields: []`이다:

```yaml
# 모든 타입 동일
- name: Decision
  layer: 1
  required_fields: []
  optional_fields: [reason, alternatives, status, reversible, confidence]
```

**의미**: 어떤 노드든 `content` 하나만으로 생성 가능. 타입별 구조적 보장이 없다.

**트레이드오프 분석**:
- **장점**: 최대 유연성. LLM이 구조화하지 못한 메모리도 저장 가능. Unclassified → promote 워크플로우에 적합.
- **단점**: 타입의 의미가 `content` 텍스트에만 의존. Decision 타입이지만 reason 없는 노드, Experiment 타입이지만 hypothesis 없는 노드 허용.
- **위험**: 타입별 분석 도구(analyze_signals, get_becoming)가 optional 필드를 가정하고 접근 시 `None` 처리 필요 증가.

**현재 완화**: enrichment 파이프라인이 사후에 optional 필드를 채우므로, 생성 시점에서는 유연성이 합리적.

**권장**: 현재 설계 유지하되, `soft_required_fields` 개념 도입 — enrichment 완료 후 해당 필드 미존재 시 quality_score 감점.

---

### L-01: validate_relation() Permissive Fallback (Type System)

**Severity**: LOW
**File**: ontology/validators.py (Lines ~125-136)

```python
def validate_relation(relation: str) -> tuple[bool, str | None]:
    try:
        # relation_defs 테이블 조회
        ...
    except Exception:
        return True, None  # 기본 통과
```

관계 검증 실패 시 **항상 통과**한다. 존재하지 않는 관계 타입도 DB에 저장 가능.

**문제점**: 타입이 아닌 관계의 오타나 잘못된 관계가 조용히 저장됨.
**완화**: 주석에 "insert_edge에서 fallback 처리"라고 명시 — 의도적 설계.
**권장**: 로깅 추가. 검증 실패 시 `action_log.record("relation_validation_skip", ...)`.

---

### L-02: Actor Validation — String-Based, No Enum (Type System)

**Severity**: LOW
**Files**: utils/access_control.py, tools/remember.py

Actor 식별이 순수 문자열 비교:

```python
# access_control.py
if actor == "paul":  # 하드코딩
    ...
actor_prefix = actor.split(":")[0]  # "enrichment:E7" → "enrichment"
```

```python
# remember.py (action_log 호출)
action_log.record(action_type="node_created", actor="claude", ...)
```

**문제점**: 오타 "cladue" 가 조용히 권한 거부 → 디버깅 어려움.
**권장**: `VALID_ACTORS = {"paul", "claude", "system", "enrichment"}` 상수 + 검증.

---

### L-03: similarity.py — Minimal but Isolated (Design Quality)

**Severity**: LOW
**File**: utils/similarity.py (41 lines)

cosine_similarity 단일 함수만 존재. promote_node.py의 `_mdl_gate()`에서 numpy로 직접 코사인 유사도를 재계산한다:

```python
# promote_node.py _mdl_gate() 내부
cos_sims = np.dot(norm_embs, norm_embs.T)  # 자체 구현
```

**문제점**: similarity.py가 존재하지만 promote_node는 이를 사용하지 않고 자체 구현. 코드 중복.
**완화**: promote_node의 구현은 행렬 일괄 계산(O(1) 호출)이므로 개별 벡터 쌍 함수와 성격이 다름.
**권장**: similarity.py에 `batch_cosine_similarity(matrix)` 추가, promote_node에서 사용.

---

### I-01: Validator Dual-Source Fallback — Well Designed (Positive)

**Severity**: INFO (Positive Finding)

validators.py의 3단계 방어:

```
1차: type_defs DB 테이블 → 정확 매칭 / 대소문자 교정 / deprecated 추적
    ↓ 실패
2차: schema.yaml 파싱 → 타입 존재 여부 확인
    ↓ 실패
3차: {"Unclassified"} 기본값 → 항상 동작 보장
```

**핵심 강점**:
- DB 장애 시에도 schema.yaml로 검증 가능 (graceful degradation)
- Deprecated 타입의 자동 마이그레이션 (`replaced_by` 필드)
- 대소문자 무시 매칭으로 LLM 출력 변동 흡수

---

### I-02: Access Control 3-Tier Model — Clean Design (Positive)

**Severity**: INFO (Positive Finding)

```
Request → A10 Firewall (L4/L5 보호)
    ↓ pass
→ Hub Protection (Top-10 노드 보호)
    ↓ pass
→ RBAC (레이어×작업×액터 매트릭스)
    ↓ pass
→ Allowed
```

**강점**:
- 각 tier가 독립적으로 판단 — 단일 책임
- `check_access()` (bool) vs `require_access()` (exception) — caller 선택권 제공
- Actor 접두어 매칭 (`"enrichment:E7"` → `"enrichment"`) — 세분화된 추적 + 범주적 권한
- Hub 보호는 동적(DB 스냅샷 기반) — 하드코딩 아님

---

### I-03: Relation Type Taxonomy — Comprehensive (Positive)

**Severity**: INFO (Positive Finding)

48개 관계 타입이 8개 의미 카테고리로 체계적 분류:

| Category | Count | Purpose |
|----------|-------|---------|
| causal | 8 | 인과 관계 |
| structural | 9 | 구조적 포함/확장 |
| layer_movement | 6 | 추상화 레벨 이동 |
| diff_tracking | 4 | 변화 추적 |
| semantic | 8 | 의미적 연결 |
| perspective | 5 | 관점/해석 |
| temporal | 4 | 시간적 순서 |
| cross_domain | 6 | 도메인 횡단 |

`infer_relation()`의 4단계 fallback(정확 매칭 → 역방향 → 레이어 기반 → connects_with)도 합리적이다.

---

## Architecture Relationships

```
schema.yaml ─────────────────────────┐
  (50 types, 48 relations)           │ fallback
  (declarative, no runtime logic)    │
                                     ▼
config.py ──────────────── validators.py
  (constants + infer_relation)       (validate_node_type, validate_relation)
  (RELATION_RULES, VALID_PROMOTIONS) (suggest_closest_type — 12/50 hints)
  (PROMOTE_LAYER, LAYER_ETA)         │
       │                             ▼
       │                        type_defs DB ──── sqlite_store
       │                        relation_defs DB
       │
       ├── access_control.py (독립: LAYER_PERMISSIONS 자체 정의)
       │     (A10 + Hub + RBAC, DB_PATH 자체 계산)
       │
       └── similarity.py (독립: numpy/math 유일 의존)
             (cosine_similarity, 41줄)
```

**핵심 관찰**: access_control.py와 similarity.py는 config.py와 **독립적**으로 동작. 이는 모듈 격리 측면에서는 좋으나, 상수 중복(DB_PATH) 위험이 있다.

---

## Summary Table

| ID | Severity | Category | Finding | Files |
|----|----------|----------|---------|-------|
| H-01 | HIGH | Evolution | 3중 진실 원천 (schema.yaml, config.py, DB) — 드리프트 위험 | schema.yaml, config.py, validators.py |
| H-02 | HIGH | Config | infer_relation() 비즈니스 로직이 config.py에 위치 | config.py |
| M-01 | MEDIUM | Config | access_control.py 상수 하드코딩 (DB_PATH, LAYER_PERMISSIONS) | access_control.py |
| M-02 | MEDIUM | Extensibility | suggest_closest_type() 12/50 타입만 힌트 보유 | validators.py |
| M-03 | MEDIUM | Config | config.py 7개 관심사 평면 혼재 (259줄) | config.py |
| M-04 | MEDIUM | Type System | 모든 required_fields=[] — 구조적 보장 없음 | schema.yaml |
| L-01 | LOW | Type System | validate_relation() 실패 시 항상 통과 | validators.py |
| L-02 | LOW | Type System | Actor 식별이 문자열 리터럴 — 오타 무방비 | access_control.py |
| L-03 | LOW | Design | similarity.py 존재하지만 promote_node는 자체 구현 | similarity.py, promote_node.py |
| I-01 | INFO | Positive | Validator 이중 소스 fallback — 견고한 설계 | validators.py |
| I-02 | INFO | Positive | Access Control 3-tier 모델 — 깔끔한 관심사 분리 | access_control.py |
| I-03 | INFO | Positive | Relation 48개 8카테고리 체계적 분류 | config.py, schema.yaml |

---

## Cross-Reference with Previous Reports

| Previous Finding | T2-C-03 Overlap |
|-----------------|-----------------|
| T2-C-01 H-01 Connection Management | access_control.py는 자체 sqlite3.connect() 사용 — 동일 패턴 |
| T2-C-02 H-01 Private API Leakage | access_control.py도 DB_PATH 자체 관리 — config 우회 |
| T2-C-02 H-03 Validation Split | validators.py는 server.py와 독립 — 이중 검증 경로 존재 |
| T2-C-02 M-02 Maturity Naming | config.py PROMOTE_LAYER vs schema.yaml layer — 동일 개념 이중 정의 |

---

## Top 3 Architecture Recommendations

1. **Single Source of Truth 확립** — schema.yaml을 canonical로 지정하고, 시작 시 DB type_defs/relation_defs 자동 동기화. config.py의 타입 관련 상수는 schema.yaml 파싱으로 생성. H-01 해결.

2. **config.py 관심사 분리** — `infer_relation()`을 `ontology/inference.py`로 이동. config.py는 순수 상수 정의만 담당. 향후 성장 시 섹션별 모듈 분리 준비. H-02, M-03 해결.

3. **access_control.py config 연결** — DB_PATH는 config.py에서 import. Actor 이름을 공유 상수로 정의. LAYER_PERMISSIONS는 access_control에 유지하되 schema.yaml의 레이어 정의와 연동 가능한 구조로 개선. M-01 해결.
