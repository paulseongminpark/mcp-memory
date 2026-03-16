<!-- pipeline: interaction-capture | type: custom | mode: standard | status: DONE -->
<!-- phase: output | updated: 2026-03-16T20:40 -->
<!-- current_task: DONE | next: — -->

# Interaction Capture
> 시작: 2026-03-16 | 타입: custom (research → ideation → impl → review)

## 목표
Claude가 사용자와의 모든 세션에서 인터랙션을 다각도로 포착하여 mcp-memory에 자동 저장하는 메커니즘 설계 + 구현.

## 핵심 문제
- Observation 108/3,696 (2.9%) — 세션당 평균 2개 수준
- 수집이 세션 끝에만 발생 (/checkpoint 수동, /session-end Learn)
- 대화 중 실시간 관찰은 attention decay로 유실
- auto_remember.py는 파일 변경만 감지 → 대화 내용 못 잡음

## 포착 차원
- 사고 방식, 선호/반응, 감정 신호, 결정 스타일, 언어 패턴, 작업 리듬, 메타인지, 관계/연결

## Phase 상태
| Phase | 폴더 | 상태 |
|---|---|---|
| Research | 10_research-r1/, 11_research-merged/ | ✅ |
| Ideation | 20_ideation-r1/, 21_ideation-merged/ | ✅ |
| Implementation | 30_impl-r1/, 31_impl-merged/ | ✅ |
| Review | 40_review-r1/, 41_review-merged/ | ✅ |
| Output | 90_output/ | ✅ |

## Current
- DONE. PDR 첫 실행 완료 (23건 저장, 8/8 차원).

## Decisions
- D1: Hook 확장(후보 A) 탈락 — 대화 접근 구조적 불가
- D2: Claude 자율 remember()(후보 B) 중심 설계 확정
- D3: 주기적 checkpoint(C) + Learn 강화(D) 보조 역할
- D4: 온톨로지 수정 불필요 — Observation(L0) + tags
- D5: 8차원, 20~25개, rigid 스킬
- D6: compact 직전 + DONE gate(G6) 하드 블록
