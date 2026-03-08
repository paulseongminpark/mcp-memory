# mcp-memory — STATE
_Updated: 2026-03-08_

## Current
- **Version**: v2.2.1
- **Branch**: main
- **NDCG@5**: 0.460 (Paul 검증 goldset v2.2) — q026-q075 수동 검증 완료
- **NDCG@10**: 0.488 (Paul 검증 goldset v2.2)
- **hit_rate**: 0.627 (Paul 검증 goldset v2.2)
- **Tests**: 163/163 PASS
- **Verification**: 41 PASS / 0 WARN / 0 FAIL
- **Active Nodes**: 2,869 (449 duplicates soft-deleted)
- **Enrichment**: 100% (0 pending)
- **Content Hash**: 100%

## Architecture
- 13 MCP tools, 6 layers (L0-L5+Unclassified), 50 node types, 48 relation types
- Hybrid search: Vector (ChromaDB) + FTS5 (SQLite) + Graph (UCB/BCM)
- Embedding: text-embedding-3-large, [Type]+summary+key_concepts+content[:200]
- RRF_K=18, GRAPH_BONUS=0.005, candidate cutoff=top_k×10
- 3-Layer type-aware search: C(타입 태그 임베딩) + A(typed vector RRF 채널) + D(다양성 보장)

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

## Tech Debt
- NetworkX full rebuild: auto/dmn 모드에서 여전히 사용
- enrichment LLM key allowlist 미구현
- q047 Identity 중복 노드 cleanup 필요 (#3773/3575/2712/3641/3707)
- q049 쿼리 범위 확장: "GPT 지침" → "멀티AI 맞춤 지침 (CLI+구독형 분기)"
- q051-q075 NDCG@5=0.244 — gold ID 1개로 축소 후 검색 상위 매칭 어려움

## Next
- q051-q075 검색 정밀도 개선 (NDCG@5=0.244 → 0.4+)
- TYPE_CHANNEL_WEIGHT 튜닝 (0.5 → 실험)
- 온톨로지 축소 실험 (50→15 코어 타입)
