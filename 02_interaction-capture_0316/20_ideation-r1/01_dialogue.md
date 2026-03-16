# Ideation R1 — PDR Skill Design Dialogue

## 확정 사항 (Research → Ideation 입력)

- Hook 경로(후보 A) 탈락 — 대화 접근 구조적 불가
- Claude 자율 remember()(후보 B) 중심
- 온톨로지 수정 불필요 — Observation(L0) + tags + source:"pdr"
- 승격: 기존 Observation → Signal → Pattern 경로
- 세션당 20~25개 관찰, 8차원 전수 스캔

## PDR Skill Spec (v0.1)

### 이름
`/pdr` — Pipeline DONE Retrospective

### 트리거 시점

| 시점 | 방식 | 범위 |
|---|---|---|
| **compact 직전** | /checkpoint 또는 /pdr 수동 호출 | 현재 세션 (compact 이전 대화 전체) |
| **Pipeline DONE gate** | G6 하드 블록 (자동 강제) | 마지막 세션 + 이전 PDR recall 통합 |

### 8차원 스캔 템플릿

Claude는 대화 전체를 처음부터 끝까지 역순회하며, 각 차원에서 관찰을 추출한다.

```
1. 사고 방식 (thinking-style)
   "Paul이 문제에 접근하는 방식, 분해 전략, 추상화 수준"
   → 최소 2개

2. 선호/반응 (preference)
   "제안에 대한 즉각 반응, 수용/거부 패턴, 도구 선호"
   → 최소 2개

3. 감정 신호 (emotional)
   "에너지 변화, 흥분/좌절, 주제별 몰입도"
   → 최소 1개

4. 결정 스타일 (decision-style)
   "선택지 평가 방식, 결합형/제거형, 속도"
   → 최소 2개

5. 언어 패턴 (language)
   "특정 표현의 의미, 축약어, 톤 변화"
   → 최소 1개

6. 작업 리듬 (work-rhythm)
   "세션 페이싱, 방향 전환 빈도, 집중 구간"
   → 최소 1개

7. 메타인지 (metacognition)
   "자기 한계 인식, 시스템으로 보완하는 전략"
   → 최소 2개

8. 관계/연결 (connection)
   "논의 중 발견한 교차점, 영역 간 링크"
   → 최소 2개
```

**최소 합계: 13 / 목표: 20~25**
차원당 최소 이하면 "해당 없음 — [이유]" 명시 필수.

### remember() 호출 형식

```python
remember(
    content="[PDR] {관찰 내용}",
    type="Observation",
    tags="pdr, {dimension-tag}, {추가 키워드}",
    project="{현재 프로젝트}",
    source="pdr",
    confidence=0.70
)
```

### 중복 방지 로직

각 관찰 저장 전:
1. `recall(content, top_k=3)` 실행
2. 유사도 높은 기존 노드 발견 시:
   - 동일 → 스킵 (저장 안 함)
   - 유사하지만 새 관점 → 저장 + edge 연결
   - 기존 Observation에 반복 확인 → Signal 승격 제안

### Pipeline DONE gate 통합

```
기존 DONE gate:
  G1: review-merged 존재
  G2: 90_output/ 존재
  G3: 00_final-output.md 존재
  G4: 01_handoff.md 존재
  G5: 00_pending/ 미완료 0

추가:
  G6: PDR 완료 (source:"pdr" 노드 ≥13개, 8차원 전수 스캔 증빙)
```

### 산출물

PDR 실행 후 생성:
```
90_output/02_pdr-report.md
  - 차원별 관찰 목록
  - 저장된 노드 ID 목록
  - 스킵된 중복 목록
  - 승격 제안 목록
```

### 기존 경로와의 역할 분리

```
auto_remember   → 도구 이벤트 자동 감지 (파일/bash)
/checkpoint     → 중간 세이브 (수동, Layer A+B)
/session-end    → 세션 경계 아카이브 (5단계)
/pdr            → 전체 대화 다각 회고 (8차원, 20-25개)
```

겹치지 않는다:
- auto_remember는 도구만 봄 → PDR은 대화를 봄
- checkpoint는 부분 스캔 → PDR은 전수 스캔
- session-end는 요약 → PDR은 원시 관찰 추출

### 토큰 비용 추정

```
recall() × 20~25회 = ~5,000 tokens (중복 체크)
remember() × 15~20회 = ~6,000 tokens (실제 저장, 중복 제외)
스캔 사고 비용 = ~3,000 tokens (8차원 순회)
────────────────────────────────
총 ~14,000 tokens/회
```

compact 직전 (500K~700K 시점)이므로 예산 충분.

### Compliance 보장

Claude가 스킵하지 못하게:
1. **rigid 스킬** — 단계 건너뛰기 금지
2. **체크리스트 기반** — 8차원 각각 명시적 보고 필수
3. **G6 하드 블록** — PDR 없이 DONE 불가
4. **산출물 필수** — 02_pdr-report.md 없으면 DONE gate 실패

## Open Questions

1. compact 직전 PDR vs Pipeline DONE PDR — 동일 스킬? 별도 모드?
2. PDR이 /checkpoint Layer B를 대체하는가, 공존하는가?
3. 멀티 세션 파이프라인에서 이전 PDR 노드를 어떻게 통합하는가?
