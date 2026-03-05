# 심화 3: 빼기 실행 계획 — 실제 DB 데이터 (2026-03-05)

## 타입 분포 (31/50 사용중)

```
Tier A (100+ 노드, 13개 = 전체의 86%):
  Workflow(567), Insight(331), Principle(284), Decision(274),
  Narrative(193), Tool(173), Framework(159), Skill(140),
  Project(133), Goal(131), Agent(130), Pattern(128), SystemVersion(122)

Tier B (10-100, 11개):
  Conversation(89), Failure(85), Experiment(72), Breakthrough(58),
  Identity(44), Unclassified(38), Evolution(28), Connection(24),
  Tension(20), Question(11), Observation(11)

Tier C (1-10, 7개, L4/L5 포함):
  Preference(7), Signal(5), AntiPattern(5), Value(2),
  Philosophy(2), Belief(1), Axiom(1)

미사용 (19개, 인스턴스 0):
  Evidence, Trigger, Context, Plan, Ritual, Constraint, Assumption,
  Heuristic, Trade-off, Metaphor, Concept,
  Boundary, Vision, Paradox, Commitment,
  Mental Model, Lens, Wonder, Aporia
```

## 관계 분포

```
Top 10 (91.7%):
  supports(1475), part_of(961), expressed_as(741), generalizes_to(606),
  instantiated_as(455), led_to(259), enabled_by(254), parallel_with(187),
  assembles(167), contains(166)

6개 잘못된 관계 (ALL_RELATIONS에 없음):
  strengthens(9), extracted_from(2), governs(32),
  instance_of(2), evolves_from(4), validated_by(3)

3개 미사용 유효 관계:
  interpreted_as, questions, viewed_through (전부 perspective 카테고리)
```

## 구조적 발견

```
레이어: L1 과밀 58.5%, L2 20.6%, L3 10%, L4 0.15%, L5 0.03%, None 1.7%
Tier: tier=2(미검증) 77.5%, tier=1 12.3%, tier=0 10.2%
Orphan: 26개 (L4/L5 6개 포함)
```

## Phase 0 결론

### 1. 19개 미사용 타입 -> 즉시 deprecated

```
replaced_by 매핑:
  Evidence -> Observation        Trigger -> Signal
  Context -> Conversation        Plan -> Goal
  Ritual -> Workflow             Constraint -> Principle
  Assumption -> Belief           Heuristic -> Pattern
  Trade-off -> Tension           Metaphor -> Connection
  Concept -> Insight             Boundary -> Principle
  Vision -> Goal                 Paradox -> Tension
  Commitment -> Decision         Mental Model -> Framework
  Lens -> Framework              Wonder -> Question
  Aporia -> Question
```

### 2. 잘못된 관계 6개 교정

```
governs(32) -> ALL_RELATIONS에 추가 (governed_by 역방향, 정당)
strengthens(9) -> supports
validated_by(3) -> validates
extracted_from(2) -> derived_from
instance_of(2) -> instantiated_as
evolves_from(4) -> evolved_from
```

### 3. perspective 관계 2개 deprecated

`interpreted_as`, `viewed_through` -> deprecated
`questions` -> 유보 (Question 타입과 자연스러운 쌍)

### 4. super-type 구조 (8개)

```
Experience(L0): Observation, Conversation, Narrative, Preference
Action(L1):    Decision, Experiment, Failure, Breakthrough, Evolution
System(L1):    Workflow, Tool, Skill, Agent, Project, Goal, SystemVersion
Signal(L1):    Signal, Question, AntiPattern
Concept(L2):   Pattern, Insight, Framework, Connection, Tension
Identity(L3):  Principle, Identity
Worldview(L4): Belief, Philosophy, Value
Axiom(L5):     Axiom
+ Unclassified (메타)
```

### 5. L1 과밀 -> 승격 필요

1,913개 L1 노드, Signal 5개뿐. 대부분 L1에서 Pattern으로 직접 기록되어 승격 경로 미활용.

### 6. tier=2 77.5% -> 검증 체계 필요

enrichment quality_score 자체가 LLM 생성값. 검증되지 않은 검증.

## Phase 1 실행 계획

```
Step 1: type_defs + 31개 활성 타입 마이그레이션
Step 2: 19개 미사용 타입 deprecated
Step 3: relation_defs + 48개 활성 관계 마이그레이션
Step 4: 6개 잘못된 관계 교정
Step 5: 2개 미사용 관계 deprecated (questions 유보)
Step 6: 26개 orphan 검토 (L4/L5 수동 edge, 나머지 inactive)
Step 7: 55개 L?(None) 노드 layer 배정
```

## 위험도 매트릭스

| 대상 | 위험도 | 되돌리기 |
|------|--------|---------|
| 19 미사용 타입 deprecated | 0 | 즉시 |
| 2 미사용 관계 deprecated | 0 | 즉시 |
| 6 잘못된 관계 교정 | 낮음 | correction_log |
| 20 orphan inactive | 낮음 | reactivate |
| super-type 추가 | 0 | 추가만 |
| L1 승격 촉진 | 낮음 | 되돌리기 가능 |
| 유사 관계 병합 | 중간 | replaced_by |
| enrichment 축소 | 높음 | action_log 필요 |
