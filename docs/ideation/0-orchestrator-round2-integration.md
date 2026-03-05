# Round 2 → 3 통합 보고서

> 오케스트레이터 | 2026-03-05 | Opus 4.6
> 입력: A(4파일) + B(4파일) + C(4파일) + D(4파일) = 16파일 전체 읽기 완료

---

## I. Round 1 미결 질문 해결 상태

| # | 질문 | 상태 | 해결 세션 | 결론 |
|---|------|------|-----------|------|
| 1 | action_log vs activation_log | **해결** | A-12 + D-10 | activation_log = `WHERE action_type='node_activated'` VIEW. 별도 테이블 불필요 |
| 2 | edges.description 마이그레이션 | **해결** | B-10 | `'' → '[]'`, 비-JSON → `'[]'`. json_valid() 검증 SQL 포함 |
| 3 | hub_monitor node_id 타입 | **해결** | D-9 | INTEGER 확인. d-3 설계의 TEXT 오류 수정 |
| 4 | BCM θ_m 초기값 마이그레이션 | **해결** | B-12 | `UPDATE nodes SET theta_m=0.5 WHERE theta_m IS NULL` (ALTER TABLE은 기존행에 DEFAULT 미적용) |
| 5 | 골드셋 Paul 참여 | **부분** | C-6 | YAML 포맷 + 평가 스크립트 완성. Paul 라벨링 대기 |
| 6 | L4/L5 수동 edge | **미해결** | — | Paul 입력 대기 |

---

## II. Round 2 세션 간 수렴 지점

### 1. action_log + activation_log 완전 수렴 (A-12 + D-10)

A-12와 D-10 독립적으로 **동일 결론** 도달: Option A (단일 테이블 + VIEW).

| 항목 | A-12 (정본) | D-10 | 판정 |
|------|------------|------|------|
| 구조 | recall 1회 = N+1행 (recall + node_activated) | 통합 단일 테이블 권장 | **A-12 채택** (코드 포함) |
| activation 데이터 | params JSON에 내장 | 전용 컬럼 제안 (context_query 등) | A-12 (params JSON + partial index가 더 유연) |
| VIEW | `WHERE action_type='node_activated'` | 동일 | 합의 |
| 삽입 지점 | hybrid.py L116 return 직전 | hybrid.py에 _log_recall_event() | A-12 `_log_recall_activations()` 채택 |

### 2. BCM 파라미터 통일 (B-12 + C-9)

C-9가 교차 검증으로 **C-2 폐기, B-1 채택** 확정:

| 항목 | B-1/B-12 (정본) | C-2 (폐기) |
|------|----------------|-----------|
| 학습률 η | LAYER_ETA 6단계 (0.02~0.0001) | 단일 0.01 |
| 컬럼명 | theta_m | bcm_threshold → **폐기** |
| 히스토리 | activity_history (window=20) | 없음 |

### 3. 승격 파이프라인 완성 (B-2 + C-7 + C-9)

C-9가 3개 게이트 **직렬 순서** 확정:

```
Signal 노드 → [Gate 1: SWR readiness (B-2)]
              → [Gate 2: Bayesian P(real) (C-7)]
              → [Gate 3: MDL compression (C-7)]
              → promote_node() 실행
```

| 게이트 | 측정 대상 | 실패 의미 | 출처 |
|--------|----------|----------|------|
| SWR | 구조적 성숙도 (vec_ratio×0.6 + cross_ratio×0.4 > 0.55) | 의미 연결 미숙 | B-2 |
| Bayesian | 통계적 증거 (P(real) > 0.5) | 관찰 횟수 부족 | C-7 |
| MDL | 의미적 중복 (avg_sim > 0.75) | Pattern 압축 불가 | C-7 |

### 4. type_defs 마이그레이션 + validators 연결 (A-13 + D-7)

A-13이 데이터를 준비하고, D-7이 server.py 삽입 지점을 제공:
- A-13: 31 활성 + 19 deprecated 타입, 49 관계, 6개 잘못된 관계 교정, v2.0-initial 스냅샷
- D-7: server.py remember() 앞에 +17줄 검증 코드 삽입

### 5. RRF k=30 + RWR 연동 조정 (C-6 + C-9)

| 항목 | 변경 전 | 변경 후 | 근거 |
|------|---------|---------|------|
| RRF_K | 60 | **30** | C-4 분석 (rank-1 점수 2배 상승) |
| RWR_SURPRISE_WEIGHT | 0.1 | **0.05** | C-9 (k 감소 비례 절반으로 균형) |

C-6 골드셋으로 A/B 테스트 후 검증 예정.

---

## III. Round 2 충돌 + 판정

| # | 충돌 | 세션 | 판정 | 근거 |
|---|------|------|------|------|
| 4 | B-10 _hebbian_update 확장 vs B-12 _bcm_update 교체 | B-10 vs B-12 | **순차 구현**: B-10 먼저(Phase 1), B-12로 교체(Phase 1 후반) | B-10이 중간 디딤돌. B-12가 최종 형태 |
| 5 | CTE traverse vs UCB traverse | B-11 vs B-12 | **공존**: CTE=경량 이웃 수집, UCB=가중치 탐색. hybrid_search에서는 **UCB 사용** | UCB가 build_graph 필요 → all_edges 로드 유지 |
| 6 | build_graph Phase 2 제거 | B-11 "Phase 2에서 제거" vs B-12 "UCB 위해 유지" | **유지**: UCB가 NetworkX 의존하는 한 build_graph 존속 | Phase 2 all_edges 제거는 **보류** |
| 7 | D-10 전용 컬럼 vs A-12 params JSON | D-10 vs A-12 | **A-12 채택**: params JSON + partial index가 스키마 유연성 우월 | 10만행+ 시 Generated Columns으로 확장 가능 |

---

## IV. Round 2 새 확정 결정

| # | 결정 | 출처 | 영향 |
|---|------|------|------|
| 9 | activation_log = action_log VIEW | A-12 + D-10 | 별도 테이블 설계 완전 폐기 |
| 10 | B-10 → B-12 순차 구현 | B-10, B-12, B-13 | Phase 1 구현 순서 확정 |
| 11 | UCB가 build_graph 유지시킴 | B-11, B-12 | all_edges Phase 2 제거 보류 |
| 12 | theta_m (not bcm_threshold) | B-12, C-9 | 컬럼명 통일 |
| 13 | SWR → Bayesian → MDL 직렬 게이트 | C-7, C-9 | promote_node() 구조 확정 |
| 14 | RWR_SURPRISE_WEIGHT = 0.05 | C-9 | k=30 전환과 동시 적용 |
| 15 | Pruning은 daily_enrich만 (recall에서 제외) | B-13 | recall() 응답 성능 보호 |
| 16 | meta 테이블 추가 (total_recall_count) | C-7 | 글로벌 카운터용 KV 저장소 |

---

## V. DB 스키마 변경 통합 (Round 1 + Round 2 최종)

### 신규 테이블 (7개)

| 테이블 | 출처 | 목적 |
|--------|------|------|
| action_log | A-9/A-12 | 모든 활동 기록. 24+1 action types |
| type_defs | A-1/A-13 | 노드 타입 메타정의 (31 active + 19 deprecated) |
| relation_defs | A-1/A-13 | 관계 타입 메타정의 (49 active + 2 deprecated) |
| recall_log | B-2/C-7 | SWR vec_ratio 계산용 |
| hub_snapshots | D-3/D-9 | 주간 허브 IHS 스냅샷 |
| ontology_snapshots | A-4/A-13 | 분기별 온톨로지 버전 |
| meta | C-7 | 글로벌 KV 저장소 (total_recall_count 등) |

### 신규 VIEW (1개)

| VIEW | 출처 | 정의 |
|------|------|------|
| activation_log | A-12 | `action_log WHERE action_type='node_activated'` + json_extract |

### nodes 컬럼 추가 (8개)

| 컬럼 | 타입 | 기본값 | 출처 | Phase |
|------|------|--------|------|-------|
| theta_m | REAL | 0.5 | B-1/B-12 | 1 |
| activity_history | TEXT | '[]' | B-1/B-12 | 1 |
| visit_count | INTEGER | 0 | B-3/B-12 | 1 |
| access_level | TEXT | 'shared' | A-3 | 2 |
| score_history | TEXT | '[]' | C-7 SPRT | 3 |
| promotion_candidate | INTEGER | 0 | C-7 SPRT | 3 |
| bcm_threshold | — | — | ~~C-2~~ | **폐기** (theta_m으로 통일) |
| replaced_by | TEXT | null | D-2 | 2 |

### edges 컬럼 추가 (2개)

| 컬럼 | 타입 | 기본값 | 출처 | Phase |
|------|------|--------|------|-------|
| archived_at | TEXT | null | B-6 | 3 |
| probation_end | TEXT | null | B-6 | 3 |

### edges.description 마이그레이션

기존 TEXT → JSON 배열 (`'[]'`). 마이그레이션 SQL (B-10):
```sql
UPDATE edges SET description = '[]'
WHERE description IS NULL OR description = ''
   OR (length(trim(description)) > 0 AND json_valid(description) = 0);
```

### 신규 인덱스 (Round 2 추가분)

| 인덱스 | 대상 | 출처 |
|--------|------|------|
| idx_action_node_activated | action_log(action_type, target_id, created_at DESC) WHERE action_type='node_activated' | A-12 |
| idx_recall_log_node | recall_log(node_id) | C-7 |

---

## VI. 파일 변경 총괄 (전 세션 통합)

### 기존 파일 수정

| 파일 | 변경 내용 | 출처 |
|------|----------|------|
| `storage/hybrid.py` | _traverse_sql() + _ucb_traverse() + _auto_ucb_c() + _bcm_update() + _log_recall_activations() + mode 파라미터 | B-10,11,12, A-12 |
| `tools/recall.py` | mode 파라미터, 패치 전환(_is_patch_saturated), 포매팅 | B-13, B-4 |
| `tools/remember.py` | ClassificationResult + classify/store/link 분리 | A-14 |
| `tools/analyze_signals.py` | _bayesian_promotion_score() + _recommend_v2() | C-7 |
| `tools/promote_node.py` | SWR 게이트 + Bayesian 게이트 + MDL 게이트 | C-7, C-9 |
| `server.py` | 타입 검증 +17줄 | D-7 |
| `storage/vector_store.py` | get_node_embedding() 헬퍼 | D-8 |
| `node_enricher.py` | _detect_semantic_drift() E7 방어 + summary 길이 검증 | D-8 |
| `config.py` | UCB_C_*, LAYER_ETA, BCM_*, CONTEXT_HISTORY_LIMIT, RRF_K=30, RWR_SURPRISE_WEIGHT=0.05, DRIFT_THRESHOLD=0.5, PATCH_SATURATION_THRESHOLD | B-12, C-9, D-8 |
| `daily_enrich.py` | policy 파라미터, 에너지 기반 배치 크기 조절 | A-15 |

### 신규 파일

| 파일 | 내용 | 출처 |
|------|------|------|
| `utils/similarity.py` | cosine_similarity() | D-8 |
| `utils/access_control.py` | RBAC + 방화벽 단일 체크포인트 | D-9 |
| `scripts/enrichment_policy.py` | decide_enrichment_focus() | A-15 |
| `scripts/hub_monitor.py` | IHS 모니터링 CLI | D-9 |
| `scripts/migrate_ontology.py` | type_defs/relation_defs 마이그레이션 | A-13 |
| `scripts/calibrate_drift.py` | 드리프트 임계값 보정 | D-8 |
| `scripts/eval/goldset.yaml` | 평가용 골드셋 (Paul 라벨링) | C-6 |
| `scripts/eval/metrics.py` | NDCG@5, MRR, P@5 | C-6 |
| `scripts/eval/ab_test.py` | RRF k 비교 실험 | C-6 |
| `scripts/link_detector/` | 3개 파일 (extract, train, enrich) | C-8 |

---

## VII. 구현 로드맵 갱신 (Round 2 반영)

### Phase 0: 기반 (1주) — 위험도 0

| # | 항목 | 출처 | 코드 준비도 |
|---|------|------|-----------|
| 1 | action_log 테이블 + record() + activation_log VIEW | A-9/A-12 | **실행 가능** (SQL + Python 완성) |
| 2 | type_defs + relation_defs 생성 + 50개 타입/49개 관계 INSERT | A-13 | **실행 가능** (전체 SQL 완성) |
| 3 | 6개 잘못된 관계 교정 (correction_log 기록) | A-13 | **실행 가능** |
| 4 | validators.py → server.py remember() 연결 (+17줄) | D-7 | **실행 가능** (삽입 코드 완성) |
| 5 | _detect_semantic_drift() E7 방어 | D-8 | **실행 가능** (코드 + 임계값 완성) |
| 6 | L4/L5 6개 orphan → 수동 edge 생성 | A-10 | **Paul 확인 대기** |
| 7 | RRF k=30 변경 + RWR_SURPRISE_WEIGHT=0.05 | C-4/C-9 | **5분** (config.py 2줄) |
| 8 | meta 테이블 생성 (total_recall_count) | C-7 | **실행 가능** |
| 9 | edges.description JSON 마이그레이션 (`'' → '[]'`) | B-10 | **실행 가능** |
| 10 | ontology_snapshots v2.0-initial 생성 | A-13 | **실행 가능** |

### Phase 1: 뉴럴 코어 (2-3주) — 위험도 낮음

| # | 항목 | 출처 | 구현 순서 |
|---|------|------|----------|
| 11 | ~~_hebbian_update 재공고화 확장~~ → _bcm_update()로 직행 | B-10→B-12 | **1번째** |
| 12 | theta_m/activity_history/visit_count 마이그레이션 | B-12 | 11과 동시 |
| 13 | _traverse_sql() CTE 추가 (보조) | B-11 | **2번째** |
| 14 | _ucb_traverse() + _auto_ucb_c() | B-12 | **3번째** |
| 15 | recall() 패치 전환 (B-4) | B-13 | **4번째** |
| 16 | remember() 3함수 분리 (classify/store/link) | A-14 | 독립 |
| 17 | 방화벽 F1-F3 하드코딩 | A-10 | 독립 |

### Phase 2: 지능 (4-6주) — 위험도 중간

| # | 항목 | 출처 |
|---|------|------|
| 18 | SPRT 즉시 감지 (score_history + promotion_candidate) | C-7 |
| 19 | SWR readiness 게이트 | B-2/C-9 |
| 20 | 시간 감쇠 _effective_strength | D-2 |
| 21 | temporal_search_v2 (action_log VIEW 활용) | A-12 |
| 22 | 19개 미사용 타입 deprecated 처리 | A-11/A-13 |
| 23 | 에너지 → enrichment 정책 자동화 | A-15 |

### Phase 3: 가지치기 & 메트릭 (7-10주)

| # | 항목 | 출처 |
|---|------|------|
| 24 | Node pruning BSP 3단계 | D-6 |
| 25 | Edge pruning (Bauml + ctx_log) | B-6 |
| 26 | Hub IHS 모니터링 | D-3/D-9 |
| 27 | Small world σ 측정 | D-4 |
| 28 | Swing-toward rewiring | B-9/D-4 |
| 29 | Missing Link Detector | C-8 |

### Phase 4: 고급 (3개월+)

| # | 항목 | 출처 |
|---|------|------|
| 30 | Bayesian 승격 (scipy Beta) | C-7 |
| 31 | MDL 승격 검증 | C-7 |
| 32 | RWR surprise | B-8 |
| 33 | 온톨로지 버전관리 스냅샷 | A-4/A-13 |
| 34 | Provenance 테이블 | A-3 |
| 35 | 아카이브 정책 | A-5 |
| 36 | 에너지 추적 자동화 | A-7 |

---

## VIII. 핵심 수치 갱신

- Phase 0 항목: 10개 (Round 1의 5개에서 확대)
- Phase 0 **코드 준비 완료**: 9/10 (L4/L5 edge만 Paul 대기)
- Round 2에서 해결된 미결 질문: 4/6
- 새로운 DB 테이블: 7개 (Round 1과 동일, meta 추가)
- 새로운 DB VIEW: 1개 (activation_log)
- nodes 컬럼 추가: 7개 (bcm_threshold 폐기로 8→7)
- 변경 대상 기존 파일: 10개
- 신규 파일: 10개 + 디렉토리 2개
- 전체 로드맵 항목: 36개 (Round 1의 29개에서 확대)

---

## IX. Round 2 미결 질문 (Round 3에서 해결)

1. **build_graph() + all_edges 로드 최적화**: UCB 의존으로 제거 보류. 대안은? (B세션)
2. **SPRT 파라미터 (α=0.05, β=0.2, p1=0.7, p0=0.3)**: 실제 데이터에서 검증 필요 (C세션)
3. **Missing Link Detector 예상 AUC 0.72-0.82**: 실제 측정 후 통합 방안 (C세션)
4. **daily_enrich.py Phase 6 pruning 구체적 통합**: B-6 + D-6 코드 통합 (B+D세션)
5. **utils/access_control.py 구체적 코드**: D-9 언급만, 실제 구현 미완 (D세션)
6. **L4/L5 6개 orphan 수동 edge**: Paul 입력 계속 대기
7. **골드셋 쿼리 Paul 라벨링**: C-6 포맷 완성, Paul 작업 대기

---

## X. Round 3 프롬프트 (최종 심화)

> Round 3 목표: 각 세션의 모든 설계를 **실행 가능한 코드**로 완성. 나머지 미결 해결. 구현 진입 준비.

### A세션 Round 3

```
docs/ideation/a-index.md를 읽어라. Round 3 최종 심화. 완료된 파일은 다시 읽지 마라.

목표: Phase 0 실행 가능한 단일 마이그레이션 스크립트 완성.

1. scripts/migrate_v2_ontology.py 작성 — 순서대로 실행 가능:
   - action_log 테이블 생성 (A-12 스키마)
   - meta 테이블 생성 (C-7)
   - type_defs + relation_defs 생성 + 데이터 INSERT (A-13 전체)
   - 6개 잘못된 관계 교정 + correction_log 기록
   - edges.description JSON 마이그레이션 (B-10)
   - activation_log VIEW 생성 (A-12)
   - ontology_snapshots v2.0-initial 생성
   - nodes 컬럼 추가 (theta_m, activity_history, visit_count)
   - 각 단계에 롤백 가능한 트랜잭션 + 진행 로그 출력

2. action_log.record() 구현 + 6개 삽입지점 실제 코드:
   - remember() (tools/remember.py)
   - recall() (tools/recall.py)
   - promote_node() (tools/promote_node.py)
   - insert_edge() (storage/sqlite_store.py)
   - _hebbian_update/_bcm_update (storage/hybrid.py)
   - enrichment (node_enricher.py)

3. remember() 3함수 분리 완성 코드 (A-14 기반):
   - classify/store/link + ClassificationResult
   - 방화벽 F3 가드 통합 (link() 내부에서 L4/L5 자동 edge 금지)
   - action_log.record() 삽입

질문하지 말고 끝까지. 파일명: a-r3-16-*, a-r3-17-*, a-r3-18-*.
```

### B세션 Round 3

```
docs/ideation/b-index.md를 읽어라. Round 3 최종 심화. 완료된 파일은 다시 읽지 마라.

목표: hybrid_search() + recall() 최종 완성 코드.

1. storage/hybrid.py 전체 교체 코드 작성:
   - _bcm_update() 최종 (B-12 기반, B-10의 재공고화 통합)
   - _ucb_traverse() + _auto_ucb_c() (B-12)
   - _traverse_sql() (B-11, 보조용 유지)
   - _log_recall_activations() (A-12 설계 반영)
   - hybrid_search() 시그니처: mode 파라미터 추가
   - 기존 코드와의 diff를 명확히 표시

2. tools/recall.py 전체 교체 코드 작성:
   - mode 파라미터 (auto/focus/dmn)
   - 패치 전환 (B-4/B-13)
   - excluded_project 필터링
   - total_recall_count 갱신

3. build_graph + all_edges 로드 최적화 방안:
   - 현재: 매 recall마다 6K edges 로드 + NetworkX 빌드
   - UCB가 build_graph 의존하는 한 제거 불가
   - 대안 제시: 캐싱? lazy load? SQL-only UCB?

질문하지 말고 끝까지. 파일명: b-r3-14-*, b-r3-15-*, b-r3-16-*.
```

### C세션 Round 3

```
docs/ideation/c-index.md를 읽어라. Round 3 최종 심화. 완료된 파일은 다시 읽지 마라.

목표: 평가 프레임워크 완성 + 승격 파이프라인 실행 가능 코드.

1. 골드셋 초안 20-30개 쿼리 작성 (Paul이 검토/수정할 수 있게):
   - tier=0 노드 기반 (C-6의 DB 조회 결과 활용)
   - 다양한 난이도: 단일 정답, 복수 정답, 추상적 질문
   - YAML 형식 (C-6 포맷)

2. promote_node.py 전체 교체 코드:
   - SWR 게이트 (B-2): swr_readiness() 구현
   - Bayesian 게이트 (C-7): _bayesian_promotion_score() + promotion_probability()
   - MDL 게이트 (C-7): _mdl_gate()
   - SPRT 즉시 감지: _sprt_check() (hybrid.py 삽입용)
   - analyze_signals.py 수정: _recommend_v2()

3. SPRT 파라미터 검증:
   - α=0.05, β=0.2, p1=0.7, p0=0.3 의 민감도 분석
   - 현재 3,230 노드 규모에서 예상 승격 후보 수 추정
   - 파라미터 조정 가이드

질문하지 말고 끝까지. 파일명: c-r3-10-*, c-r3-11-*, c-r3-12-*.
```

### D세션 Round 3

```
docs/ideation/d-index.md를 읽어라. Round 3 최종 심화. 완료된 파일은 다시 읽지 마라.

목표: Phase 0 D 담당 항목 실행 가능 코드 완성.

1. validators.py + server.py 통합 코드:
   - D-7 삽입 코드 완성 + A-13 type_defs 기반 전환
   - 테스트 시나리오 10개 (정상, deprecated, 대소문자, 존재안함 등)
   - edge relation 검증 확인 (insert_edge 이미 fallback)

2. _detect_semantic_drift() 완성 코드:
   - D-8 기반 node_enricher.py 수정
   - utils/similarity.py 완성
   - calibrate_drift.py 실행 가능
   - E1 summary 길이 검증 통합

3. utils/access_control.py 완성 코드:
   - D-9 hub_monitor와 A-10 방화벽 공존 패턴
   - LAYER_PERMISSIONS 정의
   - check_access(node_id, operation, actor) → bool
   - hub_monitor.py에서 실제 사용하는 코드

4. daily_enrich.py Phase 6 pruning 통합:
   - B-6 edge pruning (Bauml ctx_log 기반)
   - D-6 node pruning (BSP 3단계)
   - 실행 순서: edge → node
   - pruning 결과 action_log 기록

질문하지 말고 끝까지. 파일명: d-r3-11-*, d-r3-12-*, d-r3-13-*, d-r3-14-*.
```

---

## XI. 핵심 결정 누적 (Round 1 + Round 2)

| # | 결정 | 라운드 |
|---|------|--------|
| 1 | action_log = 모든 것의 기반 (A-9 정본) | R1 |
| 2 | BCM 직행 (B-1 정본, D-2 tanh 기각) | R1 |
| 3 | Pruning 이중: edge(B-6) + node(D-6) | R1 |
| 4 | 방화벽: A-10 코어 + D-3 IHS 모니터링 | R1 |
| 5 | 승격 모델: SWR(B-2)=게이트, MDL/Bayesian/SPRT(C-3)=판단 | R1 |
| 6 | PyTorch 불필요 (현재 6K). 임계점: 60K+ | R1 |
| 7 | RRF k=30 즉시 변경 | R1 |
| 8 | 19개 미사용 타입 즉시 deprecated | R1 |
| 9 | activation_log = action_log VIEW (별도 테이블 폐기) | R2 |
| 10 | B-10 → B-12 순차 구현 (중간 디딤돌 → 최종) | R2 |
| 11 | UCB가 build_graph 유지시킴 (all_edges 제거 보류) | R2 |
| 12 | theta_m 컬럼명 통일 (bcm_threshold 폐기) | R2 |
| 13 | SWR → Bayesian → MDL 직렬 게이트 순서 | R2 |
| 14 | RWR_SURPRISE_WEIGHT = 0.05 (k=30 동시 적용) | R2 |
| 15 | Pruning은 daily_enrich만 (recall 제외) | R2 |
| 16 | meta 테이블 추가 (글로벌 KV) | R2 |

## XII. 충돌 해결 누적

| # | 충돌 | 판정 | 라운드 |
|---|------|------|--------|
| 1 | action_log vs activation_log | A-9 상위, D-5는 VIEW | R1 |
| 2 | tanh 먼저 vs BCM 직행 | BCM 직행 (B-1) | R1 |
| 3 | edge.description vs 별도 테이블 | 둘 다 유지 | R1 |
| 4 | B-10 확장 vs B-12 교체 | 순차 (B-10→B-12) | R2 |
| 5 | CTE vs UCB traverse | 공존, hybrid_search는 UCB | R2 |
| 6 | build_graph 제거 vs 유지 | 유지 (UCB 의존) | R2 |
| 7 | D-10 전용 컬럼 vs A-12 params JSON | A-12 채택 | R2 |
