# Cross-Validation Synthesis — 3 CLI × 3 Rounds

> Reviewer: Codex (Phase 0 자동 교차검증)
> Date: 2026-03-08
> Input: 57 review reports (Claude/Codex/Gemini × R1/R2/R3)
> Final edit: Claude Opus (정렬/판정 추가)

---

## 1. 3자 합의 (Claude + Codex + Gemini 모두 지적)

| Sev | Finding | Files | Fix |
|-----|---------|-------|-----|
| CRITICAL | 인증/인가 경계 부재 — `skip_gates` 무인가 우회, MCP entrypoint에 `check_access()` 미적용, actor 스푸핑 가능 | promote_node.py:167, server.py:231, access_control.py:146 | MCP surface에서 `skip_gates` 제거, authenticated actor 강제, mutation tool에 `require_access()` 적용 |
| HIGH | 타임아웃/기한 제어 부재 — 임베딩/LLM 호출이 SDK 기본값에 의존, hung call 위험 | openai_embed.py:10, node_enricher.py:94 | server.py에 `asyncio.wait_for()`, SDK에 명시적 `timeout`+`max_retries` |
| HIGH | recall()이 query+write 혼합 — BCM/SPRT/logging writes가 조회 경로에서 실행, 지연+락 경합 | hybrid.py:165, hybrid.py:385, recall.py:11 | query/learning path 분리, 후처리는 background job |
| HIGH | 전체 edge 적재 + NetworkX graph build — cold cache/burst traffic에서 latency spike | hybrid.py:31, sqlite_store.py:347, graph/traversal.py:11 | SQL traversal 또는 cache lock/invalidation, full rebuild 빈도 감소 |
| HIGH | 운영 관점 테스트 부족 — concurrency, timeout, retry, real-schema integration 미검증 | test_hybrid.py:21, test_validators_integration.py:27 | real bootstrap schema integration test + concurrent stress test 추가 |

## 2. 2자 합의 (Claude + Codex 합의, Gemini 미지적)

| Sev | Finding | Files | Fix |
|-----|---------|-------|-----|
| CRITICAL | `nodes.last_activated` 누락 → `_bcm_update()` 조용히 롤백 | hybrid.py:263, sqlite_store.py:24 | bootstrap/live schema에 컬럼 추가 |
| CRITICAL | `meta`, `recall_log`, `nodes.frequency` 부재 → promotion pipeline + recall counter 비동작 | promote_node.py:41, promote_node.py:87, recall.py:104 | 테이블/컬럼 생성 + 수집 경로 연결 |
| CRITICAL | `remember()` retry-safe 아님 → duplicate node 생성 | remember.py:96, remember.py:149 | content-hash dedup 또는 idempotency key |
| HIGH | `PROMOTE_LAYER` 12/50 타입만 매핑 → `layer=NULL` + firewall/ACL 구멍 | remember.py:62, config.py:243, schema.yaml:52 | classify 시 DB type_defs.layer 또는 schema를 authoritative source로 |
| HIGH | pruning/archive 스펙 불일치 — `updated_at`를 활동성으로 사용, edge archive 카운트만 증가 | daily_enrich.py:384, daily_enrich.py:409, pruning.py:36 | `last_activated` 기반 + 실제 archive column update |
| HIGH | recall `mode` 파라미터가 MCP wrapper에서 숨겨짐 | recall.py:11, server.py:115 | server.py signature에 `mode` 노출 + contract test |

## 3. 1자만 지적 (HIGH+ only)

| Sev | Reviewer | Finding | Files | Fix |
|-----|----------|---------|-------|-----|
| CRITICAL | Claude | connection leak — write 함수에 try/finally 부재 | sqlite_store.py:242, sqlite_store.py:265 | context manager로 conn.close() 보장 |
| CRITICAL | Claude | enrichment LLM output key가 SQL column name으로 직접 투입 | node_enricher.py:768, relation_extractor.py:170 | update key allowlist 강제 |
| CRITICAL | Codex | hub_monitor.take_snapshot() schema가 live hub_snapshots와 불일치 → hub protection 무력화 | hub_monitor.py:61, access_control.py:95 | init_db()와 snapshot writer schema 일치 + startup check |

## 4. 점수 불일치 분석

### Gemini R1 9.5/10 vs Codex R1 3 CRITICAL

핵심 차이: **검토 단위**. Gemini는 파일별 구현 완성도(수식, 시그니처, 내부 구조)를 봤고 populated/migrated 상태를 전제. Codex/Claude는 `server.py → init_db()` bootstrap, live schema, cross-file dependency를 따라가며 통합 런타임 성립 여부를 검증. Gemini는 "코드가 잘 짜여있는가", Codex/Claude는 "실제로 돌아가는가"를 본 차이.

### Gemini R3 7/10 vs Codex R3 4/10 vs Claude R3 42.5%

차이: **scoring rubric**. Gemini는 single-user/manual 운영 기준 survivability. Codex는 이미 존재하는 production blockers + schema drift. Claude는 recoverability/observability/concurrency/rate limiting/retries/test gaps 포함 full production-readiness rubric. 같은 시스템, 다른 렌즈.

## 5. 통합 우선순위 (CRITICAL → HIGH)

### Infrastructure (P0)
1. bootstrap/live schema 코드 일치: `nodes.last_activated`, `meta`, `recall_log`, `hub_snapshots`
2. timeout/retry/lock 정책 통일: OpenAI calls, SQLite write retry, graph-cache lock

### Promotion Pipeline (P0)
3. SWR/Bayesian 입력을 실제 데이터로 연결 또는 gate 수식을 현존 telemetry에 맞게 재설계
4. layer 산출을 PROMOTE_LAYER에서 분리, ontology SoT로 일원화

### Security (P1)
5. `skip_gates` 제거, authenticated actor 강제, MCP entrypoint ACL 적용
6. `top_k`/content size/rate limit/FTS escaping/enrichment key allowlist 추가

### Architecture (P1)
7. recall()에서 query와 learning/logging 분리, full-graph rebuild 의존 축소
8. tools/scripts의 private `_connect()` 사용 차단, storage/service API 구축

### Tests (P2)
9. real bootstrap schema 기준 integration test
10. concurrent recall/remember, timeout, retry, pruning/hub-monitor regression test

## 6. Quick Wins (10줄 이내)

| # | Fix | Impact |
|---|-----|--------|
| Q1 | `COALESCE(last_activated, created_at)` — pruning edge age 보정 | NULL last_activated 엣지 mass deletion 방지 |
| Q2 | `_escape_fts_query()`에서 `"` → `""` 이스케이프 | FTS5 injection 방지 |
| Q3 | server.py에 `top_k` upper bound + content length 제한 | DoS 방지 |
| Q4 | MCP surface에서 `skip_gates` 차단 또는 hard-fail | 무인가 L0→L5 승격 방지 |
| Q5 | OpenAI client에 `timeout` + `max_retries` | hung call 방지 |
| Q6 | broad `except Exception: pass` → `logging.warning(...)` | silent failure 가시화 |
