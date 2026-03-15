# Ideation R1 — Context
> 2026-03-15 | FROM: 11_research-merged

## FROM
- 11_research-merged/00_orchestrator-integration.md — 통합 결론
- 11_research-merged/01_definitive-inventory.md — 수정 대상 목록

## CONFIRMED DECISIONS
- promote_node Gate 1은 recall_log source 컬럼 부재로 영구 차단
- connects_with는 0.3% (초기 가설 87.2% 오류)
- last_activated 컬럼 존재 (초기 가설 오류)

## CARRY FORWARD
- 수정 대상: hybrid.py, recall.py, promote_node.py, config.py, validators.py
- 기준선: Signal 4개, promote 0%, fallback-probable 39.6%, tests 169 PASS
- Gate 1 fix = 3함수 수정 + ALTER TABLE (Option A minimal)

## DO NOT CARRY
- 초기 가설 (generic 87.2%, last_activated 부재, BCM rollback) — 모두 오류 판정

## OPEN QUESTIONS
- Signal 고갈 해결: Gate 1 fix만으로 충분? 배치 승격 병행?
- TYPE_KEYWORDS에 누락 타입 (Identity, Observation 등) 추가 범위

## REQUIRED INPUT FILES
- storage/hybrid.py (line 448-570) — hybrid_search RRF 합산
- tools/recall.py (line 168-189) — _log_recall_results
- tools/promote_node.py (line 25-76) — swr_readiness
- config.py — TYPE_CHANNEL_WEIGHTS, TYPE_KEYWORDS, LAYER_IMPORTANCE

## ENTRY CONDITION
- Research merged 완료 (T1 ✅)
