# Round 3 최종 통합 보고서 — 오케스트레이터

> 작성: 2026-03-05
> 입력: Round 3 파일 13개 (A:3, B:3, C:3, D:4) + Round 1-2 결정 16개
> 목적: 3라운드 아이디에이션 최종 수렴, 설계 진입 판단

---

## I. 라운드 3 요약

| 세션 | 파일 | 핵심 산출물 |
|------|------|------------|
| A | r3-16, 17, 18 | Phase 0 마이그레이션 스크립트, action_log.record() 구현, remember() 3함수 분리 최종 코드 |
| B | r3-14, 15, 16 | hybrid.py BCM+UCB 전체 교체, recall.py 패치전환+mode, 그래프 최적화 3옵션 |
| C | r3-10, 11, 12 | 골드셋 25쿼리, promote_node 3-gate 파이프라인, SPRT 수학 검증 |
| D | r3-11, 12, 13, 14 | validators type_defs 전환, drift 탐지, access_control 3계층, pruning Phase 6 통합 |

**Round 3 특성**: Round 1-2가 "무엇을, 왜" 였다면, Round 3은 **"정확히 어떻게"** — 전 세션이 구현 수준의 코드/스키마/테스트를 산출.

---

## II. 3라운드 전체 수렴 결과

### 1. action_log 중심 아키텍처 (A+D 완전 수렴)

Round 1에서 "action_log = 모든 것의 기반"으로 확정된 뒤, Round 3에서 구현까지 완료:
- **A-17**: `storage/action_log.py` — `record()` 함수 + 25개 ACTION_TAXONOMY + 6개 삽입지점
- **A-16 Step 1**: action_log 테이블 생성 (마이그레이션)
- **A-16 Step 7**: `activation_log` = action_log의 VIEW (D-5 제안 수용 확정)
- **D-14**: pruning에서 action_log.record() 호출 (graceful skip)

**원칙 확정**: 로깅 실패는 주 기능을 중단시키지 않는다 (fire-and-forget).

### 2. BCM+UCB 통합 학습 (B 완성, A 기반 제공)

- **B-14**: hybrid.py 전체 교체 — `_hebbian_update()` 삭제, `_bcm_update()` + `_ucb_traverse()` 도입
- BCM 공식: `delta_w = eta * v_i * (v_i - theta_m) * v_j`, 레이어별 η (L0=0.020 ~ L5=0.0001)
- UCB 공식: `Score(j) = w_ij + c * sqrt(ln(N_i+1) / (N_j+1))`, mode별 c 값 (focus=0.3, auto=1.0, dmn=2.5)
- **A-16 Step 9**: theta_m, activity_history, visit_count 컬럼 마이그레이션 제공

### 3. 승격 파이프라인 (B+C 수렴)

Round 2에서 "SWR→Bayesian→MDL 직렬 게이트" 확정 → Round 3에서 구현+검증:
- **C-11**: promote_node.py 3-gate 전체 교체 코드
  - Gate 1 SWR: `0.6*vec_ratio + 0.4*cross_ratio > 0.55`
  - Gate 2 Bayesian: `Beta(1,10)` prior, `P = (1+k)/(11+n) > 0.5`
  - Gate 3 MDL: cosine similarity 평균 > 0.75
- **C-12**: SPRT 파라미터 수학 검증 — α=0.05, β=0.2, p1=0.7, p0=0.3
  - 진짜 Signal → 승격: 평균 **8.2 recalls**
  - 노이즈 → 기각: 평균 **4.6 recalls**
  - 1개월 후 3-5개, 6개월 후 24-32개 승격 예상

### 4. 방화벽+접근제어 통합 (A+D 수렴)

- **A-18**: F3 방화벽 (L4/L5 자동 edge 차단) — remember()의 link()에 내장
- **D-13**: access_control.py 3계층 — F1 방화벽 + Hub 보호 + LAYER_PERMISSIONS
- **D-14**: pruning에서 check_access() 경유 (L4/L5 + Top-10 Hub 자동 보호)

**통합 원칙**: `check_access()`는 읽기 전용 판정 함수. 차단 시 caller가 처리 결정.

### 5. 검증 체계 (C+D 수렴)

- **D-11**: validators.py → type_defs 기반 live 검증 + deprecated 자동 교정
- **D-12**: drift 탐지 (cosine sim < 0.5 → ChromaDB 업데이트 차단) + summary 길이 이상치 탐지
- **C-10**: 골드셋 25쿼리 (NDCG 평가 기반, tier=0 노드 14개 사용)
- **C-12**: SPRT 수학 검증 (승격 결정의 통계적 엄밀성 보장)

---

## III. 신규 결정 (Round 3)

| # | 결정 | 근거 | 세션 |
|---|------|------|------|
| 17 | **마이그레이션은 단일 스크립트, 9단계, 멱등** | 실패 복구 가능, 반복 실행 안전 | A-16 |
| 18 | **edges.description → JSON 배열 재목적화** (재공고화 ctx_log) | B-10 설계와 수렴, 비가역적이므로 백업 필수 | A-16 |
| 19 | **action_log 로깅 실패 = silent fail** (주 기능 미중단) | A-17 원칙, D-14도 동일 패턴 | A-17 |
| 20 | **edge_created는 action_log에 미삽입** (이중 기록 방지) | remember→edge_auto, enrichment→enrichment_done으로 커버 | A-17 |
| 21 | **remember() MCP 외부 API 100% 하위호환** | classify/store/link 내부 분리, 외부 시그니처 불변 | A-18 |
| 22 | **recall mode 파라미터 추가** (auto/focus/dmn) | 기존 호출 하위호환, UCB c값만 변경 | B-15 |
| 23 | **그래프 캐싱 TTL 5분, Phase 1 즉시 적용** | 10줄 추가, 위험 없음, 90% 성능 개선 | B-16 |
| 24 | **NetworkX 완전 제거는 Phase 2** (SQL-only UCB) | Phase 1에서 안정성 확보 후 전환 | B-16 |
| 25 | **SPRT 파라미터 1개월 유지 후 재조정** | C-12 수학 검증 완료, 운영 데이터 필요 | C-12 |
| 26 | **validators.py type_defs 기반 전환** (schema.yaml = fallback만) | live DB가 정본, 런타임 수정 가능 | D-11 |
| 27 | **drift 탐지 threshold 0.5, summary 이상치 2.0x** | calibrate_drift.py로 운영 중 자동 조정 | D-12 |
| 28 | **access_control = 읽기전용 판정, caller가 처리 결정** | 단일 진입점 + 유연한 처리 가능 | D-13 |
| 29 | **Pruning은 edge→node 순서, daily_enrich Phase 6** | Bäuml 맥락 보호 → BSP 3단계 순차 | D-14 |

---

## IV. 잔여 충돌 및 해결

### 충돌 8: stats 테이블 vs meta 테이블

- **B-15**: `stats` 테이블 신규 생성 (total_recall_count 저장)
- **R2 결정 #16**: `meta` 테이블 = 글로벌 KV 저장소

**판정**: `stats` 테이블 폐기 → `meta` 테이블에 통합.
`meta(key='total_recall_count', value='0')` 으로 저장.
B-15의 `_increment_recall_count()` SQL을 meta 테이블 대상으로 수정.

### 충돌 9: node_enricher.py 다중 수정

- **D-12**: E7 블록 교체 (drift 탐지) + E1 summary 길이 검증
- **D-13**: `_apply()` 앞에 check_access 삽입
- **D-14**: pruning은 daily_enrich.py에서 호출 (node_enricher 직접 수정 없음)

**판정**: 충돌 없음. D-12(E7 블록)와 D-13(함수 시작)은 수정 위치가 다름. 순서: D-13 → D-12.

### 충돌 10: _traverse_sql() vs _ucb_traverse_sql()

- **B-11 (R2)**: `_traverse_sql()` CTE 설계
- **B-16 (R3)**: `_ucb_traverse_sql()` SQL-only UCB 신설 제안

**판정**: Phase 1에서는 B-14의 NetworkX `_ucb_traverse()` 사용. Phase 2에서 B-16의 `_ucb_traverse_sql()`로 전환 후 `_traverse_sql()`은 fallback 유지.

---

## V. DB 스키마 최종 통합

### 신규 테이블 (6개)

| 테이블 | 용도 | 설계 출처 |
|--------|------|-----------|
| `action_log` | 모든 작업 기록 (25 action_type) | A-12, A-16, A-17 |
| `type_defs` | 노드 타입 정의 (31 active + 19 deprecated) | A-13, A-16 |
| `relation_defs` | 관계 타입 정의 (48 active + 2 deprecated) | A-13, A-16 |
| `ontology_snapshots` | 온톨로지 버전 스냅샷 | A-13, A-16 |
| `recall_log` | recall 결과 기록 (SPRT 입력) | C-11 |
| `hub_snapshots` | 허브 노드 주기 스냅샷 | D-3, D-9 |

**meta 테이블**: R2 결정 #16에서 확정. A-16 Step 2에서 생성. B-15의 stats 기능 흡수.

### 신규 VIEW (1개)

| VIEW | 정의 | 출처 |
|------|------|------|
| `activation_log` | `action_log WHERE action_type='node_activated'` | A-16, D-5 |

### nodes 컬럼 추가 (7개)

| 컬럼 | 타입 | 기본값 | 용도 | 출처 |
|------|------|--------|------|------|
| `theta_m` | REAL | 0.5 | BCM 슬라이딩 임계값 | B-14, A-16 |
| `activity_history` | TEXT | '[]' | 최근 활성화 이력 (JSON) | B-14, A-16 |
| `visit_count` | INTEGER | 0 | UCB 탐색 횟수 | B-14, A-16 |
| `access_level` | TEXT | NULL | RBAC 접근 레벨 | D-13 |
| `score_history` | TEXT | '[]' | SPRT 판정 입력 (JSON) | C-11 |
| `promotion_candidate` | INTEGER | 0 | SPRT 승격 후보 플래그 | C-11 |
| `replaced_by` | TEXT | NULL | deprecated 타입 → 교체 타입 | D-11 |

### edges 컬럼 추가 (2개)

| 컬럼 | 타입 | 기본값 | 용도 | 출처 |
|------|------|--------|------|------|
| `archived_at` | TEXT | NULL | edge 아카이브 시점 | D-14 |
| `probation_end` | TEXT | NULL | pruning 유예 종료일 | D-14 |

### edges.description 재목적화

| 항목 | 기존 | 변경 |
|------|------|------|
| edges.description | 텍스트 설명 | JSON 배열 `[{"q":"...","t":"..."}]` — 재공고화 ctx_log |

**비가역적 변환** — 마이그레이션 전 DB 백업 필수.

### 인덱스 추가 (10개, A-16)

action_log(3), type_defs(1), relation_defs(1), edges.description(1), nodes.theta_m(1), nodes.visit_count(1), nodes.access_level(1), ontology_snapshots(1)

---

## VI. config.py 추가사항 통합

| 상수 | 값 | 용도 | 출처 |
|------|---|------|------|
| `UCB_C_FOCUS` | 0.3 | focus 모드 탐험 계수 | B-14 |
| `UCB_C_AUTO` | 1.0 | auto 모드 (기본) | B-14 |
| `UCB_C_DMN` | 2.5 | dmn 모드 (탐험 극대화) | B-14 |
| `BCM_HISTORY_WINDOW` | 20 | BCM 이력 윈도우 크기 | B-14 |
| `CONTEXT_HISTORY_LIMIT` | 5 | 재공고화 ctx_log 최대 항목 | B-14 |
| `PATCH_SATURATION_THRESHOLD` | 0.75 | 패치 포화 판정 비율 | B-15 |
| `PROMOTION_SWR_THRESHOLD` | 0.55 | SWR Gate 통과 기준 | C-11 |
| `SPRT_ALPHA` | 0.05 | 오승격 확률 상한 | C-12 |
| `SPRT_BETA` | 0.2 | 놓침 확률 상한 | C-12 |
| `SPRT_P1` | 0.7 | 진짜 Signal 판정 기준 | C-12 |
| `SPRT_P0` | 0.3 | 노이즈 판정 기준 | C-12 |
| `SPRT_MIN_OBS` | 5 | SPRT 최소 관측 수 | C-12 |
| `DRIFT_THRESHOLD` | 0.5 | semantic drift cosine sim 하한 | D-12 |
| `SUMMARY_LENGTH_MULTIPLIER` | 2.0 | summary 이상치 배수 기준 | D-12 |
| `SUMMARY_LENGTH_MIN_SAMPLE` | 10 | 이상치 판단 최소 샘플 | D-12 |
| `LAYER_ETA` | {0:0.020,...,5:0.0001} | BCM 레이어별 학습률 | B-14 |

---

## VII. 파일 변경 총괄

### 신규 파일 (10개)

| # | 파일 | 설명 | 출처 |
|---|------|------|------|
| 1 | `scripts/migrate_v2_ontology.py` | Phase 0 단일 마이그레이션 (9단계) | A-16 |
| 2 | `storage/action_log.py` | record() + ACTION_TAXONOMY 25개 | A-17 |
| 3 | `utils/similarity.py` | cosine_similarity (numpy/fallback) | D-12 |
| 4 | `utils/access_control.py` | check_access() 3계층 | D-13 |
| 5 | `scripts/calibrate_drift.py` | drift threshold 자동 측정 | D-12 |
| 6 | `scripts/eval/goldset.yaml` | 25쿼리 평가 데이터셋 | C-10 |
| 7 | `scripts/eval/ab_test.py` | RRF 파라미터 A/B 테스트 | C-10 |
| 8 | `tests/test_validators_integration.py` | validators TC1~TC10 | D-11 |
| 9 | `tests/test_remember_v2.py` | remember 분리 테스트 12개 | A-18 |
| 10 | `scripts/sprt_simulate.py` | SPRT 시뮬레이션 도구 | C-12 |

### 수정 파일 (10개)

| # | 파일 | 변경 범위 | 출처 |
|---|------|----------|------|
| 1 | `tools/remember.py` | **전체 교체** — 4함수 + ClassificationResult + F3 방화벽 | A-18 |
| 2 | `storage/hybrid.py` | **전체 교체** — BCM+UCB, Hebbian 삭제, ctx_log 재공고화 | B-14 |
| 3 | `tools/recall.py` | **전체 교체** — mode 파라미터, 패치 전환, 통계 | B-15 |
| 4 | `tools/promote_node.py` | **전체 교체** — SWR→Bayesian→MDL 3-gate | C-11 |
| 5 | `ontology/validators.py` | **전체 교체** — type_defs 기반, deprecated 교정 | D-11 |
| 6 | `server.py` | +25줄 — import + remember() 검증 블록 | D-11 |
| 7 | `config.py` | +16 상수 추가 (위 표 참조) | B+C+D |
| 8 | `storage/vector_store.py` | +get_node_embedding() | D-12 |
| 9 | `storage/sqlite_store.py` | +log_correction() | D-12 |
| 10 | `scripts/enrich/node_enricher.py` | E7 drift 탐지 + E1 길이 검증 + check_access | D-12, D-13 |

### 수정 파일 (Phase 2, 6개 추가)

| # | 파일 | 변경 범위 | 출처 |
|---|------|----------|------|
| 11 | `tools/analyze_signals.py` | +_recommend_v2() + _bayesian_cluster_score() | C-11 |
| 12 | `scripts/hub_monitor.py` | +recommend_hub_action() + print_hub_actions() | D-13 |
| 13 | `scripts/pruning.py` | +check_access 통합 | D-13, D-14 |
| 14 | `scripts/daily_enrich.py` | +Phase 6 pruning (edge→node 순서) | D-14 |
| 15 | `storage/hybrid.py` | +_sprt_check() + promotion_candidate 갱신 | C-11 |
| 16 | `storage/hybrid.py` | +_ucb_traverse_sql() (NetworkX 제거) | B-16 |

---

## VIII. 구현 순서 — 의존성 그래프

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 0: Foundation (1주)                                    │
│                                                              │
│  [A-16] migrate_v2_ontology.py 실행                          │
│     ├→ action_log 테이블                                     │
│     ├→ type_defs / relation_defs 테이블 + 데이터              │
│     ├→ edges.description → JSON 마이그레이션                  │
│     ├→ activation_log VIEW                                   │
│     ├→ nodes: theta_m, activity_history, visit_count         │
│     └→ ontology_snapshots + meta 테이블                      │
│                                                              │
│  [D-11] validators.py → type_defs 기반 전환                   │
│     └→ server.py 검증 블록 삽입                               │
│                                                              │
│  [C-10] goldset.yaml 작성 (DB 조회로 VERIFY 항목 확정)        │
│                                                              │
│  config.py 상수 16개 일괄 추가                                │
│                                                              │
│  RRF k=30 + RWR_SURPRISE_WEIGHT=0.05 적용                    │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Core Replacement (2-3주)                            │
│                                                              │
│  [A-17] storage/action_log.py 생성 + 6개 삽입지점             │
│     └→ depends: A-16 (action_log 테이블 존재)                 │
│                                                              │
│  [A-18] tools/remember.py 전체 교체                           │
│     └→ depends: A-17 (action_log.record)                     │
│                                                              │
│  [B-14] storage/hybrid.py 전체 교체 (BCM+UCB)                 │
│     └→ depends: A-16 (theta_m 등 컬럼), config.py             │
│                                                              │
│  [B-15] tools/recall.py 전체 교체 (mode+패치전환)              │
│     └→ depends: B-14 (hybrid_search 변경)                    │
│                                                              │
│  [B-16a] TTL 캐싱 10줄 추가                                   │
│     └→ depends: B-14 (hybrid.py 내부)                        │
│                                                              │
│  [D-12] drift 탐지 (utils/similarity.py + E7 수정)            │
│     └→ 독립 (Phase 0 이후 언제든)                             │
│                                                              │
│  [D-13] access_control.py                                    │
│     └→ 독립 (Phase 0 이후 언제든)                             │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Advanced Features (4-6주)                           │
│                                                              │
│  [C-11] promote_node.py 3-gate 교체                          │
│     └→ depends: recall_log, score_history, Phase 2 migration │
│                                                              │
│  [C-12] SPRT → C-11에 내장                                   │
│                                                              │
│  [D-14] daily_enrich.py Phase 6 pruning                      │
│     └→ depends: D-13 (check_access), A-17 (action_log)      │
│                                                              │
│  hub_monitor.py → hub_snapshots 생성                          │
│     └→ D-14 hub 보호의 선행 조건                              │
│                                                              │
│  [B-16b] SQL-only UCB + NetworkX 제거                        │
│     └→ depends: Phase 1 안정화 후                             │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Validation & Tuning                                 │
│                                                              │
│  [C-10] ab_test.py 실행 (RRF k=30 vs k=60)                  │
│  SPRT 운영 데이터 수집 → 파라미터 재조정                       │
│  calibrate_drift.py 실행 → threshold 검증                    │
│  small world audit + swing-toward                            │
└─────────────────────────────────────────────────────────────┘
```

---

## IX. 테스트 전략

### Phase 0 테스트 (마이그레이션)

| 테스트 | 검증 대상 |
|--------|----------|
| 빈 DB → migrate → 정상 동작 | 신규 사용자 |
| 기존 DB → migrate → 데이터 보존 | 기존 사용자 |
| migrate 2회 실행 → 멱등성 | 안전성 |
| type_defs 31+19=50 확인 | 완전성 |
| relation_defs 48+2=50 확인 | 완전성 |
| edges.description JSON 변환 확인 | 무결성 |

### Phase 1 테스트 (핵심 교체)

| 테스트 | 검증 대상 | 출처 |
|--------|----------|------|
| remember 12개 시나리오 | 하위호환 + F3 방화벽 + action_log | A-18 |
| validators 10개 시나리오 | type 검증 + deprecated 교정 | D-11 |
| BCM theta_m 수렴 | 레이어별 학습률 차이 확인 | B-14 |
| UCB mode 3종 비교 | focus/auto/dmn 결과 차이 | B-14, B-15 |
| 패치 포화 전환 | 75% 포화 시 혼합 결과 | B-15 |
| drift 탐지 | cosine sim < 0.5 → 차단 확인 | D-12 |
| access_control L4/L5 | paul만 write 가능 | D-13 |

### Phase 2 테스트

| 테스트 | 검증 대상 | 출처 |
|--------|----------|------|
| 3-gate 직렬 통과 | SWR→Bayesian→MDL 순서 | C-11 |
| SPRT 결정 | 8.2 recalls 내 승격 판정 | C-12 |
| pruning edge→node 순서 | Bäuml 맥락 보호 동작 | D-14 |
| goldset NDCG | baseline > 0.7 목표 | C-10 |

---

## X. 설계 진입 판단

### 준비 완료 근거

| 기준 | 상태 |
|------|------|
| 핵심 결정 수렴 | **29개 확정** (R1:8 + R2:8 + R3:13), 미결 0 |
| 충돌 해결 | **10/10 해결** (R1:3 + R2:4 + R3:3) |
| DB 스키마 확정 | 6 테이블 + 1 VIEW + 7 nodes 컬럼 + 2 edges 컬럼 |
| 코드 설계 완료 | 전체 교체 5개 + 신규 10개 + 수정 11개 |
| 테스트 정의 | 22개+ 시나리오 |
| 구현 순서 확정 | Phase 0→1→2→3 의존성 그래프 |
| 수학 검증 완료 | BCM 공식, UCB 공식, SPRT 파라미터 (C-12) |

### 리스크

| 리스크 | 심각도 | 완화 |
|--------|--------|------|
| edges.description 비가역 변환 | 높음 | 백업 필수 (A-16) |
| hybrid.py 전체 교체 회귀 | 높음 | TTL 캐시 + 단계적 전환 |
| 3K 노드 BCM 초기 수렴 불안정 | 중간 | L5 η=0.0001 보호 |
| SPRT 첫 결과까지 4-8주 | 낮음 | 설계 상 의도된 보수성 |
| goldset VERIFY 항목 5개 미확인 | 낮음 | Paul DB 조회로 해결 |

### 판정: **설계 진입 승인**

3라운드 아이디에이션으로 충분한 깊이의 설계가 완성됨. Phase 0은 코드 준비 9/10 완료 상태이며, 마이그레이션 스크립트(A-16)가 즉시 실행 가능. Phase 1의 5개 전체 교체 파일도 코드 수준 설계 완료.

---

## XI. Phase 0 즉시 실행 체크리스트

```
□ 1. DB 백업: cp data/memory.db data/memory.db.pre-v2
□ 2. config.py 상수 16개 추가
□ 3. scripts/migrate_v2_ontology.py 작성+실행 (A-16 기반)
□ 4. ontology/validators.py 교체 (D-11 기반)
□ 5. server.py 검증 블록 삽입 (D-11 기반)
□ 6. tests/test_validators_integration.py 작성+실행
□ 7. RRF k=30 적용 확인
□ 8. goldset.yaml VERIFY 항목 DB 조회 확정 (C-10)
□ 9. 마이그레이션 멱등성 검증 (2회 실행 테스트)
□ 10. git commit + push
```

---

## XII. 전체 결정 인덱스 (29개)

### Round 1 (#1-8)
1. action_log = 모든 것의 기반
2. BCM 직행 (tanh 기각)
3. Pruning 이중: edge(Bäuml) + node(BSP)
4. 방화벽: A-10 코어 + D-3 IHS 공존
5. 승격 모델: SWR=게이트, MDL/Bayesian/SPRT=판단
6. PyTorch 불필요 (임계점: 60K+ edges)
7. RRF k=30 즉시 변경
8. 19개 미사용 타입 즉시 deprecated

### Round 2 (#9-16)
9. activation_log = action_log VIEW
10. B-10→B-12 순차 구현
11. UCB가 build_graph 유지시킴
12. theta_m 컬럼명 통일
13. SWR→Bayesian→MDL 직렬 게이트
14. RWR_SURPRISE_WEIGHT=0.05
15. Pruning은 daily_enrich만
16. meta 테이블 추가

### Round 3 (#17-29)
17. 마이그레이션 단일 스크립트, 9단계, 멱등
18. edges.description → JSON 재목적화
19. action_log 로깅 = silent fail
20. edge_created action_log 미삽입
21. remember() 외부 API 100% 하위호환
22. recall mode 파라미터 추가
23. 그래프 캐싱 TTL 5분 즉시 적용
24. NetworkX 제거는 Phase 2
25. SPRT 1개월 유지 후 재조정
26. validators type_defs 기반 전환
27. drift threshold 0.5, summary 2.0x
28. access_control = 읽기전용 판정
29. Pruning edge→node 순서, daily_enrich Phase 6

---

## XIII. 잔여 충돌 해결 이력 (전체 10건)

| # | 충돌 | 판정 | 라운드 |
|---|------|------|--------|
| 1 | action_log vs activation_log | A-9 action_log 상위, D-5는 VIEW | R1 |
| 2 | tanh 먼저 vs BCM 직행 | BCM 직행 (B-1 정본) | R1 |
| 3 | edge.description 재활용 vs 별도 테이블 | 둘 다 유지 (목적 다름) | R1 |
| 4 | B-10 확장 vs B-12 교체 | 순차 (B-10→B-12) | R2 |
| 5 | CTE vs UCB traverse | 공존, hybrid_search는 UCB | R2 |
| 6 | build_graph 제거 vs 유지 | 유지 (UCB 의존) | R2 |
| 7 | D-10 전용 컬럼 vs A-12 params JSON | A-12 채택 | R2 |
| 8 | stats 테이블 vs meta 테이블 | meta에 통합 (stats 폐기) | R3 |
| 9 | node_enricher 다중 수정 | 위치 상이 → 충돌 없음 | R3 |
| 10 | _traverse_sql vs _ucb_traverse_sql | Phase별 분리, 공존 | R3 |

---

> **이 문서로 3라운드 아이디에이션이 완료됩니다.**
> **다음 단계: Phase 0 구현 시작.**
