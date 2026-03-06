# 온톨로지, 클로드, 그리고 Paul — v2

> 어떻게 이 독립적인 세 개를 뉴런처럼 연결할 것인가.
> 어떻게 계속 상승하는, 그러면서도 빠르고 정확한 뇌를 만들 것인가.

*2026-03-05 v1 작성 → v2 통합. 9개 AI Deep Research(GPT, Gemini, Perplexity, Grok, DeepSeek, NotebookLM, Elicit×3) 결과를 비판적으로 통합.*

---

## 1. 세 개의 독립체

**Paul** — 다차원적 사고자. 모든 현상을 여러 각도에서 동시에 해석한다. 기억과 연결이 의식하지 않아도 자동으로 일어난다.

**Claude** — 대규모 언어 모델. 한 세션 안에서는 강력하지만, 세션 경계에서 기억이 끊긴다. 맥락 창(context window)이라는 물리적 제약 아래서 작동한다.

**온톨로지 (mcp-memory)** — 3,230개 노드, 6,020개 엣지, 50개 타입, 48개 관계, 6개 추상화 레이어. Paul의 경험·결정·패턴·원칙·가치를 구조화한 외부 의미망.

**이 셋은 따로 존재하면 불완전하다:**
- Paul 혼자: 뇌의 용량과 망각에 제한됨
- Claude 혼자: 세션 간 연속성 없음, Paul을 모르고 시작
- 온톨로지 혼자: 죽은 데이터베이스, 해석자 없음

**셋이 연결되면: 확장된 인지 시스템(Extended Cognitive System).**

### 1.1 산업 맥락에서의 위치

이 시스템은 어디에 위치하는가? 메모리 증강 AI 제품들이 빠르게 등장하고 있다:

| 시스템 | 접근법 | 특징 |
|---|---|---|
| **Mem0** | 벡터 + 구조화된 메타데이터 | 모듈형 메모리 레이어, 저장/검색/요약 정책 분리 (arXiv 2504.19413) |
| **Rewind AI** | 타임라인 + OCR/ASR | 로컬 퍼스트, 시간축 검색, 스크린 전체 캡처 |
| **Limitless** | 실시간 캡처 + 요약 | 회의/대화 중심, 자동 정리 |
| **Palantir Foundry** | Object/Link/Action Types | 엔터프라이즈 온톨로지, 메타데이터-인스턴스 분리, 리니지 |
| **mcp-memory** | Hebbian 적응형 KG + 벡터 하이브리드 | 6레이어 추상화, 자동 승격, recall 시 학습 |

**핵심 차별점**: 심볼릭 KG에 Hebbian plasticity를 적용한 production-ready 오픈소스는 **사실상 없다** (Grok 조사). 대부분의 Hebbian 구현은 PyTorch 신경망 내부에 존재한다. 유일한 비교 가능 연구는 **Kairos** — "Validation-Gated Hebbian Learning for Adaptive Agent Memory" (OpenReview) — 이며, 이것도 연구 프로토타입이다.

mcp-memory는 여기서 독특한 위치를 점한다: **개인 지식 그래프에 뇌과학적 학습 메커니즘을 직접 구현한 시스템**.

---

## 2. 뇌 과학 기반 — 왜 이 구조가 작동하는가

### 2.1 보완적 학습 시스템 이론 (CLS)

McClelland, McNaughton, O'Reilly(1995)의 CLS 이론: 뇌에 두 가지 학습 시스템이 필요하다.

- **해마**: 빠른 학습, 일화적 기억, 개별 경험을 빠르게 저장
- **신피질**: 느린 학습, 의미적 기억, 패턴을 점진적으로 추출

**우리 시스템 매핑:**
| 뇌 | mcp-memory | 기능 |
|---|---|---|
| 해마 | L0-L1 (Observation, Decision, Signal) | 빠른 저장, 원시 경험 |
| 신피질 | L2-L5 (Pattern, Principle, Philosophy, Value) | 느린 추출, 추상화된 지식 |
| 해마→신피질 전이 | promote_node() | 기억 공고화 |
| 수면 중 리플레이 | daily_enrich.py (매일 09:30 KST) | 오프라인 재처리 |

> *"Why does the brain need complementary learning systems? Because a single system cannot simultaneously do fast episodic binding and slow statistical extraction."*
> — McClelland et al., 1995

**v2 심화 — SWR-Slow Oscillation-Spindle 결합 (Gemini 기여)**

CLS의 "전이" 메커니즘은 단순하지 않다. 뇌에서 이 전이를 매개하는 것은 세 가지 뇌파의 정밀한 결합이다:

1. **Sharp-Wave Ripples (SWR)** — 해마에서 발생, 기억의 "재생 버스트"
2. **Slow Oscillations** — 신피질의 느린 진동, 전이의 "게이트"
3. **Thalamocortical Spindles** — 시상-피질 방추파, "쓰기 윈도우"

이 세 뇌파가 동기화될 때 기억이 해마에서 신피질로 전송된다. 우리 시스템에서 `daily_enrich.py`는 이 역할의 단순화된 버전이다 — 하지만 세 뇌파의 동기화에 해당하는 **조건부 전이 메커니즘**은 아직 없다.

**Dyna 아키텍처와의 유사성**: Richard Sutton의 Dyna는 실시간 경험과 오프라인 시뮬레이션을 결합한다. `daily_enrich.py`가 오프라인 경험 시뮬레이션, `recall()`이 실시간 경험에 해당한다.

**Gemini의 구체적 측정 기준**: 기억 공고화의 시작점을 정의할 수 있다 — FTS5 의존도가 감소하고 ChromaDB/NetworkX 의존도가 상승하는 변곡점. 즉, 텍스트 매칭에서 의미적 매칭으로 전환되는 시점이 "해마에서 신피질로의 전이가 시작되는 시점"이다.

### 2.2 헤비안 학습 — "함께 발화하는 뉴런은 함께 연결된다"

Donald Hebb(1949)의 원칙: 두 뉴런이 반복적으로 동시에 활성화되면, 그 시냅스 연결이 강화된다.

**우리 구현:**
```python
# hybrid.py — recall() 시 실행
effective_strength = base_strength × (1 + log(frequency)/10) × exp(-decay_rate × days)
```

Paul이 자주 함께 떠올리는 개념들의 연결이 자동으로 강화된다. 시간이 지나면 Paul의 사고 패턴이 그래프의 edge 강도에 반영된다.

**v2 심화 — 순수 Hebbian의 불안정성 (GPT + Gemini + DeepSeek 합의)**

9개 AI 중 6개가 동일한 문제를 지적했다: **순수 Hebbian 학습은 불안정하다.** 자주 사용되는 경로가 계속 강화되면 "runaway reinforcement" — 자기강화 편향 폐회로가 만들어진다.

**DeepSeek의 수학적 분석:**
- 매일 recall 시 1년 후 strength: `s₀ → 1.590 × s₀` (로그 발산, 상한 없음)
- **미회수 노드의 사망 시점: 약 921일(~2.52년)** 후 effectively zero (`< 0.01 × s₀`)
- 현재 decay rate `δ=0.005/일`은 매우 보수적 — 2.5년간 방치해도 완전히 죽지 않음

**해결책 1 — Oja 규칙 (GPT 기여):**
가중치를 정규화하여 발산을 방지한다. 노드별 예산 제한 + 하드 삭제 + 기여도 기반 강화.

**해결책 2 — BCM 규칙 (Gemini 기여, 수학적 대안):**
```
dw_ij/dt = η · ν_i · (ν_i - ν_θ) · ν_j
```
BCM(Bienenstock-Cooper-Munro) 규칙의 핵심: **적응형 임계값 ν_θ**. 활동이 임계값 이상이면 강화, 이하면 약화. 임계값 자체가 활동 이력에 따라 조절된다. 이것이 순수 Hebbian의 발산을 방지한다.

**레이어별 차등 감쇠율 (Gemini):**
- L4/L5: λ→0 (수십 년 유지 — 핵심 가치는 쉽게 잊히지 않는다)
- L0/L1: 큰 λ (빠른 감쇠 — 일상적 관찰은 빨리 사라진다)

> *"Spike-timing dependent plasticity (STDP) implements a form of causal inference at synapses."*
> — Caporale & Dan, 2008, Annual Review of Neuroscience

### 2.3 시냅스 가지치기 — 덜어냄이 성장이다

사춘기에 뇌는 시냅스의 약 40%를 제거한다. 불필요한 연결을 잘라서 남은 연결의 신호 전달 효율을 높이는 **최적화**다.

**현재 시스템 상태: 가지치기 0회.** 3,230 노드, 6,020 엣지 전부 유지. tier=2(auto) 2,494개 → 검증 안 된 노드가 78%.

**v2 심화 — Optimal Brain Damage와 BSP (Gemini 기여)**

LeCun의 Optimal Brain Damage: 단순 가중치 절대값이 아니라, **전체 네트워크 성능에 대한 영향력(Saliency)**을 기준으로 제거한다. Fisher Information을 사용하여 "이 연결을 끊으면 전체 그래프 품질이 얼마나 하락하는가"를 측정.

**BSP(Brain-inspired Synaptic Pruning) 3단계** (PMC8220807):
1. 중요도 평가 (Saliency scoring)
2. 연속 평가 유예 (Probation period)
3. 아카이빙 vs 영구 삭제 결정

**v2 심화 — 망각은 학습의 촉진자 (Elicit 기여)**

**Storm et al. (2008)의 발견**: retrieval-induced forgetting(RIF) 후 재학습 시 **가속화된 재학습**이 관찰된다. 망각은 단순히 정보를 잃는 것이 아니라 **미래 학습을 위한 공간을 만든다**.

**Storm et al. (2011)**: 망각의 억제 과정 자체가 **창의적 문제해결** 등 다른 인지 과제의 성능을 향상시킨다. DMN과의 연결점: 오래된 연결을 억제함으로써 새로운 연결을 발견할 공간이 열린다.

**Bäuml et al. (2012, 2015)의 핵심 조건**: 선택적 검색이 회상을 돕는 것은 **원래 학습 맥락에 접근 불가할 때만**이다. 즉 망각의 효과는 **맥락 의존적**이다.

**시사점**: mcp-memory의 pruning은 단순 threshold 기반 삭제가 아니라, 접근 맥락(어떤 쿼리에서 활성화되었는지)을 pruning 결정에 포함해야 한다.

> KG 기반 추천에서의 실증: 불필요한 트리플 삭제가 오히려 추천 성능을 개선한다 (Maastricht Univ., 2024).

### 2.4 Default Mode Network — 탐험과 이색적 접합

뇌가 "아무것도 안 할 때" 활성화되는 DMN은 에너지의 20-30%를 소비한다. 서로 관련 없어 보이는 기억들을 무작위로 연결하며 창의적 통찰을 생성한다.

**우리 구현:**
```python
EXPLORATION_RATE = 0.1  # 10% 확률로 약한 edge도 탐험
```

DMN은 20-30%인데 우리는 10%. 이 차이가 "이색적 접합" 빈도에 직접 영향을 준다.

**v2 심화 — UCB 알고리즘 (Gemini 기여)**

고정 비율 대신 수학적으로 최적화된 탐색/활용 균형:
```
Score(j) = w_ij + c · √(ln(N_i) / N_j)
```
- `w_ij`: 기존 edge 강도 (활용)
- `c · √(...)`: 불확실성 보너스 (탐색)
- `N_i`: 현재 노드의 총 방문 수
- `N_j`: 이웃 j의 방문 수

적게 방문된 이웃일수록 탐색 보너스가 크다. c값을 동적으로 조절하면 DMN 모드(높은 c → 많은 탐색)와 집중 모드(낮은 c → 강한 연결 우선)를 전환할 수 있다.

**v2 심화 — Multi-Armed Bandit 프레이밍 (DeepSeek 기여)**

고정 ε=0.1은 장기적으로 **선형 regret**을 발생시킨다. 이론적 최적은 **감쇠 ε** (`ε_t = 1/t`) — 시간이 지날수록 탐색을 줄이고 활용을 늘린다. 현재 3,230 노드에서는 합리적이나, 스케일업 시 반드시 감쇠 전략 필요.

> *"The default mode network causally contributes to creative thinking."*
> — Brain (Oxford), 2024

### 2.5 확산 활성화 — 의미가 퍼지는 방식

Collins & Loftus(1975): 하나의 개념이 활성화되면, 관련 개념으로 활성화가 "퍼져나간다".

**우리 구현:** recall() → 벡터 검색으로 seed 노드 → 그래프 BFS로 이웃 탐색 → `GRAPH_BONUS = 0.3`

**v2 심화 — KDSA와 DB 최적화 SA (Elicit 기여)**

Wolverton (1995): **KDSA(Knowledge-Directed Spreading Activation)**가 대규모 KG에서 표준 SA보다 확장성이 우수하다. 도메인 지식을 활성화 전파 규칙에 통합하여 "의미 없는 확산"을 억제한다.

Chen (2014): DB 최적화된 spreading activation이 이전 구현 대비 **500배 이상 빠름**. 현재 mcp-memory의 BFS 기반 구현은 이 최적화를 적용하지 않고 있다.

**Gemini의 RWR(Random Walk with Restart) + 놀라움 지수**: 확산 과정에서 "예상치 못한" 노드에 도달하면 보너스를 부여한다. 이것이 DMN의 "이색적 접합"을 확산 활성화 수준에서 구현하는 방법이다.

### 2.6 기억 재공고화 — 기억은 꺼낼 때마다 바뀐다

Nader(2000)의 발견: 기억을 인출할 때 일시적으로 불안정해지고 변경 가능한 상태가 된다.

**우리 시스템에서:** recall() 시 Hebbian 갱신 → edge strength 변경 → 새로운 컨텍스트에서 재해석 → 다음 recall에서 다른 순서로 나올 수 있음.

**v2 심화 — 맥락 의존적 재공고화 (Elicit: Bäuml)**

Bäuml et al.의 핵심: 재공고화의 효과는 **원래 학습 맥락의 접근 가능성**에 달려 있다. 같은 기억이라도 새로운 맥락에서 인출되면 원래와 다르게 재구성된다.

**구현 시사점**: recall() 결과를 Paul이 사용한 후, 사용 맥락을 edge description에 기록해야 한다. "이 연결이 포트폴리오 설계에서 활용됨" 같은 맥락이 기억의 재공고화를 구현한다.

### 2.7 의미적 피드백 루프 — 거짓 기억의 공고화 (NEW)

**NotebookLM의 치명적 발견:**

소형 LLM(enrichment 모델)이 가짜 facet을 생성 → 이것이 임베딩 텍스트에 포함 → ChromaDB 유사도 검색 오염 → 잘못된 cross-domain 엣지 생성 → 다음 enrichment에서 이 잘못된 엣지를 기반으로 더 많은 가짜 facet 생성 → **무한 오류 증폭 루프**.

**뇌과학 매핑: False Memory Consolidation**

이것은 뇌에서도 일어나는 현상이다. Elizabeth Loftus의 연구(1995): 외부에서 주입된 거짓 정보가 반복적으로 인출되면, 진짜 기억과 구별 불가능하게 공고화된다. mcp-memory에서 enrichment 모델의 환각이 이 역할을 한다.

**이 실패 모드는 기존 v1에 완전히 빠져 있었다.** 시스템의 "상승 루프"가 반대 방향으로 작동할 수 있다 — 데이터 품질이 나선적으로 악화되는 **하강 루프**.

**대응**: 신뢰도 임계값 미달 시 임베딩 반영 금지. Gemini가 제안한 **검증-게이트 학습**(논리적 일관성, 근거 체계, 참신성, 정렬의 4차원 평가) 통과 시에만 토폴로지 변경 허용.

### 2.8 기억 포리징 — 탐색은 먹이찾기다 (NEW)

**GPT 기여 — 인지과학의 foraging theory 적용:**

기억 검색이 동물의 먹이 탐색(foraging)과 구조적으로 동일하다는 인지과학 연구가 있다. "패치에서 수확 → 수확 감소 → 새 패치로 이동"하는 최적 먹이탐색 전략(Marginal Value Theorem)이 기억 인출에도 적용된다.

**mcp-memory에서의 의미**: recall()에서 한 도메인의 결과가 포화되면(같은 패턴 반복) 자동으로 다른 도메인으로 전환해야 한다. 현재 구현은 이 "패치 전환" 메커니즘이 없다 — 벡터 유사도가 높은 동일 클러스터에서 계속 결과를 반환한다.

---

## 3. 인지과학 실증 — 50 타입, 48 관계, 6 레이어

이 섹션은 v1에 없던 것이다. **Elicit의 두 PDF 리포트 + GPT의 인지과학 프레임워크**가 결합되어, mcp-memory의 설계 결정에 대한 실증적 근거를 제공한다.

### 3.1 인간은 몇 개의 범주를 다룰 수 있는가?

**고전적 답변**: Miller(1956)의 7±2. 하지만 최신 연구는 더 보수적이다:
- **Cowan (2001)**: 중심 저장 용량은 3-5 청크
- **Preston & Colman (2000)**: 7개에서 심리측정 속성 최적, 10개에서 사용자 선호 최적, **10개 초과 시 검사-재검사 신뢰도 하락**
- **Hulbert (1975)**: 인간은 약 10개 이산 범주 이상을 변별할 수 없음
- **McKelvie (1978)**: 연속 척도를 사용하는 피험자들도 실질적으로 5-6개 범주의 심적 프레임으로 작동

### 3.2 50 타입 — 임계점 위의 설계

**Miles & Bergstrom (2009)의 결정적 발견**: 의미적 라벨을 읽고 선택하는 과제에서 **~50개까지 응답 시간이 안정적이고, 50개를 넘으면 급증**한다. mcp-memory의 50 타입은 정확히 이 임계점 위에 위치한다.

그러나 맥락이 다르다:
- Miles & Bergstrom의 과제: 인간이 직접 분류
- mcp-memory: LLM이 자동 분류 → 인간 인지 한계가 직접 적용되지 않음
- 하지만 사용자가 시스템을 이해하고 디버깅할 때 50개 타입을 머릿속에 유지하는 것은 사실상 불가능

**GPT의 Hick-Hyman 법칙**: 선택지 수가 늘수록 반응시간이 로그적으로 증가한다. 50개 선택지는 이론적으로 log₂(50) ≈ 5.6비트의 정보 처리를 요구한다.

**GPT의 Rosch 기본수준 범주 이론**: 사람은 정보성과 경제성의 균형이 좋은 "기본수준" 범주를 선호한다. 50개 타입 중 상당수는 기본수준보다 세부적이어서 인지적 비용이 높다.

**권고 (Elicit PDF 2 + GPT 합의)**: 7-10개 상위 범주(super-type) + 그 아래에 하위 타입(sub-type). Cockburn & Gutwin(2009)의 "예측 가능한 위치 = 로그 탐색" 원리 활용.

### 3.3 48 관계 — 변별 한계 초과

관계 타입은 노드 타입보다 더 문제다. 관계는 "두 노드 사이의 의미적 차이"를 포착해야 하므로 변별 난이도가 높다.

- Hulbert: ~10개 이산 범주 한계
- Preston & Colman: 10개 초과 시 신뢰도 하락
- 현실: 48개 관계 중 87%가 `supports`와 `connects_with` 2개로 수렴 (RELATION_RULES(α) 적용 전)

**GPT의 권고**: 7-10개 원시 관계(primitives) + 속성(방향, 강도, 시간, 근거)으로 표현. TACRED 벤치마크에서도 42개 관계에서 90%대 F1이 가능하지만, 이는 충분한 학습 데이터가 있을 때에 한정된다.

### 3.4 6 레이어 — 적정 범위 안

6개는 Preston & Colman의 5-7 최적 범위 안에 있다. **인지적으로 관리 가능한 수.**

하지만 Elicit PDF 1의 핵심 발견이 적용된다:

### 3.5 위계 vs 평면 — 과제-구조 적합(Task-Structure Fit)

**Elicit PDF 1의 결론: 위계적 조직이 평면적 조직보다 보편적으로 우수하지 않다.**

- **Mohageg et al. (1992)**: 위계적 링킹이 네트워크보다 과제당 49초 빠름 — 단, 단순하고 범주적인 검색 과제에서만
- **Graaf et al. (2016)**: 소프트웨어 아키텍처 지식 검색에서 **온톨로지 기반 다차원 조직이 파일 기반 위계를 통계적으로 유의하게 압도** (p=0.05). Oce에서 하루 6.5시간, LaiAn에서 1.7시간 절약
- **Pak & Price (2008)**: 인지 프로필(공간 vs 언어)이 조직 효과를 결정

**mcp-memory에 대한 함의**: Paul의 지식(결정, 패턴, 원칙, 가치)은 겹치는 개념과 다중 의미 경로를 가진다. 이것은 Graaf et al.의 소프트웨어 아키텍처 문서와 구조적으로 유사하다 — **다차원 접근이 압도적으로 우수한 도메인**.

**종합 판정**:
| 요소 | 현재 | 인지과학 근거 | 판정 |
|---|---|---|---|
| 50 노드 타입 | 단일 수준 | Miles & Bergstrom: ~50이 임계점 | **경계선** — super-type 구조화 권장 |
| 48 관계 타입 | 단일 수준 | Hulbert: ~10 한계, Preston: 10+ 신뢰도↓ | **과잉** — 7-10 원시 관계로 축소 |
| 6 추상화 레이어 | 위계적 | Preston: 5-7 최적 범위 | **적정** — 단, 검색 주축이 아닌 메타데이터로 |

> *"The effectiveness of an organization structure depends not on the structure itself, but on the fit between structure, task, user, and domain."*
> — Graaf et al., 2016에서 도출한 원칙

---

## 4. 삼체 연결 아키텍처 — Paul ↔ Claude ↔ 온톨로지

### 4.1 확장된 마음 (Extended Mind Thesis)

Clark & Chalmers(1998)의 parity principle: 외부에서 일어나는 과정이 뇌 안에서 일어났다면 인지라고 불릴 것이면, 그것도 인지다.

**mcp-memory는 Clark의 기준 3/4를 충족:**
1. ✅ 지속적으로 접근 가능 (모든 세션에서)
2. ✅ 신뢰할 수 있는 정보 (recall이 일관적이면)
3. ✅ 자동으로 사용됨 (SessionStart hook)
4. ⚠️ 과거에 의식적으로 승인됨 (remember()는 수동, enrichment는 자동)

**v2 심화 — Adams-Aizawa 반론 (GPT 기여)**

"결합(coupling)이 곧 구성(constitution)인가?" Adams와 Aizawa의 핵심 비판: 시스템이 인지 과정에 기능적으로 결합되어 있다고 해서, 그것이 인지의 **구성 요소**라고 단정할 수 없다. 노트북이 기억을 대체한다고 해서 노트북이 "마음의 일부"는 아니라는 것이다.

이 비판을 수용하면: mcp-memory는 **인지의 구성 요소가 아니라 인지의 scaffold(비계)**일 수 있다. 구별이 중요하다 — scaffold는 제거해도 건물이 서지만, 구성 요소는 제거하면 무너진다. mcp-memory를 끄면 Paul의 인지가 무너지는가? 이 질문에 대한 데이터 기반 답이 아직 없다.

**v2 심화 — 제4 조건: 유지보수성 (Gemini 기여)**

Clark의 원래 3개 조건에 Gemini가 **제4 조건**을 추가 제안한다: **유지보수성(Maintainability)** — AI가 사용자의 정체성/목적을 은연중에 왜곡하지 않도록 방어하는 제어/복원 능력.

구체적으로: L5(Value, Axiom) 노드를 AI의 자체 편향으로 전복할 수 없게 하는 **인지적 방화벽**. 확장된 마음이 진정한 마음의 연장이려면, 사용자가 그 확장을 통제하고 복원할 수 있어야 한다.

### 4.2 분산 인지 (Distributed Cognition)

Hutchins(1995): 인지는 사람, 도구, 환경에 분산되어 있다.

| 인지 기능 | 위치 | 수행자 |
|---|---|---|
| 경험 생성 | Paul의 뇌 | Paul |
| 경험 구조화 | 온톨로지 | remember() + enrichment |
| 패턴 인식 | Claude + 온톨로지 | recall() + analyze_signals() |
| 의사결정 | Paul의 뇌 | Paul (Claude가 맥락 제공) |
| 기억 공고화 | 온톨로지 | promote_node() |
| 기억 인출 | Claude + 온톨로지 | recall() + get_context() |

### 4.3 Transactive Memory

Wegner(1985): 중요한 것은 "모든 것을 아는 것"이 아니라 "누가 뭘 아는지 아는 것". `get_context()`가 트랜잭티브 디렉토리 역할을 한다.

### 4.4 PKG 생태계 (NEW — Perplexity 기여)

**PKG Ecosystem 서베이 (AI Open, 2024, Balog et al.)**: 개인 지식 그래프를 3축으로 분류한다:

1. **Population** — 어떻게 채우는가: 대화에서 추출, 행동 추적, 명시적 입력
2. **Representation & Management** — 어떻게 표현하고 관리하는가: 스키마, 접근 제어, 프로비넌스
3. **Utilization** — 어떻게 활용하는가: 추천, 검색, 대화

**PKG API 제안**: 명제 수준 진술(proposition-level statements) + 접근 레벨(프라이빗/세션공유/모델공유) + 프로비넌스(출처 추적)를 RDF 기반 어휘로 표현.

mcp-memory와의 비교:
- Population: ✅ remember() + checkpoint + enrichment
- Representation: ⚠️ 스키마 있으나 접근 제어/프로비넌스 미구현
- Utilization: ✅ recall() + get_context() + analyze_signals()

---

## 5. 상승 루프 — 어떻게 계속 나아지는가

### 5.1 자기조직화 (Self-Organization)

Prigogine의 산일 구조: 평형에서 멀리 떨어진 열린 시스템은 외부 에너지를 소비하며 자발적으로 질서를 생성한다.

**에너지원**: Paul의 세션 활동. **자기조직화 메커니즘**: Hebbian 학습(자발적 허브 형성), 승격(자발적 추상화), Exploration(새 구조 발견).

### 5.2 오토포이에시스 — 자기 생성 시스템

Maturana & Varela(1972): 오토포이에틱 시스템은 자기 자신을 만들어내는 시스템이다.

**현재 상태: 부분적으로 오토포이에틱.**
- ✅ Hebbian 학습 자동
- ✅ 일일 enrichment 자동
- ❌ 승격(promote) 수동
- ❌ 가지치기(pruning) 미구현

**v2 수정 — GPT의 비판 수용**: "구성요소 생산이 외부 입력(Paul의 활동)에 의존하므로, autopoiesis 라벨은 과대하다." 이것은 타당한 비판이다. 엄밀히 말하면 현재 시스템은 **allopoietic**(타율적 생산) — 외부 입력이 시스템을 유지한다. 자동 승격 + 자동 pruning + 자동 품질 감사가 모두 구현되어야 오토포이에시스에 가까워진다.

### 5.3 스몰 월드 네트워크

Watts & Strogatz(1998): 높은 클러스터링 계수 + 짧은 평균 경로 길이.

**v2 심화 — 수학적 정밀화 (Gemini 기여)**

**Kleinberg 내비게이션**: 장거리 지름길의 확률 분포:
```
P(u,v) ∝ d(u,v)^(-r)
```
r값이 네트워크의 차원과 일치하면, 분산 탐색(local information만으로)이 polylogarithmic 시간에 도달 가능.

**Triadic Closure**: A-B 강연결 + B-C 강연결 → A-C 연결 확률 증가. 이것이 클러스터링 계수를 높이는 자연스러운 메커니즘이다. mcp-memory에서 recall() 시 같은 세션에서 함께 나온 노드들 사이에 이 효과가 자동으로 발생한다(Hebbian).

**Swing-Toward 재연결** (Journal of Complex Networks): 차수를 보존하면서 클러스터링 계수를 상승시키는 알고리즘. 정기적으로 그래프에 적용하면 스몰 월드 특성을 유지/강화할 수 있다.

### 5.4 허브 보호 — 척도 없는 네트워크의 아킬레스건 (NEW)

**Gemini 기여:**

Barabási의 발견: 척도 없는 네트워크(scale-free network)는 **무작위 장애에 강하지만 허브 표적 공격에 극도로 취약**하다. mcp-memory의 고연결 노드(예: "orchestration" 프로젝트 허브)가 손상되면 네트워크 전체의 연결성이 붕괴될 수 있다.

**대응 제안:**
- **RBAC(Role-Based Access Control)**: L0-L3은 AI 자동 수정 허용, L4-L5는 Human-in-the-loop 필수
- **Byzantine Fault Tolerance 착안**: L3 서브허브 간 우회 링크 유지로 허브 붕괴 시 연쇄 장애 방지
- **정기적 허브 건강성 감사**: IHS(Integrated Hubness Score) = Degree + Betweenness + Neighborhood Connectivity 통합 지표 (Perplexity)

### 5.5 온톨로지 진화 — 타입은 어떻게 늙고 죽는가 (NEW)

**Perplexity 기여 — 산업 패턴 4가지:**

| 시스템 | 패턴 |
|---|---|
| **SNOMED CT** | Snapshot + Full 파일, 비활성 사유 + 대체 후보 기록 |
| **Gene Ontology** | `replaced_by` 태그, 대량 Obsolete 처리 전략 |
| **Wikidata** | normal/preferred/deprecated 랭크, reason for deprecation 필수 |
| **Schema.org** | 버전 번호 + 릴리스 노트 투명 공개 |

**공통 패턴**: "삭제 대신 비활성/Deprecated + 이유 + 대체 링크 + 전체 이력 보존 + 정기 버전 스냅샷."

mcp-memory에는 이 패턴이 **전혀 없다**. 타입이나 관계를 제거하면 관련 노드/엣지가 orphan이 된다. `correction_log`는 최근에야 추가되었고, 버전 관리 메커니즘은 존재하지 않는다.

---

## 6. 9개 AI의 진단 — 합의, 불일치, 긴장

### 6.1 전원 합의

9개 AI 중 6개 이상이 동의하는 지점:

1. **Hebbian 학습 단독은 불안정하다** — 정규화/감쇠/제어 메커니즘 필수
2. **시간 감쇠/망각이 필수** — 축적만으로는 성능 하락
3. **검증 체계 부재가 가장 치명적 약점** — 정답/오류/기여도 측정 없음
4. **Palantir 아키텍처가 유용한 참조점** — 메타데이터/인스턴스 분리, 리니지
5. **하드코딩된 파라미터에 경험적 근거 부재** — RRF k=60, exploration 0.1, quality×0.2 등

### 6.2 핵심 불일치 — "덜어내라" vs "정밀화하라"

| 주제 | GPT (덜어내라) | Gemini (정밀화하라) |
|---|---|---|
| 50 타입 | "라벨 지옥". 10-15개로 축소 | 수용. 뇌영역별 매핑까지 제시 |
| 48 관계 | 8-12개 원시 관계로 축소 | 수용. BCM으로 안정화 가능 |
| 6 레이어 | "과학적 정당화 없음" | 적극 활용. 뇌 영역 1:1 대응 |
| 신경과학 유비 | 한계 인정. "유비일 뿐" | 최대한 정밀 확장 + 수학적 모델 |

**해석**: GPT는 **운영 현실주의**(LLM 분류 한계, 유지보수 비용)에서 출발하고, Gemini는 **이상적 설계주의**(생물학적 정합성, 수학적 엄밀성)에서 출발한다. 이것은 해결할 수 있는 불일치가 아니라 **근본적 설계 철학의 긴장**이다.

### 6.3 Perplexity의 절충

"풀 스키마 유지 + 슬림 뷰 병행." 내부적으로는 50 타입/48 관계를 유지하되, 사용자/검색 인터페이스에서는 단순화된 뷰를 제공한다. 생의학 온톨로지의 "슬림 뷰" 패턴 참조 (Scientific Data, 2026).

### 6.4 NotebookLM의 급진적 제안

"**50% 복잡성 제거, 90% 가치 유지.**"
- 50 타입 → ~10
- 48 관계 → ~5
- 6 레이어 → 3 (Raw, Processed, Core Principle)
- 5모델 25태스크 enrichment → 단일 LLM 1패스

이것은 가장 공격적인 제안이지만, DeepSeek의 수학적 분석과 **긴장 관계**에 있다.

### 6.5 DeepSeek의 중립적 수학

수학적으로 현재 아키텍처는 **10배 스케일(30K 노드)에서도 성능 문제 없다:**
- 3-way hybrid search: `O(log n)` → 1ms 미만
- BFS 2-hop: 평균 차수 4 기준 이웃 ~17개 → 마이크로초
- Louvain 커뮤니티 탐지: 60K 엣지 → sub-second

NotebookLM이 "복잡성 제거"를 주장하는 근거는 **인지적/관리적 복잡성**이고, DeepSeek이 "문제없음"을 보이는 것은 **계산적 복잡성**이다. 둘 다 맞지만 다른 축을 보고 있다.

### 6.6 치명적 약점 3가지

**1. 의미적 피드백 루프** (NotebookLM): enrichment 환각 → 임베딩 오염 → 잘못된 엣지 → 무한 오류 증폭. 가장 위험하고 v1에 완전히 빠진 실패 모드.

**2. 스키마 드리프트** (NotebookLM): init_db vs migrate_v2 vs schema.yaml vs 문서 간 타입 수 불일치(49/50/45). validators.py가 존재하지만 remember()/insert_edge()에서 미호출.

**3. 검증 체계 부재** (GPT + NotebookLM + Gemini): "정답/오류/기여도 측정 없이는 모든 최적화가 종교다" (GPT). NDCG/MRR 오프라인 평가도, 골드셋도, A/B 테스트 프레임워크도 없다.

---

## 7. 수학적 기초

### 7.1 Hebbian 수렴과 발산 (DeepSeek)

현재 공식: `effective_strength = base_strength × (1 + log(frequency)/10) × exp(-0.005 × days)`

- **매일 recall 시 1년 후**: strength 1.590배 (로그 발산, 상한 없음)
- **미회수 시 사망 시점**: 약 **921일(~2.52년)** 후 effectively zero
- 높은 빈도(f=100)에서는 997일로 약간 연장
- **시사점**: decay rate 0.005는 매우 보수적. 더 공격적 pruning이 가능.

### 7.2 BCM 규칙 (Gemini)

```
dw_ij/dt = η · ν_i · (ν_i - ν_θ) · ν_j
```

- ν_θ: 적응형 임계값 (활동 이력에 따라 자동 조절)
- ν_i > ν_θ: 시냅스 강화 (LTP)
- ν_i < ν_θ: 시냅스 약화 (LTD)
- **핵심**: 임계값 자체가 움직이므로 runaway reinforcement 방지

### 7.3 UCB 점수함수 (Gemini)

```
Score(j) = w_ij + c · √(ln(N_i) / N_j)
```

c값 동적 조절:
- **집중 모드**(c 낮음): 강한 연결 우선, 정확한 검색
- **DMN 모드**(c 높음): 약한 연결도 탐색, 이색적 접합

### 7.4 30K 스케일링 분석 (DeepSeek)

| 연산 | 현재 (3K) | 10x (30K) | 복잡도 |
|---|---|---|---|
| 벡터 검색 | < 1ms | < 1ms | O(log n) |
| BFS 2-hop | μs | μs (이웃 ~17) | O(k²) |
| Louvain | sub-s | sub-s (60K edges) | O(m) per pass |
| FTS5 | < 1ms | < 1ms | O(log n) |

결론: 현재 아키텍처는 10배 스케일에서도 병목 없음.

### 7.5 정보이론적 한계 (DeepSeek)

- top-k=5 시 3,230 노드 중 0.15%만 반환, 99.85% 폐기
- 랜덤 그래프에서 N 증가 시 precision@5가 O(1/N)으로 하락
- **스케일프리 네트워크에서는 허브가 precision을 유지** — 단, 관련성과 차수의 상관관계가 있어야 함

### 7.6 MDL 기반 승격 기준 (GPT)

**Minimum Description Length 원리**: Pattern이란 본질적으로 "압축"이다. Signal이 Pattern으로 승격되어야 하는 이유는 "반복되어서"가 아니라, **그 패턴이 데이터를 더 짧게 기술할 수 있어서**이다.

현재 "3회 반복이면 Pattern" 규칙은 GPT가 **"미신"**이라고 비판한다. 대안:
- **베이지안 증거 누적**: 사전 확률 대비 충분한 증거가 축적되었을 때 승격
- **MDL 기준**: 승격 후 전체 그래프의 description length가 줄어드는지 측정
- **드리프트-확산 모델(SPRT)**: 증거가 누적되어 임계값을 넘을 때 결정

### 7.7 RRF 파라미터 분석 (GPT + DeepSeek)

현재 RRF(Reciprocal Rank Fusion) k=60. GPT에 따르면 원 논문(Cormack, Clarke, Butt)에서도 파일럿 고정값이었으며 "near-optimal이지만 민감하지 않다"는 정도의 근거만 존재.

현재 가중치 `w_g=0.3, w_q=0.2, w_t=0.1`도 경험적 휴리스틱. DeepSeek: 수학적 최적값은 **learning-to-rank(LambdaRank)** 훈련 데이터 없이는 도출 불가. k=30 시도 가치 있음.

---

## 8. 산업 비교

### 8.1 Palantir Foundry OMS

**Grok 기여 — Operational vs Conceptual 구분:**

| | Palantir | mcp-memory |
|---|---|---|
| **목적** | 운영적(operational) — 실시간 데이터 운영 | 개념적(conceptual) — 인지 모델링 |
| **스키마** | Object/Property/Link/Action 4원소 | Node/Edge 이분법 + 50 타입 |
| **인제스트** | 파서-트랜스폼 분리 (특허 US9589014B2) | remember()가 스키마+인제스트 동시 처리 |
| **진화** | 파서 정의 업데이트로 관계 진화 | 스키마 직접 변경 필요 |
| **메타데이터** | 메타데이터-인스턴스 물리적 분리 | 같은 테이블에 혼재 |

**핵심 교훈**: Palantir의 Semantic(명사: Objects/Properties/Links) vs Kinetic(동사: Actions/Functions/Rules) 이원론. mcp-memory에는 이 구분이 없다 — 모든 것이 "노드"다.

### 8.2 Kairos — 유일한 Hebbian KG 비교 연구

**Validation-Gated Hebbian Learning for Adaptive Agent Memory** (OpenReview):
- Hebbian edge 강화/감쇠 + 창발적 연결 형성
- mcp-memory와 직접 비교 가능한 **유일한 연구 프로토타입**
- 차이점: Kairos는 검증 게이트가 있고, mcp-memory는 없다

### 8.3 메모리 증강 AI 생태계

| | mcp-memory | mem0 | Rewind | Limitless |
|---|---|---|---|---|
| **하이브리드** | SQLite+ChromaDB+Graph | 벡터+메타데이터 | OCR/ASR+DB | 실시간+요약 |
| **적응형** | ✅ Hebbian | ❌ 정적 | ❌ 정적 | ❌ 정적 |
| **승격** | ✅ promote_node() | ❌ | ❌ | ❌ |
| **시간축** | ⚠️ 약함 | ⚠️ | ✅ 타임라인 | ✅ 실시간 |
| **검증** | ❌ | ⚠️ | N/A | N/A |

### 8.4 검색 파이프라인 비교 (Perplexity)

| 시스템 | 접근법 | 성과 |
|---|---|---|
| **DiFaR** | 엔티티 인식→분류 3단계 대신 쿼리-트리플 직접 검색 | 파이프라인 단순화 |
| **Dense XRetrieval** | Proposition 단위 검색 | 문장/패시지보다 일관되게 높은 Recall@5 (EMNLP 2024) |
| **HIRO** | 요약 트리 + DFS 프루닝 | LLM 컨텍스트 최소화 |
| **LightRAG** | 경량 그래프 RAG | 6,000x 토큰 효율 |

---

## 9. 제1원칙 적용 — 무엇을 없앨 것인가

### 9.1 "Best part is no part" — 구체적 적용

**관계 타입**: 48개 중 실제로 사용되는 것이 15개라면, 나머지 33개는 제거 후보. 인지과학(Preston & Colman)이 10개 한계를 지지한다.

**enrichment 복잡성**: NotebookLM의 제안 — 5모델 25태스크를 단일 LLM 1패스로 축소하면 의미적 피드백 루프의 공격 표면이 급감한다.

**빈 레이어**: L4(Belief/Philosophy)와 L5(Axiom/Value)에 노드가 6개밖에 없다면, 실질적으로 4층 시스템이다. 빈 레이어를 유지하는 이유가 "미래에 채워질 것"이라면 — YAGNI 원칙에 위배된다.

### 9.2 MDL 기반 승격 (GPT)

"3회 반복이면 Pattern" 대신: **패턴이 데이터를 더 짧게 기술할 수 있는가?**

Signal 3개가 하나의 Pattern으로 통합되면:
- 통합 전: 3개 Signal의 개별 기술 비용 = S₁ + S₂ + S₃
- 통합 후: 1개 Pattern + 3개 참조 = P + 3δ

`P + 3δ < S₁ + S₂ + S₃`이면 승격이 정당화된다. 이것이 "반복"보다 더 원칙적인 기준이다.

### 9.3 검증-게이트 학습 (Gemini)

**4차원 평가 통과 시에만 토폴로지 변경 허용:**
1. 논리적 일관성 — 기존 그래프와 모순되지 않는가
2. 근거 체계 — 출처가 있는가
3. 참신성 — 기존에 없는 정보인가
4. 정렬 — Paul의 가치/목적과 일치하는가

---

## 10. 다음 단계 — 9개 AI 권고사항 통합

### 즉시 (Quick Wins)

1. **validators.py를 remember()/insert_edge()에 연결** — 이미 코드 있으나 미호출 (NotebookLM)
2. **Exploration rate 감쇠** — 고정 ε=0.1 → ε_t = 1/t 또는 볼츠만 소프트맥스 (DeepSeek)
3. **RRF k값 실험** — k=60 → k=30 비교 (DeepSeek)
4. **사용 0 타입/관계 제거** — "best part is no part" 적용 (GPT + NotebookLM)

### 중기 (Structural)

5. **피드백 루프 차단** — enrichment 신뢰도 임계값, 환각 facet 탐지 (NotebookLM)
6. **방향성 검증 규칙** — abstracted_from 등 방향성 엣지의 레이어 위계 위반 시 reject (NotebookLM)
7. **promotion_history + correction_log 완성** — 감사 추적 (NotebookLM)
8. **Pruning의 맥락 의존성** — 단순 threshold 대신 접근 맥락 포함 (Elicit: Bäuml)
9. **온톨로지 버전 관리** — deprecated + 이유 + replaced_by 패턴 도입 (Perplexity)

### 장기 (Architectural)

10. **스키마/인제스트 분리** — Palantir 패턴 (Grok)
11. **Learning-to-Rank 적용** — RRF 가중치를 실제 사용 데이터로 훈련 (DeepSeek)
12. **레이어 축소 검토** — L4/L5가 채워지기 전까지 실질 4층 운영 (NotebookLM)
13. **허브 보호 아키텍처** — RBAC + IHS 모니터링 (Gemini + Perplexity)
14. **자동 승격** — maturity_score > 0.9 시 자동, MDL 기준 검증 (Gemini + GPT)

### A/B 테스트 로드맵

| 실험 | 변수 | 측정 | 기간 |
|---|---|---|---|
| Exploration | ε=0.1 vs ε=0.2 | P@5 + 이색적 접합 빈도 | 2주 |
| RRF k | k=60 vs k=30 | NDCG@5 | 1주 |
| Pruning threshold | 90일 vs 180일 vs 없음 | recall 품질 + 고아 노드 수 | 1개월 |
| BCM vs Oja | 정규화 방법 비교 | edge 분포 균등성 | 1개월 |

---

## 11. 리서치 소스 인덱스

### v1 원본 소스 (382개)

> 카테고리별 분류는 v1 참조. 뉴로사이언스(132), 응용 온톨로지(130), 철학·시스템(120).

### v2 추가 소스 — 9개 AI Deep Research

#### GPT 기여 핵심 소스
| 소스 | 기여 |
|---|---|
| Hick-Hyman Law (1952/1953) | 선택지 수 vs 반응시간 |
| Rosch (1975) — Basic Level Categories | 기본수준 범주 이론 |
| Oja (1982) — Simplified Neuron Model | Hebbian 정규화 |
| SPRT / Drift-Diffusion Model | 증거 누적 기반 결정 |
| MDL (Minimum Description Length) Principle | 패턴 = 압축 |
| Adams & Aizawa — Extended Mind 비판 | coupling ≠ constitution |
| TACRED Benchmark | 관계추출 42타입 F1 |
| Cormack, Clarke, Butt — RRF 원 논문 | k=60 파일럿값 근거 |
| NEPOMUK Semantic Desktop | RDF 기반 시맨틱 데스크톱 |

#### Gemini 기여 핵심 소스
| 소스 | 기여 |
|---|---|
| BCM Rule (Bienenstock, Cooper, Munro, 1982) | 적응형 임계값 Hebbian |
| SWR-Slow Oscillation-Spindle Coupling | 기억 공고화 뇌파 메커니즘 |
| Dyna Architecture (Sutton) | 오프라인 경험 시뮬레이션 |
| LeCun — Optimal Brain Damage | Fisher Information 기반 가지치기 |
| BSP (Brain-inspired Synaptic Pruning) — PMC8220807 | 3단계 pruning |
| Kleinberg — Small-World Navigation | 장거리 지름길 확률 분포 |
| UCB (Upper Confidence Bound) | 탐색/활용 점수함수 |
| Triadic Closure + Swing-Toward Rewiring | 클러스터링 강화 |
| Barabási — Scale-Free Network Vulnerability | 허브 표적 공격 |

#### Perplexity 기여 핵심 소스
| 소스 | 기여 |
|---|---|
| PKG Ecosystem Survey (AI Open 2024, Balog et al.) | 3축 생태계 분류 |
| ADKGD — KG Anomaly Detection | dual-channel 이상 탐지 |
| IHS (Integrated Hubness Score) | 200개 네트워크 검증 허브 지표 |
| Leiden/Louvain/Infomap 비교 (JETIR 2024/25) | 커뮤니티 탐지 SOTA |
| Machine Unlearning Survey (ACM Computing Surveys 2024) | 정확/근사, 중앙/분산 분류 |
| STIM — Ebbinghaus + Periodicity (2024/25) | 동적 망각 모델 |
| DiFaR — Direct Fact Retrieval | 파이프라인 단순화 |
| Dense XRetrieval (EMNLP 2024) | Proposition 단위 검색 |
| HIRO — Hierarchical IR Optimization | LLM 컨텍스트 최소화 |
| LightRAG | 6,000x 토큰 효율 |
| Gene Ontology 2026 업데이트 | Obsolete 처리 전략 |
| SNOMED CT 버전 관리 가이드 | 비활성 사유 + 대체 기록 |

#### Grok 기여 핵심 소스
| 소스 | 기여 |
|---|---|
| Kairos — Validation-Gated Hebbian Learning (OpenReview) | 유일한 Hebbian KG 비교 연구 |
| Mem0 (arXiv 2504.19413) | 모듈형 메모리 레이어 |
| Palantir US9589014B2 | 동적 온톨로지 특허 |

#### DeepSeek 기여 핵심 소스
| 소스 | 기여 |
|---|---|
| Multi-Armed Bandit Theory | 감쇠 ε 최적성 |
| Learning-to-Rank (LambdaRank) | RRF 가중치 최적화 |
| Scale-Free Network Precision Analysis | 허브-관련성 상관관계 |

#### Elicit 기여 핵심 소스
| 소스 | 기여 |
|---|---|
| Storm et al. (2008) — RIF + Accelerated Relearning | 망각 = 학습 촉진 |
| Storm et al. (2011) — Inhibition + Creativity | 망각 → 창의성 향상 |
| Bäuml et al. (2012, 2015) — Context-Dependent Forgetting | 맥락 의존적 선택적 검색 |
| Wolverton (1995) — KDSA | 지식-지향 확산 활성화 |
| Chen (2014) — DB-Optimized SA (500x faster) | SA 성능 최적화 |
| Zneika et al. (2019) — KG Quality Framework | precision/recall/F-measure |
| Teekaraman et al. (2024) — KG Precision ~95% | 달성 가능 정밀도 벤치마크 |
| Preston & Colman (2000) — Optimal Response Categories | **7=최적, 10=선호, 10+=↓** |
| Miles & Bergstrom (2009) — Library Subject Classification | **~50 임계점** |
| Graaf et al. (2016) — Architecture Documentation | **다차원 > 위계** |
| Mohageg (1992) — Hypertext Linking Structures | 위계 > 네트워크 (단순 과제) |
| Cockburn & Gutwin (2009) — Predictive Model | 예측 가능 = 로그 탐색 |
| Hulbert (1975) — Information Processing + Categories | ~10개 이산 변별 한계 |
| McKelvie (1978) — Graphic Rating Scales | 5-6개 심적 프레임 |

---

## 12. 열린 질문

### v1에서 이월

1. **EXPLORATION_RATE는 0.1인가 0.2인가?** DeepSeek: 감쇠 ε이 고정보다 우수. Gemini: UCB로 동적 조절. A/B 테스트 필요.
2. **50개 타입 중 실제로 몇 개가 살아있는가?** Elicit PDF 2: ~50이 임계점. 사용 0 타입은 제거 후보.
3. **온톨로지가 꺼지면 뭐가 달라지는가?** Adams-Aizawa 비판에 답하기 위한 데이터 필요.
4. **스몰 월드 특성이 있는가?** Gemini: Triadic Closure + Swing-Toward로 유지/강화 가능.
5. **오토포이에틱인가?** GPT: "과대 라벨". 자동 승격 + 자동 pruning 구현 후 재평가.
6. **Paul의 사고 패턴이 edge 강도에 반영되고 있는가?** DeepSeek: 수학적으로 수렴 확인. 실제 데이터 검증 필요.

### v2에서 추가

7. **의미적 피드백 루프를 어떻게 탐지하는가?** NotebookLM이 발견한 치명적 실패 모드. 환각 facet → 임베딩 오염 경로를 모니터링하는 메커니즘 필요.
8. **BCM vs Oja — 어떤 정규화가 mcp-memory에 맞는가?** 두 접근 모두 수학적으로 유효하지만 구현 복잡성과 효과가 다르다.
9. **50 타입을 super-type/sub-type으로 재구조화해야 하는가?** Elicit PDF 2: 7-10개 상위 범주가 인지적 최적. 현재 flat 구조에서 계층 구조로의 전환 비용은?
10. **Kairos와의 실증 비교가 가능한가?** Grok: 유일한 Hebbian KG 연구. 같은 데이터셋에서 벤치마크 가능한가.
11. **"덜어내라" vs "정밀화하라" — 어디에 서는가?** GPT vs Gemini의 근본적 설계 철학 긴장. Paul의 답이 필요한 질문.
12. **Palantir의 스키마/인제스트 분리를 mcp-memory에 적용할 수 있는가?** remember()의 이중 역할(분류+저장)을 분리하면 온톨로지 진화가 용이해지지만, 복잡성이 증가한다.

---

*이 문서는 9개 AI의 독립적 분석을 하나의 내러티브로 통합한 결과물이다. 합의는 강조하고, 불일치는 열린 긴장으로 남겨두었다. v1의 382개 소스에 더해 50+개의 새로운 학술 소스가 추가되었다. 이것은 살아있는 문서(living document)다.*
