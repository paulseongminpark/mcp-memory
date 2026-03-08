# mcp-memory — STATE
_Updated: 2026-03-08_

## Current
- **Version**: v2.1.3
- **Branch**: main
- **NDCG@5**: 0.568 (75 queries) / 0.624 (50 queries)
- **NDCG@10**: 0.603 (75 queries) / 0.659 (50 queries)
- **hit_rate**: 0.743 (75 queries)
- **Tests**: 153/153 PASS
- **Verification**: 41 PASS / 0 WARN / 0 FAIL
- **Active Nodes**: 2,859 (449 duplicates soft-deleted)
- **Enrichment**: 100% (0 pending)
- **Content Hash**: 100%

## Architecture
- 13 MCP tools, 6 layers (L0-L5+Unclassified), 50 node types, 48 relation types
- Hybrid search: Vector (ChromaDB) + FTS5 (SQLite) + Graph (UCB/BCM)
- Embedding: text-embedding-3-large, summary+key_concepts+content[:200]
- RRF_K=18, GRAPH_BONUS=0.005, candidate cutoff=top_k×10

## v2.1.3 Changes (2026-03-08)
- LIKE boost cap 2개 (q004/q008 회귀 수정)
- post_search_learn() background thread 전환
- focus 모드: NetworkX → SQL CTE
- RRF cutoff top_k×4 → top_k×10
- verification_log 테이블 + checks/ 8모듈 (41 체크)
- goldset 25→75 확장 (Codex CLI 생성 + Opus 매핑)
- 449 중복 soft-delete, content_hash 100%
- 벡터 재임베딩 (summary+kc+content[:200])
- scripts/pipeline/ 4개: inject_synonyms, cleanup_duplicates, enrich_batch, reembed, run_pipeline

## Tech Debt
- NetworkX full rebuild: auto/dmn 모드에서 여전히 사용
- enrichment LLM key allowlist 미구현
- L1 노드(Workflow/Tool/Agent) 검색 정확도 낮음 (Principle 편향)

## Next
- NDCG 0.7 달성: L1 노드 검색 개선 (type-aware boost 또는 쿼리 분류)
- goldset relevant_ids 수동 검증 (Paul 확인 필요)
- 온톨로지 축소 실험 (50→15 코어 타입)
