[perplexity-research]

주제: 개인 온톨로지·개인 지식 그래프·망 분석·망상 기억 모델 (2024–2026 최신 연구 정리)

결론:

- Palantir Foundry는 “객체/링크/액션/함수/인터페이스 + 버전 가능한 메타데이터 서비스 + 분리된 인덱싱·쿼리 계층” 구조로 온톨로지를 운용하며, 스키마 변화 후에도 대량 객체를 점진적으로 재색인·마이그레이션하는 백엔드 아키텍처를 사용한다.palantir+3
- 최신 개인 지식 그래프 연구(PKG ecosystem, PKG API)와 상용 제품(Mem, Rewind, Obsidian graph, Notion + 외부 그래프 확장)은 “벡터 DB + 그래프(백링크/엔티티 그래프)”의 하이브리드 구조, 자동 엔티티·관계 추출, 사용자 주도 태깅/뷰, 프라이버시·보안 모델을 공통 패턴으로 쓴다.skywork+9
- 인지과학/신경과학의 연합 기억 모델(Spreading Activation, Complementary Learning Systems, Reconsolidation)은 “가중치가 있는 연상 네트워크 + 두 단계 학습 시스템(빠른 에피소드, 느린 스키마) + 재활성화 시 업데이트”라는 구조를 제안하며, 이는 개인 온톨로지의 계층·Hebbian 엣지·재작성 전략 설계에 직접 매핑 가능하다.web.stanford+8
- 3K–100K 노드 그래프에서는 커뮤니티 탐지에 Leiden(품질·안정성), Louvain(속도), Infomap(플로우 기반), 허브 탐지에 통합 허브 점수(IHS), 이상 탐지에 GNN 기반 그래프 이상 탐지·KG 특화 방법(ADKGD 등)이 실용적인 SOTA 조합이다.jetir+7
- “망각” 기술은 법적/프라이버시 관점의 머신 언러닝(정확/근사/분산 언러닝)과, 추천·KG에서의 시간 감쇠·그래프 단위 삭제·구조 단순화(트리플 제거)로 양분되며, 적절한 감쇠·삭제는 예측 성능을 오히려 높일 수 있음이 보고되었다.ijsr+7
- 대규모 온톨로지(Wikidata, SNOMED CT, Gene Ontology, Schema.org)는 “항상 전체 이력 보존 + 비파괴적 비활성/Deprecated 표시 + 대체 개념 링크(replaced_by, historical associations) + 정기 릴리스/스냅샷”으로 타입 진화를 다룬다.wikidata+8
- “급진적 단순화 = 성능 향상”의 정량적 증거는 제한적이지만, 2026년 생의학 온톨로지 슬림 뷰, 2023–24년 직접/세분화된 검색(DiFaR, Dense XRetrieval, HIRO) 연구는 *적절히 요약된 뷰나 단일·세분화 단위가 검색 품질과 효율을 개선*할 수 있음을 보여준다.aclanthology+5

아래는 항목별 핵심 논문·시스템과, “개인 온톨로지 설계 관점에서의 적용 아이디어”이다.

---

## 1. Palantir Foundry Ontology의 기술적 구조

## 1-1. 타입 시스템·관계 모델

**Palantir Ontology 개요 문서 (공식 docs)**palantir+1

- URL: https://www.palantir.com/docs/foundry/ontology/overview[[palantir](https://www.palantir.com/docs/foundry/ontology/overview)]
- 날짜: 2021-12-13 (문서지만 2024–25 릴리스에서도 동일 개념 유지)palantir+1
- 핵심 인사이트:
    - 온톨로지는 Foundry 상의 모든 데이터셋·가상 테이블·모델 위에 놓인 “조직의 디지털 트윈” 계층이며, **Object / Property / Link**(semantic)와 **Action / Function / Dynamic security**(kinetic)를 1급 개념으로 다룬다.naver+2
    - **Object Type, Link Type, Action Type, Function, Interface**가 온톨로지의 주요 타입이며, Interface는 여러 Object Type이 공유하는 “형태(Shape)와 기능”을 캡슐화하는 다형 인터페이스를 제공한다.[[palantir](https://www.palantir.com/docs/foundry/ontology/overview)]
- 개인 온톨로지 적용:
    - 지금 설계하신 50개 타입을 Foundry 스타일로 나누면:
        - “실체”는 Object Type,
        - “경험·사건·상태 변화”는 Action Type,
        - “규칙·파생 로직”은 Function Type (예: 감정 점수 계산, 가치 충돌 탐지),
        - “레이어 공통 인터페이스 (예: 모든 ‘경험’이 가지는 timestamp, involved_people)”를 Interface로 정의해 다형적 처리를 할 수 있다.[미검증]

**Ontology Metadata Service & 백엔드 아키텍처**[[palantir](https://www.palantir.com/docs/foundry/object-backend/overview)]

- URL: https://www.palantir.com/docs/foundry/object-backend/overview[[palantir](https://www.palantir.com/docs/foundry/object-backend/overview)]
- 날짜: 2021-12-13 (Object Storage V2는 이후도 계속 기본 백엔드)[[palantir](https://www.palantir.com/docs/foundry/object-backend/overview)]
- 핵심 인사이트:
    - **Ontology Metadata Service (OMS)** 가 “어떤 객체/링크/액션 타입이 존재하는지”와 그 스키마를 정의하며, 실제 인스턴스 데이터는 별도의 Object Databases에 저장된다.[[palantir](https://www.palantir.com/docs/foundry/object-backend/overview)]
    - Object Storage V2는 인덱싱과 쿼리를 분리해 **수십 억 개 객체를 가진 단일 타입**까지 수평 확장하며, **증분 인덱싱 + 스트리밍 소스 + 멀티 데이터소스 타입 + 컬럼/프로퍼티 단위 권한**을 지원한다.[[palantir](https://www.palantir.com/docs/foundry/object-backend/overview)]
- 개인 온톨로지 적용:
    - 메타데이터(타입 정의, 관계 정의, 제약)는 작은 “메타 그래프(OMS)”에, 실제 노드·에지는 별도 저장소(예: KV + 그래프 엔진)에 두어 Foundry와 같은 느슨한 결합 구조를 취하면, 타입·관계 스키마 진화 시 인스턴스 마이그레이션을 제어하기 쉽다.[미검증]

## 1-2. 온톨로지 진화·버전 관리

**Object Storage V2의 스키마 변경·마이그레이션 지원**[[palantir](https://www.palantir.com/docs/foundry/object-backend/overview)]

- URL: 위와 동일[[palantir](https://www.palantir.com/docs/foundry/object-backend/overview)]
- 핵심 인사이트:
    - V2는 **breaking schema change 이후에도 기존 사용자 편집(user edits)을 자동 마이그레이션할 수 있는 기능**을 제공, 진화 중인 온톨로지에서도 편집 이력을 잃지 않도록 설계되어 있다.[[palantir](https://www.palantir.com/docs/foundry/object-backend/overview)]
    - 최대 2,000개 프로퍼티/타입, Search Around 10만 개 객체 등 고정된 상한을 문서화해 “스키마 복잡도·쿼리 팬아웃”의 실용적 한계를 명시한다.[[palantir](https://www.palantir.com/docs/foundry/object-backend/overview)]
- 개인 온톨로지 적용:
    - 타입 변경 시 “마이그레이션 함수(Foundry Function에 해당)”를 스키마에 함께 정의해, 타입 스키마가 깨질 때마다 자동으로 과거 노드/엣지 스냅샷을 새 스키마로 재작성하는 배치 잡을 두는 패턴을 차용할 수 있다.[미검증]

---

## 2. 개인 지식 그래프 최신 접근 (Mem, Rewind, Obsidian, Notion, 학계)

## 2-1. Academic: Personal Knowledge Graph Ecosystem

**An Ecosystem for Personal Knowledge Graphs: Survey & Roadmap (AI Open 2024)**arxiv+3

- URL: https://arxiv.org/html/2304.09572v2[[arxiv](https://arxiv.org/html/2304.09572v2)]
- 날짜: 2024-03-15 (v2), 저널 AI Open 2024 게재[[krisztianbalog](https://krisztianbalog.com/files/aiopen2024-pkg.pdf)]
- 핵심 인사이트:
    - PKG를 “개인과 관련된 엔티티·속성·관계를 담고, **단일 개인이 데이터 소유권을 가지고, 개인화된 서비스 제공이 1차 목적**인 지식 그래프”로 정의하고, Population / Representation & Management / Utilization의 세 축으로 생태계를 정리한다.arxiv+2
    - 콜드 스타트 해결을 위해 이메일·캘린더·브라우저 기록 등 외부 소스에서 자동 수집(population) + 사용자가 직접 수정하는 관리 계층 + 프라이버시 보존형 개인화 서비스(질의, 추천)를 통합한 아키텍처를 제안한다.krisztianbalog+1
- 개인 온톨로지 적용:
    - 현재 3,200 노드는 대부분 수동 설계이므로, 논문의 Population 레이어를 차용해 “이메일/캘린더/브라우징 로그 → 구조화 엔티티/관계”로 흡수하는 ingestion pipeline을 별도 레이어로 두면 좋다.
    - Representation 측면에서는 RDF/Property Graph 모두 허용하지만, 개인용에서는 “액세스 제어·프라이버시·사용자 이해 가능성”을 중시해야 한다고 강조하므로, 내부 표현은 자유롭게 설계하되 **명시적 접근 레벨(프라이빗/세션공유/모델공유)** 메타데이터를 엣지/노드에 부여하는 것을 추천한다.[미검증]arxiv+1

**PKG API: RDF-based vocabulary & access control (2024)**[[semanticscholar](https://www.semanticscholar.org/paper/Personal-Research-Knowledge-Graphs-Chakraborty-Dutta/f7951a678142fa58d3b63a1a4bb89b4dab6e865f)]

- URL: [https://www.semanticscholar.org/paper/Personal-Research-Knowledge-Graphs-Chakraborty-Dutta/f7951a678142fa58d3b63a1a4bb89b4dab6e8…](https://www.semanticscholar.org/paper/Personal-Research-Knowledge-Graphs-Chakraborty-Dutta/f7951a678142fa58d3b63a1a4bb89b4dab6e8%E2%80%A6)[[semanticscholar](https://www.semanticscholar.org/paper/Personal-Research-Knowledge-Graphs-Chakraborty-Dutta/f7951a678142fa58d3b63a1a4bb89b4dab6e865f)]
- 날짜: 2024 (PKG API 관련 후속 작업 포함)[[semanticscholar](https://www.semanticscholar.org/paper/Personal-Research-Knowledge-Graphs-Chakraborty-Dutta/f7951a678142fa58d3b63a1a4bb89b4dab6e865f)]
- 핵심 인사이트:
    - PKG API는 개인 지식 그래프 안에서 **명제 수준 진술 + 접근권 + 프로비넌스(출처)** 를 표현하는 RDF 기반 어휘를 제안한다.[[semanticscholar](https://www.semanticscholar.org/paper/Personal-Research-Knowledge-Graphs-Chakraborty-Dutta/f7951a678142fa58d3b63a1a4bb89b4dab6e865f)]
    - “개인 연구 지식 그래프(PRKG)” 등 도메인 특화 PKG에서, 어떤 관계(예: *authored*, *read*, *cited*)와 엔티티를 포함할지 리스트업하고, 자동 추출 파이프라인을 설계하는 사례를 제공한다.[[semanticscholar](https://www.semanticscholar.org/paper/Personal-Research-Knowledge-Graphs-Chakraborty-Dutta/f7951a678142fa58d3b63a1a4bb89b4dab6e865f)]
- 개인 온톨로지 적용:
    - Hebbian 엣지 학습을 하더라도, **각 엣지에 ‘근거 세션/문서/대화 ID’와 타임스탬프를 붙이는 패턴**을 PKG API에서 그대로 따오면, 향후 머신 언러닝/망각·감쇠 시 삭제 근거를 명확히 유지할 수 있다.[미검증]

## 2-2. Industry: Mem, Rewind, Obsidian, Notion

**Mem AI: Vector DB + Knowledge Graph 기반 개인 지식 엔진**spark.mwm+1

- URL: https://skywork.ai/skypage/en/Mem-AI-Your-Personal-Knowledge-Engine-in-2025/1976181401534394368[[skywork](https://skywork.ai/skypage/en/Mem-AI-Your-Personal-Knowledge-Engine-in-2025/1976181401534394368)]
- 날짜: 2025-11-09 리뷰 (제품은 2022–25 진화)[[skywork](https://skywork.ai/skypage/en/Mem-AI-Your-Personal-Knowledge-Engine-in-2025/1976181401534394368)]
- 핵심 인사이트:
    - Mem은 “폴더 없이 모든 생각을 덤프 → **벡터 DB(의미 유사성)** + **지식 그래프(명시 관계)** 로 백엔드 구조를 자동 구성”하는 개인 Google/Second Brain을 지향한다.[[skywork](https://skywork.ai/skypage/en/Mem-AI-Your-Personal-Knowledge-Engine-in-2025/1976181401534394368)]
    - 노트 입력 시 AI가 엔티티·관계를 추출하여 지식 그래프를 확장하고, **유사 노트 추천, 관계 기반 Copilot, 개인 데이터로 파인튜닝된 Chat** 등 기능을 제공한다.[[skywork](https://skywork.ai/skypage/en/Mem-AI-Your-Personal-Knowledge-Engine-in-2025/1976181401534394368)]
- 개인 온톨로지 적용:
    - 현재 온톨로지에 이미 타입·관계가 정의되어 있으니, Mem처럼 “로우 경험 레이어에 들어오는 텍스트/이벤트 → (1) 벡터 임베딩, (2) 온톨로지 타입에 맞는 엔티티·관계 추출” 두 경로를 동시에 유지하는 하이브리드 설계를 그대로 가져올 수 있다.[미검증]
    - 콜드 스타트는 폴더/스키마 강요 대신, **자유 입력 → AI가 온톨로지 스키마에 맞춰 매핑 제안 → 사용자가 승인/수정** 플로우로 해결하는 쪽이 Mem의 UX와 정합적이다.[미검증][[skywork](https://skywork.ai/skypage/en/Mem-AI-Your-Personal-Knowledge-Engine-in-2025/1976181401534394368)]

**Rewind AI: 완전 타임라인 인덱스 기반 개인 기억**softwarerankinghub+1

- URL: https://www.softwarerankinghub.com/article/218[[softwarerankinghub](https://www.softwarerankinghub.com/article/218)]
- 날짜: 2026-02-24 분석 (제품은 2022–24 발전)skywork+1
- 핵심 인사이트:
    - Rewind는 화면·오디오를 로컬에서 캡처하고 OCR/ASR 후 **텍스트·메타데이터만 암호화 DB에 저장**하는 “로컬 퍼스트 개인 타임라인” 구조를 사용한다.[[softwarerankinghub](https://www.softwarerankinghub.com/article/218)]
    - 질의는 “언제/어디서/무엇을 봤나”에 대한 시간 축 탐색 + 전체 텍스트 검색으로 지원되며, 고수준 온톨로지보다는 **시간 순서와 앱 상태**가 1차 키다.skywork+1
- 개인 온톨로지 적용:
    - 지금 설계하신 6개 추상 레이어 중 **가장 하위 ‘raw experience’ 레이어는 Rewind식 ‘완전 타임라인 로그’로 유지**하고, 상위 레이어는 이 로그에서 파생된 정규화/요약 그래프로 두는 것이 CLS와도 잘 맞는다.[미검증]

**Obsidian Graph view & Link Types**help.obsidian+1

- URL: https://help.obsidian.md/plugins/graph, https://www.obsidianstats.com/plugins/graph-link-typesobsidianstats+1
- 날짜: Graph view 문서 (지속 업데이트), Link Types 플러그인 (2년 전 릴리스)help.obsidian+1
- 핵심 인사이트:
    - 기본 Graph view는 **노트 파일을 노드, 내부 링크를 엣지, 태그/첨부를 선택적 노드**로 시각화하며, 검색·필터링·애니메이션 등 상호작용으로 허브·오브잉 노드를 직관적으로 파악하게 한다.[[help.obsidian](https://help.obsidian.md/plugins/graph)]
    - Graph Link Types 플러그인은 Dataview API를 활용해 링크에 타입 라벨을 부여, 그래프에서 **관계 종류를 시각적으로 드러내는 경량 온톨로지 레이어**를 제공한다.[[obsidianstats](https://www.obsidianstats.com/plugins/graph-link-types)]
- 개인 온톨로지 적용:
    - 이미 48개 관계 타입이 있으니, Obsidian처럼 “플레이너한 링크 그래프 + 관계 타입 라벨링”으로 시각화를 두고, 복잡한 논리는 백엔드 온톨로지에서 처리하는 **2중 표현(시각용 단순 그래프 / 내부용 정교 온톨로지)** 구조를 가져오면, 사용자는 단순 그래프만 보면서도 타입 구조의 이점을 얻을 수 있다.[미검증]

**Notion AI + 외부 그래프 도구 (Graphify, Note Graph, IVGraph)**chromewebstore.google+3

- 핵심 인사이트:
    - Notion AI 자체는 시각 그래프를 제공하지 않지만, Graphify·Note Graph·IVGraph와 같은 플러그인이 **Mention, 링크, DB Relation을 이용해 로컬 퍼스트 지식 그래프 뷰**를 만든다.notion+2
    - 이 도구들은 **허브 페이지·클러스터·고아 페이지 탐지, 필터링, 3D 그래프 뷰** 등 고급 구조 분석을 제공하며, 노션의 복잡한 DB 스키마를 “그래프 한 장”으로 요약한다.ivgraph+1
- 개인 온톨로지 적용:
    - 동일한 방식으로 현재 온톨로지를 “그래프 뷰용 단순 스키마”로 export하고, **허브·클러스터·고아 노드 자동 탐색 도구**를 올리면, 설계 복잡도가 높아져도 시각 인지 비용을 낮출 수 있다.[미검증]

---

## 3. 신경과학 기반 연합 기억 구조와 지식 그래프 매핑

## 3-1. Spreading Activation (Collins & Loftus, 1975)

**A Spreading-Activation Theory of Semantic Processing**semanticscholar+2

- URL: https://api.semanticscholar.org/CorpusID:14217893, PDFbpb-us-e2.wpmucdn+1
- 핵심 인사이트:
    - 개념은 노드, 관계는 가중 엣지로 표현되며, 한 노드 활성화 시 **인접 노드로 감쇠하는 형태로 활성도가 퍼지는 모델**이다.psych.fullerton+2
    - 엣지 길이/가중치는 연합 강도를 나타내며, 짧고 강한 엣지는 빠른 연상·프라이밍을 설명한다.semanticscholar+1
- 개인 온톨로지 적용:
    - 현재 Hebbian 엣지 학습을 하신다면, **각 엣지에 w_ij(연합 강도)와 d_ij(유효 거리)를 유지하고, 쿼리 시 k-step spreading activation을 수행해 ‘맥락적으로 활성화된 하위 서브그래프’를 생성**하는 방식이 자연스럽다.[미검증]
    - Hebbian 업데이트(동시 활성 시 w_ij 증가, 비활성 시 서서히 감쇠)는 Collins–Loftus 모델에서 암묵적으로 가정하는 “경험에 따른 연합 강도 변화”를 구현한다고 볼 수 있다.[미검증]bpb-us-e2.wpmucdn+1

## 3-2. Complementary Learning Systems (CLS, McClelland 등)

**Integration of new information in memory: new insights from a CLS perspective (Phil. Trans. R. Soc. B 2020)**biorxiv+3

- URL: https://web.stanford.edu/~jlmcc/papers/McCMcNaughtonLampinen20IntegrNewInfoCLS.pdf[[web.stanford](https://web.stanford.edu/~jlmcc/papers/McCMcNaughtonLampinen20IntegrNewInfoCLS.pdf)]
- 핵심 인사이트:
    - CLS 이론은 **빠르지만 취약한 ‘해마 시스템(에피소드 저장)’과, 느리지만 일반화된 ‘신피질 시스템(스키마·개념)’이 상호 보완적으로 작동**한다고 주장한다.sciencedirect+2
    - 새로운 정보는 먼저 해마에 고도로 분리된 패턴으로 저장되고, 수면·오프라인 반복을 통해 신피질에 점진적으로 통합(interleaved learning)되며, 이 과정이 없으면 Catastrophic Forgetting이 발생한다.biorxiv+2
- 개인 온톨로지 적용:
    - 이미 6개 추상 레이어(경험 → 핵심 가치)를 설계하셨으므로, **하위 1–2 레이어를 “해마 레벨 에피소드 그래프”, 상위 3–6 레이어를 “신피질 스키마·가치 그래프”로 명시적으로 분리**하고, 야간/주기적 배치로 에피소드 패턴을 상위 스키마로 통합하는 파이프라인(리플레이)을 두면 CLS 이론과 정합적이다.[미검증]

## 3-3. Memory Reconsolidation (Nader)

**Memory reconsolidation: an update (2010), A single standard for memory (2009), Reconsolidation and the dynamic nature of memory (2015)**pubmed.ncbi.nlm.nih+4

- URL: https://pubmed.ncbi.nlm.nih.gov/20392274/, https://pubmed.ncbi.nlm.nih.gov/19229241/, https://pmc.ncbi.nlm.nih.gov/articles/PMC4588064/pubmed.ncbi.nlm.nih+2
- 핵심 인사이트:
    - 이미 공고화된 기억도 **재활성(리트리벌) 시 일시적으로 불안정 상태로 돌아가며, 다시 공고화(reconsolidation)를 거쳐야 지속된다**는 증거가 축적되었다.sciencedirect+3
    - 이 재공고화 단계는 기존 기억을 업데이트·약화·재구성할 기회를 제공하며, 임상적으로는 외상 기억 수정 등 응용이 논의된다.pmc.ncbi.nlm.nih+1
- 개인 온톨로지 적용:
    - 노드/서브그래프가 세션에서 조회될 때마다, 단순 조회가 아니라 **“재공고화 윈도우”를 열고: (1) 충돌 정보 탐지, (2) 요약·재구조화, (3) 엣지 가중치 재조정**을 수행하게 하면, 온톨로지가 정적 저장소가 아니라 재구성되는 기억에 가까워진다.[미검증]
    - 기술적으로는 “마지막 활성 timestamp + 활성 횟수 + 최근 맥락”을 노드 메타데이터에 저장하고, 재활성 시 작은 MLP/규칙 기반 레이어가 구조를 조정하도록 구현할 수 있다.[미검증]

---

## 4. 3K–100K 노드 그래프에서 커뮤니티·허브·이상 탐지

## 4-1. 커뮤니티 탐지 (Leiden, Louvain, Infomap 등)

**Comprehensive review of community detection in graphs (Neurocomputing 2024)**arxiv+1

- URL: https://www.sciencedirect.com/science/article/pii/S0925231224009408[[sciencedirect](https://www.sciencedirect.com/science/article/abs/pii/S0925231224009408)]
- 날짜: 2024-09-30[[sciencedirect](https://www.sciencedirect.com/science/article/abs/pii/S0925231224009408)]
- 핵심 인사이트:
    - 커뮤니티 검출 알고리즘을 **모듈러리티 최대화(Louvain/Leiden), 스펙트럴, 라벨 전파, 인포메이션 이론(Infomap)** 등으로 분류하고, 품질·복잡도·안정성 트레이드오프를 정리한다.arxiv+1
    - 큰 그래프(수만 노드)에서는 Louvain/Leiden이 여전히 기본 선택이며, Leiden이 Louvain의 결함(해로운 파티션, 불안정성)을 보완해 더 높은 모듈러리티와 안정적인 결과를 제공하는 것으로 보고된다.[[sciencedirect](https://www.sciencedirect.com/science/article/abs/pii/S0925231224009408)]

**Comparative study of Louvain, Leiden, Infomap (2024/25)**[[jetir](https://www.jetir.org/papers/JETIR2506955.pdf)]

- URL: https://www.jetir.org/papers/JETIR2506955.pdf[[jetir](https://www.jetir.org/papers/JETIR2506955.pdf)]
- 핵심 인사이트:
    - Reddit, Amazon, DBLP, Twitch 등 실제 네트워크에서 **Leiden이 모듈러리티와 Normalized Mutual Information(NMI) 측면에서 최고 성능, Louvain은 가장 빠른 베이스라인, Infomap은 플로우 기반 커뮤니티에 강점**을 보였다.[[jetir](https://www.jetir.org/papers/JETIR2506955.pdf)]
- 개인 온톨로지 적용:
    - 3.2K 노드 규모에서는 **Leiden을 기본 커뮤니티 탐지 알고리즘으로 사용하고, 빠른 실험에는 Louvain, “생각의 흐름/세션” 같은 플로우 분석에는 Infomap**을 사용하는 것이 합리적이다.[미검증]

## 4-2. 허브 탐지

**Integrated Hubness Score (IHS) – 세 중심성 통합 허브 지표**[[biorxiv](https://www.biorxiv.org/content/10.1101/2020.02.17.953430v1.full.pdf)]

- URL: https://www.biorxiv.org/content/10.1101/2020.02.17.953430v1.full.pdf[[biorxiv](https://www.biorxiv.org/content/10.1101/2020.02.17.953430v1.full.pdf)]
- 핵심 인사이트:
    - Degree, Betweenness, Neighborhood Connectivity 세 가지 중심성을 통합해 **위치 편향을 줄인 허브 점수(IHS)**를 제안, 200개 실세계/시뮬레이션 네트워크에서 다른 허브 지표보다 영향력 노드를 잘 찾는다고 보고했다.[[biorxiv](https://www.biorxiv.org/content/10.1101/2020.02.17.953430v1.full.pdf)]
- 개인 온톨로지 적용:
    - 노드 수 3K–100K면 IHS 계산이 현실적이므로, “삶에서 구조적으로 결정적인 개념/가치/프로젝트”를 자동 탐지할 때 IHS를 허브 점수로 쓰고, 허브 노드 주변의 엣지 학습률(가중치 업데이트 속도)을 높게 설정하는 전략을 사용할 수 있다.[미검증]

## 4-3. 그래프·지식 그래프 이상 탐지

**Deep Graph Anomaly Detection: Survey & New Perspectives (2024)**[[arxiv](https://arxiv.org/abs/2409.09957)]

- URL: https://arxiv.org/abs/2409.09957[[arxiv](https://arxiv.org/abs/2409.09957)]
- 날짜: 2024-09-15(v1), 2025-06-18(v2)[[arxiv](https://arxiv.org/abs/2409.09957)]
- 핵심 인사이트:
    - GNN 기반 그래프 이상 탐지(GAD)를 **백본 GNN 설계, Proxy Task(재구성, 예측, 대비학습 등), 이상 측정 지표** 세 관점으로 정리하고, 노드/엣지/서브그래프/그래프 단위 이상을 포괄적으로 다룬다.[[arxiv](https://arxiv.org/abs/2409.09957)]

**ADKGD: Anomaly Detection in Knowledge Graphs with Dual-Channel Training (2024)**[[arxiv](https://arxiv.org/html/2501.07078v1)]

- URL: https://arxiv.org/html/2501.07078v1[[arxiv](https://arxiv.org/html/2501.07078v1)]
- 날짜: 2024-01-13[[arxiv](https://arxiv.org/html/2501.07078v1)]
- 핵심 인사이트:
    - KG에서 트리플 추출 과정의 오류를 잡기 위해 **엔티티 뷰와 트리플 뷰 두 채널을 동시에 학습하고, 일관성 손실(consistency loss)으로 이상을 검출**하는 알고리즘을 제안, 여러 벤치마크에서 기존 방법보다 높은 이상 탐지 성능을 보인다.[[arxiv](https://arxiv.org/html/2501.07078v1)]
- 개인 온톨로지 적용:
    - “내 삶의 그래프”에도 잘못된 Hebbian 학습·잡음이 들어가므로, **(1) 노드 임베딩 기반 이상 점수, (2) 트리플 임베딩 기반 이상 점수를 같이 보고, 불일치가 큰 부분을 수동 검토 큐에 올리는 파이프라인**을 둘 수 있다.[미검증]

---

## 5. AI 시스템에서의 “망각” (Unlearning, Decay, Pruning)

## 5-1. Machine Unlearning (데이터 삭제/지식 제거)

**Machine Unlearning: A Comprehensive Survey (2024)**semanticscholar+1

- URL: https://dl.acm.org/doi/10.1145/3749987, https://arxiv.org/abs/2405.07406acm+1
- 날짜: arXiv 2024-05-12, ACM Computing Surveys 채택semanticscholar+1
- 핵심 인사이트:
    - 언러닝을 **정확(unlearning = 재학습과 동등) vs 근사, 중앙집중 vs 분산, 검증·공격 대응** 관점에서 분류하고, LLM·그래프 등 다양한 모델에 적용되는 기법을 체계적으로 정리한다.arxiv+2
    - 핵심 트레이드오프는 **망각 정확도(Forget Accuracy) vs 잔존 정확도(Retention Accuracy) vs 효율성**이며, 이 세 축을 동시에 만족시키는 것은 여전히 난제이다.ijsr+2
- 개인 온톨로지 적용:
    - “의도적 지식 폐기(예: 특정 관계·단계의 나 자신을 지우고 싶음)”를 지원하려면, 노드/엣지에 저장된 프로비넌스(근거)와 함께 **완전 삭제(정확 언러닝) vs 영향 최소화 근사 언러닝**을 선택하는 연산을 설계할 수 있다.[미검증]

## 5-2. 그래프·추천 시스템에서의 망각·감쇠

**Forgetting in Knowledge Graph Based Recommender Systems (DATA 2024)**[[cris.maastrichtuniversity](https://cris.maastrichtuniversity.nl/en/publications/forgetting-in-knowledge-graph-based-recommender-systems/)]

- URL: https://cris.maastrichtuniversity.nl/en/publications/forgetting-in-knowledge-graph-based-recommender-systems/[[cris.maastrichtuniversity](https://cris.maastrichtuniversity.nl/en/publications/forgetting-in-knowledge-graph-based-recommender-systems/)]
- 날짜: 2024-07-08[[cris.maastrichtuniversity](https://cris.maastrichtuniversity.nl/en/publications/forgetting-in-knowledge-graph-based-recommender-systems/)]
- 핵심 인사이트:
    - KG 기반 추천에서 사용자의 과거 구매/소비 이력을 모두 유지하면 검색공간·모델 복잡도가 증가하므로, **영향도 기반으로 불필요한 트리플을 삭제(forgetting)해 그래프를 단순화해도 추천 품질을 유지 혹은 개선할 수 있음**을 보여준다.[[cris.maastrichtuniversity](https://cris.maastrichtuniversity.nl/en/publications/forgetting-in-knowledge-graph-based-recommender-systems/)]

**Forgetting obsolete information improves stream-based recommenders**[[kmd.cs.ovgu](https://kmd.cs.ovgu.de/pub/matuszyk/KAIS17.pdf)]

- URL: https://kmd.cs.ovgu.de/pub/matuszyk/KAIS17.pdf[[kmd.cs.ovgu](https://kmd.cs.ovgu.de/pub/matuszyk/KAIS17.pdf)]
- 핵심 인사이트:
    - 데이터 스트림 기반 추천 시스템에서 **오래된 상호작용을 다양한 감쇠/삭제 전략으로 제거하면, 단순히 새 데이터만 추가하는 것보다 예측 성능이 유의하게 개선**된다는 실험 결과를 제시한다.[[kmd.cs.ovgu](https://kmd.cs.ovgu.de/pub/matuszyk/KAIS17.pdf)]

**Dynamic Forgetting & Spatio-Temporal Periodic Interest Modeling (STIM) (2024/25)**arxiv+1

- URL: https://arxiv.org/html/2508.02451[[arxiv](https://arxiv.org/html/2508.02451)]
- 핵심 인사이트:
    - 사용자의 반응은 **최근성(recency) + 주기성(periodicity)**을 따른다는 가정 하에, 에빙하우스형 망각 곡선을 모델에 도입해 긴 시퀀스에서 유효한 부분만 동적으로 마스킹하고, 추천 성능을 개선한다.arxiv+1
- 개인 온톨로지 적용:
    - 엣지마다 “마지막 사용 시점, 사용 빈도”를 기록하고, STIM처럼 **시간 감쇠 곡선(예: exp(-λΔt))를 엣지 가중치에 곱한 뒤, 임계값 이하 엣지는 자동 삭제/저해상도 요약 노드로 압축**하는 전략을 쓸 수 있다.[미검증]

---

## 6. 대규모 온톨로지의 버전 관리·타입 진화

## 6-1. SNOMED CT

**Versioning & Terminology Change Management (SNOMED Practical Guides, 2025)**docs.snomed+3

- URL: https://docs.snomed.org/snomed-ct-practical-guides/snomed-ct-data-analytics-guide/11-challenges/11.4-versioning, https://docs.snomed.org/snomed-ct-practical-guides/snomed-ct-terminology-services-guide/3-terminology-service-use-cases/terminology-change-managementsnomed+1
- 핵심 인사이트:
    - 국제판은 월 단위로 새로운 버전을 배포하며, 각 버전에 대해 **Snapshot(모든 구성요소의 최신 상태) + Full(전체 이력)** 파일을 제공, 구현자는 델타 또는 전체 스냅샷 로딩을 선택할 수 있다.[[docs.snomed](https://docs.snomed.org/snomed-ct-practical-guides/snomed-ct-data-analytics-guide/11-challenges/11.4-versioning)]
    - 개념 비활성화 시 “비활성 사유 + 대체 후보(역사 연관 refset)”를 기록하고, 모든 과거 정의·관계·설명을 조회할 수 있게 한다.snomed+1

## 6-2. Gene Ontology (GO)

**Gene Ontology knowledgebase in 2026 (2025, Genetics/Nature)**pmc.ncbi.nlm.nih+1

- URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC12807639/[[pmc.ncbi.nlm.nih](https://pmc.ncbi.nlm.nih.gov/articles/PMC12807639/)]
- 핵심 인사이트:
    - GO는 지속적으로 새로운 용어를 추가하고, **불분명/중복/사용되지 않는 용어를 대량으로 Obsolete 처리**하며, 2022년 이후로는 용어를 병합하지 않고 OBO의 `replaced_by` 태그를 통해 대체 용어를 명시하는 전략을 채택했다.academic.oup+1

**Obsoleting an Existing Ontology Term (GO/ODK 가이드)**go-ontology.readthedocs+1

- URL: https://ontology-development-kit.readthedocs.io/en/latest/ObsoleteTerm.html[[ontology-development-kit.readthedocs](https://ontology-development-kit.readthedocs.io/en/latest/ObsoleteTerm.html)]
- 핵심 인사이트:
    - 용어 폐지 전, 사용 중인 어노테이션·정의에서의 사용 여부를 점검하고, 관련 커뮤니티에 공지 후 Obsolete 처리, 필요한 경우 `replaced_by`나 `consider` 관계로 대체 용어를 연결한다.go-ontology.readthedocs+1

## 6-3. Wikidata & Schema.org

**Wikidata Deprecation & Ranks**wikidata+2

- URL: https://www.wikidata.org/wiki/Help:Deprecation[[wikidata](https://www.wikidata.org/wiki/Help:Deprecation)]
- 핵심 인사이트:
    - Wikidata는 진술을 삭제하는 대신 **랭크(normal/preferred/deprecated)** 로 관리하고, Deprecated는 기본 조회에서는 보이지 않도록 하되, 필요 시 전체 이력을 탐색할 수 있게 한다.wikidata+1
    - Deprecated 값에는 항상 `reason for deprecation`이 첨부되어야 하며, 잘못된 값도 이력으로 유지해 재추가를 방지하고, 지식 진화 맥락을 제공한다.lists.wikimedia+2

**Wikidata Ontology Evolution & Community-driven Subschemas**aclanthology+2

- URL: 예: https://aclanthology.org/2022WD.pdf (Analysing the Evolution of Community-Driven…), https://www.wikidata.org/wiki/Wikidata:WikiProject_Ontologyaic.ai.wu.ac+1
- 핵심 인사이트:
    - Wikidata 스키마는 상향식(bottom-up) 커뮤니티 편집을 통해 진화하며, 특정 도메인 커뮤니티가 사용하는 서브스키마의 발전 과정을 분석·시각화하는 연구가 진행되고 있다.wikidata+2

**Schema.org Release Listing & Evolution**[[schema](https://schema.org/docs/releases.html)]

- URL: https://schema.org/docs/releases.html[[schema](https://schema.org/docs/releases.html)]
- 핵심 인사이트:
    - Schema.org는 **버전 번호(예: 28.0, 2024-09-17)와 릴리스 노트**를 통해 새로운 타입·프로퍼티 추가, 정의 수정, `schemaVersion` 정의 명확화 등을 투명하게 공개한다.[[schema](https://schema.org/docs/releases.html)]
- 개인 온톨로지 적용:
    - SNOMED/GO/Wikidata/Schema.org 사례를 종합하면, **“삭제 대신 비활성/Deprecated + 이유 + 대체 링크 + 전체 이력 보존 + 정기 버전 스냅샷”**이 사실상 표준 패턴이다.
    - 개인 온톨로지도 노드/타입 ID는 가능한 한 재사용·불변으로 두고, 의미 변화·폐지는 별도 플래그와 `replaced_by`/`superseded_by` 관계로 표현하는 것이 장기적으로 안전하다.[미검증]

---

## 7. 급진적 단순화·플랫화가 검색 성능을 높인 사례

**Expert-guided, simplified views of ontologies (Scientific Data 2026)**pmc.ncbi.nlm.nih+1

- URL: https://www.nature.com/articles/s41597-025-06383-w[[nature](https://www.nature.com/articles/s41597-025-06383-w)]
- 날짜: 2026-01-08[[nature](https://www.nature.com/articles/s41597-025-06383-w)]
- 핵심 인사이트:
    - 생의학 대형 온톨로지는 매우 세밀하고 복잡해, 일반 사용자·특정 애플리케이션에는 과잉이므로, **전문가가 설계한 “simplified views(슬림 뷰)”를 생성해 검색·질의·주석 작업을 단순화하는 일반 전략**을 제시한다.pmc.ncbi.nlm.nih+1
    - 표준 용어·동의어를 유지하면서 계층·타입 일부를 접거나 제거한 뷰를 제공해, 데이터는 FAIR(Findable, Accessible, Interoperable, Reusable)하게 유지하면서 UX와 쿼리 구성을 쉽게 한다.pmc.ncbi.nlm.nih+1

**Direct Fact Retrieval from Knowledge Graphs without Entity Linking (DiFaR, 2023)**aclanthology+1

- URL: https://pure.kaist.ac.kr/en/publications/direct-fact-retrieval-from-knowledge-graphs-without-entity-linkin[[pure.kaist.ac](https://pure.kaist.ac.kr/en/publications/direct-fact-retrieval-from-knowledge-graphs-without-entity-linkin)]
- 핵심 인사이트:
    - 전통적인 **엔티티 인식 → 디스앰비규에이션 → 관계 분류** 3단계 파이프라인 대신, KG 트리플을 임베딩 공간에 올려 **쿼리-트리플 직접 근접 검색**으로 단일 스텝 검색을 수행, 여러 QA 태스크에서 경쟁력 있는 성능을 보였다.aclanthology+1
    - 이는 구조 자체를 단순화한 것이 아니라, **검색 파이프라인을 간소화해 오류 전파를 줄이고 성능을 개선**한 사례이다.pure.kaist.ac+1

**Dense XRetrieval: Retrieval Granularity Study (EMNLP 2024)**[[aclanthology](https://aclanthology.org/2024.emnlp-main.845.pdf)]

- URL: https://aclanthology.org/2024.emnlp-main.845.pdf[[aclanthology](https://aclanthology.org/2024.emnlp-main.845.pdf)]
- 핵심 인사이트:
    - Wikipedia를 **패시지/문장/“Proposition(사실 단위)”**로 나누어 밀집 검색을 수행한 결과, 다양한 QA·리트리벌 벤치마크에서 **Proposition 단위 검색이 문장·패시지보다 일관되게 높은 Recall@5 및 최종 QA 성능**을 보였다.[[aclanthology](https://aclanthology.org/2024.emnlp-main.845.pdf)]
    - 적절한 “단위 크기”로 구조를 재구성하는 것 자체가 검색 성능의 핵심 요소임을 보여준다.[[aclanthology](https://aclanthology.org/2024.emnlp-main.845.pdf)]

**HIRO: Hierarchical Information Retrieval Optimization (2024)**[[arxiv](https://arxiv.org/html/2406.09979v1)]

- URL: https://arxiv.org/html/2406.09979v1[[arxiv](https://arxiv.org/html/2406.09979v1)]
- 핵심 인사이트:
    - 문서 집합을 계층적 구조(요약 트리)로 저장하고, DFS 기반 유사도·브랜치 프루닝으로 **LLM에 전달하는 컨텍스트를 최소화하면서 정보 손실 없이 QA 성능을 향상**시키는 쿼리 전략을 제안한다.[[arxiv](https://arxiv.org/html/2406.09979v1)]
- 개인 온톨로지 적용:
    - 위 사례들은 “타입/계층을 무작정 줄이면 성능이 좋아진다”까지는 말하지 않지만,
        - (1) **전문가가 설계한 단순화 뷰(ontology slim)**,
        - (2) **검색 파이프라인 간소화**,
        - (3) **단위 크기 조정(Proposition 수준)**,
        - (4) **계층 트리 + 브랜치 프루닝**
            
            가 검색 성능·효율을 개선함을 보여준다.aclanthology+5
            
    - 개인 온톨로지에서도 “풀 스키마”와 별도로
        - LLM/RAG용 **Proposition 레벨 그래프 뷰**,
        - 사용자가 탐색할 때의 **슬림 뷰(핵심 타입·상위 계층만)**
            
            를 제공하면 구조는 유지하면서 검색 효율만 개선할 수 있다.[미검증]
            

---

## Claude 실행 지침 (구현 관점)

1. **온톨로지 메타/데이터 계층 분리**
    - `ontology_meta`(타입·관계·제약 정의, 버전 이력)와 `ontology_store`(노드·엣지 인스턴스)를 분리하는 Palantir식 구조를 채택.[[palantir](https://www.palantir.com/docs/foundry/object-backend/overview)]
    - 메타 변경 시, Object Storage V2처럼 증분 인덱싱·마이그레이션 잡를 설계.[[palantir](https://www.palantir.com/docs/foundry/object-backend/overview)]
2. **CLS 기반 2중 그래프 레이어 구현**
    - Layer 1–2: Rewind형 **에피소드/타임라인 그래프** (고해상도, 시간 축 중심).web.stanford+1
    - Layer 3–6: Mem/PKG형 **스키마/가치 그래프** (타입·가치·개념 중심).arxiv+2
    - 야간 배치로 에피소드 → 스키마 통합(리플레이) 파이프라인 구현.[미검증][[web.stanford](https://web.stanford.edu/~jlmcc/papers/McCMcNaughtonLampinen20IntegrNewInfoCLS.pdf)]
3. **Spreading Activation + Hebbian 엣지 학습 엔진**
    - 각 엣지에 `weight`, `last_used_at`, `use_count`를 저장하고, 쿼리 시 k-step spreading activation으로 활성 서브그래프를 생성.semanticscholar+1
    - 공활성 패턴에 따라 `weight`를 Hebbian 방식으로 업데이트(동시 활성 시 증가, 비활성 시 감쇠).[미검증]
4. **망각·감쇠·언러닝 연산 설계**
    - STIM·추천 논문을 참고해 **시간 감쇠 곡선 기반 엣지 가중치 감소 + 임계 이하 자동 삭제/요약** 구현.arxiv+3
    - Machine Unlearning 설문을 참고해, “특정 세션/문서/사건 기반의 노드·엣지 완전 삭제” 연산과, 근사적 영향 제거 연산을 분리 설계.arxiv+3
5. **커뮤니티·허브·이상 탐지 배치 잡**
    - 정기적으로 Leiden/Louvain/Infomap을 돌려 커뮤니티를 라벨링하고, IHS 중심성을 계산해 허브 노드를 추출.sciencedirect+2
    - ADKGD/Deep GAD 아이디어를 간소화해, 노드/트리플 임베딩 기반 이상 점수를 계산, 수동 검토용 큐에 적재.andrew.cmu+2
6. **버전 관리·Deprecated 정책**
    - SNOMED·GO·Wikidata를 참고해,
        - (a) 노드/타입 ID는 불변,
        - (b) 삭제 대신 `status = {active, inactive, deprecated}`,
        - (c) `reason`, `replaced_by`/`superseded_by` 메타데이터,
        - (d) 정기 버전 스냅샷(예: 월 1회 전체 dump)
            
            를 유지하는 버전 관리 모듈 구현.wikidata+4
            
7. **슬림 뷰·Proposition 뷰 생성 파이프라인**
    - Nature 슬림 뷰 전략 + Dense XRetrieval를 참고해,
        - (a) 전문가 규칙 기반 **슬림 뷰(핵심 타입, 상위 계층)**,
        - (b) 텍스트/이벤트를 **Proposition 단위 트리플**로 분해한 RAG용 뷰
            
            를 생성하고, HIRO식 계층 검색·브랜치 프루닝으로 LLM 컨텍스트를 최적화.nature+3
            

원하시면, 위 지침을 기준으로 **구체적인 데이터 구조·알고리즘 설계(타입 정의, 엣지 업데이트 루프, 배치 잡 스케줄링, RAG 쿼리 플로우)**를 Claude Code용 의사코드/모듈 설계 수준까지 쪼개 드릴 수 있다.