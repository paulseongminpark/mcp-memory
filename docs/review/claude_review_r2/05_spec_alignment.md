# T2-C-05 — Spec Alignment (Architecture) Review

> **Round**: 2 (Architecture)
> **Reviewer**: rv-c2 (Claude Opus)
> **Scope**: 11 R3 Final Specs (docs/ideation/*-r3-*.md), ~4,500 lines total
> **Key Question**: "스펙 자체가 잘 설계되었는가?"
> **Focus**: Spec self-consistency, contradictions between specs, over-specification, under-specification

---

## Executive Summary

11개 R3 final spec은 총 ~4,500줄로 v2.1 온톨로지 시스템의 핵심 기능을 정의한다. 개별 스펙의 수학적 엄밀성(특히 c-r3-12 SPRT 검증)은 우수하나, **스펙 간 교차 의존에서 3가지 구조적 문제**가 발견되었다: (1) 공유 개념의 소유권 불명(total_recall_count, infer_relation), (2) 스펙-구현 경계 혼재(모든 스펙에 완전한 코드 포함), (3) 임계값의 정당성 부재(SWR 0.55, 패치 포화 0.75). 스펙 간 **직접 모순 0건**이지만, **암묵적 가정 불일치 4건**이 있다.

**발견 사항**: HIGH 2 / MEDIUM 5 / LOW 2 / INFO 3

---

## Findings

### H-01: Shared Concept Ownership Undefined — "Orphan Dependencies"

**Severity**: HIGH
**Specs**: 전체에 걸친 구조적 문제

여러 스펙이 공유하는 핵심 개념의 "소유 스펙"이 지정되지 않았다:

| Shared Concept | Used By | Defined Where | Problem |
|----------------|---------|---------------|---------|
| `total_recall_count` | c-r3-11 (Bayesian Gate 2), b-r3-15 (increment) | 양쪽 모두 부분 정의 | 메타 테이블 UPSERT의 원자성, 초기값 등을 정의하는 단일 스펙 없음 |
| `infer_relation()` | a-r3-18 (remember link) | 어떤 스펙에도 없음 | config.py에 구현 존재하지만 규칙의 설계 근거/완전 목록을 다루는 스펙 없음 |
| `correction_log` 테이블 | d-r3-12 (drift), d-r3-14 (pruning) | a-r3-17에서 간접 언급 | action_log와의 관계/역할 분리가 명확하지 않음 |
| `visit_count` 필드 | b-r3-14 (UCB 분모) | b-r3-14에서 사용만 | 기존 3,230 노드의 초기값(0? 1?) 미정의 — UCB 계산에 직접 영향 |
| `embedding_provisional` | a-r3-18 (remember store) | a-r3-18에서 설정 | true→false 전환 조건/시점 정의하는 스펙 없음 |

**문제점**: 구현자가 각 스펙을 독립적으로 읽으면 공유 개념의 전체 lifecycle을 파악할 수 없다. 실제로 `_get_total_recall_count()`가 두 파일에 복사-붙여넣기 된 것(T2-C-02 H-02)은 이 스펙 부재의 직접적 결과다.

**권장**: 공유 개념을 정의하는 "cross-cutting spec" 문서 작성. 또는 각 개념에 "canonical spec" 지정.

---

### H-02: Spec-Implementation Boundary Blur — Specs as Code

**Severity**: HIGH
**Specs**: 11개 전체

모든 R3 final spec이 **완전한 구현 코드 + 테스트 시나리오**를 포함한다:

| Spec | Code LOC (추정) | Spec LOC (추정) | Code:Spec Ratio |
|------|----------------|-----------------|-----------------|
| a-r3-17 | 517 (6개 삽입지점 diff) | 183 | 2.8:1 |
| a-r3-18 | 295 (remember.py 전체) | 224 | 1.3:1 |
| b-r3-14 | 500 (hybrid.py 재작성) | 38 | 13:1 |
| c-r3-11 | 340 (promote_node.py) | 195 | 1.7:1 |
| d-r3-14 | 350 (pruning 통합) | 134 | 2.6:1 |

**문제점**:
1. "스펙"이 사실상 "구현 가이드" — 설계 의도와 코드가 혼재되어 "왜 이렇게?"를 파악하기 어려움
2. 코드가 변경되면 스펙도 outdated — 유지보수 이중 부담
3. 코드 리뷰 시 스펙 변경 의도인지 구현 세부사항인지 구분 불가

**긍정적 측면**: 구현자에게는 복사-붙여넣기 수준의 명확성 제공. 멀티세션 오케스트레이션에서 각 세션이 독립적으로 구현 가능.

**권장**: 향후 스펙은 (1) Design Decision + Rationale, (2) Interface Contract (함수 시그니처 + 반환 형식), (3) Constraints/Invariants 로 구성. 구현 코드는 별도 impl guide로 분리.

---

### M-01: Threshold Justification Absent — Magic Numbers

**Severity**: MEDIUM
**Specs**: c-r3-11, b-r3-15, d-r3-12

주요 임계값이 설정되었으나 선택 근거가 없다:

| Threshold | Value | Spec | Justification |
|-----------|-------|------|---------------|
| PROMOTION_SWR_THRESHOLD | 0.55 | c-r3-11 | 없음 (0.5~0.6 사이 임의 선택) |
| PATCH_SATURATION_THRESHOLD | 0.75 | b-r3-15 | 없음 ("포화 발생률 예상 10-20%"만 기술) |
| MDL cosine threshold | 0.75 | c-r3-11 | 없음 (고정값, config에도 안 들어감) |
| DRIFT_THRESHOLD | 0.5 | d-r3-12 | **있음** — calibrate_drift.py mean-2σ 기반 |
| SPRT α=0.05, β=0.2 | 2.773, -1.558 | c-r3-12 | **있음** — Wald(1945) 수학적 도출 |

**대조**: d-r3-12와 c-r3-12는 임계값 선택의 수학적/경험적 근거를 상세히 제시. 반면 c-r3-11의 SWR/MDL 임계값은 근거 없이 고정.

**문제점**: 임계값이 성능에 직접 영향. 근거 없는 값은 튜닝 시 기준점(baseline)이 없어 방향 설정 어려움.

---

### M-02: A-10 Firewall Partial Implementation — F2-F6 Unspecified

**Severity**: MEDIUM
**Spec**: d-r3-13 (access control)

d-r3-13은 A-10 방화벽의 **F1만 구현**하고 F2-F6은 "개별 삽입 코드로 유지"라고만 언급한다:

| Rule | Description | Status |
|------|-------------|--------|
| F1 | L4/L5 콘텐츠 보호 | **구현됨** (check_access) |
| F2 | L3+ 자동 삭제 차단 | 미명시 |
| F3 | L4/L5 자동 edge 차단 | a-r3-18에서 별도 구현 (remember.py 내부) |
| F4-F6 | 기타 보호 규칙 | 언급 없음 |

**문제점**: F3는 access_control.py가 아닌 remember.py에 하드코딩 — 중앙화된 접근 제어가 아닌 분산 구현. 다른 도구가 F3를 우회할 수 있다.

---

### M-03: correction_log vs action_log — Dual Audit Trail

**Severity**: MEDIUM
**Specs**: a-r3-17, d-r3-12, d-r3-14

두 개의 감사 추적 메커니즘이 공존하며 역할이 명확히 분리되지 않았다:

| Table | Defined In | Purpose | Used By |
|-------|-----------|---------|---------|
| action_log | a-r3-17 | 전체 시스템 활동 추적 (25 action_types) | remember, recall, enrichment |
| correction_log | d-r3-12, d-r3-14 | 필드별 변경 기록 (old/new value) | drift detection, pruning |

**중복 시나리오**: pruning stage2에서 노드 상태 변경 시:
- correction_log에 `event_type="prune_stage2"` 기록
- action_log에 `action_type="archive"` 기록해야 하지만 실제로 누락 (T2-C-02 M-03)

**권장**: correction_log를 action_log의 세부 필드로 통합하거나, 역할을 명시적으로 분리 — "correction_log = 필드 변경 diff", "action_log = 이벤트 트리거".

---

### M-04: Implicit Assumption Mismatches (4건)

**Severity**: MEDIUM

스펙 간 직접 모순은 없으나, 암묵적 가정이 불일치하는 4건:

#### (1) embedding 모델 가정
- b-r3-14: "embedding" 언급만, 모델 미명시
- d-r3-12: "OpenAI text-embedding-3 기준 DRIFT_THRESHOLD=0.5"
- config.py: `text-embedding-3-large` (3072 dim)
- **불일치 위험**: 모델 변경 시 drift threshold 재캘리브레이션 필요하지만 이 의존성이 스펙에 없음

#### (2) MDL Gate embedding 부재 시 동작
- c-r3-11: `embedding_unavailable → return True` (보수적 통과)
- **의미**: 임베딩 없는 노드는 Gate 3을 무조건 통과 → 승격 기준 약화
- d-r3-12에서 embedding_provisional 개념과 연결되지 않음

#### (3) recall count 초기화
- b-r3-15: `_increment_recall_count()` — meta 테이블에 UPSERT
- c-r3-11: `_get_total_recall_count()` — meta에서 읽기
- **가정 불일치**: b-r3-15는 "테이블 미존재 시 graceful skip", c-r3-11은 "값 0 반환"
- recall이 한 번도 실행 안 된 상태에서 promote_node 호출 시 Bayesian 분모=0 위험 (코드에서는 11+n으로 처리하지만 스펙 명시 없음)

#### (4) pruning probation 기간
- d-r3-14: 30일 probation (Stage 3)
- d-r3-12: 30일 probation (drift detection)
- **가정**: 같은 30일이지만 독립적으로 계산. 동시 발생 시 우선순위 미정의.

---

### M-05: Under-Specified Recovery/Rollback Processes

**Severity**: MEDIUM
**Specs**: d-r3-12, d-r3-14, c-r3-11

모든 스펙이 "감지 → 기록"까지만 정의하고, "복구" 프로세스는 정의하지 않는다:

| Scenario | Detection | Recovery |
|----------|-----------|----------|
| Semantic drift (d-r3-12) | cosine < 0.5 → log | **미정의** (ChromaDB 업데이트 차단만) |
| Pruning archive (d-r3-14) | 30일 후 archive | "SQL 수동 명령"으로 복구 (UI/API 없음) |
| Gate failure (c-r3-11) | Gate 1/2/3 실패 메시지 | **미정의** (재시도 조건/주기 없음) |
| Auto-edge 중복 (a-r3-18) | 없음 (감지 안 됨) | **미정의** (dedup 정책 없음) |

**문제점**: 운영 환경에서 "잘못된 상태"를 어떻게 복구하는지가 없으면, 문제 발생 시 수동 DB 조작에 의존하게 된다.

---

### L-01: Over-Specification — Test Scenarios in Specs

**Severity**: LOW
**Specs**: a-r3-18 (12 TC), d-r3-11 (10 TC), a-r3-17 (inline tests)

스펙에 상세한 테스트 시나리오가 포함되어 있다:
- a-r3-18: 12개 테스트 케이스 (103줄)
- d-r3-11: 10개 테스트 케이스 (TC1-TC10)
- a-r3-17: 6개 삽입지점별 검증 코드

**트레이드오프**: 멀티세션 오케스트레이션에서 각 세션이 독립 구현할 수 있도록 의도된 설계. 유용하지만 스펙 비대화 원인.

---

### L-02: Goldset Size Insufficiency (c-r3-10)

**Severity**: LOW
**Spec**: c-r3-10

25개 쿼리 골드셋이 3,230 노드 규모에 비해 극소(0.77%). 14개 고정 노드 ID에 의존하여 데이터 변동에 취약.

**완화**: 골드셋은 NDCG 기준선 설정 목적이므로 커버리지보다 품질이 중요. 하지만 "CRITICAL VERIFY" 3건이 미해결 상태.

---

### I-01: Mathematical Rigor Spectrum (Positive)

**Severity**: INFO (Positive Finding)

스펙의 수학적 엄밀성이 스펙트럼을 형성한다:

| Tier | Specs | Rigor Level |
|------|-------|-------------|
| **Excellent** | c-r3-12 (SPRT) | Wald(1945) 이론, 민감도 분석, 금지 파라미터, 시뮬레이션 코드 |
| **Good** | b-r3-14 (BCM/UCB), d-r3-12 (drift) | 공식 명시, 상수 도출 근거 존재 |
| **Adequate** | c-r3-11 (promotion), d-r3-14 (pruning) | 공식 있으나 임계값 근거 약함 |
| **Minimal** | b-r3-15 (recall), a-r3-18 (remember) | 알고리즘 서술 위주, 정량적 분석 부재 |

c-r3-12는 모범 사례 — 다른 스펙의 임계값도 이 수준의 검증이 권장된다.

---

### I-02: Cross-Reference Network — Strong but Asymmetric

**Severity**: INFO

스펙 간 교차 참조 네트워크:

```
a-r3-17 (action_log)  ← a-r3-18, d-r3-14
a-r3-18 (remember)    ← b-r3-14 (hybrid_search 사용)
b-r3-14 (hybrid)      ← b-r3-15 (recall), b-r3-16 (optimization)
b-r3-15 (recall)      ← c-r3-11 (total_recall_count)
c-r3-11 (promotion)   ← c-r3-12 (SPRT 파라미터)
d-r3-11 (validators)  ← a-r3-18 (validate_node_type 사용)
d-r3-13 (access)      ← d-r3-14 (check_access 사용)
```

**비대칭**: b-r3-14(hybrid)가 가장 많이 참조됨(허브 스펙). 반면 c-r3-10(goldset)은 거의 참조되지 않음(고립).

---

### I-03: Spec Versioning — R3 as Final (Positive)

**Severity**: INFO (Positive Finding)

모든 스펙이 "R3 Final"로 명확히 버전 표기되며, 이전 라운드(R1, R2) 결정의 진화 경로가 추적 가능하다:
- b-r3-14는 B-10(R1) → B-12(R2) → B-14(R3) 계보
- c-r3-11은 C-7(R2) → C-11(R3) 계보

이 versioning 패턴은 결정 이력 추적에 우수하다.

---

## Spec Quality Scorecard

| Dimension | Score | Notes |
|-----------|-------|-------|
| **Internal Consistency** | 8/10 | 개별 스펙 내부는 일관적. 교차 스펙 공유 개념만 문제 |
| **Contradictions** | 9/10 | 직접 모순 0건. 암묵적 가정 불일치 4건 |
| **Completeness** | 6/10 | 감지/기록은 상세하나 복구/rollback 일관적 부재 |
| **Mathematical Rigor** | 7/10 | SPRT 우수, 나머지 임계값 근거 부족 |
| **Maintainability** | 5/10 | 코드 내장으로 스펙이 빠르게 outdated 가능 |
| **Cross-Spec Coherence** | 6/10 | 참조 네트워크 존재하나 공유 개념 소유권 불명 |

---

## Summary Table

| ID | Severity | Category | Finding |
|----|----------|----------|---------|
| H-01 | HIGH | Coherence | 공유 개념 소유 스펙 없음 (total_recall_count, infer_relation 등) |
| H-02 | HIGH | Structure | 스펙-구현 경계 혼재 — 코드:스펙 비율 최대 13:1 |
| M-01 | MEDIUM | Rigor | SWR 0.55, 패치 0.75, MDL 0.75 임계값 근거 부재 |
| M-02 | MEDIUM | Completeness | A-10 F1만 구현, F2-F6 스펙 없음 |
| M-03 | MEDIUM | Coherence | correction_log vs action_log 이중 감사 추적 역할 미분리 |
| M-04 | MEDIUM | Consistency | 암묵적 가정 불일치 4건 (embedding 모델, MDL 통과, recall count, probation) |
| M-05 | MEDIUM | Completeness | 복구/rollback 프로세스 전면 미정의 |
| L-01 | LOW | Structure | 스펙 내 테스트 시나리오 과다 포함 |
| L-02 | LOW | Completeness | 25-query goldset 커버리지 극소 (0.77%) |
| I-01 | INFO | Positive | 수학적 엄밀성 스펙트럼 — c-r3-12 모범 사례 |
| I-02 | INFO | Structure | 교차 참조 네트워크 존재 (b-r3-14 허브) |
| I-03 | INFO | Positive | R1→R2→R3 버전 계보 추적 가능 |

---

## Top 3 Architecture Recommendations

1. **공유 개념 소유권 문서** — `0-shared-concepts.md` 작성: total_recall_count, correction_log, visit_count, embedding_provisional 등의 lifecycle, 초기값, canonical 스펙을 한 곳에 정의. H-01 해결.

2. **임계값 정당성 보고서** — c-r3-12(SPRT) 수준의 분석을 SWR, MDL, 패치 포화 임계값에도 적용. 최소한 실험 데이터 기반 선택 근거를 기록. M-01 해결.

3. **스펙 구조 분리** — Design Spec (왜, 무엇) vs Implementation Guide (어떻게, 코드) 분리. 현재 구조는 멀티세션 구현에는 효과적이었으나, 유지보수 시 코드 변경 → 스펙 outdated 위험. H-02 해결.
