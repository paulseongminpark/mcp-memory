# Implementation R1 — Context
> 2026-03-16 | FROM: 21_ideation-merged

## FROM
- 21_ideation-merged/00_orchestrator-final.md
- 21_ideation-merged/01_confirmed-decisions.md

## CONFIRMED DECISIONS
- D1: 시스템 완성 방향 (자기 성장 루프 + 관계 품질)
- D2: Gate 2 = visit_count >= 10
- D3: Gate 1 threshold 0.55→0.25 + source 인프라
- D4: nodes.frequency deprecated (visit_count 대체)
- D5: RELATION_RULES 17→40+
- D6: 구현 순서 확정

## CARRY FORWARD
- 기준선: promote 1건, Signal 4개, RULES 17개, tests 169
- 수정 대상: config.py, validators.py, promote_node.py, hybrid.py, recall.py

## DO NOT CARRY
- 초기 가설 오류 (generic 87.2%, last_activated 부재 등)
- 배치 승격 (Gate 해제 후 자연 승격 우선 관찰)

## OPEN QUESTIONS
- RELATION_RULES 최종 목록 (40+ 구체화)
- DB migration 방식 (ALTER TABLE vs init_db 수정)

## REQUIRED INPUT FILES
- config.py (RELATION_RULES, TYPE_CHANNEL_WEIGHTS, TYPE_KEYWORDS, LAYER_IMPORTANCE, infer_relation)
- ontology/validators.py (suggest_closest_type)
- tools/promote_node.py (swr_readiness, promotion_probability)
- storage/hybrid.py (hybrid_search line 516-529)
- tools/recall.py (_log_recall_results)

## ENTRY CONDITION
- Ideation merged 완료 ✅
- foundation/ 3축 ✅
