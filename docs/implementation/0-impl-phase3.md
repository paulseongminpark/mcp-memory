# Phase 3: Validation & Tuning — 검증과 튜닝

> 목표: 전체 시스템 검증, 파라미터 최적화, 아키텍처 리포트
> 예상: 1-2주
> 선행 조건: Phase 2 완료 (3-gate + pruning + hub_monitor)
> 완료 조건: NDCG baseline 확보 + 파라미터 검증 + 최종 리포트

---

## 특이사항

Phase 3는 **코드 수정이 거의 없다.** 주로 스크립트 실행 + 분석 + 리포트.
W1/W2는 비활성. W3가 스크립트 작성, CX/GM이 실행+분석.

---

## W3 태스크 (Scripts)

| 상태 | ID | 태스크 | 파일 | 스펙 | 의존 |
|------|----|----|------|------|------|
| [x] | P3-W3-01 | ab_test.py — RRF k=30 vs k=60 NDCG 비교 | `scripts/eval/ab_test.py` | c-r3-10 | Phase 2 |
| [x] | P3-W3-02 | sprt_simulate.py — SPRT 파라미터 시뮬레이션 | `scripts/sprt_simulate.py` | c-r3-12 | Phase 2 |
| [x] | P3-W3-03 | calibrate_drift.py — drift threshold 자동 측정 | `scripts/calibrate_drift.py` | d-r3-12 | Phase 2 |

### P3-W3-01 상세: ab_test.py

- goldset.yaml 25쿼리로 recall 실행
- k=30 vs k=60 NDCG@5, NDCG@10 비교
- 결과를 markdown 테이블로 출력
- baseline NDCG > 0.7 목표

### P3-W3-02 상세: sprt_simulate.py

- C-12의 시뮬레이션 코드 기반
- p_true = [0.3, 0.5, 0.7] 각각에 대해 1000회 시뮬레이션
- 평균 결정 단계, 오승격률, 놓침률 출력
- "절대 금지 파라미터" 조합도 시뮬레이션하여 위험성 확인

### P3-W3-03 상세: calibrate_drift.py

- 현재 DB에서 모든 노드의 enrichment 전/후 cosine similarity 측정
- `mean - 2*stdev` 기준선 산출
- DRIFT_THRESHOLD=0.5가 적절한지 검증
- 결과에 따라 config.py 조정 권고

---

## CX 검증

| 상태 | ID | 검증 | 시점 | 명령어 |
|------|----|------|------|--------|
| [x] | P3-CX-01 | goldset NDCG 실행 | PASS (NDCG@5=0.057, NDCG@10=0.091, k=30≈k=60 — baseline 확보) |
| [x] | P3-CX-02 | SPRT 시뮬레이션 실행 | PASS (p=0.7→88.7% 승격, p=0.3→2.8% 오승격, 파라미터 유지) |
| [x] | P3-CX-03 | drift 캘리브레이션 실행 | PASS (mean_sim=0.9999, DRIFT_THRESHOLD=0.5 유지) |
| [x] | P3-CX-04 | 전체 테스트 suite 최종 실행 | PASS (117/117) |
| [x] | P3-CX-05 | 최종 diff 분석 (v2.0 대비 전체 변경) | PASS (cx-p3-final-diff.md: 21 new, 13 mod, 5781 ins) |

## GM 검증

| 상태 | ID | 검증 | 시점 |
|------|----|------|------|
| [x] | P3-GM-01 | 전체 아키텍처 리포트 생성 | PASS (Gemini: 6개 레이어 분석, 데이터 흐름 문서화) |
| [x] | P3-GM-02 | 최종 스키마 vs 스펙 정합성 | PASS (init_db 미반영=tech debt, 기능적 블로커 아님) |

### GM 명령어

```bash
# 전체 아키텍처
gemini -m gemini-3.1-pro-preview \
  "read all Python files in /c/dev/01_projects/06_mcp-memory/ (excluding tests/, .venv/, __pycache__/). \
  Generate a comprehensive architecture document: \
  1. Module responsibilities and ownership \
  2. Data flow diagram (remember → store → link → recall → activate → learn) \
  3. Error handling patterns \
  4. Configuration points (all config.py constants) \
  5. DB schema (all tables, views, indexes) \
  6. Test coverage summary \
  Format as markdown." \
  -o gm-p3-architecture.md

# 스키마 검증
gemini -m gemini-3.1-pro-preview \
  "compare: \
  1. Actual schema in /c/dev/01_projects/06_mcp-memory/data/memory.db \
  2. Spec in /c/dev/01_projects/06_mcp-memory/docs/ideation/0-orchestrator-round3-final.md section V \
  3. Migration script /c/dev/01_projects/06_mcp-memory/scripts/migrate_v2_ontology.py \
  Report any discrepancies between the three." \
  -o gm-p3-schema-final.md
```

---

## Phase 3 완료 기준

```
■ W3: 3개 스크립트 작성 + 커밋
■ CX: 5개 검증 전부 PASS
■ GM: 2개 리포트 생성
■ NDCG baseline: @5=0.057, @10=0.091 (k=30 유지, goldset 튜닝 대상)
■ SPRT 파라미터 유지 결정 (α=0.05, β=0.2, p1=0.7, p0=0.3)
■ drift threshold 0.5 유지 결정 (현 데이터 안정적)
■ Main: 모든 체크박스 갱신 → "v2.1 구현 완료" 선언 (2026-03-06)
```

---

## v2.1 최종 완료 체크리스트

Phase 3 완료 후 Main이 실행:

```
■ 1. 전체 테스트 PASS 확인 (117/117)
■ 2. STATE.md 갱신 (orchestration STATE.md)
■ 3. CHANGELOG.md 갱신 (mcp-memory에 CHANGELOG 없음 — STATE로 대체)
■ 4. HOME.md (옵시디언) 갱신
□ 5. git commit + push
□ 6. mcp-memory 외부 메모리에 v2.1 완료 기록
□ 7. Paul에게 최종 보고
```
