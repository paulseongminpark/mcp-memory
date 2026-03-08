# mcp-memory — STATE
_Updated: 2026-03-08_

## Current
- **Version**: v2.2.0
- **Branch**: main
- **NDCG@5**: 0.441 (corrected 75q) — goldset v2.1 교정 후 기준
- **NDCG@10**: 0.467 (corrected 75q)
- **hit_rate**: 0.920 (corrected 75q)
- **Tests**: 161/161 PASS
- **Verification**: 41 PASS / 0 WARN / 0 FAIL
- **Active Nodes**: 2,869 (449 duplicates soft-deleted)
- **Enrichment**: 100% (0 pending)
- **Content Hash**: 100%

## Architecture
- 13 MCP tools, 6 layers (L0-L5+Unclassified), 50 node types, 48 relation types
- Hybrid search: Vector (ChromaDB) + FTS5 (SQLite) + Graph (UCB/BCM)
- Embedding: text-embedding-3-large, [Type]+summary+key_concepts+content[:200]
- RRF_K=18, GRAPH_BONUS=0.005, candidate cutoff=top_k×10
- 3-Layer type-aware search: C(타입 태그 임베딩) + A(키워드 부스트) + D(다양성 보장)

## v2.2.0 Changes (2026-03-08)
- **Layer C**: 타입 태그 재임베딩 — [Type] prefix로 벡터 공간 분리
- **Layer A**: 키워드 기반 타입 부스트 — TYPE_KEYWORDS 15타입, TYPE_BOOST=0.03
- **Layer D**: 타입 다양성 보장 — max_same_type_ratio=0.6, monopoly 방지
- **Goldset v2.1**: L1 relevant_ids 교정 (순환 참조 제거, type-filtered 벡터 검색 기반)
- hit_rate: 0.410→0.920 (+51pp)
- 8 신규 테스트 (test_type_boost 5 + test_type_diversity 3)

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
- goldset q026-q050 relevant_ids 수동 검증 필요 (NDCG@5=0 다수)
- goldset q051-q075 relevant_ids 정확도 향상 필요 (auto-correction 한계)

## Next
- goldset relevant_ids 수동 검증 (Paul 확인 필요) — NDCG 정확도의 병목
- TYPE_BOOST 파라미터 튜닝 (0.03 → 실험)
- 온톨로지 축소 실험 (50→15 코어 타입)
