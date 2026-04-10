# mcp-memory — STATE
_Updated: 2026-04-10_

## Current
- **Version**: v7.4 (Ontology Full Activation)
- **Branch**: main
- **Active Nodes**: 3,226
- **Active Edges**: 7,439 (cross-domain 32.1%, direction 96.2%)
- **Ontology**: 15 active types + Correction(system), 49 relation types
- **knowledge_core**: 205
- **validated**: 1,107 (34.3%)
- **Embedding**: LOCAL (multilingual-e5-large 1024d) — missing 0
- **Learning**: Hebbian frequency-based, co-retrieval 145 edges (strength avg 0.908)
- **Quality**: NDCG@5 0.425, NDCG@10 0.432, hit_rate 87.8% (goldset v4, 82 queries)
- **Maturity**: avg 0.498, min 0.105, max 0.985 (v7.4 활성화)
- **Growth**: observation_count nonzero 653, direction 96.2% assigned
- **Reranker**: ms-marco-MiniLM-L-6-v2 (cross-encoder, local), weight=0.35
- **Source tiers**: user(+0.12) > claude(+0.08) > checkpoint(+0.04) > neutral > save_session(-0.02) > obsidian(-0.05)
- **Auto-promote**: daily_enrich Phase 0에 통합, 세션 종료 시 자동 실행
- **Scripts**: 44개 운영 (71→44, 27개 archived)
- **Beads**: tasks.db 4도구
- **API**: enrichment 배치만 OpenAI (실시간 경로 = 0 API)

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
- Growth cycle: auto_promote (daily_enrich Phase 0) → Hebbian learning (recall) → enrichment

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

## Next (Phase 5 잔여 → Phase 6)
- [ ] hints 295건 재생성 (retrieval_hints IS NULL — 스크립트 ready: hints_generator.py)
- [ ] Step 2.5: ChromaDB re-embed (스크립트 ready: reembed.py)
- [ ] Step 3: co-retrieval 실행 (스크립트 ready: co_retrieval.py)
- [ ] Step 4: L3 자율성 규칙 구현 (dispatch routing만 존재, 규칙 엔진 미구현)
- [ ] Phase 6: NDCG 측정 스크립트 작성 + goldset 75개 완성 + 0.9 검증
- [ ] ingest cleanup: 56노드 정리 (계획: 00_pending/ingest-cleanup-0311.md)
- [ ] Identity dedup: 5노드 (#3773/3575/2712/3641/3707)
- [ ] schema.yaml v3 업데이트 (deprecated 타입 제거)


