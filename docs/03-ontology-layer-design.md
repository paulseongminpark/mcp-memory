# 온톨로지 레이어 설계 — 다층 의미망 아키텍처

> **Status**: 설계 논의 중 (2026-03-03)
> **Context**: Paul + Claude 대화에서 발생. 핵심 설계 결정.
> **Goal**: "현실의 나를 모두 다 모방할 수 있는 결정체"
> **철학적 기반**: 들뢰즈 (차이와 반복, 리좀, 강도, 잠재성/현실성, 배치)

---

## 핵심 질문

### 레이어가 많을수록 좋은가?

딥러닝의 근본 질문과 동일하다.

**많을수록 좋은 것:**
- 표현력 (representational power) 증가
- 더 세밀한 추상화 수준 구분
- 복잡한 추론 경로 가능 ("이 결정 → 원칙 → 세계관")

**많을수록 나빠지는 것:**
- 분류 모호성 증가 (GPT가 혼동)
- 관리 복잡도 증가
- 분류 비용 증가 (API)
- vanishing signal — 너무 추상적인 레이어는 실제 데이터가 없음

**결론**: 레이어 수는 "표현하고 싶은 추상화 수준의 수"와 같아야 한다.
레이어 그 자체가 목적이 아니라, 각 레이어가 뚜렷한 존재론적 의미를 가져야 한다.

---

## 가중치 문제

### 신경망 비유에서 온톨로지로

신경망에서 가중치는 학습으로 결정된다.
이 시스템에서 가중치 대응물:

| 개념 | 구현 |
|------|------|
| edge.strength | 0.1~1.0 (이미 있음) |
| 레이어 간 거리 페널티 | 인접 레이어: ×1.0, 2단계 건너뛰기: ×0.5, 3단계+: ×0.2 |
| 방향 가중치 | 구체→추상 (abstracted_from): 강함, 추상→구체 (governs): 더 강함 |
| 시간 가중치 | 최근 노드일수록 recall()에서 boost |
| 반증 페널티 | contradicts edge: ×(-1) 방향으로 영향 |

**recall() 적용 시**:
"어떤 결정 검색 → 그 결정을 추상화한 원칙 자동 탐색 → 원칙의 상위 세계관까지 트리 탐색 → 다층 컨텍스트 구성"

---

## 현재 3레이어 → 6레이어 확장 제안

### 기존 3레이어 (단순)
```
Layer 3: 나는 어떤 사람인가 (Identity)
Layer 2: 나는 어떻게 생각하는가 (Concepts)
Layer 1: 나는 무엇을 했는가 (Operations)
```

### 확장 6레이어 (철학/미학 통합)

```
┌─────────────────────────────────────────────┐
│ Layer 5: 존재/미학 (Being & Aesthetics)      │
│   — "무엇이 아름다운가, 무엇이 옳은가"         │
│   Axiom · Value · Aesthetic · Wonder · Aporia│
├─────────────────────────────────────────────┤
│ Layer 4: 세계관 (Worldview)                  │
│   — "세상은 어떻게 작동하는가"                │
│   Belief · Philosophy · Lens · Ideology      │
├─────────────────────────────────────────────┤
│ Layer 3: 원칙/정체성 (Principles & Identity) │
│   — "나는 무엇을 따르는가"                    │
│   Principle · Identity · Boundary · Vision   │
│   Paradox · Mental Model                     │
├─────────────────────────────────────────────┤
│ Layer 2: 개념/패턴 (Concepts & Patterns)     │
│   — "반복되는 구조는 무엇인가"                │
│   Pattern · Framework · Heuristic            │
│   Trade-off · Tension · Signal · Metaphor    │
├─────────────────────────────────────────────┤
│ Layer 1: 행위/사건 (Actions & Events)        │
│   — "나는 무엇을 했는가"                      │
│   Decision · Workflow · Plan · Experiment    │
│   Failure · Tool · Skill · Ritual · Goal     │
│   AntiPattern · Breakthrough · Evolution     │
├─────────────────────────────────────────────┤
│ Layer 0: 관찰/경험 (Raw Experience)          │
│   — "무엇이 일어났는가"                       │
│   Observation · Evidence · Assumption        │
│   Context · Trigger · Conversation           │
└─────────────────────────────────────────────┘
```

---

## 레이어별 타입 상세

### Layer 5: 존재/미학
| 타입 | 정의 |
|------|------|
| `Axiom` | 증명 불필요한 근본 가정. 의심하지 않는 것. |
| `Value` | 무엇을 좋다고 여기는가. 가치 판단의 기준. |
| `Aesthetic` | 아름다움의 기준. 우아함, 날카로움의 정의. |
| `Wonder` | 경이로움. 탐구를 유발하는 것. 미학 전공의 핵심. |
| `Aporia` | 해결 불가능한 것으로 남겨두는 것. Paradox와 다름 — 이건 열린 채로 둔다. |

### Layer 4: 세계관
| 타입 | 정의 |
|------|------|
| `Belief` | 확실하지 않지만 믿는 것. Principle보다 약함. |
| `Philosophy` | 삶/시스템에 대한 철학적 입장. |
| `Lens` | 세상을 바라보는 특정 프레임. 같은 사실도 다르게 보임. |
| `Ideology` | 체계화된 신념 집합. |

### Layer 3: 원칙/정체성
| 타입 | 정의 |
|------|------|
| `Principle` | 행동을 규율하는 원칙. (기존 유지) |
| `Identity` | 나는 누구인가. (기존 유지) |
| `Boundary` | 넘지 않는 선. 거부하는 것. |
| `Vision` | 장기 미래 방향. Goal보다 추상적. |
| `Paradox` | 모순처럼 보이지만 공존하는 것. |
| `Mental Model` | 세상의 특정 부분을 이해하는 방식. |

### Layer 2: 개념/패턴
| 타입 | 정의 |
|------|------|
| `Pattern` | 반복 확인된 구조. (기존 유지) |
| `Framework` | 여러 패턴을 묶은 체계. (기존 유지) |
| `Heuristic` | 경험칙. "대체로 ~하면 된다." |
| `Trade-off` | A를 얻으면 B를 잃는 구조. |
| `Tension` | 두 힘의 팽팽한 긴장. (기존 유지) |
| `Signal` | Pattern이 되기 전 단계의 조짐. |
| `Metaphor` | 비유. (기존 유지) |
| `Connection` | 새로운 연결 발견. (기존 유지) |

### Layer 1: 행위/사건
| 타입 | 정의 |
|------|------|
| `Decision` | 의사결정. (기존 유지) |
| `Workflow` | 절차. (기존 유지) |
| `Plan` | 구현 계획 문서. (**신규**) |
| `Experiment` | 실험. (기존 유지) |
| `Failure` | 실패. (기존 유지) |
| `AntiPattern` | 반패턴. (기존 유지) |
| `Breakthrough` | 돌파구. (기존 유지) |
| `Evolution` | 시스템 진화 이력. (기존 유지) |
| `Tool` | 도구. (기존 유지) |
| `Skill` | 스킬. (기존 유지) |
| `Ritual` | 반복 루틴. Workflow보다 개인적. (**신규**) |
| `Goal` | 목표. (기존 유지) |

### Layer 0: 관찰/경험
| 타입 | 정의 |
|------|------|
| `Observation` | 단순 관찰 사실. 원자적. (**신규**) |
| `Evidence` | 주장을 뒷받침하는 데이터/사례. (**신규**) |
| `Assumption` | 검증되지 않은 전제. (**신규**) |
| `Context` | 배경 조건, 상황 정보. (**신규**) |
| `Trigger` | 어떤 행동/결정을 유발하는 조건. (**신규**) |
| `Conversation` | 원시 대화 데이터. (기존 유지) |
| `Narrative` | 스토리 형식 서술. (기존 유지) |
| `Preference` | 선호. (기존 유지) |
| `Question` | 미해결 질문. (기존 유지) |

---

## 레이어 간 관계 타입

### 상향 (구체 → 추상)
- `abstracted_from` — "이 패턴은 이 관찰들에서 추상화됨"
- `generalizes_to` — "이 결정은 이 원칙으로 일반화됨"
- `led_to_understanding` — "이 실패가 이 원칙을 낳음"
- `crystallized_into` — "여러 Observation이 하나의 Axiom으로 결정화됨"

### 하향 (추상 → 구체)
- `governs` — "이 원칙이 이 결정을 규율함"
- `instantiated_as` — "이 철학이 이 워크플로우로 구현됨"
- `expressed_as` — "이 가치가 이 패턴으로 표현됨"
- `constrains` — "이 경계가 이 행동을 제약함"

### 레이어 내부 (수평)
기존 관계 타입 유지: `supports`, `contradicts`, `parallel_with`, `led_to`, `caused_by` 등

---

## API 비용 현실

| 시나리오 | 비용 |
|---------|------|
| 현재 (26 타입, 4003 노드) | ~$0.04 |
| 확장 (50 타입, 4003 노드) | ~$0.06 (system prompt +300 tokens) |
| 2단계 분류 (레이어→타입 순) | ~$0.08 |
| 재분류 시 (변경분만) | 거의 0 |

**결론**: 타입을 50개로 늘려도 비용 영향 미미.
관건은 **분류 정확도** — 타입이 많을수록 GPT가 혼동할 수 있음.
해결책: **2단계 분류 파이프라인** (레이어 먼저, 타입 나중)

---

---

## 들뢰즈 철학과 온톨로지 설계

### 근본적 긴장

내가 처음 제안한 6레이어 계층 구조는 **들뢰즈가 비판한 수목형(arborescent) 사고**다.
뿌리(Axiom) → 줄기(Principle) → 가지(Pattern) → 잎(Observation) — 위계 구조.

들뢰즈는 이 대신 **리좀(Rhizome)**을 제안: 뿌리도 끝도 없고, 어디서든 연결 가능한 수평적 네트워크.

### 핵심 통찰: 그래프 DB는 이미 리좀이다

노드와 edge의 네트워크 자체가 리좀적 구조다.
"레이어"는 구조가 아니라 **분석적 관점** — 같은 데이터를 보는 렌즈.

→ 레이어를 **위계**가 아닌 **강도(Intensity)의 차이**로 재해석해야 한다.

### 들뢰즈 개념의 온톨로지 적용

| 들뢰즈 개념 | 온톨로지 적용 |
|-------------|--------------|
| **잠재성(Virtual)** | 아직 현실화되지 않은 실재. `Signal`이 아직 `Pattern`이 되지 않은 상태 |
| **현실화(Actualization)** | `Signal` → `Pattern` → `Axiom` 흐름. 강도가 결정화되는 과정 |
| **강도(Intensity)** | edge.strength가 단순 유사도가 아닌 "차이의 정도" |
| **차이와 반복** | 같은 패턴의 반복은 매번 차이를 포함. `Evolution` 타입이 이것을 추적 |
| **배치(Assemblage)** | 이질적 노드들의 임시 결합. 클러스터 = Assemblage |
| **탈영토화** | `Unclassified`, `Line_of_Flight` — 분류 거부, 기존 패턴 이탈 |
| **사건(Event)** | 단순 발생이 아닌 의미론적 사건. 변화를 유발하는 것 |
| **도주선(Line of Flight)** | 기존 패턴을 벗어나는 이탈. 새로운 영토로 향하는 벡터 |

### 들뢰즈적 신규 타입

| 타입 | 레이어 | 정의 |
|------|--------|------|
| `Becoming` | 2 | 생성 중인 것. Being이 아닌 과정 자체 |
| `Virtual` | 5 | 잠재적인 것. 아직 현실화되지 않았지만 실재함 |
| `Event` | 0→1 | 들뢰즈적 사건. 의미론적 단절 |
| `Line_of_Flight` | 1→? | 기존 영토에서의 이탈. 탈영토화 벡터 |
| `Assemblage` | 2 | 이질적 요소들의 임시적 결합 체 |
| `Intensity` | 전층위 | 측정 불가능한 질적 차이 자체 |
| `Fold` | 4 | 라이프니츠-들뢰즈의 주름. 내부와 외부의 접힘 |

### 레이어를 강도로 재해석

```
높은 강도 (존재론적 진동)
  Layer 5: Virtual · Axiom · Wonder · Aporia · Fold

중고 강도 (개념화된 차이)
  Layer 4: Belief · Philosophy · Lens · Becoming

중간 강도 (패턴화)
  Layer 3: Principle · Identity · Mental Model · Paradox

낮은 강도 (개념적 결정)
  Layer 2: Pattern · Framework · Heuristic · Trade-off · Assemblage

매우 낮은 강도 (행위적 결정)
  Layer 1: Decision · Plan · Workflow · Experiment · Line_of_Flight

원초적 강도 (순수 차이)
  Layer 0: Observation · Event · Trigger · Conversation
```

### 리좀적 검색의 의미

recall()이 "이 결정 → 원칙 → 세계관"으로 올라가는 게 아니라:
**어디서든 시작해서, 강도를 따라 연결을 탐색**.

`Observation`에서 `Axiom`으로 직접 연결될 수도 있다.
`Line_of_Flight`는 모든 레이어 경계를 무시하고 연결될 수 있다.

---

## 미결 질문

1. 수목형 레이어 vs 리좀적 강도 — 두 관점을 어떻게 실용적으로 결합할 것인가
2. `Virtual` 타입 — GPT가 "이것이 아직 현실화되지 않은 잠재성인가"를 어떻게 분류하나
3. `Line_of_Flight` — 기존 패턴 이탈을 자동 감지할 수 있는가
4. `Aporia` vs `Paradox` — 해결 불가로 열어두는 것(Aporia) vs 공존하는 모순(Paradox)
5. 레이어 간 가중치 감쇠 수치 — 실험으로 조정 필요
6. Paul의 들뢰즈적 렌즈가 실제로 어떤 타입/관계에 가장 강하게 반영되어야 하는가

---

## 다음 단계

→ 전체 설계도는 **05-full-architecture-blueprint.md** 참조.

- [ ] 2단계 분류 파이프라인 구현 (레이어 먼저)
- [ ] ontology/schema.yaml에 `layer` 필드 추가
- [ ] recall()에 레이어 탐색 로직 추가
- [ ] 실험: 같은 데이터 3레이어 vs 6레이어 분류 결과 비교
