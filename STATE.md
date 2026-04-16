# mcp-memory — STATE
_Updated: 2026-04-14_

## Current
- **Version**: v8.2.0 (Dual-provider + OpenAI Free Tier)
- **Masterplan Basis**: `MASTERPLAN-FINAL-v3.md` → **v8 Architecture Spec v3** (Phase 0 완료)
- **Phase 0 Exit**: 5/5 PASS (2026-04-12)
- **전구간 자동화**: captures→claims→traits→policy→context_pack→Claude 완전 자동 루프
- **Task Scheduler**: `mcp-memory-daily-enrich` Disabled (수동 실행 전환, 04/16)
- **Bulk API**: gpt-4.1 (OpenAI 대형풀 250K/일 free tier, 최고 지능)
- **Fallback**: Groq 70b → Gemini 3 Flash (자동 전환, 3회 재시도 후 fallback)

## Ontology Redesign (v8 — Phase 0 DONE)
- **Pipeline**: `07_ontology-redesign_0410` (status: DONE)
- **Phase**: DONE (G1-G6 PASS, 2026-04-12)
- **설계 SoT**: `20_architect-r1/03_architecture-spec-v3.md`
- **구현 가이드**: `39_build-merged/01_final-impl-guide.md`

### Multi-provider Hardening + 04/14 장애 복구 (2026-04-14)
- **04/14 06:00 장애**: Phase 1 E13/E14/E16/E17 35건 전량 401 인증 실패
  - 원인: Windows User env에 `GROQ_API_KEY=gsk_gsk_...` 이중 프리픽스 오염
  - dotenv 기본 `override=False`라 .env의 올바른 값이 덮이지 못함
- **Node/Graph Groq 라우팅 누락 발견**: v8.1에서 relation_extractor만 Groq 라우팅 추가, node_enricher/graph_analyzer는 누락 → 동일 패턴으로 수정
- **openai SDK 무한 backoff hang**: 429 발생 시 SDK 기본 retry가 지수 backoff로 hang 유발 → `max_retries=0` + `timeout=30s` 필수
- **Groq 무료 tier 실측 한도**:
  - llama-3.3-70b-versatile: **TPD 100K (금방 소진)**, RPM 30
  - llama-3.1-8b-instant: TPD 500K (여유), allowlist 준수율 40% (E13 부적합)
- **CONCURRENT_WORKERS**: 10 → 3 (Groq RPM 30 기준)
- **User env 삭제**: `[Environment]::SetEnvironmentVariable('GROQ_API_KEY', null, 'User')`
- **config.py 수정**: `load_dotenv(override=True)`, `API_TIMEOUT=30`, bulk 8b 임시 전환
- **수정 파일**: config.py, scripts/enrich/{node_enricher,relation_extractor,graph_analyzer}.py

### E17 3-Layer + Groq Bulk 전환 (2026-04-13)
- **E17 3-layer 분류**: auto_merge (동일 relation+빈 desc→규칙 병합) / llm_same_rel / llm_diff_rel
- **find_duplicate_edges**: `WHERE status='active'` 필터 추가
- **_classify_group**: description='[]' 빈 값 처리, strength=None 안전 처리 (Codex 지적)
- **Groq 연동**: bulk tier → llama-3.3-70b-versatile (Groq API, OpenAI 호환)
- **실측**: E13 JSON 100%, allowlist 100%, 0.7-1.5초/건. E14 정상
- **효과**: 1,344 duplicate groups → 547 (active 필터) → 106 auto + 441 LLM. OpenAI 예산 소모 0
- **token_counter**: groq pool 추가 (10M limit)
- **daily_enrich**: groq_limit 인자 전달
- **.env**: GROQ_API_KEY 추가

### Phase 0 사후 정비 (2026-04-13)
- **Edge pruning 버그 수정**: status 필터 누락 + 공식 결함 (freq 기반→stored strength 기반)
- **Edge 복구**: 5,311건 (양쪽 active) deleted→active. edges/node: 1.49→3.08, orphan: 262→32
- **0-claim 마커**: claim_extractor 무한 재시도 해소 (unprocessed 104→0)
- **Traits 분류**: 67 unclassified→2 (archived 필터 버그 수정)
- **Scheduler bat 보강**: PATH/인자전달/exit code

### Build R1 (Phase 0 인프라) + R2 (Codex Finding 수정)
- **v8 7 테이블 + 4 trigger**: D20 evidence bridge 물리 강제 (INSERT+UPDATE)
- **Self-Model 53 active**: 52 verified, 8차원 ≥ 3, avg evidence 2.34
- **D20 backfill 완료**: legacy placeholder 135건 → real claims 변환
- **D18 slot precedence**: reject + temporal + conflict escalation + open_questions
- **init_db fail-close**: 테이블/트리거 누락 시 RuntimeError

### Exit 5/5 PASS
- ✅ **Exit 1**: context_pack v5 (결정 56줄 + 15 traits + policy)
- ✅ **Exit 2**: orphan 0, append-only trigger, 추출률 55%
- ✅ **Exit 3**: 53 active / 8차원 8/8 / 52 verified / avg_ev 2.34
- ✅ **Exit 4**: response_no_trailing_summary rule 체인 작동
- ✅ **Exit 5**: inject→reject→verify 자동 폐회로

<!-- CURRENT:BEGIN -->
- **Branch**: main
- **Active Nodes / Edges**: ~3,400+ / ~10,900+ (04/16 E13 +63, E14 refined 476, E17 merged 1)
- **Traits**: 152+
- **Bulk API**: gpt-4.1 (OpenAI free tier 250K/일)
- **Fallback chain**: gpt-4.1 → Groq 70b → Gemini 3 Flash
- **OpenAI**: 크레딧 충전 후 free tier 복구 완료 (04/16)
- **Build R1**: Phase 1 완료 (workflow.md wiki-first), Phase 2~6 대기
<!-- CURRENT:END -->

## Performance Optimization (2026-04-10)
- **P0 Warmup**: 서버 시작 시 SentenceTransformer + CrossEncoder + 벡터 캐시 사전 로드 (콜드스타트 153초 제거)
- **P1 N+1 제거**: hybrid_search 모순 체크 get_edges 50회→get_contradicted_node_ids 1회 (350ms→10ms)
- **P2 커넥션 캐싱**: thread-local SQLite 연결 재사용 + PRAGMA cache_size 2MB→20MB
- **P3 임베딩 캐싱**: embed_text dict 캐시 (동일 쿼리 반복 호출 108ms→18ms)
- **Tests**: 96 passed (기존 실패 2건: bcm→hebbian 리네임 미갱신, sessions 테이블 미생성 — 별도)

## Architecture
- 18 MCP tools, 4 layers (L0-L3), 15+1 node types, 49 relation types
- Hybrid search: Vector (SQLite BLOB + numpy) + FTS5 (SQLite) + Graph (UCB/Hebbian)
- 1-Store: SQLite 단일 저장소 (ChromaDB 제거, 벡터 BLOB 13MB, brute-force cosine)
- Embedding: intfloat/multilingual-e5-large (1024d, local, EMBEDDING_PROVIDER=local)
- RRF_K=18, GRAPH_BONUS=0.005, reranker=ON, maturity gating
- Learning: frequency-based Hebbian (co-recall → strength +0.015, 재공고화 유지)
- Source tracking: recall_log.sources JSON (vector/fts5/graph/typed_vector)
- Growth cycle: growth_score batch (Phase 0a) → auto_promote (Phase 0) → Hebbian + obs_count (recall) → enrichment

## v3.1.0-dev Changes (2026-03-16, 온톨로지 강화)
- **Gate 2 재캘리브**: Bayesian Beta(1,10) → visit_count ≥ 10 직접 threshold
- **Gate 1 완화**: SWR threshold 0.55→0.25 (cross_ratio만으로 통과 가능)
- **Source 인프라**: hybrid_search source 태깅 → recall_log.sources JSON 기록
- **RELATION_RULES 확장**: 17→49개 (7.6%→37.3% type pair 커버리지)
- **Cross-project 관계**: mirrors/influenced_by/transfers_to (기존: parallel_with/connects_with)
- **Deprecated 정리**: TYPE_CHANNEL_WEIGHTS/TYPE_KEYWORDS v3 15타입 기준, LAYER_IMPORTANCE L4/L5 제거
- **swr_readiness 수정**: recall_log.sources JSON 파싱으로 vec_ratio 계산
- Tests: 169/169 PASS (테스트도 v3 기준으로 갱신)

## v3.0.0-rc Changes (2026-03-11, Phase 5 진행 중)
- **Ontology v3**: 타입 51→15 축소 (Tier1:7핵심 + Tier2:5맥락 + Tier3:3전환)
- **DB 마이그레이션**: merge=506, edge=46, Workflow LLM재분류=532 (61 archived), leaked=0
- **classifier.py**: 15개 active 타입 프롬프트 전면 교체
- **retrieval_hints**: gpt-5-mini 배치(20/호출) 2927/2947 완료 (99.3%)
- **type_filter canonicalization**: deprecated→replaced_by 자동 변환 (H1)
- **recall_id**: uuid.hex[:8] 세션 식별 (H2)
- **hints plumbing**: server→remember→store→insert_node 체인 (H4)
- **PROMOTE_LAYER v3**: L0(3), L1(7), L2(3), L3(2) + Unclassified
- **RELATION_RULES**: 25→17개 (deprecated 타입 제거)
- Tests: 163→169 (+6)
- **잔여**: ~~re-embed(2.5)~~ ~~co-retrieval(3)~~ dispatch(4), NDCG 0.9 목표(6)

## v2.2.1 Changes (2026-03-08)
- **Layer A 리팩터**: TYPE_BOOST additive → Type-Aware Vector Channel (4번째 RRF 채널)
  - TYPE_CHANNEL_WEIGHT=0.5, MAX_TYPE_HINTS=2, 타입별 독립 벡터 검색
  - 기존 additive boost는 enrichment 격차 대비 무효 → RRF 채널 기반으로 교체
- **Goldset v2.2**: q026-q075 Paul 수동 검증 완료 (50개 쿼리)
  - also_relevant 정리 (5개→1~3개), 잘못된 gold ID 교체
  - q026-q050 NDCG@5: 0.123→0.519 (+0.396)
  - 발견: q047 Identity 중복 노드 5개 (cleanup 필요), q049 쿼리 범위 확장 필요
- Tests: 161→163 (+2: max_type_hints_cap, returns_list)

## v2.2.0 Changes (2026-03-08)
- **Layer C**: 타입 태그 재임베딩 — [Type] prefix로 벡터 공간 분리
- **Layer A (legacy)**: 키워드 기반 타입 부스트 — TYPE_KEYWORDS 15타입 (v2.2.1에서 RRF 채널로 교체)
- **Layer D**: 타입 다양성 보장 — max_same_type_ratio=0.6, monopoly 방지
- **Goldset v2.1**: L1 relevant_ids 교정 (순환 참조 제거, type-filtered 벡터 검색 기반)

## v2.1.3 Changes (2026-03-08)
- LIKE boost cap 2개 (q004/q008 회귀 수정)
- post_search_learn() background thread 전환
- focus 모드: NetworkX → SQL CTE
- RRF cutoff top_k×4 → top_k×10
- verification_log 테이블 + checks/ 8모듈 (41 체크)
- goldset 25→75 확장 (Codex CLI 생성 + Opus 매핑)
- 449 중복 soft-delete, content_hash 100%
- 벡터 재임베딩 (summary+kc+content[:200])
- scripts/pipeline/ 5개: inject_synonyms, cleanup_duplicates, enrich_batch, reembed, run_pipeline

## R2 Metadata Saturation (2026-04-07)
- **node_role**: 22.3% → **100%** (4082건 backfill)
- **generation_method**: 23.1% → **100%** (4801건 backfill)
- distribution: knowledge_candidate 4522, session_anchor 340, work_item 345, external_noise 37, knowledge_core 8
- edge gen: enrichment 2785, session_anchor 1687, legacy_unknown 1397, co_retrieval 168, rule 131, semantic_auto 72
- Tests: 186 → **193** (+7 saturation tests)
- Gate: G2 통과 (node_role ≥80%, generation_method ≥85%)

## v3.3.1-dev Changes (2026-04-07, Signal 성장 엔진)
- **Signal 클러스터 합성**: Observation 417개 → cosine distance 0.35 agglomerative clustering → 51개 clusters → gpt-4.1-mini 합성 → 51 Signal 생성
- **realizes edge 128개**: Signal→Observation evidence 연결
- **Signal spine**: 19→70 (목표 50+ 달성)
- **promote_node 흐름 검증**: Signal→Pattern 승격 + 복구 정상 작동
- **Tests**: 186/186 PASS (변경 없음)
- **NDCG**: 0.214 (변동 없음 — Signal은 goldset 미포함)

## Tech Debt
- NetworkX full rebuild: auto/dmn 모드에서 여전히 사용
- enrichment LLM key allowlist 미구현
- q047 Identity 중복 노드 cleanup 필요 (#3773/3575/2712/3641/3707)
- q049 쿼리 범위 확장: "GPT 지침" → "멀티AI 맞춤 지침 (CLI+구독형 분기)"
- q051-q075 NDCG@5=0.244 — gold ID 1개로 축소 후 검색 상위 매칭 어려움

## v8 Loop 자동화 배선 (2026-04-12)
- **claim extraction 자동화**: daily_enrich Phase 0c — 미처리 captures 자동 claims 추출 (Ollama 로컬)
- **retrieval_logs 실시간 기록**: recall() 매 호출 시 Governance Plane에 검색 이벤트 기록
- **feedback_events 자동 기록**: flag_node() 시 feedback_events 테이블에 자동 기록
- **policy compiler**: 52 verified traits → 52 policy rules JSON 자동 컴파일 (daily_enrich Phase 0b)
- **context_pack 세션 자동 주입**: session-start.sh hook에서 Paul 선호 + dont/avoid 규칙 자동 출력
- **self-model 자동 갱신**: daily_enrich Phase 0b — concepts→trait extract + unclassified→classify (Ollama)

## Growth Semantics Audit (2026-04-12)
- **compute_growth_score()**: canonical 공식 추출 → `utils/growth.py` (quality 30% + edges 20% + visits 20% + diversity 20% + recency 10%)
- **observation_count 활성화**: recall 시 `post_search_learn`에서 +1 (dead field → live)
- **Naming canonicalization**: maturity→growth_score, _compute_maturity→_compute_cluster_readiness
- **daily_enrich Phase 0a**: 전체 active 노드 DB maturity 배치 갱신
- **auto_promote**: quality floor → growth_score ≥ 0.5 통합 기준
- **보고서**: `scripts/growth_audit_report.py` (type별 분포)
- **Tests**: 11 new (compute_growth_score 8 + observation_count 2 + batch update 1)

## Next — v8 Phase 1+ (Phase 0 Exit 달성 후)

### 즉시 검증 (Phase 0 사후)
- [x] context_pack 자동 주입 확인 — 52 rules 정상 주입 (2026-04-13)
- [x] 미처리 captures 처리 완료 — 113 claims 추출 + 55건 마커 backfill, unprocessed=0 (2026-04-13)
- [x] Phase 6 pruning 버그 발견·수정·복구 (2026-04-13)
- [x] 2026-04-13 06:00 daily_enrich 자동 실행 확인 — Phase 0 정상, E17 무한실행 사고 → kill + budget cap 수정 (2026-04-13)
- [x] E17 3-layer 리팩토링 — auto_merge/llm_same_rel/llm_diff_rel + Codex 검증 (2026-04-13)
- [x] Groq bulk 전환 — llama-3.3-70b-versatile, 실측 JSON 100% + allowlist 100% (2026-04-13)
- [x] 04/14 06:00 daily_enrich 자동 실행 — Phase 0 성공, Phase 1 전량 실패 (.env override 버그)
- [x] Node/Graph Groq 라우팅 누락 발견·수정 (2026-04-14)
- [x] openai SDK max_retries=0 + timeout=30s 추가 — hang 방지 (2026-04-14)
- [x] User env GROQ_API_KEY 이중 프리픽스 오염 제거 (2026-04-14)

### 즉시 (2026-04-16)
- [x] Groq 70b TPD 리셋 확인 → OK (04/16 11:00)
- [x] OpenAI 429 해결 — 원인: $0 잔액 차단. 크레딧 충전으로 free tier 복구
- [x] E13/E14/E16/E17 완료 — gpt-4.1로 전량 처리 (E13 +63, E14 476 refined, E17 1 merged)
- [x] Gemini fallback 코드 추가 — 5파일 수정, 3회 재시도 후 fallback
- [x] config.py bulk → gpt-4.1 (OpenAI free tier 대형풀 250K/일)
- [x] Task Scheduler daily-enrich Disabled (수동 전환)
- [x] Build R1 Phase 1: workflow.md wiki-first 체크리스트 추가
- [ ] Build R1 Phase 2~6 (post_user_prompt_capture.py, session-start.sh, E2E 검증)

### 중기
- [ ] Phase 1 PostgreSQL 이주 (Trigger: Phase 0 Exit 충족, 아직 미착수)

### Phase 1: PostgreSQL 이주 (Trigger: Phase 0 Exit ✅)
- [ ] PostgreSQL 17 + pgvector 설치
- [ ] SQLite → PostgreSQL 데이터 마이그레이션 (Migration Contract 준수: UUID v7, status enum, approval state)
- [ ] MCP 도구 리와이어 (remember → capture+claim+concept 파이프라인)
- [ ] Exit: capture→claim→concept 흐름이 PostgreSQL에서 라이브 작동

### Phase 2: Paul Model 본격 확장
- [ ] self_model_traits 52 → 100+ 목표
- [ ] approval 워크플로 고도화 (자동 제안 → Paul 승인 UI)
- [ ] self_trait_conflicts 자동 탐지 강화
- [ ] Exit: 30+ traits 이상 (달성), 8차원 균형 검증

### Phase 3: Policy Compiler 본격화
- [ ] slot precedence 정밀화 (현재 기본형 → 충돌 해소 테스트)
- [ ] Redis 도입 (trigger: context compile latency > 500ms)
- [ ] 타입 canonical core 10개 확정 (Phase 0 데이터 기반, D19)
- [ ] Exit: 검증된 Principle이 policy_rule로 컴파일되고 Claude 세션에 주입됨

### Phase 4: Promotion + Governance
- [ ] promotion_engine 4-Gate 본격 구현
- [ ] drift_incidents, eval_runs 테이블 활성화
- [ ] runtime 반영 규칙 본격 구현 (reject 감점, contradiction 제외)
- [ ] Exit: Obs→Signal→Pattern→Principle→Policy 자동 승격 라이브 작동

### Phase 5: Graph + Visibility
- [ ] Neo4j 도입 (trigger: SQL CTE 5s+ 또는 3-hop+)
- [ ] Obsidian export/import 양방향
- [ ] Exit: Paul이 Obsidian에서 자기 Principle/Pattern을 읽고 확인 가능

### Legacy 잔여 (v7 시절)
- [ ] hints 295건 재생성
- [ ] co-retrieval 실행
- [ ] ingest cleanup 56노드
- [ ] Identity dedup 5노드 (#3773/3575/2712/3641/3707)
- [ ] schema.yaml v3 업데이트


