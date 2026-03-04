# MCP Memory v2.0 전체 시스템 감사 보고서

> 날짜: 2026-03-04
> 작성: Claude Opus 4.6 (Claude Code 세션 내 직접 점검)
> 범위: 온톨로지, 데이터 정합성, 파이프라인, recall/checkpoint, 세션 통합

---

## 요약 (Executive Summary)

| 구성요소 | 상태 | 비고 |
|---------|------|------|
| 6레이어 분류 | **부분 작동** | L0-L3만 사용, L4-L5 비어있음 |
| 45타입 온톨로지 | **부분** | 25/45 타입만 실데이터 존재 |
| 48관계 타입 | **심각** | 95.1%가 generic (connects_with+supports) |
| 다면분류 (facets/domains) | **미시작** | 스키마 존재, 데이터 0% |
| Enrichment E1-E25 | **미시작** | 코드 완료, 한 번도 실행 안 됨 |
| 헤비안 학습 | **미작동** | 코드 존재, frequency 항상 0 |
| Becoming (승격) | **차단됨** | tier/maturity/observation_count 컬럼 누락 |
| Recall 3중 검색 | **OK** | Vector+FTS5+Graph RRF 작동 중 |
| Session Context | **OK** | 세션 시작 시 context 전달 확인 |
| Checkpoint | **OK** | /checkpoint 스킬 작동 확인 |
| 대시보드 | **OK** | auto-refresh 제거 완료 |

**한 줄 진단: 설계와 코드는 완성됐지만, enrichment 파이프라인이 한 번도 실행되지 않아 v2의 핵심 약속이 전혀 실현되지 않고 있다.**

---

## 1. 데이터 현황

### 1.1 기본 수치
- 노드: **3,140**개
- 엣지: **5,426**개
- 고아 노드: **277**개 (8.8%)
- 세션: **1**개 (E2E test session만)
- 활성 타입: **25**/45

### 1.2 노드 타입 분포
```
Workflow 566 (18%) | Insight 312 (10%) | Principle 283 (9%)
Decision 230  (7%) | Narrative 193 (6%) | Tool 171 (5%)
Framework 159 (5%) | Skill 140 (4%)    | Project 133 (4%)
Goal 131      (4%) | Agent 130 (4%)    | Pattern 122 (4%)
SystemVersion 122  | Conversation 89   | Experiment 72
Breakthrough 58    | Failure 54        | Identity 44
Unclassified 38    | Evolution 28      | Connection 23
Tension 20         | Question 10       | Preference 7
AntiPattern 5
```

**미사용 타입 (20개)**: Signal, Observation, Evidence, Trigger, Context, Plan, Ritual, Constraint, Assumption, Belief, Philosophy, Mental Model, Lens, Boundary, Vision, Paradox, Commitment, Heuristic, Trade-off, Concept 등 (v2.0 45타입 기준)

### 1.3 프로젝트 분포
```
orchestration  1,304 (41.5%)
tech-review      534 (17.0%)
monet-lab        522 (16.6%)
portfolio        437 (13.9%)
(없음)           211  (6.7%)
mcp-memory       130  (4.1%)
system             2  (0.1%)
```

### 1.4 레이어 분포
```
L0 (원시 경험):     299 (9.5%)
L1 (행위/사건):   1,826 (58.2%)    ← 대부분
L2 (개념/패턴):     628 (20.0%)
L3 (원칙/정체성):   327 (10.4%)
NULL:                60  (1.9%)
L4 (세계관):          0  (0%)       ← 비어있음
L5 (가치/존재론):     0  (0%)       ← 비어있음
```

---

## 2. 온톨로지 정합성

### 2.1 schema.yaml vs 실제 데이터

**schema.yaml 정의**: 45 active + 7 reserved = 52 타입
**실제 DB**: 25 타입만 사용

**schema.yaml에 있고 DB에 없는 타입 (20개)**:
- L0: Observation, Evidence, Trigger, Context
- L1: Signal, Plan, Ritual, Constraint, Assumption
- L2: Heuristic, Trade-off, Concept
- L3: Boundary, Vision, Paradox, Commitment
- L4: Belief, Philosophy, Mental Model, Lens
- L5: (전체 비어있음)

**원인**: remember() 호출 시 사용자/Claude가 수동으로 타입 지정 → 익숙한 타입만 반복 사용. Signal/Observation 같은 자동 분류 타입은 사용 패턴이 없음.

### 2.2 관계 타입 — 치명적 문제

```
connects_with  2,583 (47.6%)  ← remember() auto-edge: 다른 타입
supports       2,579 (47.5%)  ← remember() auto-edge: 같은 타입
────────────────────────────────────
소계           5,162 (95.1%)  ← 의미 없는 generic 관계

led_to            77 (1.4%)
part_of           61 (1.1%)
governed_by       26
extends           22
inspired_by       17
기타              61
────────────────────────────────────
소계             264 (4.9%)   ← 실제 의미 있는 관계
```

**48개 관계 타입 중 25개 미사용**: realized_as, crystallized_into, abstracted_from, generalizes_to, constrains, generates, differs_in, variation_of, triggered_by, resulted_in, prevented_by, enabled_by, blocked_by, expressed_as, derived_from, viewed_through, interpreted_as, questions, validates, simultaneous_with, assembles, transfers_to, mirrors, correlated_with, refuted_by

**근본 원인**: `remember.py`의 auto-edge 로직:
```python
# 같은 type → "supports", 다른 type → "connects_with"
relation = "supports" if existing_type == node_type else "connects_with"
```
이 2가지만 사용하므로 관계 의미가 전혀 없음.

### 2.3 v2 시맨틱 필드 — 전부 비어있음

| 필드 | 채움률 | 용도 |
|------|--------|------|
| summary | 0% | E1에서 생성 예정 |
| key_concepts | 0% | E2에서 생성 예정 |
| facets | 0% | E4에서 생성 예정 (다면분류 핵심) |
| domains | 0% | E5에서 생성 예정 (크로스도메인 핵심) |
| secondary_types | 0% | E6에서 생성 예정 |
| quality_score | 0% | E8에서 생성 예정 |
| abstraction_level | 0% | E9에서 생성 예정 |
| temporal_relevance | 0% | E10에서 생성 예정 |
| actionability | 0% | E11에서 생성 예정 |

### 2.4 누락 컬럼 (migrate_v2.py 미완성)

| 컬럼 | 테이블 | 용도 | 상태 |
|------|--------|------|------|
| tier | nodes | 품질등급 (0=raw, 1=refined, 2=curated) | **MISSING** |
| maturity | nodes | Becoming 성장 점수 (0.0~1.0) | **MISSING** |
| observation_count | nodes | 유사 관찰 횟수 | **MISSING** |

---

## 3. Recall / Checkpoint / 세션 통합

### 3.1 Recall 기능
- **작동 중**: Vector + FTS5 + Graph 3중 검색 + RRF 통합
- **미작동**: enrichment 가중치 (quality_score, temporal_relevance 모두 NULL → 0)
- **미작동**: 헤비안 학습 (frequency 업데이트 코드 존재하나 실제 갱신 0건)

### 3.2 Session Start Hook 통합
- **작동 중**: session_context.py → 최근 Decision/Question/Failure/Insight 출력
- **문제**: 에러 시 조용히 무시 (`2>/dev/null`)
- **문제**: session_context.py가 get_context()와 별도 구현 (로직 복제)

### 3.3 Checkpoint Skill
- **작동 중**: /checkpoint → 대화 스캔 → recall() 중복체크 → remember() 저장
- **문제**: remember()의 auto-edge가 connects_with/supports만 생성
- **문제**: checkpoint으로 저장한 노드도 enrichment 미실행 상태

### 3.4 Session 저장
- sessions 테이블: **1건** (E2E test session만)
- SessionEnd hook에서 save_session() 미호출
- 실질적으로 세션 기록 자동화 없음

---

## 4. 파이프라인 상태

### 4.1 Enrichment Pipeline (daily_enrich.py)
- **코드**: 완성 (2,800 LOC, 19개 Fix 적용)
- **실행**: **한 번도 안 됨** (--dry-run 포함)
- **차단 요인**:
  - tier/maturity/observation_count 컬럼 누락
  - OpenAI API 키 설정 미확인
  - 프롬프트 품질 검증 미완

### 4.2 Auto-edge 문제
```python
# remember.py 현재 로직
if same_type: relation = "supports"
else: relation = "connects_with"
```
→ 5,162/5,426 엣지가 의미 없는 generic 관계
→ E14(관계 정밀화)가 이를 구체적으로 교체해야 하나, 실행 안 됨

---

## 5. 다음 단계 (우선순위)

### 즉시 (차단 해제)
1. **migrate_v2.py 보완**: tier, maturity, observation_count 컬럼 추가
2. **daily_enrich.py --dry-run**: 50개 표본으로 프롬프트 품질 확인
3. **OpenAI API 키 확인**: 환경변수/config 설정 검증

### 단기 (1주)
4. **Enrichment Phase 1 실행**: E1-E5 (summary, key_concepts, facets, domains, embedding_text)
5. **E14 관계 정밀화**: connects_with/supports → 구체적 관계로 교체
6. **E15 방향 분류**: edge direction/reason 채우기
7. **헤비안 학습 활성화**: recall() → frequency 업데이트 검증

### 중기 (2주)
8. **E18-E25 그래프 분석**: 클러스터링, 고아 연결, 모순 탐지
9. **Becoming 시스템**: Signal→Pattern→Principle 승격 첫 실행
10. **remember() auto-edge 개선**: suggest_type() 활용해 관계 다양화
11. **save_session() 자동화**: SessionEnd hook에서 자동 호출

### 설계 개선
12. **L4/L5 노드 생성 전략**: Belief/Philosophy/Value 타입 자동 승격 or 수동 분류
13. **schema.yaml v2**: 미사용 20개 타입 활성화 가이드
14. **recall() enrichment 가중치**: v2 필드 채워지면 자동 활성화 확인

---

## 6. 리스크

| 리스크 | 영향 | 완화 |
|--------|------|------|
| Enrichment 토큰 비용 폭발 | 3,140노드 × 25작업 | Phase별 예산 관리 + --dry-run 선행 |
| Auto-edge 95% generic | 그래프 분석 무의미 | E14 정밀화 우선 실행 |
| L4/L5 비어있음 | 가치체계 미형성 | 수동 분류 + E23 승격 조합 |
| 단일 세션 기록 | 세션 히스토리 부재 | save_session() hook 자동화 |
| schema 불일치 | 20개 타입 dead | v2.1에서 재분류 |

---

## 부록: 대시보드 스크린샷

대시보드 (localhost:7676) 접속 확인:
- auto-refresh 5초 → 수동 새로고침으로 변경 완료
- Knowledge Graph: D3.js force simulation 작동 확인
- 노드/엣지 수치 정확성 확인

## 부록: Codex CLI E2E 테스트

Codex CLI (`codex exec --full-auto`) 실행 시도.
결과: [실행 중 / 별도 리포트 생성 예정]
