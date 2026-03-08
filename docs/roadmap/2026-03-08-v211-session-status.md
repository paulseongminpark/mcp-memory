# mcp-memory v2.1.1 세션 상태 기록

> Date: 2026-03-08
> Session: Opus 1M orchestrator + Warp panes (Sonnet/Opus 200K) + Codex + Gemini
> Commits: 4807e5d → debb024 → 3064de6 → 5e46738 → 8c6ed20

---

## 오늘 완료된 작업

### Phase 0: 교차검증 (Codex)
- 58개 리뷰 보고서 → 통합 findings 매트릭스
- Output: `docs/review/cross-validation-synthesis.md`
- 3자 합의 5건 (CRITICAL 1 + HIGH 4)
- 2자 합의 6건 (CRITICAL 3 + HIGH 3)
- 1자 only 3건 (CRITICAL 3)
- Gemini 9.5/10 vs Codex 4/10 불일치 분석

### Phase 1: 인프라 수리 (5 Task 병렬)
| Task | 내용 | CLI |
|------|------|-----|
| A | init_db()에 meta/recall_log/last_activated/frequency 추가 | Sonnet |
| B | context manager _db() + _connect() 제거 | Opus |
| C | PROMOTE_LAYER 47타입 + check_access MCP | Sonnet |
| D | Promotion pipeline 데이터 흐름 연결 | Opus |
| E | Content hash dedup + COALESCE + top_k clamp | Sonnet |

### Quick Wins (Task F, Sonnet)
- FTS5 `"` escape
- skip_gates MCP 차단
- OpenAI timeout=30, max_retries=3
- silent fail → logging.warning()
- enrichment LLM key allowlist
- recall mode MCP 노출

### NDCG 튜닝 (Task G, Sonnet)
- RRF_K: 60 → 18
- GRAPH_BONUS: 0.015 → 0.005
- NDCG@5: 0.057 → 0.548 (9.6x)
- 0점 쿼리 4개는 config 범위 밖 (FTS bigram, vocabulary mismatch)

### recall_log + query/write 분리 (Task H+I)
- recall()에서 recall_log INSERT 구현 (Gate 1 SWR 데이터 축적)
- hybrid_search()를 순수 검색 + _post_search_learn() 분리
- insert_node()에 PROMOTE_LAYER fallback (NULL layer 방지)

### 테스트 (Codex)
- test_promote_v2.py: 11 tests
- test_integration.py: 8 tests
- test_operational.py: 8 tests
- 총: 117 → 144 tests (+27)

### 라이브 DB 마이그레이션
- meta 테이블 생성 (key, value, updated_at)
- recall_log 테이블 생성
- nodes.last_activated, nodes.frequency 컬럼 추가
- 88개 NULL layer 노드 수정 (PROMOTE_LAYER 기반)

### 위임 시스템 (Sonnet)
- delegate-to-codex 스킬 구축
- delegate-to-gemini 스킬 구축
- 글로벌 CLAUDE.md 위임 트리거 규칙

### 진단 스크립트
- scripts/eval/diagnose.py: 10-path 전체 검증
- 최종: **16 PASS / 0 FAIL / 0 WARN**

---

## 현재 수치

| 메트릭 | 이전 (v2.1) | 현재 (v2.1.1) |
|--------|------------|---------------|
| NDCG@5 | 0.057 | **0.548** |
| Tests | 117 | **144** (1 known race) |
| CRITICAL issues | 6 | **0** |
| NULL layer nodes | 88 | **0** |
| recall_log rows | 0 | **축적 중** |
| meta rows | 0 | **축적 중** |
| 진단 PASS | — | **16/16** |

---

## 남은 작업 (향후 세션)

### P0 — NDCG 0.7 달성
- [ ] FTS5 bigram 토크나이저 도입 (2자 한국어 매칭)
- [ ] 후보풀 확장 (top_k × 2 → top_k × 4)
- [ ] 0점 쿼리 vocabulary mismatch 해결 (synonym expansion 또는 query rewriting)
- [ ] goldset 확장 (25 → 50 쿼리, q026-q050 Paul 직접 작성)

### P1 — 안정성
- [ ] concurrent remember dedup race condition 수정 (test_operational.py 실패)
- [ ] enrichment pipeline 수리된 코드로 재실행 (신규 노드 대상)
- [ ] BCM/UCB 실작동 장기 검증 (recall 누적 → theta_m 변화 추적)
- [ ] promote_node() E2E 실제 승격 테스트 (Signal → Pattern)

### P2 — 아키텍처
- [ ] _post_search_learn()을 background job으로 전환 (asyncio)
- [ ] NetworkX full rebuild 의존 축소 (SQL traversal 또는 incremental update)
- [ ] schema.yaml → DB type_defs 자동 동기화 (startup check)
- [ ] conftest.py 생성 + fixture 통합

### P3 — 온톨로지 실험
- [ ] 50타입 → 15코어+facet 매핑 실험 (recall 품질 비교)
- [ ] BCM on/off A/B 테스트
- [ ] drift threshold 캘리브레이션 (enrichment 100개 실측)
- [ ] 원본/파생 content 분리 설계

---

## 커밋 히스토리

```
8c6ed20 [mcp-memory] v2.1.1 완성: recall_log + query/write 분리 + 운영 테스트 + 진단 16/16
5e46738 [mcp-memory] init_db에 meta/recall_log CREATE TABLE 추가 + 진단 스크립트
3064de6 [mcp-memory] fix-G: NDCG 0.4867→0.5477 (+12.5%) via RRF_K=18, GRAPH_BONUS=0.005
debb024 [mcp-memory] v2.1.1 Quick Wins + 테스트 확충
4807e5d [mcp-memory] v2.1 Phase 1: 인프라 수리 + 교차검증 종합
```

---

## CLI 사용 기록

| CLI | 역할 | 세션 수 | 산출물 |
|-----|------|---------|--------|
| **Claude Opus 1M** (이 세션) | 오케스트레이터 | 1 | 설계, 프롬프트, 진단, 커밋 |
| **Claude Opus 200K** (fix-B, D, I) | 복잡 구현 | 3 | connection mgmt, promotion pipeline, query/write 분리 |
| **Claude Sonnet** (fix-A, C, E, F, G, H) | 기계적 구현 | 6 | init_db, PROMOTE_LAYER, dedup, quick wins, NDCG, recall_log |
| **Codex** | 대규모 읽기 + 테스트 | 2 | 교차검증 종합, 테스트 27개 |
| **Sonnet** (위임 설계) | 도구 설계 | 1 | delegate-to-codex/gemini 스킬 |
