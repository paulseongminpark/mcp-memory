# mcp-memory 온톨로지 종합 보고서
> 2026-04-10 작성 | v7.3 기준 | 모든 역사·현황·미래 방향 포함

---

## 0. 태초의 의도

> "Claude가 기억을 가진 채 시작하고, 그 기억이 성장/교정되고, 다시 운영 문서와 다음 세션으로 환류된다."

Paul의 근본 동기: **뇌의 다차원적 연결을 외부화하고 싶다.** 하나의 현상에서 과거-현재-미래를 동시에, 여러 각도에서 해석하는 방식 자체가 핵심. 이색적 접합 — 서로 다른 도메인의 개념을 연결해서 새로운 의미를 만드는 것. 이것을 AI/시스템으로 재현하는 것이 궁극적 목표.

2026-03-03 Paul + Claude 대담에서 7가지 결함을 진단하고 설계 원칙을 도출:
1. 다면 분류 (1노드=1타입이 아닌 primary+secondary+facets)
2. 경계 없는 연결 (project 벽 제거, cross-domain 기본)
3. 살아있는 강도 (Hebbian + 시간 감쇠)
4. Becoming (성숙도 + 승격 시스템)
5. 데이터 계층 (raw/refined/curated)
6. 도메인 확장 (인문/문학/예술)
7. 다중 관점 (Lens)

---

## 1. 버전 히스토리 — 거쳐온 모든 단계

| 버전 | 날짜 | 핵심 변경 | NDCG@5 |
|------|------|-----------|--------|
| v0.1 | 03-03 | 초기 설계 확정. 7 MCP tools, SQLite+FTS5+ChromaDB+NetworkX. 26타입, 33관계 | — |
| v2.0 | 03-04 | 13 tools, 6 layers, 50 types, 48 relations. 3-Store. enrichment 62% | 0.057 |
| v2.1.1 | 03-06 | init_db 동기화, PROMOTE_LAYER 50타입 | 0.548 |
| v2.1.2 | 03-08 | FTS5 한국어 조사 제거, content_hash UNIQUE | 0.581 |
| v2.1.3 | 03-08 | LIKE boost, RRF cutoff ×10, 449 중복 soft-delete | 0.624 |
| v2.2.0 | 03-08 | 3-Layer Type-Aware Search, hit_rate 41%→92% | — |
| v2.2.1 | 03-08 | TYPE_BOOST→RRF 4채널, Goldset v2.2 Paul 수동 검증 | 0.460 |
| v3.0-rc | 03-11 | **온톨로지 v3**: 51→15 타입 축소. 전체 마이그레이션. hints 99.3% | — |
| v3.1-dev | 03-16 | RELATION_RULES 17→49개, SWR 0.55→0.25, cross-project 관계 3종 | — |
| v3.2-dev | 04-07 | recall 품질 신호, flag_node, enrichment 버그 수정 | — |
| v3.3-dev | 04-07 | 온톨로지 전면 강화: active-only filter, 메타데이터 5컬럼, 186 tests | — |
| v3.3.1 | 04-07 | Signal 클러스터 합성: 417 Obs → 51 Signal, realizes 128개 | — |
| v4 본선 | 04-07 | 14 gate 전부 PASS. 5,259 노드, 7,001 에지, 193 tests | — |
| v5.1 | 04-08 | Beads, maturity gating, overfetch 3x | — |
| **v6.0** | **04-09** | **Local embedding (multilingual-e5-large 1024d). BCM→Hebbian. auto_promote** | 0.285 |
| v6.0.1 | 04-09 | Time decay, pruning, growth hook | — |
| **v7.0** | **04-10** | **1-Store: ChromaDB→SQLite BLOB. config 3분할. enrichment 1모델** | — |
| v7.1 | 04-10 | 50-세션 시뮬레이션: 890승격, validated 6.3%→33.6% | 0.293 |
| **v7.2** | **04-10** | **Goldset v4 동기화: NDCG 0.293→0.425 (+45%)** | **0.425** |
| v7.3 | 04-10 | 성능 4건: 콜드스타트 제거, N+1 fix, 커넥션/임베딩 캐싱 | — |
| v7.3-enr | 04-10 | Gemini 2.5 Flash cross-domain 489 에지. 19.3%→25.1% | — |

---

## 2. 현재 아키텍처

### 2.1 저장소 (1-Store, v7.0~)
- **SQLite 단일 DB**: `data/memory.db` (nodes + edges + FTS5)
- `data/tasks.db`: Beads 태스크 그래프 (4 MCP tools)
- ~~ChromaDB~~ v7.0에서 제거 (631MB 회수 가능)
- 벡터: `nodes.embedding` BLOB (float32, 1024d, ~13MB, 3,225개)
- 서버 시작 시 전체 벡터 메모리 캐시 (brute-force cosine, ~0.5ms)
- PRAGMA: WAL, busy_timeout 5000ms, cache_size 20MB

### 2.2 검색 (Hybrid 3+1채널 RRF)
1. **Vector**: SQLite BLOB + numpy cosine similarity
2. **FTS5**: SQLite 전문검색 (한국어 조사 제거, OR 매칭, 2글자 LIKE 보조)
3. **Graph**: SQL CTE(focus) / NetworkX(auto/dmn), UCB traversal
4. **Typed Vector** (조건부): 타입 힌트 감지 시 추가 4번째 채널
- **Reranker**: ms-marco-MiniLM-L-6-v2 (cross-encoder, local)
- **RRF 공식**: `score = Σ (1 / (RRF_K + rank_i))` across channels

### 2.3 학습
- **Hebbian**: frequency-based. co-recall 시 edge strength += 0.015 (양쪽 result), += 0.005 (한쪽만)
- **시간 감쇠**: 0.999^days, floor 0.05 (daily_enrich Phase 6)
- **Pruning**: strength < threshold 에지 제거 (첫 실행 199 pruned)

### 2.4 성장 사이클
```
remember() → 신규 노드 생성 (provisional)
    ↓
daily_enrich Phase 0: auto_promote (visit+edges+quality 기준)
    ↓
recall() → Hebbian 학습 (edge strength 증가)
    ↓
daily_enrich Phase 1-5: LLM enrichment (summary, hints, edges)
    ↓
daily_enrich Phase 6: 시간 감쇠 + pruning
```

### 2.5 MCP Tools (18개)
remember, recall, get_context, save_session, flag_node, promote_node, emit_event, resolve_event, analyze_signals, get_becoming, generate_next, dashboard, visualize, export_ontology, ontology_review, create_task, complete_task, query_tasks

---

## 3. 온톨로지 스펙

### 3.1 노드 타입 (15 active + 2 system)

| Tier | 타입 | Layer | 역할 |
|------|------|-------|------|
| **Tier 1 핵심** | Observation | L0 | 원시 관찰. 성장 시작점 |
| | Signal | L0 | 반복 관찰에서 패턴 전조 |
| | Pattern | L2 | 검증된 반복 패턴 |
| | Insight | L2 | 단발 통찰 |
| | Principle | L3 | 추상화된 원칙 |
| | Framework | L2-L3 | 구조화된 지식 체계 |
| | Identity | L3 | Paul 자기 서술 |
| **Tier 2 맥락** | Decision | L1 | 결정과 근거 |
| | Failure | L1 | 실패와 교훈 |
| | Experiment | L1 | 실험과 결과 |
| | Goal | L1 | 목표와 방향 |
| | Tool | L1 | 도구/환경 정보 |
| **Tier 3 전환** | Correction | system | 오류 교정 |
| | Narrative | L1 | 세션 기록 |
| | Project | L0 | 프로젝트 메타 |
| system | Unclassified | L1 | 미분류 대기 |

### 3.2 승격 경로
```
Observation ──triggered_by──→ Signal
Signal ──realized_as──→ Pattern / Insight
Pattern ──crystallized_into──→ Principle / Framework
Insight ──crystallized_into──→ Principle / Framework
```

### 3.3 관계 타입 (49개, 9 카테고리)
- **causal (8)**: caused_by, led_to, triggered_by, resulted_in, resolved_by, prevented_by, enabled_by, blocked_by
- **structural (9)**: part_of, composed_of, extends, governed_by, governs, instantiated_as, expressed_as, contains, derived_from
- **layer_movement (6)**: realized_as, crystallized_into, abstracted_from, generalizes_to, constrains, generates
- **diff_tracking (4)**: differs_in, variation_of, evolved_from, succeeded_by
- **semantic (8)**: supports, contradicts, analogous_to, parallel_with, reinforces_mutually, connects_with, inspired_by, exemplifies
- **perspective (5)**: viewed_through, interpreted_as, questions, validates, contextualizes
- **temporal (4)**: preceded_by, simultaneous_with, born_from, assembles
- **cross_domain (6)**: transfers_to, mirrors, influenced_by, showcases, correlated_with, refuted_by
- **behavioral (1)**: co_retrieved

### 3.4 Node Roles
| Role | 용도 | Scoring 영향 |
|------|------|-------------|
| knowledge_core | 핵심 지식 (context 필수 포함) | — |
| knowledge_candidate | 승격 대기 (기본값) | — |
| session_anchor | 세션 컨텍스트 | -0.08 penalty |
| work_item | 작업 항목 | -0.06 penalty |
| external_noise | 노이즈 | -0.10 penalty |

### 3.5 Epistemic Status
provisional → validated → knowledge_core (승격)
outdated, flagged, superseded (퇴화)

---

## 4. 검색 파라미터 (모든 상수)

| 파라미터 | 값 | 비고 |
|---------|-----|------|
| RRF_K | 18 | 60→18 (NDCG +12.5%) |
| GRAPH_BONUS | 0.005 | 기본 그래프 보너스 |
| SIMILARITY_THRESHOLD | 0.55 | 에지 생성 최소 유사도 |
| DEFAULT_TOP_K | 5 | 기본 반환 수 |
| GRAPH_MAX_HOPS | 2 | 그래프 탐색 깊이 |
| RERANKER_WEIGHT | 0.35 | reranker 가중치 |
| RERANKER_GAP_THRESHOLD | 0.05 | reranker 적용 최소 갭 |
| RERANKER_CANDIDATE_MULT | 3 | overfetch 배수 |
| TYPE_CHANNEL_WEIGHT | 0.5 | 타입 채널 기본 가중치 |
| MAX_TYPE_HINTS | 2 | 타입 힌트 최대 개수 |
| DECAY_LAMBDA | 0.01 | 시간 감쇠 (half-life ~69일) |
| PROMOTED_MULTIPLIER | 1.5 | 승격 후보 부스트 |
| CONFIDENCE_WEIGHT | 0.05 | confidence 가중치 |
| CONTRADICTION_PENALTY | -0.10 | contradicts 에지 페널티 |
| COMPOSITE_WEIGHT_DECAY | 0.001 | recency tiebreaker |
| COMPOSITE_WEIGHT_IMPORTANCE | 0.001 | layer tiebreaker |

### SOURCE_BONUS (7단계)
user: +0.12 > claude: +0.08 > checkpoint: +0.04 > (neutral) > save_session: -0.02 > pdr: -0.02 > hook: -0.04 > obsidian: -0.05

### UCB 탐험 계수 (mode별)
focus: 0.3, auto: 1.0, dmn: 2.5

### GRAPH_BONUS_BY_CLASS
semantic: 0.015, evidence: 0.012, temporal: 0.005, structural: 0.002, operational: 0.0

### Maturity Gating
- Level 0 (bootstrap): knowledge_core < 20
- Level 1 (growing): 20 ≤ core < 50
- Level 2 (mature): 50 ≤ core < 100 — graph_channel ON
- Level 3 (full): core ≥ 100 — complex_scoring ON ← **현재 여기 (core=205)**

---

## 5. Enrichment 파이프라인 (daily_enrich.py)

| Phase | 모델 | 토큰 예산 | 작업 |
|-------|------|-----------|------|
| 0 | (무비용) | — | auto_promote 실행 |
| 1 | gpt-5-mini | 1,800K | E1-E5, E7-E11, E13-E14, E16-E17: 신규 노드 통합 enrichment |
| 2 | o3-mini | 450K | E15(edge direction), E20-E22(temporal/contradiction/assemblage) |
| 3 | gpt-4.1 | 50K | E6(secondary_types), E12(layer verification) |
| 4 | gpt-5.2 | 100K | E18-E19, E24-E26(cluster/missing links/merge/edge descriptions) |
| 5 | o3 | 75K | E23(Signal→Pattern/Principle 승격 판단) |
| 6 | (DB) | — | 시간 감쇠, edge pruning, 30일 archive |
| 7 | — | — | 리포트 생성 |

### API Provider
- **OpenAI**: gpt-5-mini / o3-mini / gpt-4.1 / gpt-5.2 / o3 (무료 데이터 공유 프로그램)
- **Gemini**: 2.5 Flash via Vertex AI (GCP project-d8e75491-ca74-415f-802, 42만원 크레딧)
- **Anthropic**: claude-haiku-4-5 / claude-sonnet-4-6 (대체 경로)

---

## 6. 현재 DB 실측 (2026-04-10)

### 6.1 규모
| 항목 | 수치 |
|------|------|
| Active 노드 | 3,225 |
| Active 에지 | 6,905 |
| Archived 노드 | 2,156 |
| validated | 1,095 (34.0%) |
| knowledge_core | 205 |
| provisional | 2,106 (65.3%) |
| NDCG@5 | **0.425** |
| hit_rate | **87.8%** |
| cross-domain | **25.1%** (~1,735 에지) |
| missing embedding | 4 (0.1%) |
| co-retrieval edges | 145 |
| Gemini edges | 644 |

### 6.2 타입 분포 + 건강도

| 타입 | 수 | avg visit | zero% | avg quality | 진단 |
|------|-----|-----------|-------|-------------|------|
| Decision | 728 | 1.87 | 59.6% | 0.813 | 운영 결정 과다 |
| Observation | 390 | 0.29 | **80.5%** | 0.796 | ⚠️ 성장 시작점 방치 |
| Principle | 339 | 5.70 | 10.3% | 0.856 | ✅ 건강 |
| Insight | 333 | 1.01 | 57.4% | 0.831 | 중간 |
| Pattern | 285 | 1.49 | 47.7% | 0.803 | 중간 |
| Tool | 219 | 0.68 | 65.8% | 0.804 | 연결 부족 |
| Narrative | 153 | 0.41 | 77.1% | 0.775 | 세션 로그, 예상 |
| Framework | 149 | 2.58 | 47.7% | 0.821 | 중간 |
| Failure | 137 | 1.75 | 38.7% | 0.801 | 개선 가능 |
| Goal | 135 | 3.01 | 22.2% | 0.820 | ✅ |
| Project | 106 | 1.09 | 61.3% | 0.810 | 메타, 예상 |
| Question | 96 | 0.44 | 78.1% | 0.738 | ⚠️ 미활용 |
| Signal | 59 | 0.76 | 64.4% | 0.811 | 승격 대기 |
| Experiment | 48 | 2.33 | 10.4% | 0.807 | ✅ |
| Identity | 41 | **7.39** | 7.3% | 0.813 | ✅ 최고 활용 |
| Correction | 7 | 0.00 | **100%** | 0.579 | ⚠️ 완전 방치 |

### 6.3 에지 분포

| relation | 수 | avg strength | 비고 |
|----------|-----|-------------|------|
| supports | 1,100 | 0.719 | 최다 |
| contains | 962 | 0.847 | 계층 |
| led_to | 655 | 0.626 | 인과 |
| expressed_as | 581 | 0.752 | 표현 |
| part_of | 390 | 0.727 | 구조 |
| generalizes_to | 370 | 0.713 | 추상화 |
| co_retrieved | 145 | 0.417 | 실사용 |

### 6.4 generation_method 분포
| 방법 | 수 | 비율 |
|------|-----|------|
| semantic_auto | 2,701 | 39.2% |
| enrichment | 2,118 | 30.7% |
| session_anchor | 900 | 13.1% |
| gemini-enrichment | 644 | 9.3% |
| orphan_repair | 223 | 3.2% |
| co_retrieval | 145 | 2.1% |
| rule | 134 | 1.9% |

### 6.5 source_kind 분포
| 소스 | 수 | avg quality |
|------|-----|------------|
| obsidian | 1,550 | 0.817 |
| save_session | 449 | 0.770 |
| pdr | 422 | 0.804 |
| checkpoint | 349 | 0.838 |
| claude | 267 | 0.820 |
| user | 46 | **0.866** |

---

## 7. 거쳐온 모든 파이프라인과 결정

### 7.1 ontology-maturation (05, CLOSED 2026-04-10)
**목적**: "좋은 memory system" → "Claude 운영체계로 쓰이는 ontology"

**WS 구조**: WS-0(평가기준동결) → WS-1(SoT+Retrieval) → WS-2(데이터성숙) → WS-3(그래프의미화) → WS-4(루프폐쇄)

**Paul 결정 3건 (04-08)**:
1. SoT = get_context() primary, proven_knowledge.md fallback
2. MEMORY.md = 분리 유지
3. quality_score = maturity gating 위임

**성공 기준 6/6 달성 (04-10)**:
- NDCG@5 0.425 (목표 0.35) ✅
- knowledge_core 205 (목표 50) ✅
- operational edges 0 ✅
- low-edge <25%: 15.3% ✅
- SoT 단일화 ✅
- writer blank 0 ✅

### 7.2 ontology-repair (06, ACTIVE — Harden)
**목적**: v6.0→v7.0 인프라 수리 + 신경망 메커니즘

**주요 결정 (04-09~10)**:
- embed_text() OpenAI → local
- BCM → frequency-based Hebbian
- ChromaDB → SQLite BLOB (1-Store)
- config 3파일 분리
- enrichment 5모델 → 1모델
- SOURCE_BONUS 7단계

**50-세션 시뮬레이션 결과**:
- 890건 승격 (validated 6.3%→34%)
- 489 Gemini 에지 (cross-domain 19.3%→25.1%)
- NDCG 0.293→0.425 (goldset 동기화)

### 7.3 ontology-llm-ideation (personal-llm 01, ACTIVE — Diagnose)
**목적**: 온톨로지 기반 Paul 개인화 LLM 훈련

**CRITICAL 3건 미수정**:
- C1: finetune.py argparse 미동기화
- C2: Windows 경로 하드코딩
- C3: Multi-judge 비용 과소추정

---

## 8. 발견된 문제점 (Triage)

### P0 — 즉시 수정 (구조적 장애)

| # | 문제 | 영향 | 원인 | 해결 |
|---|------|------|------|------|
| P0-1 | **maturity 필드 전부 0.0** | 승격 파이프라인 판단 불가 | maturity 업데이트 함수 미호출 | visit+edges+co_retrieval 복합 공식 구현 |
| P0-2 | **observation_count 전부 0** | Obs→Signal 자동 승격 불가 | 카운터 집계 로직 미구현 | edge 수 기반 역산 or recall 시 카운팅 |
| P0-3 | **direction=NULL 에지 77.8%** | 그래프 계층 탐색 최적화 불가 | 일괄 방향 추론 미실행 | relation→direction 매핑 일괄 업데이트 |

### P1 — 높은 우선순위 (검색/성장 품질)

| # | 문제 | 영향 | 해결 |
|---|------|------|------|
| P1-1 | Observation 80.5% zero-visit | 성장 파이프라인 시작점 방치 | recall 시 Observation boost or 강제 노출 |
| P1-2 | retrieval_hints 276개 NULL | 키워드 검색 히트 -8.6% | hints 자동 생성 (scripts/hints_generator.py ready) |
| P1-3 | co_retrieval 에지 strength 0.417 | 실사용 패턴 반영 약함 | visit 비례 동적 강화 |
| P1-4 | cross-domain 25.1% (목표 30%) | 이색적 접합 미달 | Gemini enrichment 추가 배치 |
| P1-5 | 고품질 미방문 노드 500+ (quality≥0.85, visit=0) | 잠자는 가치 | 탐색 다양성 보너스 구현 |

### P2 — 중간 우선순위 (데이터 품질)

| # | 문제 | 해결 |
|---|------|------|
| P2-1 | Correction 7개 전부 visit=0, quality 0.579 | 검색 경로에 포함 or 타입 재평가 |
| P2-2 | <50자 초단문 노드 190개 | 병합 or archive |
| P2-3 | 고아 노드 91개 (Tool 35, Goal 20, Project 14) | 수동 연결 or orphan_repair 재실행 |
| P2-4 | promotion_candidate 17개 방치 | auto_promote 스캔 확대 |
| P2-5 | enrichment 미보강 98개 | daily_enrich 실행 |

### P3 — 장기 개선 (아키텍처)

| # | 방향 | 기대 효과 |
|---|------|----------|
| P3-1 | NetworkX 잔존 제거 (auto/dmn SQL CTE 전환) | 의존성 제거, 1-Store 완성 |
| P3-2 | Gemini enrichment를 daily_enrich 통합 | 자동화 |
| P3-3 | maturity 계산 공식 구현 + epistemic_status 자동 갱신 | 성장 파이프라인 자동화 |
| P3-4 | cross-domain recall 알고리즘 개선 (project 벽 약화) | 이색적 접합 강화 |

---

## 9. Scope 분류

### Scope A: DB 데이터 품질
- maturity 필드 활성화 (P0-1)
- observation_count 역산 (P0-2)
- direction 일괄 추론 (P0-3)
- hints 276개 생성 (P1-2)
- 초단문 190개 정리 (P2-2)
- 고아 91개 연결 (P2-3)
- 미보강 98개 enrichment (P2-5)

### Scope B: 검색 알고리즘
- Observation boost (P1-1)
- co_retrieval strength 동적 강화 (P1-3)
- 탐색 다양성 보너스 (P1-5)
- cross-domain recall 개선 (P3-4)
- NetworkX→SQL CTE (P3-1)

### Scope C: 성장 파이프라인
- Obs→Signal 자동 승격 (P0-2 + P1-1)
- promotion_candidate 스캔 확대 (P2-4)
- maturity 계산 구현 (P3-3)
- Gemini enrichment 자동화 (P3-2)

### Scope D: Claude Code 상호작용
- Correction 노드 검색 포함 (P2-1)
- recall 시 Failure/Question 타입 부스트
- get_context() 반환에 미방문 고품질 노드 포함
- remember() 시 maturity/observation_count 자동 갱신

---

## 10. 기술 스택 전체

### 저장소
| 기술 | 역할 | 상태 |
|------|------|------|
| SQLite 3.x | 1-Store (노드, 에지, FTS5, 벡터 BLOB) | ✅ 운영 |
| tasks.db | Beads 태스크 그래프 | ✅ 운영 |
| ~~ChromaDB~~ | 벡터 DB | v7.0 제거 |
| ~~NetworkX~~ | 그래프 탐색 | auto/dmn 잔존 |

### 임베딩
| 모델 | 차원 | 용도 |
|------|------|------|
| intfloat/multilingual-e5-large | 1024d | 현재 기본 (local) |
| text-embedding-3-large (OpenAI) | 3072d | 폴백 |
| ms-marco-MiniLM-L-6-v2 | — | reranker (cross-encoder) |

### LLM
| 모델 | Provider | 용도 |
|------|----------|------|
| gpt-5-mini | OpenAI (무료) | enrichment Phase 1 |
| o3-mini | OpenAI (무료) | enrichment Phase 2 |
| gpt-4.1 | OpenAI (무료) | enrichment Phase 3 |
| gpt-5.2 | OpenAI (무료) | enrichment Phase 4 |
| o3 | OpenAI (무료) | enrichment Phase 5 (승격 판단) |
| gemini-2.5-flash | GCP Vertex AI | cross-domain enrichment |

### Python 의존성
fastmcp, sentence-transformers, numpy, sqlite3, python-dotenv, google-genai

### 런타임
- FastMCP stdio 모드
- CONCURRENT_WORKERS=10, BATCH_SIZE=10
- thread-local SQLite 연결 재사용
- embed_text dict 캐시 (max 32)
- 서버 시작 시 SentenceTransformer + CrossEncoder + 벡터 캐시 preload

---

## 11. 방법론

### 검색 품질 측정
- **Goldset v4**: 82 쿼리, Paul 수동 검증 (2026-04-10 동기화)
- **NDCG@K**: K=5, K=10
- **hit_rate**: 상위 K에 gold ID 1개 이상 포함 비율
- goldset 변경 시 별도 파일 (v5) + 이전 결과 보존

### 승격 판단
- **SWR (Source-Weighted Recall)**: 소스별 가중치 적용 recall 점수
- **auto_promote**: visit + edges + quality 기준 (daily_enrich Phase 0)
- **수동 대규모**: visit≥2 AND edges≥2 AND quality≥0.7 → validated (이번 세션)

### 크로스도메인 에지 생성
- **co_retrieval**: recall 시 동시 반환된 노드 쌍 자동 에지
- **Gemini enrichment**: isolated 노드 + 다른 프로젝트 후보 → LLM 관련성 판단
- **enrichment pipeline**: daily_enrich E19(missing links)

### 데이터 수집 경로
| 경로 | source_kind | 빈도 |
|------|-------------|------|
| Claude remember() | claude | 실시간 |
| checkpoint 스킬 | checkpoint | 수동 |
| save_session | save_session | 세션 종료 |
| PDR (Pipeline Done Retrospective) | pdr | 파이프라인 완료 시 |
| Hook (PostToolUse) | hook | 자동 |
| Obsidian ingest | obsidian | 초기 1회 |
| User 직접 입력 | user | 수동 |

---

## 12. 다음 세션 작업 목록 (우선순위)

### 즉시 (P0)
1. [ ] maturity 필드 계산 공식 구현 + 일괄 업데이트
2. [ ] observation_count 역산 (에지 수 기반)
3. [ ] edge direction 일괄 추론 (relation→direction 매핑)

### 높음 (P1)
4. [ ] retrieval_hints 276개 자동 생성
5. [ ] cross-domain 30% 달성 (Gemini 추가 배치)
6. [ ] Observation recall boost 구현
7. [ ] co_retrieval strength 동적 강화

### 중간 (P2)
8. [ ] 초단문 190개 정리
9. [ ] 고아 91개 연결
10. [ ] enrichment 미보강 98개 실행
11. [ ] promotion_candidate 17개 수동 승격 검토

### 장기 (P3)
12. [ ] NetworkX 완전 제거 → SQL CTE
13. [ ] Gemini enrichment daily_enrich 통합
14. [ ] 성장 파이프라인 자동화 (maturity→epistemic_status)
15. [ ] recall 시 미방문 고품질 노드 탐색 다양성 보너스

---

## 13. 핵심 파일 경로

| 파일 | 역할 |
|------|------|
| `STATE.md` | 현재 상태 SoT |
| `CHANGELOG.md` | 버전 이력 |
| `config.py` | 진입점 (81줄) |
| `config_search.py` | 검색 파라미터 (308줄) |
| `config_ontology.py` | 온톨로지 상수 (329줄) |
| `storage/hybrid.py` | 핵심 검색 엔진 |
| `storage/sqlite_store.py` | DB 추상화 |
| `storage/vector_store.py` | 벡터 저장소 |
| `embedding/local_embed.py` | 로컬 임베딩 |
| `tools/remember.py` | 노드 생성 |
| `tools/recall.py` | 검색 |
| `tools/get_context.py` | 세션 컨텍스트 |
| `scripts/daily_enrich.py` | enrichment 오케스트레이터 |
| `scripts/auto_promote.py` | 자동 승격 |
| `scripts/eval/ndcg.py` | 검색 품질 측정 |
| `scripts/eval/goldset_v4.yaml` | 평가 기준 (82 쿼리) |
| `scripts/gemini_cross_domain.py` | Gemini 크로스도메인 에지 |
| `data/memory.db` | 운영 DB |
| `data/backup/` | DB 백업 |

---

_이 문서는 다음 세션에서 온톨로지 작업 시작 전 읽는 마스터 레퍼런스._
_모든 수치는 2026-04-10 기준. 작업 진행에 따라 갱신 필요._
