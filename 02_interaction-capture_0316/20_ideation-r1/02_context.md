# Ideation — Context
> 2026-03-16 | FROM: 11_research-merged/

## FROM
11_research-merged/00_orchestrator-integration.md + 01_definitive-inventory.md

## CONFIRMED DECISIONS
- 후보 A(hook 확장) 탈락 — Hook은 대화 접근 불가
- 후보 B(Claude 자율 remember()) 중심 설계 확정
- 후보 C(주기적 checkpoint), D(Learn 강화)는 보조 역할

## CARRY FORWARD
- 갭 매트릭스 6개 치명적 차원
- 기존 3경로의 정확한 역할과 비용
- 온톨로지 타입 체계 (Observation → Signal → Pattern)

## DO NOT CARRY
- Hook 시스템 상세 코드 (결론만: 대화 접근 불가)
- auto_remember FILE_TYPE_MAP/BASH_SIGNAL_MAP 상세

## OPEN QUESTIONS
- Claude가 자율적으로 remember()를 호출하게 만드는 최적 메커니즘은?
- 토큰 예산 제약 하에서 최적 빈도는?
- 저장 품질을 보장하는 필터링 로직은?

## REQUIRED INPUT FILES
- 없음 (Research merged가 충분)

## ENTRY CONDITION
- Research merged 완료 ✅
