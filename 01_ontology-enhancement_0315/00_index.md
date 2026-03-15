<!-- pipeline: ontology-enhancement | type: custom | mode: standard | status: DONE -->
<!-- phase: output | updated: 2026-03-16T01:00 -->
<!-- current_task: DONE | next: — -->

# Ontology Enhancement
> 시작: 2026-03-15 | 타입: custom (research → ideation → impl → review)

## 목표
mcp-memory 온톨로지 품질 강화. promote_node Gate 1 fix + deprecated 정리.

## Phase 상태
| Phase | 폴더 | 상태 |
|---|---|---|
| Research | 10_research-r1/, 11_research-merged/ | ✅ |
| Ideation | 20_ideation-r1/, 21_ideation-merged/ | ✅ |
| Implementation | 30_impl-r1/, 31_impl-merged/ | ✅ |
| Review | 40_review-r1/, 41_review-merged/ | ✅ |
| Output | 90_output/ | ✅ |

## Current
- Ideation R1 완료: Gate 1 fix 설계 + Signal 배치 승격 + deprecated 정리 범위 확정

## Decisions
- 2026-03-15: custom 타입 (research → ideation → impl → review), 정식 모드
- 2026-03-15: 초기 가설 교정 — generic 87.2% 오류(실제 0.3%), last_activated 존재, BCM 정상
- 2026-03-15: Gate 1 fix = Option A (minimal source 태깅, 3함수 + ALTER TABLE)
- 2026-03-16: 방향 = "자기 성장 루프 관통 + 관계 품질 강화" (버그 수리 아님, 시스템 완성)
- 2026-03-16: Gate 2 = Bayesian 제거 → visit_count >= 10 직접 threshold
- 2026-03-16: RELATION_RULES 17→40+ 확장 + cross-project 로직 추가
- 2026-03-16: 구현 6항목: deprecated정리 → Gate2→Gate1→source인프라→RULES확장→cross-project
