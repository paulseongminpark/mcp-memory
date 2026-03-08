# mcp-memory CHANGELOG

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
