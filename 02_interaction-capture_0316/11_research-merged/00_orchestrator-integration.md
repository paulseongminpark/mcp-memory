# Research Integration — Interaction Capture

## 핵심 발견

### 1. 근본 제약
Hook은 대화 내용에 접근 불가 (보안 경계). auto_remember 확장은 구조적으로 불가능.

### 2. 현재 수집 경로 3개
| 경로 | 자동화 | 대화 접근 | 한계 |
|---|---|---|---|
| auto_remember | 완전 자동 | ❌ | 11개 파일 + 9개 bash 신호만 |
| /checkpoint | 수동 | Claude 판단 | 까먹으면 0건 |
| /session-end | 반자동 | 1줄 | 세션 끝에만, 중간 유실 |

### 3. 치명적 갭
사고방식, 선호/반응, 감정 신호, 결정 스타일, 언어 패턴, 작업 리듬 — 모두 미포착 또는 수동 의존.

### 4. 유일한 해결 경로
**Claude 자율 remember() 호출** (후보 B). Claude만이 대화 전체를 보면서 MCP를 호출할 수 있음.

## Ideation 입력
- 후보 A(hook 확장) 탈락 확정
- 후보 B(Claude 자율) 중심 설계
- 후보 C(주기적 checkpoint) + D(Learn 강화)는 보조
- 토큰 예산, 노이즈 필터링, 기존 경로 통합이 핵심 과제
