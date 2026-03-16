# Definitive Inventory — 수집 경로 + Hook 역량

## 수집 경로 인벤토리

### auto_remember.py
- 위치: ~/.claude/hooks/auto_remember.py (176줄)
- 트리거: PostToolUse (Write/Edit/Bash)
- FILE_TYPE_MAP: 11개 파일 → Decision/Principle/Framework/Pattern/Tool
- BASH_SIGNAL_MAP: 9개 신호 → Failure/Experiment/Observation
- 비용: 60-100 tokens/call, 세션당 600-5000 tokens
- source: "hook:PostToolUse"

### /checkpoint skill
- Layer A: 작업 결과 (Decision, Failure, Preference)
- Layer B: Paul 관찰 (Observation → Signal → Pattern 승격)
- 빈도: 세션당 0-10회 (수동 의존)
- 중복 감지: recall() top_k=3, similarity < 0.2 → 스킵

### /session-end compressor
- 모델: Sonnet
- 5단계: LOG → Living Docs → Commit → save_session → Learn
- Step 4.5: Lens 축적 (읽기 전략 Pattern)
- Step 5 Learn: 4차원 → 1 Insight 노드
- save_session(): Narrative + Decision×N + Question×M 노드 + 명시적 edge

## Hook 시스템 역량
- 이벤트: SessionStart, PreToolUse, PostToolUse, PreCompact, Notification
- stdin: tool_name + tool_input + tool_result (PostToolUse만)
- **대화 접근: 모든 이벤트에서 불가** (의도적 보안 경계)

## 갭 매트릭스
| 차원 | auto_remember | checkpoint | session-end | 상태 |
|---|---|---|---|---|
| 사고 방식 | ❌ | ⚠️ 수동 | ⚠️ 1줄 | 치명적 |
| 선호/반응 | ❌ | ⚠️ 수동 | ❌ | 치명적 |
| 감정 신호 | ❌ | ⚠️ 수동 | ❌ | 치명적 |
| 결정 스타일 | ❌ | ⚠️ 수동 | ❌ | 치명적 |
| 언어 패턴 | ❌ | ❌ | ❌ | 부재 |
| 작업 리듬 | ❌ | ❌ | ❌ | 부재 |
