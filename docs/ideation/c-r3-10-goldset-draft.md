# 세션 C — R3-10: 골드셋 초안 (25개 쿼리)

> 2026-03-05 | R3 심화 | tier=0 노드 기반 | Paul 검토/수정 대상

## 사용 방법

- `scripts/eval/goldset.yaml` 로 저장 후 `python scripts/eval/ab_test.py` 실행
- `relevant_ids`: 반드시 포함되어야 할 정답 (NDCG 가중치 1.0)
- `also_relevant`: 부분 정답 (가중치 0.5)
- `# VERIFY` 주석: Paul이 실제 DB에서 확인 후 ID 교체 필요

---

## 노드 ID 레퍼런스 (C-6 DB 조회 확정분)

| ID | 타입 | qs | 핵심 내용 |
|---|---|---|---|
| 43 | Principle | 0.95 | 단일 진실 소스: STATE.md |
| 181 | Principle | 0.92 | Context = Currency |
| 377 | Principle | 0.95 | 토큰은 화폐다, 200K 윈도우 |
| 378 | Principle | 0.92 | 세 가지 원칙: Baseline최소화/오프로딩/계층위임 |
| 404 | Principle | 0.92 | 빼기가 더하기보다 어렵다 |
| 405 | Principle | 0.92 | AI는 도구가 아니라 팀원이다 |
| 406 | Principle | 0.92 | 7일이면 충분하다 |
| 755 | Principle | 0.92 | 단일 진실 소스 — Obsidian vs Claude 충돌 방지 |
| 756 | Principle | 0.92 | 쓰기 권한 분리 — 여러 AI 동시 수정 금지 |
| 771 | Principle | 0.92 | SoT: 각 정보는 정확히 1곳에만 존재 |
| 4161 | Belief | 0.92 | 모든 현상을 다차원으로 해석하는 것이 사고의 본질 |
| 4163 | Value | 0.95 | 뇌의 다차원적 연결 외부화 욕구 |
| 4165 | Philosophy | 0.92 | 의지 대신 환경과 규칙을 설계하라 |
| 4166 | Value | 0.92 | 이색적 접합: 서로 다른 도메인 연결로 새로운 의미 |

---

## goldset.yaml 전체

```yaml
# scripts/eval/goldset.yaml
# 형식: query → 정답 node_id 목록
# 난이도: easy(단일 정답) / medium(복수 정답) / hard(추상적 질문)

version: "1.0"
created: "2026-03-05"
total_queries: 25
author: "C-session-draft"

queries:

  # ============================================================
  # TIER 1 — 단일 정답 (q001-q010): 명확한 키워드 매칭 가능
  # ============================================================

  - id: "q001"
    difficulty: easy
    query: "뇌의 다차원 연결을 외부화하고 싶다"
    relevant_ids: [4163]
    also_relevant: [4161, 4166]
    notes: "Paul의 근본 동기 Value 노드 — 가장 핵심적인 tier=0"

  - id: "q002"
    difficulty: easy
    query: "이색적 접합으로 새로운 의미 만들기"
    relevant_ids: [4166]
    also_relevant: [4163, 4161]
    notes: "창의성 접근법 Value 노드"

  - id: "q003"
    difficulty: easy
    query: "의지에 의존하지 않고 환경을 설계하라"
    relevant_ids: [4165]
    also_relevant: [4163, 406]
    notes: "시스템 설계 Philosophy — 행동 유도 설계"

  - id: "q004"
    difficulty: easy
    query: "7일이면 충분하다. 완벽한 설계를 기다리지 말고 만들면서 개선"
    relevant_ids: [406]
    also_relevant: [404, 405]
    notes: "반복 개발 원칙 — v3.3 경험 기반"

  - id: "q005"
    difficulty: easy
    query: "빼기가 더하기보다 어렵다. 불필요한 에이전트를 없애는 결정"
    relevant_ids: [404]
    also_relevant: [4165, 378]
    notes: "감법 원칙 — Dieter Rams / 일론 머스크 best part is no part"

  - id: "q006"
    difficulty: easy
    query: "AI는 도구가 아니라 팀원이다"
    relevant_ids: [405]
    also_relevant: [404, 406, 378]
    notes: "AI 협업 철학 — 잘 설계된 시스템에서 AI의 역할"

  - id: "q007"
    difficulty: easy
    query: "STATE.md가 유일한 진실이다"
    relevant_ids: [43]
    also_relevant: [755, 771]
    notes: "단일 진실 소스의 구체적 구현 — STATE.md 명시"

  - id: "q008"
    difficulty: easy
    query: "Obsidian과 Claude에 둘 다 쓰면 충돌이 생긴다"
    relevant_ids: [755]
    also_relevant: [756, 43, 771]
    notes: "단일 진실 소스의 실제 위반 사례"

  - id: "q009"
    difficulty: easy
    query: "여러 AI가 동시에 파일을 수정하면 안 된다"
    relevant_ids: [756]
    also_relevant: [755, 771]
    notes: "쓰기 권한 분리 원칙"

  - id: "q010"
    difficulty: easy
    query: "모든 현상을 다차원으로 해석하는 것이 사고의 본질"
    relevant_ids: [4161]
    also_relevant: [4163, 4166]
    notes: "다차원 인식론 Belief 노드"

  # ============================================================
  # TIER 2 — 복수 정답 (q011-q020): 의미 이해 필요
  # ============================================================

  - id: "q011"
    difficulty: medium
    query: "토큰은 화폐다. 컨텍스트를 비용으로 관리해야 한다"
    relevant_ids: [181, 377]
    also_relevant: [378]
    notes: "토큰=화폐 원칙이 2개 노드에 중복 표현됨 — 둘 다 정답"

  - id: "q012"
    difficulty: medium
    query: "단일 진실 소스 원칙"
    relevant_ids: [43, 755, 771]
    also_relevant: [756]
    notes: "SoT 원칙이 3개 노드로 분산 — 모두 정답"

  - id: "q013"
    difficulty: medium
    query: "오케스트레이션 시스템의 핵심 원칙 세 가지"
    relevant_ids: [378]
    also_relevant: [181, 377, 404, 405]
    notes: "Baseline최소화/오프로딩/계층위임 — 378이 핵심, 나머지 보완"

  - id: "q014"
    difficulty: medium
    query: "컨텍스트 토큰 비용을 최소화하는 방법"
    relevant_ids: [181, 377, 378]
    also_relevant: [43]
    notes: "토큰 관리 원칙 클러스터"

  - id: "q015"
    difficulty: medium
    query: "지식 그래프 운영의 핵심 원칙"
    relevant_ids: [43, 755, 756, 771]
    also_relevant: [181]
    notes: "단일 진실/쓰기권한/SoT — mcp-memory 운영 원칙"

  - id: "q016"
    difficulty: medium
    query: "AI와 협업할 때 지켜야 할 원칙"
    relevant_ids: [405, 404]
    also_relevant: [406, 378, 756]
    notes: "AI 팀원 + 감법 + 7일 원칙이 협업 원칙 구성"

  - id: "q017"
    difficulty: medium
    query: "Paul의 창의적 사고 방식"
    relevant_ids: [4166, 4161]
    also_relevant: [4163, 4165]
    notes: "이색적 접합 + 다차원 해석 = 창의성 구조"

  - id: "q018"
    difficulty: medium
    query: "정보 충돌을 방지하는 시스템 설계"
    relevant_ids: [755, 756, 771]
    also_relevant: [43]
    notes: "단일 진실 소스 + 쓰기 권한 분리 = 충돌 방지"

  - id: "q019"
    difficulty: medium
    query: "컨텍스트 윈도우 200K를 효율적으로 사용하는 방법"
    relevant_ids: [377, 181]
    also_relevant: [378]
    notes: "# VERIFY: 200K 컨텍스트 관련 추가 노드 있을 수 있음"

  - id: "q020"
    difficulty: medium
    query: "반복 개선과 감법 설계의 조합"
    relevant_ids: [406, 404]
    also_relevant: [4165, 405]
    notes: "7일 반복 + 빼기 원칙이 함께 적용됨"

  # ============================================================
  # TIER 3 — 추상적 질문 (q021-q025): L4/L5 노드 필요
  # ============================================================

  - id: "q021"
    difficulty: hard
    query: "왜 이 외부 메모리 시스템을 만드는가"
    relevant_ids: [4163]
    also_relevant: [4161, 4165, 4166]
    notes: "근본 동기 — L4 Value/Belief/Philosophy가 정답 레이어"

  - id: "q022"
    difficulty: hard
    query: "뇌와 인공 시스템의 유사성"
    relevant_ids: [4161, 4163]
    also_relevant: [4165]
    notes: "다차원 인식 + 외부화 욕구 — 추상적이지만 L4가 정답"

  - id: "q023"
    difficulty: hard
    query: "Paul이 가장 중요하게 생각하는 가치는 무엇인가"
    relevant_ids: [4163, 4166]
    also_relevant: [4161, 4165]
    notes: "Value 레이어 전체가 후보 — 4163(뇌 확장)이 핵심"

  - id: "q024"
    difficulty: hard
    query: "시스템이 자율적으로 작동하게 만드는 조건"
    relevant_ids: [4165, 405]
    also_relevant: [378, 406, 404]
    notes: "환경 설계 + AI 팀원 + 오케스트레이션 원칙 조합"

  - id: "q025"
    difficulty: hard
    query: "마찰을 최소화해서 생각과 행동의 간격을 줄이는 방법"
    relevant_ids: [4165]
    also_relevant: [404, 406, 181]
    notes: "# VERIFY: 마찰 제거 관련 Signal→Pattern 노드 있을 수 있음"
```

---

## Paul 검토 항목

### 확인 필요 (VERIFY 표시)
- `q019`: 200K 컨텍스트 관련 추가 Principle 노드 ID
- `q025`: 마찰 제거(friction removal) 관련 노드가 DB에 있는가
- q024의 `4165` 단독 relevant_id 적절한가? (또는 다른 Philosophy 노드?)

### 추가 권장
다음 내용의 tier=0 노드가 DB에 있다면 추가:
- Obsidian 볼트 계층 구조 Framework
- 메타-오케스트레이터 중심 팀 구조 Framework
- 개인 지식 그래프 4가지 핵심 원칙 Principle
- checkpoint DB 동시 쓰기 충돌 방지 Pattern

```bash
# tier=0 노드 전체 조회 (Paul이 실행)
sqlite3 data/memory.db "
  SELECT id, type, layer, quality_score, substr(content,1,80)
  FROM nodes
  WHERE quality_score >= 0.9
    AND status = 'active'
  ORDER BY quality_score DESC, layer DESC
  LIMIT 60;
"
```

### 추가 쿼리 후보 (Paul이 채울 수 있게)

```yaml
  # Paul이 추가 (실제 검색 경험 기반)
  - id: "q026"
    difficulty: easy
    query: "# Paul이 작성"
    relevant_ids: []
    also_relevant: []
    notes: ""
```

---

## 다음 단계

1. Paul: DB 조회로 VERIFY 항목 확인 + 오류 수정
2. Paul: q026-q030 추가 (경험 기반)
3. 완성된 goldset → `scripts/eval/goldset.yaml` 저장
4. `python scripts/eval/ab_test.py` 실행 → RRF k=30 vs k=60 검증
