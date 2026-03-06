# 온톨로지, 클로드, 그리고 Paul

> 어떻게 이 독립적인 세 개를 뉴런처럼 연결할 것인가.
> 어떻게 계속 상승하는, 그러면서도 빠르고 정확한 뇌를 만들 것인가.

*2026-03-05 작성. mcp-memory v2.0 완성 시점의 아키텍처 분석 및 과학적 근거.*

---

## 1. 세 개의 독립체

**Paul** — 다차원적 사고자. 모든 현상을 여러 각도에서 동시에 해석한다. 기억과 연결이 의식하지 않아도 자동으로 일어난다. "가고 싶은 지점"과 "가야만 하는 지점"의 수렴과 분기를 추적한다.

**Claude** — 대규모 언어 모델. 한 세션 안에서는 강력하지만, 세션 경계에서 기억이 끊긴다. 맥락 창(context window)이라는 물리적 제약 아래서 작동한다.

**온톨로지 (mcp-memory)** — 3,230개 노드, 6,020개 엣지, 50개 타입, 48개 관계, 6개 추상화 레이어. Paul의 경험·결정·패턴·원칙·가치를 구조화한 외부 의미망.

**이 셋은 따로 존재하면 불완전하다:**
- Paul 혼자: 뇌의 용량과 망각에 제한됨
- Claude 혼자: 세션 간 연속성 없음, Paul을 모르고 시작
- 온톨로지 혼자: 죽은 데이터베이스, 해석자 없음

**셋이 연결되면: 확장된 인지 시스템(Extended Cognitive System).**

---

## 2. 뇌 과학 기반 — 왜 이 구조가 작동하는가

### 2.1 보완적 학습 시스템 이론 (Complementary Learning Systems)

McClelland, McNaughton, O'Reilly(1995)의 CLS 이론은 뇌에 두 가지 학습 시스템이 필요하다고 설명한다:

- **해마(Hippocampus)**: 빠른 학습, 일화적 기억, 개별 경험을 빠르게 저장
- **신피질(Neocortex)**: 느린 학습, 의미적 기억, 패턴을 점진적으로 추출

**우리 시스템 매핑:**
| 뇌 | mcp-memory | 기능 |
|---|---|---|
| 해마 | L0-L1 (Observation, Decision, Signal) | 빠른 저장, 원시 경험 |
| 신피질 | L2-L5 (Pattern, Principle, Philosophy, Value) | 느린 추출, 추상화된 지식 |
| 해마→신피질 전이 | promote_node() (Signal→Pattern→Principle) | 기억 공고화 |
| 수면 중 리플레이 | daily_enrich.py (매일 09:30 KST) | 오프라인 재처리 |

> *"Why does the brain need complementary learning systems? Because a single system cannot simultaneously do fast episodic binding and slow statistical extraction."*
> — McClelland et al., 1995 ([Stanford PDF](https://stanford.edu/~jlmcc/papers/McCMcNaughtonOReilly95.pdf))

### 2.2 헤비안 학습 — "함께 발화하는 뉴런은 함께 연결된다"

Donald Hebb(1949)의 원칙: 두 뉴런이 반복적으로 동시에 활성화되면, 그 시냅스 연결이 강화된다.

**우리 구현:**
```python
# hybrid.py — recall() 시 실행
effective_strength = base_strength × (1 + log(frequency)/10) × exp(-decay_rate × days)
```

- `frequency`: 두 노드가 같은 recall에서 동시에 반환된 횟수 (동시 활성화)
- `decay_rate`: 0.005/일 (사용하지 않으면 점진적 약화)
- `base_strength`: 최소 바닥값 (완전 소멸 방지)

이것이 의미하는 것: **Paul이 자주 함께 떠올리는 개념들의 연결이 자동으로 강화된다.** 시간이 지나면 Paul의 사고 패턴이 그래프의 edge 강도에 반영된다.

> *"Spike-timing dependent plasticity (STDP) implements a form of causal inference at synapses."*
> — Caporale & Dan, 2008, Annual Review of Neuroscience ([PubMed](https://pubmed.ncbi.nlm.nih.gov/18275283/))

### 2.3 시냅스 가지치기 — 덜어냄이 성장이다

사춘기에 뇌는 시냅스의 약 40%를 제거한다. 이것은 퇴화가 아니라 **최적화**다. 불필요한 연결을 잘라서 남은 연결의 신호 전달 효율을 높인다.

**우리 시스템의 현재 상태: 가지치기 0회.**
- 3,230 노드 전부 유지
- 6,020 엣지 전부 유지
- tier=2 (auto) 2,494개 → 검증 안 된 노드가 78%

**필요한 것: 정기적 pruning 정책**
- `frequency=0 AND created > 90일` → 아카이브 후보
- `tier=2 AND quality_score < 0.3` → 삭제 후보
- "best part is no part" = 노드를 최적화하는 게 아니라 불필요한 노드를 제거하는 것

### 2.4 Default Mode Network — 탐험과 이색적 접합

뇌가 "아무것도 안 할 때" 활성화되는 DMN(Default Mode Network)은 뇌 에너지의 20-30%를 소비한다. 이 네트워크가 하는 일: 서로 관련 없어 보이는 기억들을 무작위로 연결하며 창의적 통찰을 생성.

**우리 구현:**
```python
EXPLORATION_RATE = 0.1  # 10% 확률로 약한 edge도 탐험
```

DMN은 20-30%인데 우리는 10%. 이 차이가 "이색적 접합" 빈도에 직접 영향을 준다.

> *"The default mode network causally contributes to creative thinking."*
> — Brain (Oxford), 2024 ([Oxford Academic](https://academic.oup.com/brain/article/147/10/3409/7695856))

> *"Disrupting DMN via cortical stimulation limits divergent thinking."*
> — University of Utah, 2025 ([Utah Medicine](https://medicine.utah.edu/neurosurgery/news/2025/01/mapping-creativity-role-of-default-mode-network))

### 2.5 확산 활성화 — 의미가 퍼지는 방식

Collins & Loftus(1975)의 확산 활성화 이론: 하나의 개념이 활성화되면, 관련 개념으로 활성화가 "퍼져나간다". 강한 연결일수록 빠르게, 약한 연결일수록 느리게.

**우리 구현:**
- recall() → 벡터 검색으로 seed 노드 선정 → 그래프 BFS로 이웃 탐색
- `GRAPH_BONUS = 0.3` → 이웃 노드에 활성화 보너스
- `layer_penalty` → 레이어 거리가 멀수록 활성화 감쇠

이것이 뇌의 semantic priming과 동일한 메커니즘이다.

> *"Activation spreads through semantic networks based on associative strength and distance."*
> — Collins & Loftus, 1975 ([APA PsycNet](https://psycnet.apa.org/record/1976-03421-001))

### 2.6 기억 재공고화 — 기억은 꺼낼 때마다 바뀐다

Nader(2000)의 발견: 기억을 인출할 때, 그 기억은 일시적으로 불안정해지고 변경 가능한 상태가 된다. 이것이 "기억 재공고화(reconsolidation)".

**우리 시스템에서의 의미:**
recall()로 노드를 꺼낼 때마다:
1. Hebbian 갱신 → edge strength 변경 (기억의 물리적 변화)
2. 새로운 컨텍스트에서 재해석 → Paul의 이해가 업데이트됨
3. 다음 recall에서 다른 순서로 나올 수 있음 (기억의 재구성)

> *"Retrieved memories become labile and must be re-stabilized through reconsolidation."*
> — Nader et al., 2000, Nature ([Nature](https://www.nature.com/articles/35021052))

---

## 3. 삼체 연결 아키텍처 — Paul ↔ Claude ↔ 온톨로지

### 3.1 확장된 마음 (Extended Mind Thesis)

Andy Clark & David Chalmers(1998): 인지는 뇌 안에만 있지 않다. 외부 도구가 인지 과정에 통합되면, 그것은 마음의 **일부**가 된다.

Clark의 "parity principle": 만약 어떤 과정이 뇌 안에서 일어났다면 인지라고 불릴 것인데, 그것이 외부에서 일어난다면 — 그것도 인지다.

**mcp-memory는 Paul의 확장된 마음인가?**

Clark의 기준을 적용:
1. ✅ 지속적으로 접근 가능 (모든 세션에서)
2. ✅ 신뢰할 수 있는 정보 (recall이 일관적이면)
3. ✅ 자동으로 사용됨 (SessionStart hook)
4. ⚠️ 과거에 의식적으로 승인됨 (remember()는 수동, 하지만 enrichment는 자동)

> *"If the resources in Otto's notebook play the same role as internal memory, they are part of his cognitive process."*
> — Clark & Chalmers, 1998 ([PhilPapers](https://philpapers.org/rec/CLATEM))

### 3.2 분산 인지 (Distributed Cognition)

Edwin Hutchins(1995): 인지는 개인의 머릿속에 있지 않다. 사람, 도구, 환경에 **분산**되어 있다.

**우리 시스템의 인지 분산:**
| 인지 기능 | 위치 | 수행자 |
|---|---|---|
| 경험 생성 | Paul의 뇌 | Paul |
| 경험 구조화 | 온톨로지 | remember() + enrichment |
| 패턴 인식 | Claude + 온톨로지 | recall() + analyze_signals() |
| 의사결정 | Paul의 뇌 | Paul (Claude가 맥락 제공) |
| 기억 공고화 | 온톨로지 | promote_node() |
| 기억 인출 | Claude + 온톨로지 | recall() + get_context() |

어느 하나가 빠져도 전체 인지 루프가 깨진다.

> *"Knowledge is not stored in any individual component but emerges from the interactions among components."*
> — Hutchins, 1995, Cognition in the Wild ([MIT Press](https://mitpress.mit.edu/9780262581462/cognition-in-the-wild/))

### 3.3 Transactive Memory — 누가 뭘 아는지 아는 것

Daniel Wegner(1985)의 트랜잭티브 메모리: 그룹에서 중요한 것은 "모든 것을 아는 것"이 아니라 **"누가 뭘 아는지 아는 것"**이다.

**Paul-Claude-온톨로지 트랜잭티브 시스템:**
- Paul이 아는 것: 맥락, 의도, 가치판단, 창의적 연결
- Claude가 아는 것: 코드 분석, 패턴 인식, 체계적 추론
- 온톨로지가 아는 것: Paul의 과거 결정, 패턴, 원칙, 실패 이력

**세션 시작 시 get_context()는 트랜잭티브 디렉토리 역할을 한다** — Claude에게 "온톨로지에 뭐가 있는지"를 알려줌으로써 전체 시스템의 지식 접근성을 높인다.

> *"The transactive memory system is an emergent group-level property that combines individual knowledge with shared awareness of who knows what."*
> — Wegner, 1985 ([Harvard PDF](https://dtg.sites.fas.harvard.edu/DANWEGNER/pub/Wegner%20Transactive%20Memory.pdf))

---

## 4. 상승 루프 — 어떻게 계속 나아지는가

### 4.1 자기조직화 (Self-Organization)

Prigogine의 산일 구조(Dissipative Structures): 평형에서 멀리 떨어진 열린 시스템은 외부 에너지를 소비하며 자발적으로 질서를 생성한다.

**우리 시스템의 에너지원:** Paul의 세션 활동 (remember, recall, 대화)
**자기조직화 메커니즘:**
- Hebbian 학습 → 자주 쓰는 경로가 강화 (자발적 허브 형성)
- 승격 메커니즘 → Signal이 반복되면 Pattern으로 (자발적 추상화)
- Exploration → 10% 무작위 탐험이 새로운 구조를 발견

### 4.2 오토포이에시스 (Autopoiesis) — 자기 생성 시스템

Maturana & Varela(1972): 오토포이에틱 시스템은 자기 자신을 만들어내는 시스템이다. 시스템의 구성요소가 시스템을 재생산하고, 시스템이 구성요소를 재생산한다.

**우리 시스템은 오토포이에틱인가?**
- Paul이 대화 → Claude가 분석 → 온톨로지에 저장 → 다음 세션에서 Claude가 인출 → Paul이 새로운 연결 발견 → 새로운 대화...
- 이 루프가 **외부 개입 없이 자기 강화**된다면 = 오토포이에틱

현재 상태: **부분적으로 오토포이에틱**
- ✅ Hebbian 학습은 자동
- ✅ 일일 enrichment는 자동
- ❌ 승격(promote)은 수동
- ❌ 가지치기(pruning)는 미구현

완전한 오토포이에시스를 위해 필요한 것: 자동 승격 + 자동 pruning + 자동 품질 감사

> *"An autopoietic machine is a machine organized as a network of processes of production of components that produces the components which realize the network."*
> — Maturana & Varela, 1972 ([Springer](https://link.springer.com/book/10.1007/978-94-009-8947-4))

### 4.3 스몰 월드 네트워크 — 뇌의 구조

Watts & Strogatz(1998): 뇌는 "작은 세상" 네트워크다 — 높은 클러스터링 계수(로컬 그룹이 강하게 연결) + 짧은 평균 경로 길이(아무 노드든 몇 홉이면 도달).

**우리 시스템이 스몰 월드인지 검증해야 한다:**
- 프로젝트별 클러스터 (orchestration, portfolio, tech-review) = 로컬 그룹
- 크로스 도메인 연결 = 장거리 바로가기
- 두 속성이 동시에 존재하면 → 스몰 월드 → 효율적 정보 전달

> *"Networks of dynamical systems with small-world topology can synchronize much more easily than regular lattices."*
> — Watts & Strogatz, 1998, Nature ([Nature](https://www.nature.com/articles/30918))

### 4.4 상승 스파이럴 — 구체적 메커니즘

```
Paul의 경험 (L0)
    ↓ remember()
온톨로지에 저장
    ↓ daily_enrich.py
enrichment (요약, 개념 추출, 품질 점수)
    ↓ analyze_signals()
반복 패턴 감지
    ↓ promote_node()
Signal → Pattern → Principle 승격
    ↓ get_context()
다음 세션에서 Claude에게 제공
    ↓ 대화
Paul이 새로운 연결 발견
    ↓ remember()
... (루프 반복, 매 사이클마다 추상화 수준 상승)
```

이 루프가 돌 때마다:
1. **L0-L1에 경험이 축적**된다
2. **L2에 패턴이 결정화**된다
3. **L3-L5에 원칙과 가치가 공고화**된다
4. **Claude가 더 높은 수준의 맥락에서 시작**한다
5. **Paul이 더 깊은 연결을 발견**한다

이것이 "계속 상승하는 뇌"의 구체적 메커니즘이다.

---

## 5. 제1원칙 적용 — 무엇을 없앨 것인가

### 5.1 "왜 50개 타입인가?"

인지과학에서 최적 분류 수:
- Miller(1956): 작업기억 용량 7±2
- Rosch(1975): 기본 수준 범주(basic-level categories)가 인지적으로 가장 효율적
- 실무 온톨로지: Gene Ontology ~44,000 terms, SNOMED CT ~350,000

50개는 "인간이 구별 가능한 범위"에 있다. 하지만 **실제로 50개가 모두 사용되는가?**
→ 사용 0인 타입이 있다면 제거해야 한다.

### 5.2 "왜 48개 관계인가?"

LLM 분류기가 48개 관계를 정확하게 구분할 수 있는가?
- 규칙 기반 매핑으로 58%만 커버됨 (나머지는 generic)
- E14 API 정밀화 후에도 15% 이하 generic이 목표

**제1원칙 질문**: 48개 중 실제로 사용되는 관계가 15개라면, 나머지 33개는 제거하는 것이 "best part is no part"다.

### 5.3 "왜 6개 레이어인가?"

비교:
| 시스템 | 레이어 수 | 구조 |
|---|---|---|
| 뇌 피질 | 6층 | I-VI (실제 뉴런 층) |
| DIKW 피라미드 | 4층 | Data→Information→Knowledge→Wisdom |
| Bloom's Taxonomy | 6단계 | Remember→Understand→Apply→Analyze→Evaluate→Create |
| 우리 시스템 | 6층 | L0-L5 |

6층이 뇌 피질 구조와 Bloom's Taxonomy와 일치하는 것은 우연이 아닐 수 있다. 하지만 **L4와 L5에 노드가 6개밖에 없다면** — 실질적으로 4층 시스템이다. L4/L5가 채워질 때까지는 DIKW 피라미드와 동등하다.

---

## 6. 다음 단계 — 뇌에서 배울 것

### 6.1 수면 리플레이 → 자동 승격

뇌는 수면 중에 해마의 기억을 신피질로 재생(replay)한다. 이것이 기억 공고화의 핵심 메커니즘이다.

**구현 제안**: daily_enrich.py에 "자동 승격 후보 탐지" 추가
- 같은 Signal이 3회 이상 반복 → Pattern 승격 제안
- 같은 Pattern이 다른 도메인에서도 발견 → Principle 승격 제안
- maturity_score > 0.9 → 자동 승격 (Paul 승인 불필요)

### 6.2 시냅스 가지치기 → 자동 아카이브

**구현 제안**: 월 1회 pruning 스크립트
- `frequency=0 AND days_since_created > 90 AND tier=2` → archive 상태로
- `quality_score < 0.3 AND layer <= 1` → 삭제 후보 (Paul에게 보고)
- archive된 노드는 recall에서 제외되지만 DB에 남음 (복구 가능)

### 6.3 DMN 탐험율 조정 → A/B 테스트

현재 EXPLORATION_RATE = 0.1. DMN은 20-30%.
**구현 제안**:
- 1주일간 0.1로 recall 품질 측정
- 1주일간 0.2로 recall 품질 측정
- P@5 (정확도)와 "이색적 접합 발견 빈도" 비교

### 6.4 기억 재공고화 → recall 시 업데이트

현재 recall()은 Hebbian 갱신(frequency, last_activated)만 한다.
**추가 제안**: recall() 결과를 Paul이 사용한 후, 사용 맥락을 edge의 description에 추가
- "이 연결이 포트폴리오 설계에서 활용됨" 같은 맥락 기록
- 이것이 "기억이 인출될 때 변화한다"의 구현

---

## 7. 리서치 소스 인덱스

> 아래는 이 문서의 과학적 근거를 위해 수집된 382개 소스의 분류 인덱스이다.
> 전체 목록은 별도 파일 참조.

### 뉴로사이언스 (132개)
| 카테고리 | 수 | 핵심 소스 |
|---|---|---|
| Hebbian Learning | 8 | McClelland (Stanford), SoftHebb (arXiv), LTP Review (Physiology) |
| Memory Consolidation | 11 | CLS Theory (McClelland 1995/2016), Sleep Replay (Nature), Hippocampal Replay |
| Cognitive Architecture | 10 | ACT-R vs Soar, GWT (Baars), CLARION, HTM (Hawkins), Thousand Brains |
| Connectionism vs Symbolicism | 9 | Neurosymbolic AI Survey 2024, Minsky Frames, Society of Mind |
| Spreading Activation | 6 | Collins & Loftus 1975, fMRI Priming, Emotional Memory |
| Memory Reconsolidation | 6 | Nader 2000 (Nature), Prediction Error, Memory Editing |
| Prefrontal Cortex & Abstraction | 5 | Hierarchical PFC, Abstract Rule Discovery, RLPFC Development |
| Default Mode Network | 5 | DMN & Creativity (Brain 2024), Causal Role (Oxford), Utah 2025 |
| Dual Process Theory | 4 | Kahneman System 1/2, Critical Analysis |
| Embodied Cognition | 5 | Stanford SEP Entry, Schema Theory, Piaget |
| Rhizomatic Thinking | 6 | Deleuze & Guattari, Web as Rhizome, Becoming Rhizome |
| PKM & Second Brain | 13 | Zettelkasten, Building a Second Brain, Evergreen Notes, Memex |
| Palantir Ontology | 8 | Foundry Docs, 3-Layer Analysis, AIP + Ontology SDK |
| MIT/Stanford KR | 10 | Protege, Semantic Web, OWL, BFO, YAGO |
| GNNs for Reasoning | 11 | R-GCN, KG-ICL (NeurIPS 2024), MRGAT, TransE/TransR |
| Cross-cutting | 15 | Free Energy Principle (Friston), Tulving, Place/Grid Cells, DNC (DeepMind) |

### 응용 온톨로지 & AI (130개)
| 카테고리 | 수 | 핵심 소스 |
|---|---|---|
| Knowledge Graph Completion | 8 | Link Prediction, Missing Edge Inference |
| Ontology Evolution | 6 | Versioning, Migration Strategies |
| Human-AI Knowledge Building | 6 | Co-creation, Collaborative Ontology |
| Google Knowledge Graph | 5 | Architecture, Entity Resolution |
| Wikidata | 6 | Governance, Type System, Community |
| Neo4j / Graph DB | 5 | Property Graphs, Query Patterns |
| Semantic Memory in AI | 7 | LLM Knowledge Storage, Retrieval |
| RAG | 10 | LightRAG (6,000x token 효율), GraphRAG, Hybrid RAG |
| Knowledge Distillation | 5 | Teacher-Student, Compression |
| Episodic vs Semantic in AI | 6 | Memory Architecture, Dual Store |
| Knowledge Lifecycle | 6 | Creation, Curation, Archival |
| KG Quality Metrics | 6 | Precision, Recall, F1 for KGs |
| Temporal KGs | 5 | Time-Aware Reasoning |
| Personal AI Memory | 9 | Mem0 (+26% accuracy), A-MEM (NeurIPS 2025), Cognee (92.5%) |
| Cross-cutting | 35 | Neuro-symbolic, LLM KG, Hebbian Validation |

### 철학 & 시스템 사고 (120개)
| 카테고리 | 수 | 핵심 소스 |
|---|---|---|
| Extended Mind | 7 | Clark & Chalmers 1998, Supersizing the Mind, Natural-Born Cyborgs |
| Distributed Cognition | 5 | Hutchins (Cognition in the Wild), HCI Framework |
| Stigmergy | 5 | Mathematical Modelling, Universal Coordination |
| Autopoiesis | 5 | Maturana & Varela 1972, Systems Practice |
| Enactivism & 4E | 6 | IEP Entry, Stanford SEP, 4E Cognition |
| Cybernetics | 6 | Wiener 1948, Second-Order (von Foerster), Ashby Variety |
| Complex Adaptive Systems | 6 | MIT CAS, Kauffman Edge of Chaos, Prigogine |
| Noosphere | 4 | Teilhard de Chardin, Vernadsky, Anthropocene Reassessment |
| Memetics | 4 | Dawkins, Cultural Evolution, Semiotics Interface |
| Actor-Network Theory | 5 | Latour (Reassembling the Social), ANT Clarifications |
| Semiotics | 4 | Peirce vs Saussure, Sign Systems |
| Category Theory / KR | 5 | Ologs (Spivak), Bicategories, Double-Functorial |
| Information Ecology | 3 | Nardi & O'Day, Information Environments |
| Exocortex | 4 | External Brain Augmentation, Science Exocortex 2025 |
| Transactive Memory | 4 | Wegner 1985, TMS Integrative Review |
| First Principles & Minimalism | 6 | Musk 5-Step, Occam's Razor in Ontology, SEP Simplicity |
| Foundational Visionaries | 6 | Bush (Memex), Engelbart, Licklider, Ted Nelson |
| Knowledge Creation | 6 | Nonaka SECI, Polanyi Tacit Knowledge, Weick Sensemaking |
| Network Science | 4 | Watts-Strogatz, Barabasi Scale-Free |
| Systems Thinking | 7 | Meadows Leverage Points, Bateson, Beer VSM, Ostrom |
| Philosophy of Mind | 5 | Assemblage Theory, IIT, Incomplete Nature |
| Cognitive Science | 7 | Affordance (Gibson), Cognitive Load, PDP, ZPD |

---

## 8. 열린 질문 — 답해야 할 것들

1. **EXPLORATION_RATE는 0.1인가 0.2인가?** DMN 비유는 0.2-0.3을 시사하지만, recall 정확도가 떨어질 수 있다. A/B 테스트 필요.

2. **50개 타입 중 실제로 몇 개가 살아있는가?** 사용 0인 타입은 "best part is no part"에 의해 제거 후보.

3. **온톨로지가 꺼지면 뭐가 달라지는가?** 이 질문에 대한 데이터 기반 답이 필요. get_context() 없이 세션을 돌려보고 차이를 측정.

4. **스몰 월드 특성이 있는가?** NetworkX로 클러스터링 계수와 평균 경로 길이를 측정하면 답이 나온다.

5. **이 시스템은 오토포이에틱인가?** 자동 승격 + 자동 pruning이 구현되면 "예"에 가까워진다.

6. **Paul의 사고 패턴이 실제로 edge 강도에 반영되고 있는가?** Hebbian 갱신 로그를 분석해서 확인.

---

*이 문서는 살아있는 문서(living document)다. 검증 결과와 Deep Research 결과가 들어오면 업데이트된다.*
