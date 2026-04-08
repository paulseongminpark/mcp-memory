# mcp-memory Session Summary

## 15:23 [mcp-memory] NDCG 진단 + 인과 연결 스크립트

### 작업 내용
- NDCG 진단 프롬프트 작성 (Codex/Gemini 위임용)
- `scripts/connect_causal.py` — 인과 관계 edge 연결 스크립트
- `scripts/connect_islands.py` — 고립 노드 연결 스크립트
- `NEXT-SESSION.md` — 다음 세션 작업 가이드

### 결정
- NDCG@5 0.232 → 원인 분석 우선 (goldset 품질 vs 검색 품질 분리 진단)
- Codex/Gemini 병렬 진단 위임 전략

### 미결
- [ ] NDCG 진단 결과 반영 (Codex/Gemini 실행 대기)
- [ ] re-embed 실행 (reembed.py ready)
- [ ] co-retrieval 실행 (co_retrieval.py ready)

### 세션 목표 + 남은 할 일
- **목표**: NDCG@5 0.232 원인 진단 및 개선 경로 수립
- **남은 할 일**: Codex/Gemini 진단 결과 수신 → 원인 확정 → 개선 구현
