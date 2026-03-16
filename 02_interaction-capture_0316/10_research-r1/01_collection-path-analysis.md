# Collection Path Analysis — 현재 수집 경로 코드 분석

## 1. 수집 경로 요약

| 경로 | 트리거 | 자동화 | 대화 접근 | 세션당 노드 |
|---|---|---|---|---|
| auto_remember.py | PostToolUse (Write/Edit/Bash) | 완전 자동 | **불가** | 10~50 |
| /checkpoint | 사용자 수동 호출 | 수동 | Claude 판단 | 0~10 |
| /session-end Learn | 세션 종료 | 반자동 | 1줄 요약 | 1 |

**현재 Observation 108/3,696 (2.9%)** — 세션당 평균 2개 수준.

---

## 2. auto_remember.py — 파일/Bash 변경 감지

### 위치
`/c/Users/pauls/.claude/hooks/auto_remember.py` (176줄)

### 동작
- PostToolUse hook → Write/Edit/Bash 이벤트만 처리
- stdin JSON: `{tool_name, tool_input, tool_result}`

### FILE_TYPE_MAP (11개 파일만)
| 파일 | 타입 | 레이어 | confidence |
|---|---|---|---|
| STATE.md | Decision | 1 | 0.70 |
| decisions.md | Decision | 1 | 0.70 |
| CHANGELOG.md | Decision | 1 | 0.70 |
| PLANNING.md | Decision | 1 | 0.70 |
| CLAUDE.md | Principle | 3 | 0.85 |
| GEMINI.md | Framework | 2 | 0.75 |
| AGENTS.md | Framework | 2 | 0.75 |
| KNOWLEDGE.md | Pattern | 2 | 0.75 |
| REFERENCE.md | Framework | 2 | 0.75 |
| schema.yaml | Framework | 2 | 0.75 |
| config.py | Tool | 1 | 0.70 |

### BASH_SIGNAL_MAP (9개 신호)
| 신호 | 타입 | 비고 |
|---|---|---|
| FAIL, ERROR, error:, ❌, 실패 | Failure | 우선 감지 (break) |
| PASS, ✅, NDCG, hit_rate | Experiment | |
| 테스트, 완료 (trigger only) | Observation | fallback |

### 포착하는 것
- 11개 핵심 파일의 생성/수정 (미리보기 120자)
- Bash 성공/실패 신호 (출력 200자)

### 포착하지 못하는 것
- **대화 내용** — stdin에 conversation 데이터 없음
- **사용자 선호/반응** — 메타데이터 무시
- **감정 신호** — 텍스트 분석 없음
- **사고 방식** — 도구 입력만 처리
- **비매핑 파일** — 11개 외 모든 파일 무시

### 토큰 비용
- Write/Edit: ~60 tokens/call
- Bash: ~100 tokens/call
- 세션당: 600~5,000 tokens

---

## 3. /checkpoint — 수동 관찰 포착

### 구조
- **Layer A**: 작업 결과 (Decision, Failure, Preference 등)
- **Layer B**: Paul 관찰 (Observation → Signal → Pattern 승격 경로)

### Layer B 타입 결정 로직
```
recall(candidate_content, top_k=3)
  ├─ 유사 노드 없음 → Observation (L0)
  ├─ Signal 노드 발견 → [Pattern 승격 제안]
  └─ Pattern 이미 존재 → 중복 스킵
```

### 포착하는 것
- Claude의 메타 관찰 (사고 패턴, 행동 양식)
- 세션 내 결정/실패/인사이트
- 승격 경로를 통한 패턴 누적

### 포착하지 못하는 것
- **수동 의존** — 사용자가 호출하지 않으면 0건
- **Pre-session 패턴** — compact 이전 관찰 유실
- **무의식적 행동** — 명시적으로 명명되지 않은 패턴
- **교차 세션 연속성** — 세션 M의 Signal = 세션 N의 Signal?

### 빈도
- 세션당 3~10회 (사용자 기억력 의존)
- 실제: 까먹으면 0회

---

## 4. /session-end (compressor + Learn)

### 5단계
1. LOG → session-summary.md, daily log
2. Living Docs → STATE.md, CHANGELOG.md
3. Commit → git add/commit/push
4. save_session() → Narrative + Decision + Question 노드 + 명시적 edge
4.5. Lens → 읽기 전략 Pattern 노드
5. Learn → 4차원 (Discovery, Lesson, Improvement, Paul 관찰) → 1 Insight 노드

### save_session() 데이터 구조
```python
save_session(
    summary="1-2줄",           # → Narrative 노드
    decisions=["결정1", ...],  # → Decision 노드 × N (edge strength 0.9)
    unresolved=["미결1", ...], # → Question 노드 × M (edge strength 0.8)
    project="프로젝트명",
    active_pipeline="상대경로"  # → /restore 복구 포인트
)
```

### 포착하는 것
- 세션 요약 (Narrative)
- 명시적 결정 목록
- 미해결 질문 목록
- 읽기 전략 메타데이터 (Lens)
- 1줄 학습 (Learn)

### 포착하지 못하는 것
- **중간 관찰** — 세션 끝에만 실행
- **결정 근거** — 왜(why)가 아닌 무엇(what)만
- **시간 패턴** — 작업 순서, 페이싱
- **다중 프로젝트** — 단일 project만

---

## 5. Claude Code Hook 시스템 — 근본 제약

### 핵심 발견
**Hook은 대화 내용에 접근할 수 없다.**

| 접근 가능 | 접근 불가 |
|---|---|
| tool_name, tool_input | 사용자 메시지 |
| tool_result (PostToolUse) | Claude 응답/추론 |
| 파일 내용 (도구 통해) | 대화 히스토리 |
| Bash 출력 | 세션 메타데이터 |
| 디스크 파일 (직접 읽기) | 컨텍스트 윈도우 |

### Hook 이벤트 타입
| 이벤트 | stdin | 대화 접근 |
|---|---|---|
| SessionStart | 없음 | ❌ |
| PreToolUse | tool_name + tool_input | ❌ |
| PostToolUse | tool_name + tool_input + tool_result | ❌ |
| PreCompact | 없음 | ❌ |
| Notification | 없음 | ❌ |

**결론: 어떤 hook 이벤트도 대화 내용을 제공하지 않는다.**
이것은 보안/프라이버시 경계로 의도적 설계.

---

## 6. 갭 매트릭스

| 포착 차원 | auto_remember | /checkpoint | /session-end | 현재 상태 |
|---|---|---|---|---|
| 파일 변경 | ✅ (11개만) | — | — | 부분 |
| Bash 신호 | ✅ (9개 패턴) | — | — | 부분 |
| 결정 사항 | — | ✅ | ✅ | 양호 |
| 실패/에러 | ✅ | ✅ | ✅ | 양호 |
| **사고 방식** | ❌ | ⚠️ 수동 | ⚠️ 1줄 | **치명적 갭** |
| **선호/반응** | ❌ | ⚠️ 수동 | ❌ | **치명적 갭** |
| **감정 신호** | ❌ | ⚠️ 수동 | ❌ | **치명적 갭** |
| **결정 스타일** | ❌ | ⚠️ 수동 | ❌ | **치명적 갭** |
| **언어 패턴** | ❌ | ❌ | ❌ | **완전 부재** |
| **작업 리듬** | ❌ | ❌ | ❌ | **완전 부재** |
| 결정 근거 | ❌ | ⚠️ | ⚠️ | 약함 |
| 교차 세션 연속 | ❌ | ❌ | ⚠️ | 약함 |

### 갭 근본 원인
1. **Hook 한계**: 대화 내용 접근 불가 → auto_remember로 해결 불가
2. **수동 의존**: /checkpoint는 인간 기억력에 의존 → 세션 70%에서 0회
3. **시점 집중**: /session-end는 끝에만 → 중간 관찰은 attention decay로 유실
4. **단일 채널**: 각 경로가 독립 → 교차 검증 없음

---

## 7. 해결 후보 재평가

| 후보 | 실현 가능성 | 이유 |
|---|---|---|
| A. auto_remember 확장 | **❌ 불가** | Hook이 대화 접근 불가. 근본 한계. |
| B. Claude 자율 remember() | **✅ 가장 유망** | Claude는 대화 전체를 봄. MCP 호출 가능. |
| C. 주기적 자동 checkpoint | **⚠️ 보조** | 빈도/토큰 조절 어려움. 하지만 B와 결합 가능. |
| D. session-end Learn 강화 | **⚠️ 보조** | 세션 끝에만. 중간 유실 동일. 하지만 강화 가치 있음. |

### 후보 B 상세
- **원리**: CLAUDE.md 규칙으로 "관찰 시 즉시 remember() 호출" 지시
- **장점**: Claude는 대화 전체 + 도구 결과 + 컨텍스트를 모두 봄
- **단점**: 토큰 비용 (remember() MCP 호출마다 ~200-500 tokens)
- **핵심 과제**: 언제/무엇을 저장할지 판단 기준 (노이즈 vs 신호)

---

## 8. 다음 단계 (Ideation R1 입력)

### 확정된 사실
1. Hook 경로(A)는 대화 캡처에 구조적으로 부적합
2. Claude 자율 호출(B)이 유일한 대화 접근 경로
3. 기존 3경로는 "도구 이벤트"와 "세션 경계"만 커버
4. "대화 중 실시간 관찰" 공백이 핵심 갭

### Ideation에서 탐색할 질문
1. Claude 자율 remember()의 트리거 조건은? (매 턴? 감지 시? 주기적?)
2. 저장할 차원별 우선순위는? (사고방식 > 선호 > 감정?)
3. 토큰 예산 내에서 최적 빈도는? (세션당 10회? 20회? 30회?)
4. 노이즈 필터링 메커니즘은? (중복 검출, 최소 임계치)
5. 기존 3경로와의 통합 설계는? (역할 분리 vs 교차 검증)
6. Observation → Signal 승격을 자동화할 수 있는가?
