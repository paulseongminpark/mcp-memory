# mcp-memory v2.0 — 전체 설계도

> **Status**: 설계 확정 대기 (2026-03-04)
> **Author**: Paul + Claude (Opus 4.6)
> **From**: v0.1.0 (플랫 구조, 정적 edge, 단일 타입)
> **To**: v2.0 (6레이어, 살아있는 edge, 다면 분류, 리좀적 검색)

---

## Part 1: 전체 구조도

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Paul (사용자)                                │
│    대화 · 옵시디언 · 과거 데이터(문학/철학/예술) · /checkpoint       │
└────────────┬──────────────────────────────────────┬─────────────────┘
             │ remember()                           │ recall()
             ▼                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Claude (의미 판단자)                            │
│                                                                     │
│  역할:                                                              │
│  ① 저장 시: 다면 분류 (type + secondary + facets + layer)            │
│  ② 검색 시: 리좀적 전파 결과 해석 + 이색적 접합 발견                  │
│  ③ 성장 시: Signal → Pattern 승격 판단                               │
│  ④ 연결 시: 크로스도메인 edge 생성 판단                              │
└────────────┬──────────────────────────────────────┬─────────────────┘
             │                                      │
             ▼                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MCP Server (FastMCP, stdio)                       │
│                                                                     │
│  도구:                                                              │
│  remember()      — 저장 (다면 분류 + 자동 edge + tier 지정)          │
│  recall()        — 리좀적 검색 (3중 하이브리드 + 전파 + 헤비안)       │
│  get_context()   — 세션 컨텍스트 (최근 결정/질문/실패)               │
│  analyze_signals() — Signal 클러스터 분석 → 승격 후보 반환            │
│  promote_node()  — 타입 승격 실행 + 이력 보존                        │
│  get_becoming()  — Becoming 중인 노드들 현황                         │
│  connect()       — 수동 edge 생성 (크로스도메인 포함)                 │
│  inspect()       — 노드 상세 조회 (전체 메타, 연결, 이력)             │
└────────┬──────────┬──────────┬──────────────────────────────────────┘
         │          │          │
         ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────────────────┐
│ SQLite   │ │ ChromaDB │ │ NetworkX             │
│ +FTS5    │ │ (Vector) │ │ (Graph Traversal)    │
│          │ │          │ │                      │
│ nodes    │ │ 3072dim  │ │ 활성화 전파           │
│ edges    │ │ cosine   │ │ 헤비안 강화           │
│ sessions │ │ search   │ │ 레이어 간 가중치       │
│ tiers    │ │          │ │ 크로스도메인 탐색      │
└──────────┘ └──────────┘ └──────────────────────┘
```

---

## Part 2: 노드 스키마 (새 구조)

```
노드 {
  id: 4521

  # 다면 분류
  primary_type: "Decision"
  secondary_types: ["Insight", "Identity"]
  layer: 1

  # Paul의 차원
  facets: ["developer", "philosopher"]
  domains: ["orchestration", "portfolio"]   # 복수 도메인 가능

  # 데이터 계층
  tier: 2                    # 0=raw, 1=refined, 2=curated
  source: "checkpoint:session-2026-03-04"

  # 성숙도 (Becoming)
  maturity: 0.8              # 0.0=씨앗 ~ 1.0=결정화
  observation_count: 5       # 유사 관찰 횟수
  promotion_history: [
    {from: "Signal", to: "Pattern", date: "2026-02-28", reason: "3회 반복 확인"},
    {from: "Pattern", to: "Decision", date: "2026-03-01", reason: "Claude 판단"}
  ]

  # 기본
  content: "Context as Currency를 설계 원칙으로 확정..."
  tags: "orchestration,v4.0,core-principle"
  confidence: 0.9
  created_at: "2026-03-01"
}
```

---

## Part 3: Edge 스키마 (살아있는 연결)

```
edge {
  id: 8901
  source_id: 4521
  target_id: 3200

  # 관계
  relation: "governed_by"
  direction: "upward"        # upward/downward/horizontal/cross-layer

  # 살아있는 강도
  base_strength: 0.7         # 생성 시 강도
  frequency: 12              # recall()에서 통과한 횟수
  last_activated: "2026-03-04T14:30:00"
  decay_rate: 0.005          # 하루 감쇠율

  # 계산된 강도
  effective_strength:         # = base × (1 + log(frequency)/10) × recency_factor
    → 자주 활성화되면 강해짐
    → 오래 안 쓰면 약해짐
    → 하지만 base는 보존됨 (완전히 사라지지 않음)

  # 레이어 가중치
  layer_distance: 1           # source와 target의 레이어 차이
  layer_penalty: 1.0          # 인접=1.0, 2단계=0.6, 3단계+=0.3

  created_at: "2026-03-01"
}
```

---

## Part 4: 6레이어 + 45개 타입

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layer 5 — 가치/존재론 (강도: 최고, 변화: 극히 드묾)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Axiom         근본 가정. 의심하지 않는 것.
  Value         판단의 기준. 무엇이 중요한가.
  Wonder        경이로움. 탐구를 유발하는 것.
  Aporia        해결 불가로 열어두는 것.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layer 4 — 세계관 (강도: 높음, 변화: 느림)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Belief        확실하지 않지만 믿는 것.
  Philosophy    삶/시스템에 대한 철학적 입장.
  Mental Model  세상의 특정 부분을 이해하는 방식.
  Lens          세상을 바라보는 특정 프레임.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layer 3 — 원칙/정체성 (강도: 중고, 변화: 큰 사건으로)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Principle     행동을 규율하는 원칙.
  Identity      나는 누구인가.
  Boundary      넘지 않는 선.
  Vision        장기 미래 방향.
  Paradox       모순처럼 보이지만 공존.
  Commitment    헌신. 약속.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layer 2 — 개념/패턴 (강도: 중간, 변화: 주~월 단위)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Pattern       반복 확인된 구조.
  Insight       인사이트. 순간적 이해.
  Framework     여러 패턴을 묶은 체계.
  Heuristic     경험칙.
  Trade-off     A를 얻으면 B를 잃는 구조.
  Tension       두 힘의 팽팽한 긴장.
  Metaphor      비유.
  Connection    새로운 연결 발견.
  Concept*      추상적 아이디어의 정의.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layer 1 — 행위/사건 (강도: 낮음, 변화: 일~주 단위)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Decision      의사결정.
  Plan          구현 계획.
  Workflow      절차.
  Experiment    실험.
  Failure       실패.
  Breakthrough  돌파구.
  Evolution     시스템 진화 이력.
  Signal        아직 Pattern 안 된 잠재적 패턴.
  Goal          목표.
  Ritual        반복 루틴.
  Tool          도구.
  Skill         스킬.
  AntiPattern   반패턴.
  Constraint    제약 조건.
  Assumption    검증 안 된 전제.
  SystemVersion 시스템 버전.
  Agent         에이전트.
  Project       프로젝트 정보.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layer 0 — 원시 경험 (강도: 최저, 변화: 매일)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Observation   단순 관찰 사실.
  Evidence      주장을 뒷받침하는 사례.
  Trigger       변화를 유발하는 조건.
  Context       배경 조건.
  Conversation  원시 대화 데이터.
  Narrative     스토리 형식 서술.
  Question      미해결 질문.
  Preference    선호.

미래 예약 (과거 데이터 투입 시 활성화):
  Thesis*       철학적 명제.
  Argument*     논증 구조.
  Passage*      인상적 문단/인용.
  Style*        글쓰기 문체.
  Voice*        글의 목소리/퍼소나.
  Composition*  시각적/구조적 배치.
  Influence*    영향 관계.

* = 미래 예약. schema에 정의하되, 현재 분류에 사용 안 함.
  총: 45개 활성 + 7개 예약 = 52개
```

---

## Part 5: Edge 관계 타입 (48개)

### 인과 (팔란티어 핵심) — 8개
```
caused_by       ← 원인
led_to          → 결과로 이어짐
triggered_by    ← 트리거됨
resulted_in     → 결과
resolved_by     ← 해결됨
prevented_by    ← 방지됨
enabled_by      ← 가능케 함
blocked_by      ← 막힘
```

### 구조적 — 8개
```
part_of         ⊂ 부분
composed_of     ⊃ 구성됨
extends         → 확장
governed_by     ← 규율됨
instantiated_as → 구현됨
expressed_as    → 표현됨
contains        ⊃ 포함
derived_from    ← 파생됨
```

### 레이어 이동 (들뢰즈 통찰) — 6개
```
realized_as       ↑ Signal → Pattern (잠재→현실)
crystallized_into ↑ 여러 관찰 → 하나의 원칙으로 결정화
abstracted_from   ↑ 구체에서 추상으로
generalizes_to    ↑ 일반화
constrains        ↓ 제약 (추상이 구체를 제약)
generates         ↓ 생성 (원칙이 결정을 낳음)
```

### 차이 추적 (들뢰즈) — 4개
```
differs_in      ↔ 같은 타입이지만 차이가 있음
variation_of    ↔ 반복이지만 변주
evolved_from    → 이전 버전에서 진화
succeeded_by    → 다음 버전
```

### 의미론적 — 8개
```
supports          ↔ 지지
contradicts       ↔ 모순
analogous_to      ↔ 유사 (크로스도메인 핵심!)
parallel_with     ↔ 동시적
reinforces_mutually ↔ 상호 강화
connects_with     ↔ 연결
inspired_by       ← 영감
exemplifies       → 예시
```

### 관점 (다중 해석) — 4개
```
viewed_through    → Observation이 Lens를 통해 해석됨
interpreted_as    → Lens에서 Insight로
questions         → 의문을 제기
validates         → 검증
```

### 시간적 — 4개
```
preceded_by       ← 이전
simultaneous_with ↔ 동시
born_from         ← 에서 탄생
assembles         ⊃ 이질적 요소들을 묶음 (Assemblage)
```

### 크로스도메인 특수 — 6개
```
transfers_to      → 한 도메인의 패턴이 다른 도메인에 적용됨
mirrors           ↔ 다른 도메인에서 같은 구조 반영
influenced_by     ← 다른 도메인에서 영향 받음
showcases         → 보여줌
correlated_with   ↔ 상관관계
refuted_by        ← 반증됨
```

---

## Part 6: 하나의 데이터가 흐르는 전체 경로

### 시나리오: Paul이 대화에서 "이 시스템은 유기적이어야 한다"고 말함

```
Step 1: 저장 — remember()
━━━━━━━━━━━━━━━━━━━━━━━
  Claude가 /checkpoint에서 이 발언을 포착

  → remember(
      content: "시스템은 유기적이어야 한다. 고정되면 죽는다.",
      type: "Principle",
      secondary_types: ["Belief"],
      layer: 3,
      facets: ["philosopher", "developer"],
      domains: ["orchestration", "mcp-memory"],   # 크로스도메인!
      tier: 2,                                     # Paul 승인
      tags: "organic,governance,core"
    )

Step 2: 자동 edge 생성
━━━━━━━━━━━━━━━━━━━━━
  2a. ChromaDB 유사도 검색 → 기존 노드 발견:
      #1203 "Context as Currency 설계" (distance: 0.28)
      #892  "에이전트를 15개로 줄인 결정" (distance: 0.31)

  2b. 자동 edge 생성:
      → {source: 신규, target: #1203, relation: "governs",
         direction: "downward", base_strength: 0.72}
      → {source: 신규, target: #892, relation: "governs",
         direction: "downward", base_strength: 0.69}

  2c. 크로스도메인 감지:
      #1203은 orchestration, #892은 mcp-memory
      → 두 도메인을 잇는 Principle이 됨
      → 이것이 이색적 접합의 씨앗

Step 3: 검색 — recall("유기적 시스템")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  3a. 3중 하이브리드 검색:
      Vector (ChromaDB): [신규노드, #1203, #892, #445...]
      Keyword (FTS5): [신규노드, #1203, #330...]
      → RRF 병합 → 씨앗 노드 5개 확정

  3b. 리좀적 전파 (핵심!):
      씨앗 5개에서 동시에 활성화 시작
      → edge.effective_strength > 0.4인 것만 따라감
      → 레이어 경계 무시: Principle(L3) → Decision(L1) → Pattern(L2)
      → project 경계 무시: orchestration → portfolio → mcp-memory

      전파 과정에서 발견:
      #445 "portfolio에서 4장 카드로 줄인 결정" (portfolio 도메인)
      ← 같은 "유기적 구조" Principle에 연결!
      ← 이것이 이색적 접합: 시스템 설계 원칙이 포트폴리오 결정과 연결

  3c. 헤비안 강화:
      이번 recall()에서 통과한 edge들의 frequency +1
      → 다음에 같은 경로가 더 잘 찾아짐

  3d. 결과 반환:
      Claude가 해석하여 Paul에게:
      "유기적 시스템에 대한 원칙 → 이것이 portfolio 카드 결정과
       mcp-memory 설계 양쪽에 영향을 주고 있음.
       관련 결정 3건, 패턴 2건, 미해결 질문 1건."

Step 4: 시간이 지남 — Becoming
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  4a. 이 Principle이 반복적으로 recall()됨 → frequency 증가
      → effective_strength 상승

  4b. 새로운 노드가 이 Principle과 연결됨 → maturity 증가
      0.5 → 0.7 → 0.9

  4c. 충분히 성숙하면 → 더 상위 레이어로 승격 가능
      Principle(L3) → Philosophy(L4): "유기적 거버넌스 철학"
      → Claude가 승격 판단 + Paul 승인

  4d. 승격 이력 보존:
      promotion_history: [
        {from: "Principle", to: "Philosophy",
         date: "2026-04-15",
         reason: "3개 도메인에서 반복 확인, 12개 하위 노드 연결"}
      ]

Step 5: 대시보드에서 확인
━━━━━━━━━━━━━━━━━━━━━━━━
  Knowledge Graph에서:
  - 이 Philosophy 노드가 중심에 위치
  - orchestration, portfolio, mcp-memory 3개 도메인의 결정들이 방사형으로 연결
  - edge 두께가 frequency에 비례
  - 클릭하면 승격 이력, 연결된 모든 노드, facets 보임
```

---

## Part 7: 이것으로 얻는 것

### 1. 이색적 접합
- project 경계를 넘어 "portfolio 결정"과 "시스템 설계"가 같은 원칙에서 나왔음을 발견
- 지금은 불가능. v2.0에서 가능.

### 2. 기억이 성장한다
- Signal이 Pattern이 되고, Principle이 되는 과정이 기록됨
- "이 원칙은 어떻게 생겨났는가"를 역추적 가능

### 3. 자주 생각하는 것이 강해진다
- 헤비안 학습으로 Paul의 사고 패턴이 시스템에 학습됨
- 자주 recall하는 연결은 더 잘 찾아짐

### 4. 다차원적 Paul을 담는다
- facets: philosopher, developer, designer, writer
- 같은 노드를 다른 facet으로 읽을 수 있음

### 5. 미래 데이터를 받을 수 있다
- 문학/철학/예술 타입이 예약되어 있음
- 과거 데이터 넣으면 기존 기술 노드와 크로스도메인 연결 발생

### 6. Claude가 더 잘 돕는다
- recall() 결과가 단순 "비슷한 것 목록"이 아닌 "의미 지도"
- 이색적 접합 발견 → Paul에게 "이런 연결이 있습니다" 제안 가능

---

## Part 8: 리스크 점검

### 치명적 문제 (반드시 해결)

**R1. 분류 정확도 하락**
- 45개 타입 → GPT가 혼동할 가능성 높음
- 특히 Layer 2-3 경계: Pattern vs Principle, Heuristic vs Principle
- 해결: 2단계 분류. 먼저 레이어(0~5) 분류, 그 다음 해당 레이어 내 타입.
  → 1단계에서 6개 중 택1, 2단계에서 4~18개 중 택1. 정확도 향상.

**R2. 헤비안 학습의 편향**
- 자주 recall하는 도메인의 edge만 강해짐
- Paul이 orchestration을 많이 검색하면 → orchestration edge만 강해짐
  → portfolio, 문학, 철학 도메인 edge는 약해짐
  → 이색적 접합이 오히려 줄어듦
- 해결: 감쇠에 하한선 설정. edge.base_strength 이하로는 안 떨어짐.
  + 주기적 "탐험 모드": recall()의 10%를 약한 edge 경로로 강제 탐색.

**R3. 리좀적 전파의 폭발**
- threshold 0.4로 전파하면 3,085개 노드에서 수백~수천 개 활성화 가능
- 응답 시간 급증
- 해결:

```python
def propagate(seed_nodes, threshold=0.4, max_depth=2, max_nodes=50):
    activated = set(seed_nodes)
    frontier = [(nid, 0) for nid in seed_nodes]  # (node, depth)

    while frontier and len(activated) < max_nodes:
        nid, depth = frontier.pop(0)
        if depth >= max_depth:
            continue

        for edge in get_edges(nid):
            eff = effective_strength(edge)
            eff *= layer_penalty(edge.layer_distance)  # 레이어 거리 페널티
            eff *= tier_weight(get_node(edge.target).tier)  # tier 가중치

            if eff > threshold and edge.target not in activated:
                activated.add(edge.target)
                frontier.append((edge.target, depth + 1))
                strengthen_edge(edge.id)  # 헤비안: 통과한 edge 강화

    return activated
```

### 심각한 문제 (우선 해결)

**R4. ChromaDB 성능**
- 3,085개에서 이미 segfault 경험
- facets/secondary_types 검색하려면 where 필터 복잡해짐
- 해결: ChromaDB metadata에 layer, tier만 넣고,
  secondary_types/facets는 SQLite에서만 관리.

**R5. 리좀적 전파의 폭발**
- threshold 0.4로 전파하면 3,085개 노드에서 수백~수천 개 활성화 가능
- 응답 시간 급증
- 해결: 전파 depth 제한 (기본 2홉, 최대 4홉).
  활성화 노드 상한 (기본 50개).
  tier 가중치로 raw 노드 제외.

**R6. GPT API 비용 증가**
- 2단계 분류: 배치당 API 호출 2회
- 45개 타입 system prompt 길어짐
- 해결: 1단계(레이어)는 규칙 기반으로 가능한 것 먼저.
  예: source가 "obsidian:docs/plans/"이면 → Layer 1 (Plan).
  규칙으로 안 되면 GPT 호출. 비용 50% 절감.

### 운영 문제 (모니터링)

**R7. 승격 오류**
- Claude가 Signal → Pattern 승격을 잘못 판단하면?
- 되돌리기 어려움 (edge가 이미 생성됨)
- 해결: 승격 전 Paul 승인 옵션. 자동 승격은 maturity > 0.9만.
  승격 rollback 도구 추가.

**R8. facets 정의 불완전**
- "philosopher", "developer" 등 — 어떤 facets가 있는지 아직 미정의
- Paul의 실제 차원을 모르면 facets가 무의미
- 해결: 초기에는 빈 facets로 시작.
  대화에서 점진적으로 facets 발견 + 추가.
  → 이것 자체가 Becoming (시스템이 Paul을 점점 이해해감)

**R9. 과거 데이터 품질**
- 문학/철학/예술 텍스트의 청크 분할이 기술 문서와 다름
- ## 헤딩 기반 청크는 에세이에 적합하지 않을 수 있음
- 해결: 도메인별 chunker 필요. 기술문서용 / 에세이용 / 짧은 메모용.

### 아직 미해결

**R10. 대시보드 설계**
- 새 아키텍처의 모든 정보를 보여주는 대시보드 미설계
- 레이어별 뷰, facet별 필터, 크로스도메인 그래프, 승격 이력 타임라인 등
- 이것은 별도 설계 필요.

---

## Part 9: 치명적 리스크 해결 방안 (구체적)

### R1 해결: 2단계 분류 파이프라인

```
Step 1 (규칙 기반, API 호출 없음):
  파일 경로로 레이어 추정:
    docs/plans/ → Layer 1 (Plan)
    STATE.md → Layer 1 (SystemVersion)
    .claude/skills/ → Layer 1 (Workflow)
    KNOWLEDGE.md → Layer 2 (Framework)
    _history/evidence/ → Layer 0 (Narrative)
  → 규칙으로 약 60% 커버

Step 2 (GPT, 규칙 실패 시):
  "이 텍스트는 어떤 레이어인가? (0~5)"
  → 6개 중 택1. 정확도 높음.

Step 3 (GPT, 레이어 내 타입):
  "Layer 2에 해당하는 이 텍스트의 타입은?"
  → 최대 12개 중 택1. 정확도 유지.

효과: GPT 호출 40% 절감 + 정확도 상승.
```

### R2 해결: 헤비안 편향 방지

```python
def update_edge_strength(edge):
    """recall()이 edge를 통과할 때마다 호출"""
    # 헤비안 강화
    edge.frequency += 1
    boost = min(0.3, math.log(edge.frequency + 1) / 10)

    # 시간 감쇠
    days_since = (now - edge.last_activated).days
    decay = edge.decay_rate * days_since

    # 핵심: 하한선 — base_strength의 50% 이하로 안 떨어짐
    effective = max(
        edge.base_strength * 0.5,
        edge.base_strength + boost - decay
    )
    return effective

def recall(query):
    """10% 확률로 탐험 모드 — 약한 edge 경로 강제 탐색"""
    if random.random() < 0.1:
        results = explore_weak_edges(query)  # 약한 크로스도메인 edge 탐색
    else:
        results = normal_search(query)
    return results
```

탐험 모드가 이색적 접합의 핵심 — 평소 안 쓰는 경로를 10% 확률로 탐색.

### R3 해결: 전파 폭발 방지

Part 8 R3에 코드 포함. 핵심 파라미터:
- `max_depth=2` (기본 2홉, 최대 4홉까지 조절 가능)
- `max_nodes=50` (활성화 노드 상한)
- `tier_weight`: raw=0.3, refined=0.7, curated=1.0

---

## Part 10: Claude의 지속적 역할 — 자동화 설계

Claude는 도구 실행자가 아니라 **의미 판단자이자 공동 성장 파트너**.

### Claude가 관여하는 5가지 지점

#### ① /checkpoint (세션 중, 수동 트리거)
```
Paul이 /checkpoint 호출
→ Claude가 대화 스캔, 기억 후보 추출
→ 다면 분류 (primary + secondary + facets + layer)
→ Paul 승인 → remember()로 저장 (tier: 2 = curated)
→ 자동 edge 생성 + 크로스도메인 감지
```

#### ② recall() 결과 해석 (매 검색 시, 자동)
```
Paul 또는 Claude가 recall() 호출
→ 리좀적 전파 결과 반환
→ Claude가 해석:
   - 예상치 못한 크로스도메인 연결 발견 시 → Paul에게 제안
   - "이 portfolio 결정과 이 mcp-memory 설계가 같은 원칙에서 나왔습니다"
→ 헤비안 강화 자동 실행 (통과한 edge의 frequency +1)
```

#### ③ Signal 승격 판단 (주기적, 자동 + 수동)
```
자동 트리거: 새 노드 저장 시 유사 Signal 3개 이상 감지
→ Claude에게 알림: "Signal 클러스터 발견"
→ Claude가 analyze_signals() 호출, 맥락 분석
→ 승격 판단:
   - maturity > 0.9 → 자동 승격 가능
   - maturity 0.6~0.9 → Paul 승인 필요
   - maturity < 0.6 → 아직 이름
→ promote_node() 호출 → realized_as edge + 승격 이력 보존
```

#### ④ 세션 시작 (자동, session-start.sh)
```
session_context.py → SQLite에서 직접 조회:
  - 최근 결정 3건
  - 미해결 질문 3건
  - 최근 실패 3건
  - Becoming 현황: maturity가 높아지고 있는 Signal들
→ Claude에게 컨텍스트 제공
→ "이 Signal들이 성숙 중입니다" 알림
```

#### ⑤ 세션 종료 (compressor → save_session)
```
compressor가 세션 요약 생성
→ save_session()으로 세션 데이터 저장 (tier: 1 = refined)
→ 세션 간 연속성 유지
→ 다음 세션 시작 시 ④에서 이어받기
```

### 의미망 성장 순환 사이클

```
Paul 대화
    ↓
Claude /checkpoint 추출
    ↓
노드 저장 (Signal, tier 2)
    ↓
유사 Signal 누적 (maturity 상승)
    ↓
Claude가 패턴 인식 (analyze_signals)
    ↓
Pattern으로 승격 (promote_node + realized_as edge)
    ↓
여러 Pattern이 Principle로 결정화 (crystallized_into)
    ↓
Principle이 크로스도메인 연결 생성 (governs 여러 도메인)
    ↓
recall()에서 이색적 접합 발견
    ↓
Claude가 Paul에게 제안: "이런 연결이 있습니다"
    ↓
Paul의 새 Insight → 새 대화
    ↓
다시 처음으로 (사이클 반복)
```

이 순환이 반복될수록:
- edge.frequency 증가 → 자주 쓰는 연결 강화 (헤비안)
- Signal → Pattern → Principle 체인이 늘어남 (Becoming)
- 크로스도메인 연결 증가 → 이색적 접합 축적
- facets 점진적 발견 → 시스템이 Paul을 더 잘 이해

### MCP 도구 확장 (v2.0)

현재 7개 → 11개:

| 도구 | 역할 | 신규? |
|------|------|-------|
| `remember()` | 저장 (다면 분류 + 자동 edge + tier) | 확장 |
| `recall()` | 리좀적 검색 (3중 하이브리드 + 전파 + 헤비안) | 확장 |
| `get_context()` | 세션 컨텍스트 | 확장 |
| `search_nodes()` | 고급 검색 (facet/layer/domain 필터) | 기존 |
| `get_relations()` | 관계 조회 | 기존 |
| `save_session()` | 세션 저장 | 기존 |
| `get_session()` | 세션 조회 | 기존 |
| `analyze_signals()` | Signal 클러스터 분석 → 승격 후보 반환 | **신규** |
| `promote_node()` | 타입 승격 + 이력 보존 + realized_as edge | **신규** |
| `get_becoming()` | Becoming 중인 노드들 현황 | **신규** |
| `inspect()` | 노드 상세 (전체 메타, 연결, 승격 이력) | **신규** |

---

## Part 11: 구현 순서

### Phase 1: 기반 — 스키마 마이그레이션
1. ontology/schema.yaml 업데이트 (45+7 타입, 48 관계, layer 필드)
2. SQLite 스키마 마이그레이션
   - nodes: +secondary_types, +facets, +layer, +tier, +maturity, +observation_count, +promotion_history
   - edges: +frequency, +last_activated, +decay_rate, +direction, +layer_distance
3. 기존 3,085개 노드에 layer 필드 부여 (타입→레이어 매핑)
4. 기존 edge에 frequency=0, decay_rate=0.005 기본값
5. 분류 불가 89개 처리 (portfolio 삭제 + Plan 재분류)

### Phase 2: 핵심 메커니즘 — 살아있는 edge + 리좀적 검색
6. 2단계 분류 파이프라인 (규칙→레이어→타입)
7. 헤비안 학습 (recall 시 edge.frequency +1, effective_strength 재계산)
8. 시간 감쇠 (하루 단위 decay, base_strength × 0.5 하한선)
9. 리좀적 전파 (propagate() 함수, depth 제한 + 상한선)
10. 크로스도메인 recall() (project 필터 제거 모드 기본)
11. 탐험 모드 (10% 확률로 약한 edge 강제 탐색)

### Phase 3: Becoming — Signal 승격 시스템
12. analyze_signals() MCP 도구 구현
13. promote_node() MCP 도구 구현
14. get_becoming() MCP 도구 구현
15. inspect() MCP 도구 구현
16. /checkpoint에 Signal 승격 판단 통합
17. remember()에 다면 분류 지원 (secondary_types, facets, domains)

### Phase 4: 대시보드 — 전면 재설계
18. 자동새로고침 제거, 수동 브라우저 새로고침
19. 그래프 안정화 (시뮬레이션 고정 버튼, alphaDecay 조정)
20. 레이어별 뷰 (토글로 L0~L5 on/off)
21. 노드 상세 패널 (클릭 시 전체 내용 + 연결 + 승격 이력)
22. 노드 검색 + 타입/프로젝트/facet 필터
23. 크로스도메인 그래프 (도메인별 색상, 경계 넘는 edge 강조)
24. 전체 노드 테이블 (페이지네이션, 정렬, 필터)
25. Becoming 타임라인 (Signal→Pattern→Principle 승격 이력)
26. 관계 탐색 depth 슬라이더 (1~4홉)

### Phase 5: 미래 데이터
27. 에세이/철학 텍스트용 chunker (단락 기반)
28. 미래 예약 7개 타입 활성화 (Thesis, Argument, Passage, Style, Voice, Composition, Influence)
29. 과거 데이터 ingestion
30. 크로스도메인 edge 자동 생성 (기존 기술 노드 ↔ 인문/예술 노드)

---

## Part 12: 4-Model Enrichment Pipeline

> **상세 스펙**: `docs/06-enrichment-pipeline-spec.md` 참조

### 개요

OpenAI Data Sharing 무료 토큰을 매일 90% 활용하여 의미망을 자동으로 성장시키는 파이프라인.
4개 GPT 모델 + Codex CLI + Claude가 각자의 강점에 맞는 역할을 수행.

### 토큰 예산 (일일)

```
대형 풀 250K/day (90% = 225K):
  gpt-5.2  — 심층 생성 (L4-L5 분류, 내러티브, 공백 분석)     100K
  o3       — 깊은 추론 (온톨로지 검증, 이색적 접합, 승격)      75K
  gpt-4.1  — 정밀 검증 (재분류, 레이어 확인)                  50K

소형 풀 2,500K/day (90% = 2,250K):
  gpt-5-mini — 대량 enrichment (summary, tags, 관계, embedding) 1,800K
  o3-mini    — 배치 추론 (모순, Assemblage, 시간 체인)          450K

+ Codex CLI — 코드/프롬프트/온톨로지 검증                     별도 (매일)
```

### 25개 Enrichment 작업

노드 단위 12개 (E1~E12): summary, key_concepts, tags, facets, domains,
  secondary_types, embedding_text, quality_score, abstraction_level,
  temporal_relevance, actionability, layer 검증

Edge 단위 5개 (E13~E17): 크로스도메인 관계, 동일도메인 정밀화,
  edge 방향/이유, strength 보정, 중복 병합

그래프 단위 8개 (E18~E25): 클러스터 테마, 빠진 연결, 시간 체인,
  모순 탐지, Assemblage, 승격 후보, 병합 후보, 지식 공백

### 분류 파이프라인 (4경로)

```
경로 1: 실시간 (remember/checkpoint)
  → Claude 직접 4필드 + 시스템 3필드 + GPT 비동기 8필드

경로 2: 배치 (Obsidian 인제스션)
  → 규칙(60%) → gpt-5-mini 레이어 → gpt-5-mini 타입 → confidence 에스컬레이션

경로 3: recall() 중 수동적 교정
  → Claude가 오분류 감지 → tier별 자동/확인 교정

경로 4: 월/목 정기 감사
  → 월: 전체 감사, 목: 빠른 점검
```

### 실행 스케줄

```
매일 KST 09:30 (UTC 00:30, 토큰 리셋 직후):
  Phase 1: gpt-5-mini 대량 enrichment (1,800K)
  Phase 2: o3-mini 배치 추론 (450K)
  Phase 3: gpt-4.1 정밀 검증 (50K)
  Phase 4: gpt-5.2 심층 생성 (100K)
  Phase 5: o3 깊은 추론 (75K)
  Phase 6: Codex CLI 검증
  Phase 7: 리포트 생성

월/목: Claude 감사 세션 (리포트 기반)
```

### 1회성 마이그레이션 (Day 1-3)

Day 1: 전 노드 summary + tags + embedding_text + 레이어 검증
Day 2: 크로스도메인 관계 + facets + domains + 클러스터 분석
Day 3: edge 보정 + 모순/Assemblage + 점수 산정 + 승격 후보

### Phase 5 → Phase 6 통합 (구현 순서 업데이트)

Phase 5 기존: 미래 데이터 → Phase 6으로 이동
Phase 5 신규: Enrichment Pipeline (daily_enrich.py 구현)

```
Phase 5: Enrichment Pipeline
31. token_counter.py (토큰 예산 관리)
32. node_enricher.py (E1-E12)
33. relation_extractor.py 확장 (E13-E17)
34. graph_analyzer.py (E18-E25)
35. daily_enrich.py (메인 파이프라인)
36. codex_review.py (Codex CLI 검증)
37. migrate_v2.py (1회성 마이그레이션)
38. 프롬프트 템플릿 작성 + 50개 표본 테스트

Phase 6: 미래 데이터 (기존 Phase 5에서 이동)
39. 에세이/철학 텍스트용 chunker
40. 미래 예약 7개 타입 활성화
41. 과거 데이터 ingestion
42. 크로스도메인 edge 자동 생성
```
