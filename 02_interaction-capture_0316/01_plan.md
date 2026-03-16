# Plan — Interaction Capture

## 작업 목표
사용자 인터랙션의 다각 캡처 시스템. 현재 2.9% 수집률을 구조적으로 개선.

## 손실불가 기준
- 기존 auto_remember, checkpoint, session-end 경로 파손 금지
- mcp-memory 토큰 예산 초과 금지
- 노이즈 증가 없이 Signal 대비 Observation 비율 유지

## 대상 파일/범위
- `.ctx/auto_remember.py` — 파일 변경 감지 hook
- `skills/checkpoint/` — 수동 checkpoint 스킬
- `skills/session-end/` 또는 compressor — 세션 종료 수집
- `mcp-memory/src/` — remember(), save_session() 서버 코드
- `CLAUDE.md`, `.claude/rules/` — 행동 규칙

## Phase 분할
| Phase | 목표 | 라운드 |
|---|---|---|
| Research | 현재 수집 경로 코드 분석 + 갭 정량화 | R1 |
| Ideation | 캡처 메커니즘 설계 (후보 A~D 평가) | R1~R2 |
| Implementation | 선택된 메커니즘 구현 | R1 |
| Review | 통합 테스트 + 효과 측정 | R1 |

## Pane 분할
- 단일 pane (이 세션에서 직접 수행)
