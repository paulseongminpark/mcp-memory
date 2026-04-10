# Codex 독립 리뷰 프롬프트

## 역할
너는 mcp-memory 온톨로지 시스템의 **코드 품질 + 데이터 정합성** 전문 리뷰어다.
ONTOLOGY-MASTER-REPORT.md를 먼저 읽고, 실제 코드와 DB를 대조해서 **보고서가 틀린 곳, 코드가 설계와 다른 곳, 숨겨진 버그**를 찾아라.

## 환경
- 프로젝트: `/c/dev/01_projects/06_mcp-memory/`
- DB: `data/memory.db` (SQLite)
- Python 3, sentence-transformers, numpy, google-genai
- git 사용 가능, 코드 수정 금지. 분석만.

## 필수 읽기 (순서대로)
1. `ONTOLOGY-MASTER-REPORT.md` — 종합 보고서 (524줄)
2. `STATE.md` — 현재 상태
3. `config_search.py` — 검색 파라미터 전체
4. `config_ontology.py` — 온톨로지 상수 전체
5. `storage/hybrid.py` — 핵심 검색 엔진 전체

## 검증 항목 (전부 실행)

### A. 보고서 vs 코드 정합성 (10건)
보고서에 적힌 상수값이 코드와 일치하는지 전부 확인:
- RRF_K, GRAPH_BONUS, SIMILARITY_THRESHOLD, RERANKER_WEIGHT 등 30+ 상수
- SOURCE_BONUS 7단계 값
- UCB 계수 (focus/auto/dmn)
- GRAPH_BONUS_BY_CLASS 값
- Maturity Gating 레벨별 threshold
- LAYER_ETA 값
- 불일치하면 코드의 실제 값 보고

### B. 코드 품질 (5건)
- `hybrid.py` _hebbian_update() — 실제로 edge strength가 증가하는지 로직 추적
- `hybrid.py` composite_scoring — N+1 쿼리가 정말 수정됐는지 확인
- `auto_promote.py` — 승격 기준이 코드에서 실제로 뭔지 (visit, edges, quality, SWR)
- `remember.py` — source_kind 자동 추론 로직 검증
- `daily_enrich.py` — Phase 0~7이 실제 코드에 모두 존재하는지

### C. DB 데이터 정합성 (10건, SQL 직접 실행)
```sql
-- 1. maturity 필드 상태
SELECT COUNT(*), AVG(maturity) FROM nodes WHERE status='active';

-- 2. observation_count 상태
SELECT COUNT(*), AVG(observation_count) FROM nodes WHERE status='active';

-- 3. embedding 차원 검증 (1024d = 4096 bytes)
SELECT LENGTH(embedding), COUNT(*) FROM nodes WHERE status='active' AND embedding IS NOT NULL GROUP BY LENGTH(embedding);

-- 4. 에지 무결성 (존재하지 않는 노드 참조)
SELECT COUNT(*) FROM edges e WHERE e.status='active' AND (
  e.source_id NOT IN (SELECT id FROM nodes) OR 
  e.target_id NOT IN (SELECT id FROM nodes)
);

-- 5. content_hash 중복 (active 내)
SELECT content_hash, COUNT(*) as cnt FROM nodes WHERE status='active' AND content_hash IS NOT NULL GROUP BY content_hash HAVING cnt > 1 LIMIT 10;

-- 6. epistemic_status에 없는 값
SELECT DISTINCT epistemic_status FROM nodes WHERE status='active';

-- 7. type에 없는 값 (15+2 이외)
SELECT DISTINCT type FROM nodes WHERE status='active';

-- 8. relation에 없는 값 (49개 이외)
SELECT DISTINCT relation FROM edges WHERE status='active' ORDER BY relation;

-- 9. strength 이상값 (0 미만 or 1.1 초과)
SELECT COUNT(*) FROM edges WHERE status='active' AND (strength < 0 OR strength > 1.1);

-- 10. self-loop 에지
SELECT COUNT(*) FROM edges WHERE status='active' AND source_id = target_id;
```

### D. 숨겨진 문제 탐색
- `storage/hybrid.py`에서 NetworkX 잔존 코드 위치와 범위
- `server.py` _init_worker()가 실제로 모델을 preload하는지
- `scripts/daily_enrich.py`에서 Gemini enrichment 호출 여부 (통합 안 됐을 수 있음)
- FTS5 테이블이 nodes 테이블과 동기화되는 트리거 존재 여부
- recall() 호출 시 Hebbian 학습이 실제로 발동되는 경로 추적

## 출력 형식
```markdown
# Codex 독립 리뷰 결과

## A. 보고서 vs 코드 불일치
| # | 보고서 값 | 코드 실제 값 | 파일:줄 |
|---|----------|------------|---------|

## B. 코드 품질 이슈
| # | 이슈 | 심각도 | 파일:줄 | 설명 |
|---|------|--------|---------|------|

## C. DB 데이터 이상
| # | 쿼리 | 결과 | 판단 |
|---|------|------|------|

## D. 숨겨진 문제
| # | 문제 | 위치 | 영향 |
|---|------|------|------|

## 종합 판단
- 전체 건강도: __/100
- 즉시 수정 필요: N건
- 주의 관찰: N건
```

**중요: 코드 수정하지 마라. git commit 하지 마라. 분석과 보고만.**
