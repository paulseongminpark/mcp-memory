# mcp-memory CHANGELOG

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

