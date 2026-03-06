# 오케스트레이터 인덱스 — 온톨로지 아이디에이션

> compact 후 이 파일만 읽고 이어서 진행한다.
> 역할: 4개 세션(A/B/C/D) 결과 수집 → 통합 → 심화 프롬프트 생성 → 반복

## 워크플로우

```
[Round 1] 초기 프롬프트 → A/B/C/D 작업 → 오케스트레이터 통합 보고 → 심화 프롬프트
[Round 2] 심화 1차 → A/B/C/D 작업 → 오케스트레이터 통합 보고 → 심화 프롬프트
[Round 3] 심화 2차 → A/B/C/D 작업 → 오케스트레이터 최종 통합 → 설계 진입
```

이 패턴은 아이디에이션 → 설계 → 실행 → 검증 모든 단계에서 동일하게 적용한다.

## 세션 구성

| 세션 | 담당 | 모델 | 상태 |
|------|------|------|------|
| A | 아키텍처 & 팔란티어 벤치마크 | Opus | **완료** (r0-r3, 19파일) |
| B | 뉴럴 메커니즘 구현 설계 | Sonnet | **완료** (r0-r3, 17파일) |
| C | PyTorch/ML 실험 가능성 | Sonnet | **완료** (r0-r3, 13파일) |
| D | 검증 & 허브 보호 & 메트릭스 | Sonnet | **완료** (r0-r3, 15파일) |

## 파일 네이밍 규칙

`{세션}-r{라운드}-{번호}-{주제}.md`

- r0: 분할 전 원본 (레퍼런스)
- r1: 초기 아이디에이션
- r2: 심화 1차
- r3: 심화 2차 (최종)

예: `a-r1-1-palantir.md`, `b-r2-10-reconsolidation-impl.md`
인덱스 파일(`a-index.md`, `0-orchestrator-index.md`)은 라운드 없이 유지.
오케스트레이터 보고서는 라운드별 생성: `0-orchestrator-round{N}-integration.md`

## 파일 목록 (라운드별)

### A세션 (19파일)
- r0: a-r0-architecture.md
- r1: a-r1-{1~11} (11개) — palantir, validation-gate, pkg, versioning, archive, firewall, energy, subtraction, action-log-deep, firewall-code, subtraction-data
- r2: a-r2-{12~15} (4개) — actionlog-activation-merge, migration-sql, remember-refactor, energy-enrichment
- r3: a-r3-{16~18} (3개) — migrate-script, actionlog-record, remember-final

### B세션 (17파일)
- r0: b-r0-neural-mechanisms.md, b-r0-neural-index.md
- r1: b-r1-{1~9} (9개) — bcm-vs-oja, swr-transfer, ucb-c, patch-foraging, reconsolidation, pruning, chen-sa, rwr-surprise, swing-toward
- r2: b-r2-{10~13} (4개) — reconsolidation-impl, cte-impl, bcm-ucb-integration, recall-flow
- r3: b-r3-{14~16} (3개) — hybrid-final, recall-final, graph-optimization

### C세션 (13파일)
- r0: c-r0-pytorch-ml.md
- r1: c-r1-{1~5} (5개) — kg-embedding, hebbian-bcm, promotion-models, rrf-experiment, roadmap
- r2: c-r2-{6~9} (4개) — goldset-design, promotion-integration, link-detector, cross-session-alignment
- r3: c-r3-{10~12} (3개) — goldset-draft, promotion-final, sprt-validation

### D세션 (15파일)
- r0: d-r0-validation-metrics.md
- r1: d-r1-{1~6} (6개) — fatal-weaknesses, consensus, hub-ihs, small-world, temporal, pruning
- r2: d-r2-{7~10} (4개) — validators-impl, drift-detector-impl, hub-monitor-ready, activation-actionlog-merge
- r3: d-r3-{11~14} (4개) — validators-final, drift-final, access-control, pruning-integration

## 통합 보고서 목록

| # | 파일 | 내용 | 라운드 |
|---|------|------|--------|
| 1 | `0-orchestrator-round1-integration.md` | 4세션 연결/충돌/로드맵, Round 2 프롬프트 | Round 1→2 |
| 2 | `0-orchestrator-round2-integration.md` | Round 2 수렴/충돌/스키마 통합, Round 3 프롬프트 | Round 2→3 |
| 3 | `0-orchestrator-round3-final.md` | **최종 통합 완료**, 설계 진입 승인 | Round 3→설계 |

## 핵심 결정 (확정)

### Round 1
1. **action_log = 모든 것의 기반** (A-9 설계가 정본, D-5 activation_log는 view/subset)
2. **BCM 직행** (B-1, D-2의 "tanh 먼저" 기각)
3. **Pruning 이중**: edge(B-6 Bäuml) + node(D-6 BSP) 둘 다 필요
4. **방화벽**: A-10 코어 + D-3 IHS 모니터링 공존
5. **승격 모델**: SWR(B-2) = 게이트, MDL/Bayesian/SPRT(C-3) = 판단
6. **PyTorch 불필요** (현재 6K edges). 임계점: 60K+ edges
7. **RRF k=30** 즉시 변경 (C-4)
8. **19개 미사용 타입 즉시 deprecated** (A-11)

### Round 2
9. **activation_log = action_log VIEW** (별도 테이블 폐기, A-12+D-10 수렴)
10. **B-10→B-12 순차 구현** (중간 디딤돌→최종)
11. **UCB가 build_graph 유지시킴** (all_edges 제거 보류)
12. **theta_m 컬럼명 통일** (bcm_threshold 폐기, C-9 확인)
13. **SWR→Bayesian→MDL 직렬 게이트** (C-9 확정)
14. **RWR_SURPRISE_WEIGHT=0.05** (k=30 동시 적용)
15. **Pruning은 daily_enrich만** (recall에서 제외, B-13)
16. **meta 테이블 추가** (글로벌 KV 저장소)

### Round 3
17. **마이그레이션 단일 스크립트, 9단계, 멱등** (A-16)
18. **edges.description → JSON 재목적화** (재공고화 ctx_log, 비가역적)
19. **action_log 로깅 = silent fail** (주 기능 미중단)
20. **edge_created action_log 미삽입** (이중 기록 방지)
21. **remember() 외부 API 100% 하위호환** (내부 classify/store/link 분리)
22. **recall mode 파라미터 추가** (auto/focus/dmn, 기존 호출 호환)
23. **그래프 캐싱 TTL 5분** (Phase 1 즉시 적용, 90% 성능 개선)
24. **NetworkX 제거는 Phase 2** (SQL-only UCB 전환)
25. **SPRT 파라미터 1개월 유지 후 재조정** (C-12 수학 검증 완료)
26. **validators type_defs 기반 전환** (schema.yaml = fallback만)
27. **drift threshold 0.5, summary 2.0x** (calibrate_drift.py로 조정 가능)
28. **access_control = 읽기전용 판정** (caller가 처리 결정)
29. **Pruning edge→node 순서, daily_enrich Phase 6** (Bäuml→BSP)

## 충돌 해결 이력

| # | 충돌 | 판정 | 라운드 |
|---|------|------|--------|
| 1 | action_log vs activation_log | A-9 action_log 상위, D-5는 view | R1 |
| 2 | tanh 먼저 vs BCM 직행 | BCM 직행 (B-1 정본) | R1 |
| 3 | edge.description 재활용 vs 별도 테이블 | 둘 다 유지 (목적 다름) | R1 |
| 4 | B-10 확장 vs B-12 교체 | 순차 (B-10→B-12) | R2 |
| 5 | CTE vs UCB traverse | 공존, hybrid_search는 UCB | R2 |
| 6 | build_graph 제거 vs 유지 | 유지 (UCB 의존) | R2 |
| 7 | D-10 전용 컬럼 vs A-12 params JSON | A-12 채택 | R2 |
| 8 | stats 테이블 vs meta 테이블 | meta에 통합 (stats 폐기) | R3 |
| 9 | node_enricher 다중 수정 | 위치 상이 → 충돌 없음 | R3 |
| 10 | _traverse_sql vs _ucb_traverse_sql | Phase별 분리, 공존 | R3 |

## 구현 로드맵 요약 (Phase 0-3, Round 3 최종)

- **Phase 0** (1주): 마이그레이션 스크립트(A-16), validators(D-11), config.py 상수 16개, goldset(C-10), RRF k=30
- **Phase 1** (2-3주): action_log(A-17), remember 교체(A-18), hybrid.py BCM+UCB(B-14), recall.py(B-15), TTL 캐시(B-16a), drift(D-12), access_control(D-13)
- **Phase 2** (4-6주): promote 3-gate(C-11+C-12), pruning Phase 6(D-14), hub_monitor, SQL-only UCB(B-16b)
- **Phase 3** (검증): ab_test NDCG, SPRT 운영 데이터 수집, calibrate_drift, small world audit

## DB 스키마 변경 총괄

### 신규 테이블 (7개)
action_log, type_defs, relation_defs, recall_log, hub_snapshots, ontology_snapshots, meta

### 신규 VIEW (1개)
activation_log (action_log WHERE action_type='node_activated')

### nodes 컬럼 추가 (7개)
theta_m, activity_history, visit_count, access_level, score_history, promotion_candidate, replaced_by
(~~bcm_threshold~~ 폐기 → theta_m으로 통일)

### edges 컬럼 추가 (2개)
archived_at, probation_end
(description: 기존 TEXT → JSON 마이그레이션)

## 안전 규칙 (2026-03-05 사고 후 확립)

> 사고: 오케스트레이터 통합 전에 범용 프롬프트 전송 → B가 소스코드 커밋, C가 config 커밋. git revert로 복구.

**워크플로우 (절대 순서 변경 금지):**
```
[Step 1] A~D 세션이 라운드 N 작업 완료
[Step 2] 오케스트레이터가 전체 읽기 → 통합 보고서 → Round N+1 프롬프트 생성
[Step 3] 오케스트레이터가 만든 구체적 프롬프트를 각 세션에 붙여넣기
```
Step 2를 건너뛰고 Step 3을 직접 하면 사고 발생.

1. **단계를 절대 건너뛰지 않는다** — 오케스트레이터 통합 완료 전 프롬프트 전송 금지
2. **범용 프롬프트("이어서 진행해라") 절대 금지** — 오케스트레이터가 만든 프롬프트만 사용
3. **아이디에이션 세션은 plan 모드로 실행** — 코드 수정/커밋을 구조적으로 차단
4. **모든 프롬프트에 안전장치 필수:**
   `중요: 이것은 아이디에이션이다. 소스코드 수정 금지. git commit 금지. docs/ideation/ 안에 md 파일만 생성하라.`
5. **잘못된 작업 발생 시 /clear** (/compact 아님)

## 현재 상태 (compact 후 이 섹션을 가장 먼저 확인)

**현재: 3라운드 아이디에이션 완료. 설계 진입 승인.**

완료된 것:
- Round 1-2-3 통합 보고서 3개 작성 완료
- 결정 29개 확정, 충돌 10개 해결
- DB 스키마, 파일 변경, 구현 순서 모두 확정

다음 할 일:
1. `0-orchestrator-round3-final.md` 섹션 XI의 Phase 0 체크리스트 따라 구현 시작
2. 아이디에이션 세션(A~D)은 종료 — 더 이상 프롬프트 전송 불필요
