# Phase 2: Advanced Features — 고급 기능

> 목표: 통계 기반 승격 (3-gate), 자동 가지치기, 허브 모니터링
> 예상: 4-6주
> 선행 조건: Phase 1 완료 (핵심 5파일 교체 + 테스트 PASS)
> 완료 조건: CX 통합 테스트 PASS + GM 리뷰

---

## 의존성 그래프

```
Phase 1 완료
    │
    ├─── W1 ──────┐      ├─── W2 ──────────┐      ├─── W3 ─────────────┐
    ▼              │      ▼                  │      ▼                    │
P2-W1-01           │  P2-W2-01              │  P2-W3-01                │
(hybrid +sprt)     │  (promote 3-gate)      │  (hub_monitor)           │
    │              │      │                  │      │                    │
    └──→ P2-W2-01  │      ▼                  │      ▼                    │
      블록 해제    │  P2-W2-02              │  P2-W3-02                │
                   │  (analyze_signals)     │  (pruning +check_access) │
                   │                        │      │                    │
                   │                        │      ▼                    │
                   │                        │  P2-W3-03                │
                   │                        │  (daily_enrich Phase 6)  │
                   │                        │                          │
                   └────────────────────────┴──────────────────────────┘
                                    │
                              CX: 통합 테스트 → GM: Phase 2 리뷰
```

**W1과 W3 즉시 시작 가능. W2는 P2-W1-01(hybrid +sprt) 완료 후 시작.**

---

## W1 태스크 (Storage)

| 상태 | ID | 태스크 | 파일 | 스펙 | 의존 |
|------|----|----|------|------|------|
| [x] | P2-W1-01 | hybrid.py +_sprt_check() + promotion_candidate 갱신 | `storage/hybrid.py` | c-r3-11 | Phase 1 |

### P2-W1-01 상세

- `_sprt_check(node_id, score_history)`: SPRT 누적 LLR 계산
- `promotion_candidate` 플래그 갱신 (0/1)
- 매 recall 시 결과 노드에 대해 실행 (score > 0.5 → +LLR, else → -LLR)
- 승격 임계 A = 2.773, 기각 임계 B = -1.558
- config.py의 SPRT_* 상수 사용

---

## W2 태스크 (Tools)

| 상태 | ID | 태스크 | 파일 | 스펙 | 의존 |
|------|----|----|------|------|------|
| [x] | P2-W2-01 | promote_node.py 전체 교체 — SWR→Bayesian→MDL 3-gate | `tools/promote_node.py` | c-r3-11 | **P2-W1-01** |
| [x] | P2-W2-02 | analyze_signals.py +_recommend_v2() + _bayesian_cluster_score() | `tools/analyze_signals.py` | c-r3-11 | P2-W2-01 |

### P2-W2-01 상세: promote_node.py 3-gate

**Gate 1 — SWR Readiness:**
- recall_log에서 vec/fts 비율 + 이웃 프로젝트 다양성
- `readiness = 0.6 * vec_ratio + 0.4 * cross_ratio > 0.55`

**Gate 2 — Bayesian P(real pattern):**
- Prior: Beta(1, 10), Posterior: `(1+k) / (11+n)`
- P < 0.5 → `insufficient_evidence` 반환

**Gate 3 — MDL:**
- related_nodes 임베딩 cosine sim 평균 > 0.75
- 2개 미만 또는 임베딩 없으면 통과 (보수적)

`skip_gates=True` 관리자 옵션 보존 (Paul 직접 승격용).

### P2-W2-02 상세: analyze_signals.py

- `_recommend_v2()`: SPRT promotion_candidate 플래그 소비
- `_bayesian_cluster_score()`: 클러스터별 Bayesian 신뢰도
- 결과 구조에 bayesian_p, sprt_flagged 추가

---

## W3 태스크 (Utils + Scripts)

| 상태 | ID | 태스크 | 파일 | 스펙 | 의존 |
|------|----|----|------|------|------|
| [x] | P2-W3-01 | hub_monitor.py +recommend_hub_action() + print_hub_actions() | `scripts/hub_monitor.py` | d-r3-13 | Phase 1 |
| [x] | P2-W3-02 | pruning.py +check_access 통합 | `scripts/pruning.py` | d-r3-13, d-r3-14 | Phase 1 |
| [x] | P2-W3-03 | daily_enrich.py +Phase 6 (edge→node pruning) | `scripts/daily_enrich.py` | d-r3-14 | P2-W3-01, P2-W3-02 |

### P2-W3-03 상세: daily_enrich Phase 6

실행 순서:
1. Phase 6-A: Edge pruning — `strength = freq × exp(-0.005 × days)` < 0.05 → 후보
   - Bäuml ctx_log 다양성 >= 2 → keep
   - source tier=0 or layer>=2 → archive (복구 가능)
   - 그 외 → delete
2. Phase 6-B: Node Stage 2 — BSP 후보 식별 (L0/L1만)
   - quality_score < 0.3 AND observation_count < 2 AND last_activated < -90일 AND edge_count < 3
   - check_access()로 L4/L5 + Top-10 hub 보호
3. Phase 6-C: Node Stage 3 — 30일 경과 → archived
4. Phase 6-D: action_log 기록

`--dry-run` 지원 필수.

---

## CX 검증

| 상태 | ID | 검증 | 시점 |
|------|----|------|------|
| [x] | P2-CX-01 | SPRT 판정 테스트 (mock score_history) | PASS (cx-p2-sprt.md) |
| [x] | P2-CX-02 | 3-gate 직렬 통과 테스트 | PASS (cx-p2-promote.md) |
| [x] | P2-CX-03 | pruning dry-run 실행 + 결과 검토 | PASS (Phase 6 정상: keep=57 archive=1882 delete=4388) |
| [x] | P2-CX-04 | 전체 테스트 suite (Phase 0+1+2) | PASS (cx-p2-full.md) |

## GM 검증

| 상태 | ID | 검증 | 시점 |
|------|----|------|------|
| [x] | P2-GM-01 | Phase 2 전체 리뷰 (승격 로직, 가지치기 안전성) | PASS (Gemini: 6/6 파일 전부 PASS, 운영 적용 가능) |

---

## Phase 2 완료 기준

```
■ W1: 1개 태스크 완료 + 커밋
■ W2: 2개 태스크 완료 + 커밋
■ W3: 3개 태스크 완료 + 커밋 (archived_at 수정 포함)
■ CX: 4개 검증 전부 PASS
■ GM: Phase 2 리뷰 통과 (Gemini 6/6 PASS)
■ Main: 모든 체크박스 갱신 → "Phase 2 완료" 선언 (2026-03-06)
```
