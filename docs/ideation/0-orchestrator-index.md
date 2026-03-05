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
| A | 아키텍처 & 팔란티어 벤치마크 | Opus | Round 2 통합 완료, Round 3 프롬프트 전달 대기 |
| B | 뉴럴 메커니즘 구현 설계 | Sonnet | Round 2 통합 완료, Round 3 프롬프트 전달 대기 |
| C | PyTorch/ML 실험 가능성 | Sonnet | Round 2 통합 완료, Round 3 프롬프트 전달 대기 |
| D | 검증 & 허브 보호 & 메트릭스 | Sonnet | Round 2 통합 완료, Round 3 프롬프트 전달 대기 |

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

### A세션 (16파일)
- r0: a-r0-architecture.md
- r1: a-r1-{1~11} (11개) — palantir, validation-gate, pkg, versioning, archive, firewall, energy, subtraction, action-log-deep, firewall-code, subtraction-data
- r2: a-r2-{12~15} (4개) — actionlog-activation-merge, migration-sql, remember-refactor, energy-enrichment

### B세션 (14파일)
- r0: b-r0-neural-mechanisms.md, b-r0-neural-index.md
- r1: b-r1-{1~9} (9개) — bcm-vs-oja, swr-transfer, ucb-c, patch-foraging, reconsolidation, pruning, chen-sa, rwr-surprise, swing-toward
- r2: b-r2-{10~13} (4개) — reconsolidation-impl, cte-impl, bcm-ucb-integration, recall-flow

### C세션 (10파일)
- r0: c-r0-pytorch-ml.md
- r1: c-r1-{1~5} (5개) — kg-embedding, hebbian-bcm, promotion-models, rrf-experiment, roadmap
- r2: c-r2-{6~9} (4개) — goldset-design, promotion-integration, link-detector, cross-session-alignment

### D세션 (11파일)
- r0: d-r0-validation-metrics.md
- r1: d-r1-{1~6} (6개) — fatal-weaknesses, consensus, hub-ihs, small-world, temporal, pruning
- r2: d-r2-{7~10} (4개) — validators-impl, drift-detector-impl, hub-monitor-ready, activation-actionlog-merge

## 통합 보고서 목록

| # | 파일 | 내용 | 라운드 |
|---|------|------|--------|
| 1 | `0-orchestrator-round1-integration.md` | 4세션 연결/충돌/로드맵, Round 2 프롬프트 | Round 1→2 |
| 2 | `0-orchestrator-round2-integration.md` | Round 2 수렴/충돌/스키마 통합, Round 3 프롬프트 | Round 2→3 |
| 3 | (대기) `0-orchestrator-round3-final.md` | 최종 통합, 설계 진입 판단 | Round 3→설계 |

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

## 구현 로드맵 요약 (Phase 0-4, Round 2 갱신)

- **Phase 0** (1주, 10항목): action_log+VIEW, type_defs/relation_defs, validators, drift 방어, RRF k=30, meta 테이블, edges JSON 마이그레이션, 스냅샷. **9/10 코드 준비 완료**
- **Phase 1** (2-3주, 7항목): _bcm_update, CTE+UCB, 패치 전환, remember 분리, 방화벽
- **Phase 2** (4-6주, 6항목): SPRT, SWR 게이트, 시간감쇠, temporal_search_v2, deprecated 처리, 에너지 정책
- **Phase 3** (7-10주, 6항목): node/edge pruning, hub IHS, small world, swing-toward, Missing Link
- **Phase 4** (3개월+, 7항목): Bayesian/MDL, RWR, 버전관리, provenance, 아카이브, 에너지 자동화

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

## compact 후 재개 프롬프트

```
이 세션은 온톨로지 아이디에이션 오케스트레이터다.
0-orchestrator-index.md를 읽어라.
현재 Round [N] 결과를 읽고 통합해야 한다.
1단계: 0-orchestrator-index.md 읽기 (현황 파악)
2단계: 각 세션의 최신 파일을 Sonnet Explore 에이전트 4개로 병렬 읽기
3단계: 통합 보고서 작성 (0-orchestrator-roundN-integration.md)
4단계: Round [N+1] 심화 프롬프트 생성
```
