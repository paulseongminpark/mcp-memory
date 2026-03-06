# 2026-03-05 온톨로지 아이디에이션 & 아키텍처 대화록

> **세션 규칙**: 이 파일은 대화 진행 중 실시간으로 업데이트된다. compact 이후에도 계속 유지. 사용자 추가 지시 있을 때까지.

---

## 배경 — 다른 AI들의 지적 vs 우리 설계

외부 AI들이 온톨로지 강화 포인트로 제시한 내용:
1. Validator를 DB 앞단 게이트로 (type/relation/layer/facets/domains 검증)
2. 2단계 분류 (레이어→타입) 고정
3. 승격(Observation→Signal→Pattern…)을 DB에 진짜로 박기
4. Edge 품질 강화 — 포괄형 관계 정밀화
5. 스키마 버저닝/마이그레이션 체계
6. 관계 타입 방향성 표준화
7. 가중치 정책을 recall 정책 1급으로
8. 오분류를 시스템이 먹고 자라게 (correction_log)
9. Signal→Pattern 승격은 Paul 승인+롤백 기본값
10. FTS5 summary/key_concepts 인덱싱
11. Conflict Resolution (facets/layer/secondary_types 충돌)
12. SessionStart L2+ quality_score 기반 컨텍스트

---

## 현재 상태 전체 진단 (2026-03-05 기준)

### 이미 해결된 것

| 항목 | 상태 |
|------|------|
| SessionStart L2+ 재작성 | ✅ 3/4 23:20 완료 (L2+ quality 상위 15 + Signal 30일 + Observation 7일) |
| Hebbian 갱신 | ✅ recall() → frequency+1, last_activated 갱신 |
| remember() type 검증 | ✅ validate_node_type() → schema.yaml 기반, fallback Unclassified |
| quality_score × 0.2 RRF | ✅ temporal × 0.1도 적용 중 |
| enrichment 속도 최적화 | ✅ 9 API → 1 API, ThreadPoolExecutor 10 workers |

### 🔴 CRITICAL (구조적 결함)

1. **`promotion_history` 컬럼이 DB에 없다** — init_db()에도 migrate_v2.py에도 없음. promote_node() MCP 도구 있는데 이력 저장 불가. Becoming 전체 롤백/감사 불가능.

2. **`correction_log`가 init_db()에 없다** — migrate_v2.py step3에만 있음. 신규 DB 생성 시 누락. schema drift 시한폭탄.

3. **Generic 관계 95.1%** — edges 대부분이 "supports"/"connects_with". 48개 relation type 사실상 사용 안 됨. 그래프가 무뎌진 상태.

4. **L4/L5 레이어가 비어있다** — Belief/Philosophy/Value/Axiom 노드 없음. Becoming 목적지 자체가 미개척.

### 🟡 HIGH (기능 약점)

5. **FTS5 v2가 migrate_v2.py 의존** — init_db()는 v1 FTS5
6. **Relation validation gate 없음** — validators.py에 있지만 remember()/insert_edge()에서 호출 안 됨
7. **tier_weight가 recall RRF에서 안 쓰임**
8. **EXPLORATION_RATE 미구현** — "이색적 접합" 실제로 안 일어남

### 🟢 MEDIUM

9. schema.yaml 헤더 "49" ≠ 실제 50 (카운트 불일치)
10. o3 reasoning token fallback 정책 미정
11. ChromaDB atomic swap vs upsert 미결
12. E12 conflict resolution 정책 불명확

### 다른 AI 지적 vs 우리 설계 비교 결론

**설계 완성도: 90%. 구현 완성도: 65%.**

다른 AI들 지적은 대부분 맞지만 새로운 게 없다. 우리 설계 문서가 이미 더 깊이 다루고 있다. 진짜 문제는 구현 격차.

**우리만의 강점** (다른 AI 미제안):
- Facets × Domains 다차원 분류
- Becoming (maturity progression) 개념
- Hebbian edge learning
- Layer penalty rhizomatic propagation 제어

---

## 대화 — 전체 보완 방향

### Paul:
> 설계 어떻게 보완하고, 관계 문제 어떻게 해결하고, 드리프트 어떻게 해소하지. 전체적으로 다 하고 싶은데. 어떻게 손봐야할지 모르겠다.

### Claude:

문제가 4층으로 쌓여있다:

**바닥층: init_db() vs migrate_v2 drift**
→ 이게 해소 안 되면 다른 모든 수정이 "어느 코드에 넣지?"로 매번 막힘

**1층: 누락된 컬럼/테이블** (promotion_history, correction_log in init_db, FTS5 v2)
→ drift 해소하면서 같이 넣으면 됨. 독립 작업이 아님.

**2층: Validation gate 강화** (relation allowlist, tier_weight, EXPLORATION_RATE)
→ 기존 코드에 몇 줄 추가 수준. 구조 변경 아니라 끼워넣기.

**3층: 데이터 품질 문제** (generic 관계 95.1%, L4/L5 빈 레이어)
→ 코드 변경이 아니라 운영/파이프라인 문제. E14 소급 실행 + 수동 L4/L5 시드 노드 필요.

**바닥층(drift 해소)을 먼저 하면 나머지가 자연스럽게 풀리는 구조.**

방법 두 가지:
- **A. init_db()를 v2 완전체로** — correction_log, promotion_history, FTS5 v2 전부 넣기. 빠르지만 두 곳에 스키마 중복.
- **B. migrate_v2를 init_db에 흡수** — init_db = 최신 baseline, migrate = delta만. 깔끔하지만 리팩토링 큼.

**Generic 관계 95.1% 해결:**
- E14 소급 실행 필수 (5,777 edges 정밀화)
- 비용 문제 → "가장 중요한 edges만 먼저" (tier=0 노드의 edges부터)

**L4/L5 빈 레이어:**
- 자동 생성 아니라 Paul이 직접 시드 노드 입력 필요
- 또는 checkpoint에서 대화 분석 → L4/L5 후보 제안

**질문: 지금 가장 아프게 느껴지는 게 뭐야?** 시작점은 Paul이 결정.

---

### Paul:
> 전부 동시에.

### Claude:

**3 Wave 접근으로 전체 병렬 실행.**

#### Wave 1: 기반 정비 (전제조건)
- 방법 A 선택: init_db()를 v2 완전체로 만든다
- 이유: init_db = "생성", migrate_v2 = "마이그레이션". 역할이 다르니 중복이 아니라 계층 분리
- 추가 항목: promotion_history TEXT (JSON), correction_log CREATE, FTS5 v2 (summary/key_concepts), 트리거 v2
- migrate_v2에도 promotion_history ALTER TABLE ADD step 추가

#### Wave 2: Validation & 검색 강화 (Wave 1과 병렬)
- 2a. relation validation gate (remember + insert_edge)
- 2b. tier_weight in recall RRF (tier_bonus: {0: 0.15, 1: 0.05, 2: 0.0})
- 2c. EXPLORATION_RATE = 0.1 (config.py + recall graph traversal)

#### Wave 3: 데이터 품질 (Wave 1+2 완료 후)
- 3a. Generic 관계 E14 소급 — tier=0 edges 먼저(~200) → L2+ edges(~500) → 나머지(~5K, 3-5일 분산)
- 3b. L4/L5 시드 노드 — Paul 직접 remember() or checkpoint 자동 추출 (경로 A 선행)

```
Wave 1 ─┐
Wave 2 ─┤ 병렬
        │
Wave 3 ─┘ 순차 (1+2 완료 후)
```

**미결 질문: tier 배정 정책**
- 현재 tier default=2(auto). core가 되려면 수동 배정 필요.
- 누가/언제 tier=0으로 바꾸는가? enrichment? promote_node()? Paul 수동?
- tier_weight를 recall에 넣으려면 이 정책이 먼저 정해져야 함.

---

### Paul:
> 어떻게 하는게 좋은가. 1이 제일 나은가. 어떻게 처리해야 좋을까.

### Claude:

**Option별 분석:**

| Option | 장점 | 단점 | 지금 효과 |
|--------|------|------|-----------|
| 1. 승격 시 자동 | 미래에 맞음 | promote_node 거의 안 쓰임 | ❌ 없음 |
| 2. L2+ 자동 | 즉시 적용, 예측 가능 | layer 높다고 꼭 고품질은 아님 | ✅ 즉시 |
| 3. quality_score | 실제 품질 기반 | enrichment 62%, NULL 많음 | ❌ 아직 |

**추천: Option 2를 기본 + 나중에 확장**

```
Phase 1 (즉시): layer 기반 tier
  L0-L1: tier=2 (auto)
  L2:    tier=1 (reviewed)
  L3+:   tier=0 (core)

Phase 2 (enrichment 100% 후): quality override
  quality_score >= 0.9 → tier 한 단계 올림

Phase 3 (운영 중): promote_node() 시 tier 동시 업그레이드
```

단순 + 즉시 효과 + 확장 가능.

---

### Paul:
> 이대로 가도 되나? 옆 세션 Opus가 제시한 상세 설계가 있다:
> - 오판 수정 3건 (promotion_history metadata JSON 정상, generic 87.2%, 신규 발견 4건)
> - 3 Wave + 10개 작업(A~K) + 4병렬 트랙 + 리스크 대응
> - tier 정책: tier=0 L4+, tier=1 qs>=0.85 AND L2+, tier=2 나머지

### Claude:

**Opus 설계 비판적 리뷰 결과:**

수용한 것:
- promotion_history = metadata JSON에 이미 있음 (내 오판 수정 ✅)
- Generic 87.2% (95.1% → 수치 수정)
- 신규 발견 4건 (E14 0%, 고아 240, confidence 99.7%=1.0, auto-edge generic)
- Wave 구조, 병렬 배치, 리스크 대응 전반 ✅

**tier 정책만 수정 필요:**

| 정책 | Opus 제안 | 내 수정 | 이유 |
|------|-----------|---------|------|
| tier=0 | layer >= 4 | **layer >= 3** | L4/L5 현재 0개. L3(Principle/Identity)이 core 돼야 recall 차별화 |
| tier=1 | qs >= 0.85 AND L2+ | **qs >= 0.8 AND L2** | 0.85는 너무 빡빡. enrichment 64%만 완료 상태에서 0.8이 실용적 |
| tier=2 | 나머지 | 동일 | — |

**최종 합의된 tier 정책:**
```
tier=0: layer >= 3       ← 원칙/정체성/세계관/가치 = 무조건 core
tier=1: L2 + qs >= 0.8   ← 검증된 패턴/인사이트만 reviewed
tier=2: 나머지           ← 기본값
```

---

### Paul:
> Opus가 tier 수정 수용하고 실행 중. 더 논의할 사항 있는지 판단해봐.

### Claude:

**추가 논의 2건 (실행에 영향 줄 수 있는 것만):**

**1. L3 328개 전부 tier=0 — 10% = core. 너무 많지 않나?**
- 결론: (A) 그냥 간다. 10%는 아직 소수파. L3는 본질적으로 core.
- L2 658개 + L0-L1 2,000+과의 차별화에 328개 core는 의미 있다.
- 나중에 enrichment 완료 후 quality gate 추가 가능.

**2. remember() 자동 edge generic 근본 문제 — B(relation gate)만으로는 안 풀림**
- 현재: 새 노드도 계속 "supports"/"connects_with"로 들어감
- E14 소급으로 기존 해결 + 하지만 새 edge는 계속 generic
- 근본 해결 3가지:
  - **(α) 규칙 기반 매핑**: 타입 조합 → relation 자동 결정 (비용 0, 즉시)
    ```
    Decision → Pattern: "led_to"
    Observation → Signal: "triggered_by"
    Signal → Pattern: "realized_as"
    같은 프로젝트: "part_of"
    다른 레이어: "abstracted_from" / "expressed_as"
    ```
  - (β) 미니 LLM 호출 ($0.001/건, 나중에)
  - (γ) 배치 처리 = 현재 설계 (1일 딜레이)
- **추천: (α)를 B(relation gate)에 같이 넣기. Opus 실행 중이면 지금 반영.**

---

### Paul (Opus 판단 전달):
> 1번 (A)로 간다. 선 실행, 후 정제. enrichment 완료 후 quality<0.5 L3는 tier=1 강등.
> 2번 (α) 규칙 기반 매핑이 압도적. 이유 3가지: 비용 0 + E14 작업량 절감 + forward/retroactive 동시.
>
> 매핑 테이블:
> ```
> (Observation, Signal)  → "triggered_by"
> (Signal, Pattern)      → "realized_as"
> (Pattern, Principle)   → "crystallized_into"
> (Insight, Principle)   → "crystallized_into"
> (Decision, Pattern)    → "led_to"
> (Failure, Decision)    → "resolved_by"
> (Failure, Insight)     → "led_to"
> (Question, Insight)    → "resolved_by"
>
> # 레이어 fallback
> src_layer < tgt_layer → "abstracted_from"
> src_layer > tgt_layer → "expressed_as"
> 같은 프로젝트·레이어  → "part_of"
> 다른 프로젝트·레이어  → "connects_with" (유일한 generic 잔류)
> ```
>
> 적용 순서: config.py 매핑 → insert_edge 규칙 적용 → 기존 generic 일괄 재분류 → E14 잔여분만
>
> 구현 진행 중. 향후 검증 방법은?

### Claude:

**검증 계획 — 3단계**

#### Stage 1: 구현 직후 즉시 (Wave 1+2 완료 시점, 5분)
- 1a. DB 스키마: correction_log 존재, FTS5에 summary/key_concepts 포함
- 1b. tier 분포: tier=0 ~328, tier=1 > 0 (L2 + qs >= 0.8)
- 1c. relation gate: 잘못된 relation → connects_with fallback + correction_log 기록
- 1d. EXPLORATION_RATE = 0.1 존재

#### Stage 2: 규칙 재분류 후 (Wave 3 중간, 15분)
- 2a. generic 비율: 87.2% → **40% 이하** (규칙 적용 후)
- 2b. 규칙 정확도: 50개 랜덤 샘플 육안 → **80% 이상 합격**
- 2c. 방향성 모순 0건 (abstracted_from인데 source_layer > target_layer 같은 것)

#### Stage 3: 전체 완료 후 시스템 검증 (Wave 3 완료, 20분)
- 3a. recall 품질 Before/After — 5개 테스트 쿼리, tier=0/1이 상위 60% 이상
- 3b. SessionStart에 L3+ 노드 포함 확인
- 3c. generic 비율 E14 후: **15% 이하**
- 3d. 고아 노드: 240 → **50 이하**
- 3e. L4/L5 시드: 4-6개 존재

#### 합격 기준 요약

| 지표 | 합격 | 불합격 시 |
|------|------|-----------|
| tier 분포 | 0:~328, 1:>0, 2:나머지 | 스크립트 디버그 |
| generic (규칙 후) | < 40% | 매핑 보완 |
| generic (E14 후) | < 15% | 프롬프트 튜닝 |
| 규칙 정확도 | >= 80% | 매핑 수정 |
| recall tier 0/1 | >= 60% | tier_bonus 조정 |
| 고아 노드 | < 50 | edge 생성 스크립트 |
| 방향성 모순 | 0건 | 규칙 버그 |

**추가 제안**: 규칙 재분류 시 correction_log에 `corrected_by = 'rule'` 기록.
→ 나중에 rule vs e14 vs paul 정확도 비교 가능.

---

### Paul (Opus 검증 결과 전달):
> Stage 1: 완료, 바로 검증 가능. 단 correction_log에 edge_id 컬럼 없음.
> Stage 2: 규칙 재분류 완료. generic 42% (합격선 40% 근접). 50개 샘플 + 방향성 모순 미검증.
> Stage 3: Phase 1 실행 중. recall/고아 노드 이후.
>
> 핵심 갭: 규칙 재분류 2,750건이 correction_log에 안 들어감. corrected_by='rule' 구분 불가.
> Opus 제안: (1) ALTER TABLE edge_id 추가, 소급 기록 건너뛰되 앞으로는 기록.
>
> 실행할까, correction_log 수정부터?

### Claude:

**Opus (1) 동의. 소급 건너뛰기 반대.**

소급 기록 해야 하는 이유:
1. Stage 2b 정확도 검증에 "규칙으로 바뀐 edge" 목록 필요
2. rule vs e14 정확도 비교 = 규칙 매핑 개선 피드백 루프 데이터
3. 비용 0 (로컬 SQLite INSERT, 5초)

추천 순서:
```
1. ALTER TABLE correction_log ADD COLUMN edge_id INTEGER;
2. 2,750건 소급 INSERT (old_value='supports'/'connects_with', corrected_by='rule')
3. Stage 1 + 2 검증 동시
```

42% generic = 간신히 합격. 매핑 테이블 확장 후보 8건 있으나, E14 결과 본 후 판단.

---

### Paul (검증 결과 전달):

| 항목 | 결과 | 판정 |
|------|------|------|
| 1a. correction_log + FTS5 v2 | 존재 | PASS |
| 1b. tier 분포 | 334/393/2503 | PASS |
| 1b. L2 quality gate | 9건 누락 (checkpoint 노드) | FIX |
| 1d. EXPLORATION_RATE | 0.1 | PASS |
| 2a. generic 비율 | 41.8% | NEAR (40% 합격선) |
| 2b. 정확도 | 8/8 = 100% (샘플 적음) | PASS |
| 2c. abstracted_from 모순 | 70건 | FIX |
| L4/L5 시드 | 6개 | PASS |
| 고아 노드 | 262 (목표 50) | Phase 1 후 |

버그 2건:
1. `infer_relation`에서 `src_layer < tgt_layer → "abstracted_from"` 이 잘못됨. L1→L3은 "generalizes_to"가 맞음.
2. checkpoint 노드 9건 tier 배정 누락 (tier 배정 후 유입)

> Opus: 전부 지금 수정

### Claude:

**Bug 1 분석: abstracted_from은 설계 결함**

규칙의 의미론이 틀림. `src_layer < tgt_layer → "abstracted_from"`은 말이 안 됨 (L1이 L3에서 추상화됐다?).

수정:
```
src < tgt (아래→위): "generalizes_to"     ← 변경
src > tgt (위→아래): "expressed_as"       ← 유지
src == tgt 같은 프로젝트: "part_of"
src == tgt 다른 프로젝트: "connects_with"
```
"abstracted_from"은 규칙 매핑에서 제거. E14가 문맥으로 판단할 관계.

**Bug 2 분석: tier 배정 후 유입 = 시스템 결함**

근본 해결: remember() 안에서 INSERT 시점에 tier 자동 배정.
```python
layer = PROMOTE_LAYER.get(type, None)
tier = 0 if layer >= 3 else (1 if layer == 2 and qs >= 0.8 else 2)
```

**추가**: 2b 샘플 8개는 너무 적음. 50개로 확대 필요.

---

## 2026-03-05 02:57 — 내일 작업 지시: v2.0 완성 후 3축 검증 + 제1원칙 적용

### Paul:
> v2.0이 내일 오전 완료된다. 이후 검증 3축:
> 1. **온톨로지 자체 검증** — 분류/연결/흐름이 실제로 제대로 작동하는지 철저 분석
> 2. **사용 검증** — 세션 시작/중간/마무리에서 실제로 어떻게 사용되는지 놓치는 부분 없이
> 3. **시스템 궁합 검증** — orchestration 스킬/에이전트/MD/설정과 온톨로지가 제대로 맞물리는지
>
> 적용할 원칙 2가지:
> - **제1원칙 사고**: "왜 꼭 그래야 하는가?" 반복. 전제를 의심하고 해체.
> - **Best part is no part**: 최고의 효율 = 부품/과정 자체를 없애는 것. 불필요한 것을 최적화하지 말고 제거.

### Claude:

**내일 검증 프레임 — 3축 + 제1원칙**

#### 축 1: 온톨로지 자체 검증
- 타입별/관계별/레이어별 실사용 분포
- 크로스 도메인 연결 존재 여부
- 승격 경로 실재성
- **외부 AI에게 DB 덤프 → "약점 찾아라"** (선입견 없는 검증)
- 제1원칙: "왜 50개 타입이어야 하는가?" → 사용 0인 타입 = 제거 후보

#### 축 2: 사용 검증
- 세션 시작/중간/마무리에서 어떤 도구가 어떤 hook/skill에서 호출되는가
- 13개 MCP 도구 중 실제 사용 빈도
- Best part is no part: 7개 안 쓰이면 → 제거 or "요청 시 로드"

#### 축 3: 시스템 궁합
- 스킬/에이전트/MD/Hook → 온톨로지 연결 추적
- SoT 위반 확인 (STATE.md vs 온톨로지 중복?)
- 날카로운 질문: "온톨로지를 꺼버리면 내일 세션에서 뭐가 달라지는가?"

#### 실행 배정
| 축 | 실행자 | 이유 |
|---|---|---|
| 1. 온톨로지 자체 | 외부 AI | 선입견 없는 분석 |
| 2. 사용 검증 | Opus | 코드 추적 |
| 3. 시스템 궁합 | Opus + Paul | 시스템 전체 맥락 대화 |

#### 근본 질문 (제1원칙)
> "이 온톨로지가 정말 필요한가? MEMORY.md 200줄로 충분하지 않았는가?"
→ "규모의 문제"를 데이터로 증명해야 함.

---

### Paul:
> 다른 각도 3개 제시. 온톨로지는 뉴런처럼 작동해야 한다. 너와 내가 상호작용하고 상승하는 통로.
> 제1원칙 + best part is no part 적용. 불필요한 것을 최적화가 아니라 제거.
> 아티클 작성 지시 + Gemini/Perplexity/GPT deep research 프롬프트 요청.

### Claude:

**3가지 다른 각도:**

#### 각도 1: 정보 엔트로피 — 신호 vs 잡음
- 3,200노드에서 recall top 5 = 99.8%를 버림. 잡음 비율은?
- 검증: Precision@K, 50자 미만 노드 수, 중복 노드(cosine>0.95), description 없는 edge 비율
- **시냅스 가지치기**: 뇌는 시냅스 40% 제거. 우리는 가지치기 0회. pruning 정책 필요.

#### 각도 2: 시간 역학 — 망각할 줄 아는가
- decay_rate=0.005가 실제로 작동하는가? 100일 후 60% 잔존 = 너무 느린가?
- temporal_relevance가 자동 감소하는가, enrichment 시점 고정인가?
- **핵심**: 1년 후 30,000노드면 recall 작동하는가? 스케일링 정책 없음.
- 해마→피질 전이 = L0→L5 승격인데, 실제로 일어나고 있는가?

#### 각도 3: 창발성 — 부분의 합보다 큰 것이 있는가
- Community detection으로 프로젝트 경계를 넘는 클러스터 존재 확인
- Small-world 특성 (짧은 경로 + 높은 클러스터링) = 뇌의 전형적 구조
- 허브 노드 = Paul의 핵심 원칙이 가장 많이 연결돼야 자연스러움
- EXPLORATION_RATE=0.1 vs DMN=20-30%. 너무 적은가?

**Deep Research 프롬프트 3개 (Gemini/Perplexity/GPT) 제공 완료.**
리서치 에이전트 3개 백그라운드 실행 중 — 뉴로사이언스/응용온톨로지/철학·시스템 각 100+소스 목표.

---

### Paul:
> 또 다른 무료 AI한테 시킬 수 있는거 없나. 이런 식으로 조사시키고 싶다.

### Claude:

**9개 무료 AI 리서치 배정 완료:**

| AI | 역할 | 프롬프트 제공 |
|---|---|---|
| Gemini | 뉴로사이언스 + 아키텍처 | ✅ |
| Perplexity | 최신 구현체 + 산업 동향 | ✅ |
| GPT o3 | 비판적 구조 분석 | ✅ |
| DeepSeek R1 | 수학적 수렴/스케일링 증명 | ✅ |
| NotebookLM | 내부 문서 모순 탐지 (업로드) | ✅ |
| Elicit + Consensus | 학술 논문 100+ 수집 | ✅ |
| Copilot | 웹 + 학술 통합 (Palantir/MIT) | ✅ |
| Grok | X 실시간 담론/트렌드 | ✅ |
| Phind | 코드 구현 패턴 | ✅ |

각 플랫폼 특성에 맞게 프롬프트 차별화. 결과는 한 곳에 모아서 아티클에 통합.

---

## 아티클 작성 완료

**파일**: `docs/2026-03-05-ontology-claude-paul.md`
**제목**: 온톨로지, 클로드, 그리고 Paul
**구조**: 8개 섹션
1. 세 개의 독립체
2. 뇌 과학 기반 (CLS, Hebbian, Pruning, DMN, Spreading Activation, Reconsolidation)
3. 삼체 연결 아키텍처 (Extended Mind, Distributed Cognition, Transactive Memory)
4. 상승 루프 (Self-Organization, Autopoiesis, Small-World, 구체적 메커니즘)
5. 제1원칙 적용 (50타입? 48관계? 6레이어?)
6. 다음 단계 (수면 리플레이, 가지치기, DMN A/B, 재공고화)
7. 리서치 소스 인덱스 (382개, 3개 카테고리)
8. 열린 질문 6개

**리서치 에이전트 결과**: 뉴로사이언스 132 + 응용 온톨로지 130 + 철학·시스템 120 = **382개 소스**

(대화 계속)

