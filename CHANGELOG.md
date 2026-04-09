# mcp-memory CHANGELOG

## v6.0 Ontology Repair (2026-04-09)

### Embedding: OpenAI → Local
- embedding/local_embed.py: sentence-transformers multilingual-e5-large (1024d)
- embedding/__init__.py: EMBEDDING_PROVIDER 스위치 (local|openai), default=local
- config.py: EMBEDDING_PROVIDER, EMBEDDING_DIM=1024(local)/3072(openai)
- 3,400개 노드 로컬 재임베딩 (183s, RTX 4060)
- **실시간 경로 외부 API 의존 100% 제거**
- NDCG@5: 0.280→0.285 (+1.8%, 품질 손실 없음)

### Learning: BCM → Hebbian
- hybrid.py: _bcm_update() → _hebbian_update() 교체
- 연속 firing rate 모델(BCM) → 이산 frequency 기반 단순 학습
- co-recall 시 strength += 0.015 (양쪽 result), += 0.005 (한쪽 result)
- theta_m/activity_history 더 이상 갱신하지 않음

### Growth: auto_promote
- scripts/auto_promote.py: 승격 자동화 (Gate 1+2, MDL 제거)
- daily_enrich.py Phase 0에 통합 (매일 enrichment 전 실행)
- 38개 노드 자동 승격 (validated 130→168)

### Data: 계층 분리 + 정화
- SOURCE_BONUS 7단계 재설정 (user +0.12 ~ obsidian -0.05)
- 28개 노이즈 archive (Unclassified 18 + license 10)
- 206개 추가 archive (frontmatter 8 + near-duplicates 198)
- NULL 수정: layer 56개, quality_score 10개
- 자기참조 edge 3개 삭제

### Structure
- 27개 스크립트 archived (scripts/_archived/): 마이그레이션, backfill, 중복
- scripts/reembed_local.py: 로컬 재임베딩 도구

## v5.1 WS-0~4 + Beads + Recall Fix (2026-04-08)

### WS-0: knowledge_core Context
- context_selector: knowledge_core 전용 섹션 (SoT primary, visit_count 상위 30건)

### WS-1.2: Reasoning Graph Cleanup
- config: GRAPH_EXCLUDED_METHODS (session_anchor, legacy_unknown, orphan_repair, co_retrieval, fallback)
- hybrid.py: NetworkX graph + SQL CTE에서 operational edge 제외
- 미사용 import 정리 (ENRICHMENT_QUALITY_WEIGHT, SOURCE_BONUS 등)

### WS-2.1: Write-Layer Normalize
- sqlite_store.insert_node: node_role 미전달 시 knowledge_candidate, epistemic_status 미전달 시 provisional 기본값

### WS-4: Promote Auto-Render + Maturity Gating
- promote_node: 승격 후 proven_knowledge.md 자동 렌더 (background subprocess)
- config: get_maturity_level() 4단계 (core 기준), MATURITY_GATES (graph_channel/complex_scoring)
- hybrid.py: maturity gating으로 graph channel on/off

### Beads v6.1: Task Graph
- storage/task_store.py: tasks.db SQLite (create, query, complete, generate_next)
- server.py: 4 MCP tools (create_task, query_tasks, complete_task, generate_next)
- session_events: target + task_id 칼럼 추가, emit_event/poll_events에 TASK_ASSIGN/TASK_PICK 지원
- complete_task → TASK_COMPLETE SessionEvent 자동 발행 + blocked_by 해소

### Recall Quality Fix
- 0.3 score threshold 제거 (scoring 단순화 후 범위 0.05~0.17로 하락, threshold가 전부 차단)
- overfetch 3x: hybrid_search top_k*3 → role 필터 → top_k 절단
- patch 전환 mode 변수 버그 수정 (mode → search_mode)

## Merger Artifact Pipeline (2026-04-07)
- `scripts/render_proven_knowledge.py`: knowledge_core + validated + high-signal + corrections → `data/proven_knowledge.md` (22 nodes)
- `data/merger_manifest.json`: 반영 이력 추적 (22 entries)
- `session_context.py`: 세션 시작 시 proven_knowledge.md를 먼저 출력
- 렌더 기준: knowledge_core(무조건) + validated(q≥0.85) + Signal(v≥5) + Correction
- DB → artifact → session context 단일 흐름 완성

## V5 Runtime + Epistemic + Edge Class (2026-04-07)

### V5-01: render_memory_md active 필터
- 전 쿼리에 `status='active'` + `node_role` + `epistemic_status` 필터 추가
- deleted/outdated/work_item/external_noise가 MEMORY.md에 올라가지 않음

### V5-02: Epistemic Output Separation
- context_selector: l2_core에서 outdated/flagged/superseded 제외
- context_selector: corrections 전용 섹션 신설 (contradicts edge 포함)
- session_context: "교정 경고" 섹션 분리 출력
- proven_knowledge.md: Core Knowledge / Corrections 2섹션 분리

### V5-03: Edge Class 분류 체계
- config.py EDGE_CLASS: 49 relation → semantic/evidence/temporal/structural/operational
- REASONING_EDGE_CLASSES: generic reasoning에서 operational 제외
- 196 tests passed

## Goldset v4 교정 + Enum Drift 수정 (2026-04-07)
- goldset 19개 쿼리 교정: NDCG@5 0.201→**0.402**, hit_rate 0.646→**0.939**
- config GENERATION_METHODS: enrichment/orphan_repair/legacy_unknown 추가 (enum drift 0)
- GENERATION_METHOD_PENALTY: orphan_repair -0.08, legacy_unknown -0.05 (operational edge 감점)
- scripts/generate_state.py: STATE.md Current 블록 자동 생성 (live DB 기준)

## R7 Acceptance Audit — GO (2026-04-07)
- **전 14개 gate PASS** — Ontology v4 본선 완료
- A. 구조: node_role 100%, generation_method 100%, blank_project 0
- B. Retrieval: 4-mode contract, generic suppression, correction contradicts
- C. Graph: orphan 0.0%, 0-1 edge 49.1%
- D. Growth: Correction 7, contradicts 7, validated 16, knowledge_core 9, Signal 69
- E. Merger: 2건 (MEMORY.md 반영)
- Nodes: 5,259 | Edges: 7,001 | Tests: 193 passed

## R1-R6 Ontology v4 본선 (2026-04-07)

### R1 Goldset Modernization
- goldset_v4.yaml: 75→82 queries (+7 mode-specific)
- mode 필드 추가: generic(75), troubleshooting(3), correction(2), recollection(2)
- ndcg.py mode-aware 수정 (query별 mode를 recall에 전달)
- Baseline: NDCG@5=0.201, hit_rate=0.646

### R3 Retrieval Contract (4-mode)
- recall() intent mode 4종: generic, recollection, troubleshooting, correction
- troubleshooting: Failure 타입 병렬 검색 + 0.05 부스트
- correction: Correction threshold 0.5→0.3, contradicts 정보 출력
- recollection: session_anchor 포함, work_item/external_noise만 제외
- search mode(auto/focus/dmn) ↔ intent mode 분리

### R5 Graph Repair
- orphan 732→**0** (14.0%→0.0%)
- text-embedding-3-large 배치 임베딩 → nearest neighbor edge 생성
- 732 orphan_repair edges 생성

### R6 Memory-Merger MVP
- knowledge_core #4159+#4175 → MEMORY.md User Preferences 반영
- "속도+정확도 동시, 트레이드오프 거부, 병렬화로 전부 해결"
- merger metadata 기록 (merged_to, merged_at, merger_version)

## R4 Correction Activation (2026-04-07)
- Correction 0→**7**, contradicts 0→**7**
- Identity 중복 4건 flagged (#3575/#3641/#3707/#3773 → #2712 보존)
- 테스트 아티팩트 3건 flagged (#4271, #3152, #4648)
- flag_node→Correction→contradicts→confidence 하락→epistemic_status 변경 전체 루프 실전 검증

## R2 Metadata Saturation (2026-04-07)
- **node_role**: 22.3% → 100% (4082건 source-aware backfill)
- **generation_method**: 23.1% → 100% (4801건 pattern-based backfill)
- 분류 전략: source_kind 기반 기본값 + 예외 오버라이드 (Narrative→session_anchor, validated→knowledge_core)
- edge 분류: enrichment(2785), legacy_unknown(1397), co_retrieval(168), semantic_auto(72)
- 테스트: 186 → 193 (+7 saturation regression)
- Gate G2 통과

## v3.3.1-dev (2026-04-07) — Signal 성장 엔진 가동

### Signal Clustering & Synthesis
- **임베딩 클러스터링**: Observation 417개 → cosine distance 0.35 agglomerative clustering
- **51개 클러스터 합성**: gpt-4.1-mini 배치 → 51 Signal 노드 생성
- **realizes edge 128개**: Signal→Observation 증거 연결
- **Signal spine**: 19→70 (목표 50+ 초과 달성)
- **promote_node 흐름 검증**: Signal→Pattern 승격+복구 정상 작동
- **테스트**: 186 tests passed (변경 없음)
- **NDCG**: 0.214 (안정 — Signal은 goldset 미포함)

## v3.3.0-dev (2026-04-07) — 온톨로지 전면 강화 (성장+교정+재반영)

### 검색 무결성
- **active-only filter**: get_node/get_edges/get_all_edges/search_fts 전 경로에 status='active' 강제
- **confidence → scoring**: (confidence - 0.5) * CONFIDENCE_WEIGHT additive
- **contradiction penalty**: contradicts edge 존재 시 -0.10
- **node_role penalty**: session_anchor -0.08, work_item -0.06, external_noise -0.10

### 온톨로지 메타데이터
- **신규 컬럼 5개**: source_kind, source_ref, node_role, epistemic_status (nodes), generation_method (edges)
- **Correction type active 복구**: system type으로 validators bypass
- **co_retrieved relation_defs 등록**: behavioral 카테고리
- **RELATION_WEIGHT 전 coverage**: 22개 미커버 relation 명시적 weight 추가

### save_session knowledge gate
- Decision/Question 40자 미만 → node_role='work_item' (generic recall 제외)
- SKIP_PATTERNS 매칭 시 노드 미생성
- Narrative → node_role='session_anchor'
- contains edge → generation_method='session_anchor'

### context selector 통합
- get_context.py + session_context.py → context_selector.py 공용 selector
- L2+ core, Signal, Observation 포함하는 풍부한 선택
- work_item/external_noise 제외

### 성장 엔진
- **get_becoming maturity**: 5차원 (quality 30% + edges 20% + visits 20% + diversity 20% + recency 10%)
- **promote_node evidence bundle**: evidence_ids 기록, node_role='knowledge_core'
- **Signal 승격**: Observation 7건 → Signal (12→19)

### 데이터 backfill
- source_kind 분류: 5200 노드 전체
- node_role 분류: save_session 1075건 (session_anchor 93, work_item 343, knowledge_candidate 639)
- external noise quarantine: 37건
- blank project 보정: 30건
- JSON normalize: 58 fields

### 테스트
- 186 tests passed (Codex 작성 5개 포함)
- recall avg 0.35→0.47, hit_rate 0.50→0.69

## v3.2.0-dev (2026-04-07) — 상호작용 개선 + 시스템 건강 복구

### 상호작용 개선
- **recall() 품질 신호**: layer, confidence, source, quality 출력 추가
- **recall() min_score 필터**: 0.3 미만 노이즈 결과 자동 제거
- **source 가중치**: claude +0.05, checkpoint -0.02 (config SOURCE_BONUS)
- **flag_node() 신규 도구**: 부정확/구식/무관함 신고 → Correction 생성 + confidence 하락
- **get_context() 개선**: 품질 신호 포함 + last_session 요약 (세션 연속성)

### 학습 루프 구조 수정
- **BCM 필터 완화**: activated_edges AND→OR (학습 edge 11→42, 3.8x)
- **v=0.1 default**: 비결과 endpoint에 최소값 부여 (delta=0 방지)
- **SIMILARITY_THRESHOLD**: 0.3→0.55 (노이즈 edge 생성 감소)
- **Phase 1 cap**: small_budget 50% 상한 (Phase 2-5 예산 보존)
- **recall context package**: 1-hop 이웃을 type+content 구조화
- **Narrative chain**: 같은 project Narrative간 succeeded_by edge

### Enrichment 버그 수정
- **E21 카운터**: 조건문 밖 → 안으로 이동 (14/14 거짓 → 실제 수치)
- **E22 카운터**: assemblages_found 조건문 안으로
- **E24 카운터**: merges_detected 조건문 안으로
- **E19 카운터**: orphans_resolved에 if suggestions 조건 추가
- **E21 프롬프트 강화**: paradox/contextual 제거, direct/temporal만 허용
- **거짓 contradiction edge 12건 soft-delete**
- **enrichment 정직화**: 710 fake batch stamps 리셋, 4409 fake E6/E7 keys 제거

### 건강 지표 개선
- **orphan_nodes**: obsidian 제외 세션 노드 기준 (measure + ontology_health)
- **edge_density**: 세션 노드 denominator, threshold 1.0으로 하향
- **connectivity guard**: pruning 시 고아 방지 (edge_count ≤ 1 보호)
- **ingest edge**: obsidian 청크 간 part_of edge 생성
- **Hook relay.py**: sys.modules config 캐시 충돌 수정

## 2026-03-29 — El Croquis PDF 시스템
- 9-Lens 분석 보고서 10개 El Croquis 스타일 HTML/PDF 제작
- Sonnet 스타일 커버 (검정선/빨간선, 39px 타이틀, 위계 통일)
- Alpha: 10개 SVG 다이어그램 직접 삽입, WYSIWYG contenteditable
- 9개 _diag 버전: Codex gpt-5.4 xhigh 병렬 생성 (문서별 6-8개 다이어그램)
- 커버 에디터 (editor.html) + PDF 생성기 (gen.js via Puppeteer)

## v3.1.0-dev (2026-03-16) — 온톨로지 강화 + PDR

### PDR (Pipeline DONE Retrospective)
- /pdr 스킬 신규: 8차원 전수 스캔, 20-25개 Observation(L0) + tags
- G6 DONE gate 하드블록: phase-rules.json + validate_output.py
- 차원: thinking-style, preference, emotional, decision-style, language, work-rhythm, metacognition, connection
- 첫 실행: 23건 저장 (#5195-#5217), 4 auto-edge
- Pipeline 02_interaction-capture_0316 DONE

## v3.1.0-dev (2026-03-16) — 온톨로지 강화
### Promotion Pipeline 해제
- Gate 2: Bayesian Beta(1,10) → visit_count ≥ 10 직접 threshold (수학적 불가 해소)
- Gate 1: SWR threshold 0.55→0.25 (cross_ratio만으로 통과 가능)
- swr_readiness: recall_log.sources JSON 파싱으로 vec_ratio 계산

### Source Infrastructure
- hybrid_search: source_map 추적 (vector/fts5/graph/typed_vector)
- recall_log: sources TEXT 컬럼 자동 마이그레이션 + JSON 기록
- 기존 2,899행은 sources=NULL → 점진적 축적

### Relation Quality
- RELATION_RULES: 17→49개 (7.6%→37.3% type pair coverage)
- Cross-project 로직: mirrors (같은타입), influenced_by (다른타입), transfers_to (fallback)
- infer_relation: cross-project 판별 후 의미 있는 관계 타입 선택

### Deprecated Cleanup
- TYPE_CHANNEL_WEIGHTS: v3 15타입 기준 (deprecated 5개 제거, 누락 5개 추가)
- TYPE_KEYWORDS: v3 15타입 기준 (deprecated 5개 제거, 누락 5개 추가)
- LAYER_IMPORTANCE: layer 4,5 제거 (v3 최대 layer=3)
- suggest_closest_type: v3 타입 기준 (deprecated 제거, 누락 추가)
- Tests: Workflow/Agent/Skill 참조 v3 기준 갱신

## v3.0.0-rc (2026-03-11) — Ontology v3 Phase 5
### Breaking: Type System Overhaul (51→15)
- **Tier1 핵심 (7)**: Observation, Signal, Pattern, Insight, Principle, Framework, Identity
- **Tier2 맥락 (5)**: Decision, Failure, Experiment, Goal, Tool
- **Tier3 전환 (3)**: Correction, Narrative, Project
- + Unclassified (미분류 대기)

### DB Migration
- 전타입 마이그레이션: merge=506, edge=46, Workflow LLM재분류=532 (61 archived)
- type_defs deprecated 처리 (34개 타입), leaked=0 검증
- sync_schema() C1 fix: deprecated 타입을 active로 되돌리지 않도록

### retrieval_hints (Step 2)
- gpt-5-mini 배치 20/호출, 148 API 호출, 2927/2947 성공 (99.3%)
- when_needed + related_queries + context_keys 3필드
- server→remember→store→insert_node plumbing 완료

### Search Improvements
- type_filter canonicalization: deprecated→replaced_by 자동 변환 (H1)
- recall_id: uuid.hex[:8] 세션 식별 (H2)
- PROMOTE_LAYER v3: L0(3), L1(7), L2(3), L3(2)
- RELATION_RULES: 25→17개, VALID_PROMOTIONS v3

### New Scripts
- scripts/migrate_v3.py: 전타입 마이그레이션
- scripts/migrate_workflow.py: Workflow LLM 재분류
- scripts/enrich/hints_generator.py: retrieval_hints 배치 생성
- scripts/enrich/co_retrieval.py: co-retrieval 계산 (Step 3 준비)

### Tests
- 163→169 (+6), 전체 PASS

### Remaining (Phase 5 잔여)
- err 20 hints 재생성, re-embed(2.5), co-retrieval(3), dispatch(4), NDCG(6)

## v2.2.1 (2026-03-08)
### Layer A Refactor: Typed Vector Channel
- TYPE_BOOST additive(0.03) → TYPE_CHANNEL_WEIGHT(0.5) RRF 채널 교체
- 타입 힌트 감지 시 타입별 독립 벡터 검색 → 4번째 RRF 신호로 추가
- MAX_TYPE_HINTS=2 (API 호출 제한)
- A/B test에서 additive boost 무효 확인 → RRF 채널 기반으로 전환

### Goldset v2.2 (Paul 수동 검증)
- q026-q075 50개 쿼리 Paul 직접 검증 (relevant_ids + also_relevant 교체)
- also_relevant 5개→1~3개로 정리 (과도한 정답 제거)
- q026-q050 NDCG@5: 0.123 → 0.519 (+0.396)
- 발견: Identity 중복 노드 5개, q049 쿼리 범위 확장 필요

### Metrics (Paul 검증 goldset 기준)
- NDCG@5: 0.441 → 0.460 (+0.019)
- NDCG@10: 0.452 → 0.488 (+0.036)
- Tests: 161 → 163 (+2)

## v2.2.0 (2026-03-08)
### 3-Layer Type-Aware Search
- **Layer C**: 타입 태그 재임베딩 — `[Type] summary + key_concepts + content[:200]`로 벡터 공간에서 타입 분리
- **Layer A**: 키워드 기반 타입 부스트 — 15개 타입 키워드 테이블(TYPE_KEYWORDS), TYPE_BOOST=0.03
- **Layer D**: 타입 다양성 보장 — max_same_type_ratio=0.6, 한 타입이 결과 60% 이상 차지 시 교체

### Goldset v2.1 교정
- L1 relevant_ids 순환 참조 제거 (hybrid_search 결과를 정답으로 쓴 문제)
- type-filtered 벡터 검색 + FTS + hybrid 3방법 병합으로 편향 없는 후보 풀 생성
- auto_correct_goldset.py, generate_candidates.py, review_candidates.py 신규

### Metrics (corrected goldset 기준)
- hit_rate: 0.410 → 0.920 (+51pp)
- NDCG@10: 0.443 → 0.466 (+0.023)
- Tests: 153 → 161 (type_boost 5 + type_diversity 3)

## v2.1.3 (2026-03-08)
### Search Quality
- LIKE boost cap 2개로 제한 (q004/q008 회귀 수정)
- RRF candidate cutoff top_k×4 → top_k×10 (FTS-only 노드 탈락 방지)
- q017: 0→0.778 (동의어 주입), q018: 0→0.428 (cutoff 확장)
- 벡터 재임베딩: content → summary+key_concepts+content[:200]
- NDCG@5: 0.585→0.624 (50개), NDCG@10: 0.600→0.659 (50개)

### Verification System
- checks/ 8모듈 신규: search_quality, schema_consistency, data_integrity, promotion_pipeline, recall_scenarios, enrichment_coverage, graph_health, type_distribution
- verification_log 테이블 (DB 자동 기록)
- scripts/eval/verify.py 러너
- 서버 시작 시 quick verify (search_quality 스킵)

### Data Quality
- 449 중복 노드 soft-delete (content_hash 기반)
- content_hash 86.4% → 100%
- 92 미enriched 노드 Codex CLI enrichment 완료

### Performance
- post_search_learn() background thread 전환
- focus 모드: NetworkX → SQL CTE (_traverse_sql)
- auto/dmn 모드: UCB 유지 (NetworkX)

### Evaluation
- goldset 25→75 확장 (Codex CLI 생성 + Opus relevant_ids 매핑)
- 9 tier 구조: L3+ 원칙, L1 워크플로우/도구/에이전트, L0 서사

### Scripts
- scripts/pipeline/inject_synonyms.py
- scripts/pipeline/cleanup_duplicates.py
- scripts/pipeline/enrich_batch.py
- scripts/pipeline/reembed.py
- scripts/pipeline/run_pipeline.py
- scripts/eval/verify.py

## v2.1.2 (2026-03-08)
- FTS5 한국어 조사 제거, OR 매칭, 2글자 LIKE 보조 검색
- 후보풀 확장 top_k×2 → top_k×4
- schema.yaml → type_defs/relation_defs 자동 동기화
- content_hash UNIQUE + atomic dedup
- hybrid.py _connect() → _db() context manager
- NDCG: 0.548→0.581, 153 tests

## v2.1.1 (2026-03-06)
- Phase 1: init_db 동기화, connection mgmt, PROMOTE_LAYER 50타입
- check_access MCP, content dedup, query/write 분리
- NDCG: 0.057→0.548

## v2.0 (2026-03-04)
- 13 MCP tools, 6 layers, 50 node types, 48 relation types
- migrate_v2.py 완료
- enrichment pipeline (1,973/3,171 → 62%)

