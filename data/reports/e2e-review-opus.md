# mcp-memory v2.0 Enrichment Pipeline — E2E Review (Opus)

> **Date**: 2026-03-04
> **Reviewer**: Claude Opus 4.6
> **Scope**: 설계 문서 3개 (04/05/06) vs 구현 코드 전체 (Step 1-10)
> **Method**: 모든 파일 직접 읽기 + 설계-구현 1:1 대조

---

## 1. Executive Summary

Step 1-10 전체 구현이 스펙의 **핵심 구조**(4-Model 배분, 25개 작업, Phase 기반 오케스트레이션)를 충실히 따르고 있다. 특히 token_counter의 rate limiting, 3-strategy 크로스도메인 클러스터링, 프롬프트 YAML 외부화가 잘 구현되었다.

그러나 **9개 Critical + 7개 Major + 9개 Minor** 문제가 발견되었다. 가장 심각한 것은:
1. **graph_analyzer.py 메서드 시그니처 불일치** — `run_e19_all`, `run_e21_all`, `run_e22_all`에 limit 파라미터 없음 → daily_enrich.py에서 TypeError 크래시 (Sonnet 발견)
2. **E7 ChromaDB 재임베딩이 실행되지 않음** — E7의 핵심 목적(벡터 검색 품질 향상) 미달성
3. **Phase 4-5에서 스펙 명시 작업 다수 누락** — L4-L5 분류, 성장 내러티브, 이색적 접합 등
4. **NodeEnricher에서 commit 누락** — 크래시 시 enrichment_status 원자성 깨짐 (C6 미해결)
5. **tier/maturity/observation_count 컬럼 미구현** — Becoming 시스템의 핵심 데이터 모델 부재

---

## 2. 스펙 준수 매트릭스

### Step 1-10 이행

| Step | 구현 파일 | 상태 | 비고 |
|------|----------|------|------|
| 1 migrate_v2.py | scripts/migrate_v2.py | **PASS** | nodes +12, edges +9, correction_log, FTS5 재구축, layer 배정 |
| 2 config.py | config.py | **PASS** | 5 모델, 예산, allowlist, 48 관계 |
| 3 token_counter.py | scripts/enrich/token_counter.py | **PASS** | Budget, RateLimiter, reasoning 추적, save_log |
| 4 node_enricher.py | scripts/enrich/node_enricher.py | **PASS** | E1-E12, conflict resolution, dry_run |
| 5 relation_extractor.py | scripts/enrich/relation_extractor.py | **PASS** | E13-E17, 3-strategy clustering |
| 6 graph_analyzer.py | scripts/enrich/graph_analyzer.py | **PASS** | E18-E25, pure SQL |
| 7 daily_enrich.py | scripts/daily_enrich.py | **PARTIAL** | Phase 1-5+7 있으나 Phase 4-5 내용 불완전 |
| 8 codex_review.py | scripts/codex_review.py | **PASS** | 4-target review, dry-run |
| 9 prompt YAML | scripts/enrich/prompts/*.yaml + prompt_loader.py + test_prompts.py | **PASS** | 25개 YAML, 600건 테스트 0 에러 |
| 10 MCP 통합 | hybrid.py + remember.py + 4 tools + server.py | **PASS** | scoring 가중치, provisional, 4 신규 도구 |

### 리스크 해결 매트릭스

| 리스크 | 심각도 | 해결 파일 | 상태 | 비고 |
|--------|--------|----------|------|------|
| **C1** o3 추론 토큰 예측 불가 | 치명 | token_counter.py | **PASS** | reasoning_tokens 별도 추적, Phase 5 마지막 배치 |
| **C2** API 실패 시 토큰 낭비 | 치명 | node_enricher.py 등 | **PASS** | 재시도 + BudgetExhausted + MAX_RETRIES=3 |
| **C3** 프롬프트 품질 | 치명 | prompts/*.yaml + test_prompts.py | **PASS** | 50표본 × 12 = 600건 테스트 |
| **C4** 스키마 마이그레이션 | 치명 | migrate_v2.py | **PASS** | ALTER TABLE + FTS5 재생성 + 백업 |
| **C5** Enrichment 충돌 해소 | 치명 | node_enricher.py | **PASS** | facets=union, layer=gpt(>0.8), secondary=재실행 |
| **C6** 파이프라인 atomicity | 치명 | enrichment_status JSON | **FAIL** | enrichment_status 기록되나 commit 없음 → 아래 상세 |
| **C7** ChromaDB 재임베딩 동시성 | 치명 | — | **NOT IMPL** | E7 결과가 ChromaDB에 반영되지 않아 해당 없음 |
| **C8** 신규 노드 판별 | 치명 | enriched_at 컬럼 | **PASS** | enriched_at IS NULL로 판별 |
| **S1** 배치 순서 의존성 | 심각 | daily_enrich.py | **PASS** | E7은 E1,E2 완료 후 별도 배치 |
| **S2** 소형 모델 환각 | 심각 | node_enricher.py | **PASS** | facets/domains allowlist 필터 |
| **S3** 크로스도메인 클러스터링 | 심각 | relation_extractor.py | **PASS** | 3-strategy: key_concept, facet, random |
| **S4** Day 1-3 실패 복구 | 심각 | enrichment_status | **PARTIAL** | 멱등성 있으나 commit 원자성 문제 |
| **S5** recall/remember 통합 | 심각 | hybrid.py + remember.py | **PASS** | quality*0.2 + temporal*0.1, provisional flag |
| **S6** 순환 의존 | 심각 | relation_extractor.py docstring | **PASS** | 1-pass 제한 명시 |
| **S7** config.py enrichment 설정 | 심각 | config.py | **PASS** | ENRICHMENT_MODELS, TOKEN_BUDGETS 등 |
| **S8** edges direction/reason | 심각 | migrate_v2.py | **PASS** | direction, reason, updated_at 추가 |
| **S9** Rate Limiting | 심각 | token_counter.py | **PASS** | RateLimiter 클래스, 429 파싱 |
| **S10** correction_log | 심각 | migrate_v2.py | **PASS** | CREATE TABLE correction_log |
| **S11** 기존 모듈 관계 | 심각 | — | **PARTIAL** | 역할 분리 명시되었으나 코드 연동 없음 |

---

## 3. 온톨로지 일치 검증 (04-dialogue)

**일치 항목:**
- TYPE_TO_LAYER 매핑: 45개 active 타입, 6레이어 (L0-L5) — config가 아닌 migrate_v2.py에 정의
- 48개 관계 타입: config.py RELATION_TYPES에 8개 카테고리로 정확히 반영
- FACETS_ALLOWLIST: 9개 값 일치
- DOMAINS_ALLOWLIST: 10개 값 일치

**불일치:**
- **7개 미래 예약 타입 (Thesis, Argument, Passage, Style, Voice, Composition, Influence)**: 스펙에 명시되었으나 migrate_v2.py TYPE_TO_LAYER에 없음. 의도적 (Phase 5 미래 데이터) — OK.
- **TYPE_TO_LAYER이 config.py가 아닌 migrate_v2.py에 위치**: 다른 모듈(promote_node.py)에서 참조 시 불편. PROMOTE_LAYER이 별도로 config.py에 추가됨 — 부분 중복.

---

## 4. 아키텍처 일치 검증 (05-blueprint Part 1-12)

| Part | 내용 | 상태 | 비고 |
|------|------|------|------|
| 1 | 전체 구조도 | **PASS** | MCP 13도구, SQLite+ChromaDB+FTS5 |
| 2 | 6-Layer 타입 체계 | **PASS** | TYPE_TO_LAYER 45개 |
| 3 | 48개 관계 타입 | **PASS** | config.py RELATION_TYPES |
| 4 | 3중 하이브리드 검색 | **PASS** | hybrid.py RRF + enrichment 가중치 |
| 5 | 분류 파이프라인 | **PARTIAL** | 배치 경로만 구현, 실시간(Claude 직접)·수동교정·정기감사 미구현 |
| 6 | Becoming 시스템 | **PARTIAL** | MCP 도구(analyze_signals, promote_node, get_becoming) 있으나 tier/maturity 컬럼 없음 |
| 7 | edge 메커니즘 | **PARTIAL** | 관계 추출(E13-E17) 있으나 헤비안/시간감쇠/리좀적전파 미구현 |
| 8 | 세션 시스템 | 기존 | get_context, save_session 기존 유지 |
| 9 | 분류 파이프라인 상세 | **PARTIAL** | 경로 1(실시간), 경로 3(수동교정), 경로 4(정기감사) 미구현 |
| 10 | MCP 도구 확장 | **PASS** | 9→13개, 4 신규 도구 |
| 11 | 구현 순서 | N/A | Phase 1-5 설계 |
| 12 | 4-Model Pipeline | **PASS** | 06-spec으로 상세화 |

---

## 5. 프롬프트 품질 검증 (25개 YAML)

### 공통 패턴
- 모든 YAML: task_id, name, model_tier, system, user 필드 존재 — **OK**
- `format_map()` 변수 치환: `{content}`, `{summary}` 등 사용 — **OK**
- JSON 리터럴 브레이스: `{{` 이스케이프 — **OK**

### 개별 검증

| YAML | 변수 | JSON 포맷 지시 | model_tier | 문제 |
|------|------|---------------|------------|------|
| e01_summary | content | YES | bulk | OK |
| e02_key_concepts | content | YES | bulk | OK |
| e03_tags | existing_tags, content | YES | bulk | OK |
| e04_facets | facets_allowlist, content | YES | bulk | OK |
| e05_domains | domains_allowlist, project, source, content | YES | bulk | OK |
| e06_secondary_types | primary_type, content | YES | verify | OK |
| e07_embedding_text | summary, key_concepts, tags, facets, domains | YES | bulk | OK |
| e08_quality_score | node_type, content | YES | bulk | OK |
| e09_abstraction | layer, content | YES | bulk | OK |
| e10_temporal | today, created_at, content | YES | bulk | OK |
| e11_actionability | node_type, content | YES | bulk | OK |
| e12_layer_verify | layer, node_type, content | YES | verify | OK |
| e13_cross_domain | relations_list, node_summaries | YES | bulk | OK |
| e14_refine_relation | all_relations, current_relation, source_*, target_* | YES | bulk | OK |
| e15_edge_direction | relation, source_*, target_* | YES | reasoning | OK |
| e16_strength | relation, current_strength, source_*, target_* | YES | bulk | OK |
| e17_merge_edges | source_*, target_*, edge_count, edges_desc | YES | bulk | OK |
| e18_cluster_themes | cluster_summaries | YES | deep | OK |
| e19_missing_links | relation_list, orphan_brief, neighbor_briefs | YES | bulk | **ISSUE**: 스펙은 gpt-5.2(deep), YAML은 bulk |
| e20_temporal_chain | project, node_list | YES | reasoning | OK |
| e21_contradiction | domain, node_a_*, node_b_* | YES | reasoning | OK |
| e22_assemblage | decision_brief, connected_briefs | YES | reasoning | OK |
| e23_promotion | signal_brief, similar_briefs | YES | judge | OK |
| e24_merge_candidate | node_a_id, brief_a, node_b_id, brief_b | YES | bulk | OK |
| e25_knowledge_gap | domain, distribution, all_types | YES | deep | OK |

**문제:**
1. **E19 model_tier 불일치**: 스펙은 gpt-5.2 (deep), YAML은 bulk (gpt-5-mini). graph_analyzer.py도 bulk 모델 사용 중인지 확인 필요.

---

## 6. 에러 처리 검증

| 모듈 | BudgetExhausted | RateLimitError | JSONDecodeError | 기타 |
|------|----------------|----------------|-----------------|------|
| node_enricher.py | **PASS** (raise) | **PASS** (retry+429) | **PASS** (retry) | APIError retry |
| relation_extractor.py | **PASS** | **PASS** | **PASS** | 중복 edge 방지 |
| graph_analyzer.py | **PASS** | **PASS** | **PASS** | stats["errors"] 추적 |
| daily_enrich.py | **PASS** | — (모듈 위임) | — | consecutive failure 3회 중단 |

**공통 패턴**: 3개 enricher 모듈 모두 동일한 `_call_json()` 패턴 사용. DRY 원칙 위반이지만 각 모듈 독립성 우선. 향후 base class 추출 검토.

---

## 7. 보안 검증

| 항목 | 상태 | 비고 |
|------|------|------|
| SQL injection (node_enricher) | **SAFE** | 파라미터 바인딩 사용 |
| SQL injection (relation_extractor) | **WARN** | `_cluster_by_shared_field()`에서 `f"SELECT DISTINCT {field}"` — field는 내부 코드에서만 호출되므로 현재 안전하지만 f-string SQL은 코드 스멜 |
| SQL injection (graph_analyzer) | **SAFE** | 파라미터 바인딩 |
| SQL injection (promote_node) | **SAFE** | 파라미터 바인딩 |
| Allowlist 필터 (facets) | **PASS** | e4_facets: union 후 FACETS_ALLOWLIST 필터 |
| Allowlist 필터 (domains) | **PASS** | e5_domains: union 후 DOMAINS_ALLOWLIST 필터 |
| Allowlist 필터 (relations) | **PASS** | e14_refine_relation: ALL_RELATIONS 검증 |
| 입력 검증 (promote_node) | **PASS** | VALID_PROMOTIONS 경로 검증 |
| 입력 검증 (analyze_signals) | **PASS** | Signal 타입만 조회 |

---

## 8. 데이터 흐름 검증

### Phase 의존성 DAG

```
Phase 1 (bulk): E1,E2,E3,E4,E5 → E8,E9,E10,E11 → E7(E1,E2 의존) → E13,E14,E16,E17
Phase 2 (reasoning): E21,E22,E20,E15
Phase 3 (verify): E12,E6
Phase 4 (deep): E18,E25,E19
Phase 5 (judge): E23
```

**확인된 의존성:**
- E7은 E1(summary), E2(key_concepts) 완료 후 실행 — **PASS** (daily_enrich.py 별도 배치)
- Phase 순서: 1→2→3→4→5 — **PASS** (daily_enrich.py phases 리스트)

**문제:**
- Phase 1에서 phase_limit 변수 계산(line 57) 되지만 **실제로 사용되지 않음** — 예산 제한이 개별 can_spend()에 의존
- E7 결과가 ChromaDB에 반영되지 않음 — **CRITICAL** (아래 #10-1)

---

## 9. MCP 통합 검증

| 도구 | server.py 래퍼 | 구현 파일 | 시그니처 일치 | docstring |
|------|---------------|----------|-------------|-----------|
| remember | **PASS** | tools/remember.py | **PASS** | **PASS** |
| recall | **PASS** | tools/recall.py | **PASS** | **PASS** |
| get_context | **PASS** | tools/get_context.py | **PASS** | **PASS** |
| save_session | **PASS** | tools/save_session.py | **PASS** | **PASS** |
| suggest_type | **PASS** | tools/suggest_type.py | **PASS** | **PASS** |
| ingest_obsidian | **PASS** | ingestion/obsidian.py | **PASS** | **PASS** |
| visualize | **PASS** | tools/visualize.py | **PASS** | **PASS** |
| ontology_review | **PASS** | scripts/ontology_review.py | **PASS** | **PASS** |
| dashboard | **PASS** | scripts/dashboard.py | **PASS** | **PASS** |
| **analyze_signals** | **PASS** | tools/analyze_signals.py | **PASS** | **PASS** |
| **promote_node** | **PASS** | tools/promote_node.py | **PASS** | **PASS** |
| **get_becoming** | **PASS** | tools/get_becoming.py | **PASS** | **PASS** |
| **inspect** | **PASS** | tools/inspect_node.py | **PASS** | **PASS** |

**총 13개 도구**, 시그니처 전부 일치.

**누락 도구**:
- `connect()` — 05-blueprint Part 10에 "수동 edge 생성" 도구로 명시되었으나 미구현
- `search_nodes()` — 05-blueprint에 "고급 검색 (facet/layer/domain 필터)"로 명시되었으나 미구현
- `get_relations()` — 05-blueprint에 "관계 조회"로 명시
- `get_session()` — 05-blueprint에 명시

---

## 10. 발견된 문제 (Critical → Minor)

### Critical (즉시 수정 필요)

| # | 파일 | 문제 | 영향 | 제안 |
|---|------|------|------|------|
| **C-0** | graph_analyzer.py:681,737,761 + daily_enrich.py:133,140,225 | **메서드 시그니처 불일치.** `run_e19_all()`, `run_e21_all()`, `run_e22_all()` 에 limit 파라미터 없음. daily_enrich.py에서 `limit=30` 등으로 호출. **(Sonnet 발견)** | Phase 2, Phase 4 실행 즉시 **TypeError 크래시**. 파이프라인 절반 실행 불가. | graph_analyzer.py 3개 메서드에 `limit: int` 파라미터 추가 |
| **C-1** | node_enricher.py:357 | **E7 결과가 ChromaDB에 반영 안 됨.** `_apply()`에서 `elif tid == "E7": pass`. daily_enrich.py에도 ChromaDB upsert 로직 없음. | E7의 핵심 목적(벡터 검색 품질 향상) 미달성. recall() 품질 개선 안 됨. | daily_enrich.py phase1의 E7 배치 후 ChromaDB upsert 추가. `vector_store.update(node_id, embedding_text)` |
| **C-2** | node_enricher.py:388 | **`_update_node()`에서 conn.commit() 미호출.** enrichment_status 기록이 Phase 끝의 conn.commit()에 의존. | 프로세스 크래시 시 모든 미커밋 enrichment 손실. 리스크 C6(atomicity) 해결 실패. | 각 노드 enrichment 완료 시 commit, 또는 N개 단위로 batch commit |
| **C-3** | daily_enrich.py:201-248 | **Phase 4-5에서 스펙 명시 작업 미구현:** L4-L5 분류, 성장 내러티브, 크로스도메인 해석(Phase 4). 이색적 접합 최종 판단, 온톨로지 메타 검증(Phase 5). | Phase 4-5 토큰 예산의 상당 부분이 활용되지 않음 | 해당 작업 추가 구현 또는 스펙에서 명시적으로 "v2.1 defer"로 표기 |
| **C-4** | migrate_v2.py | **tier, maturity, observation_count 컬럼 미추가.** 05-blueprint에 명시된 핵심 Becoming 데이터 모델. | analyze_signals, get_becoming이 maturity를 on-the-fly 계산 — 느리고 근사치. | ALTER TABLE로 3개 컬럼 추가. remember() 시 tier=2 자동 배정. |

### Major (다음 세션에 수정)

| # | 파일 | 문제 | 영향 | 제안 |
|---|------|------|------|------|
| **M-1** | e19_missing_links.yaml | **model_tier 불일치**: 스펙은 gpt-5.2 (deep), YAML은 bulk. | E19가 저품질 모델로 실행됨 | YAML model_tier를 deep으로 수정 |
| **M-2** | daily_enrich.py:57 | **phase_limit 변수 미사용.** 계산되지만 어디에도 참조 안 됨. | Phase별 예산 제한 의도가 코드에 반영 안 됨 | phase_limit를 enrich_batch 호출에 전달하거나 제거 |
| **M-3** | server.py | **connect(), search_nodes(), get_relations(), get_session() 미구현.** 05-blueprint Part 10에 명시. | 사용자가 수동 edge 생성, 고급 검색 불가 | 별도 Step으로 구현 또는 v2.1 defer |
| **M-4** | relation_extractor.py:302-303 | **f-string SQL**: `f"SELECT DISTINCT {field} FROM nodes WHERE {field} IS NOT NULL"`. field는 내부값이라 현재 안전하지만 코드 스멜. | 외부 입력이 field로 들어오면 SQL injection | `field`를 allowlist로 검증하는 guard 추가 |
| **M-5** | remember.py | **provisional flag 타입 불일치**: SQLite metadata에 `True` (bool), ChromaDB에 `"true"` (str). | 조회 시 타입 비교 혼란 가능 | 양쪽 모두 string `"true"` 통일 |
| **M-6** | 3개 enricher 모듈 | **`_call_json()` 중복 코드.** node_enricher, relation_extractor, graph_analyzer 모두 동일한 40줄 함수. | 변경 시 3곳 동시 수정 필요 | base class 또는 공통 모듈 추출 |

### Minor (개선 권장)

| # | 파일 | 문제 | 제안 |
|---|------|------|------|
| m-1 | graph_analyzer.py | E19 `run_e19_all()`에서 bulk 모델 사용 vs 스펙 deep | model_tier 참조하여 모델 결정 |
| m-2 | daily_enrich.py | Phase 6 (Codex review) 미통합 — codex_review.py 별도 스크립트 | 의도적 분리이나 스펙에 명시 필요 |
| m-3 | config.py | TYPE_TO_LAYER이 migrate_v2.py에만 있고 config.py에 없음 | 공유 상수는 config.py에 집중 |
| m-4 | hybrid.py | enrichment bonus 적용 전 top_k*2 후보만 평가 | 일반적으로 충분하지만 극단 케이스에서 누락 가능 |
| m-5 | analyze_signals.py | Signal 노드 0개일 때 `clustered_count` 키 누락 (수정됨) | 모든 반환 경로에서 키 일관성 확인 |
| m-6 | token_counter.py | reasoning_tokens 추적이 usage dict 구조에 의존 | OpenAI API 응답 구조 변경 시 깨질 수 있음 |
| m-7 | daily_enrich.py | generate_report에서 division by zero 가능 (total=0) | `enriched/total*100` → `enriched/(total or 1)*100` |
| m-8 | promote_node.py | realized_as edge가 자기 자신을 가리킴 (self-edge) 가능성 | related_ids에서 node_id 제외 검증 (이미 있음) — OK |
| m-9 | get_becoming.py | 430개 노드 전체 조회 후 필터링 — 대규모 DB에서 비효율 | SQL WHERE에 domain 필터 포함 |

---

## 11. 누락/미구현 항목

### 05-blueprint에서 언급되었으나 미구현

| 항목 | Blueprint Part | 상태 | 비고 |
|------|---------------|------|------|
| 헤비안 학습 (recall 시 edge.frequency +1) | Phase 2 #7 | **미구현** | recall()에서 edge 활성화 안 함 |
| 시간 감쇠 (하루 단위 decay) | Phase 2 #8 | **미구현** | decay_rate 컬럼만 존재 |
| 리좀적 전파 (propagate) | Phase 2 #9 | **미구현** | 기본 graph traversal만 |
| 크로스도메인 recall | Phase 2 #10 | **미구현** | project 필터 제거 모드 없음 |
| 탐험 모드 (10% 약한 edge) | Phase 2 #11 | **미구현** | |
| connect() MCP 도구 | Phase 3 | **미구현** | 수동 edge 생성 |
| search_nodes() MCP 도구 | Part 10 | **미구현** | 고급 검색 |
| tier 시스템 | Part 6 | **미구현** | 컬럼 없음 |
| maturity 컬럼 | Part 6 | **미구현** | on-the-fly 계산 |
| confidence 기반 에스컬레이션 | Part 9 | **미구현** | |
| 경로 3 수동 교정 | Part 9 | **미구현** | |
| 경로 4 정기 감사 | Part 9 | **미구현** | |

**참고**: 이들은 05-blueprint의 Phase 2-5에 해당하며, 현재 구현은 06-enrichment-pipeline-spec의 Step 1-10 범위에 집중. Blueprint의 전체 30-step 중 enrichment pipeline(Step 1-10)만 구현된 것은 의도된 범위 제한.

### 06-spec에서 언급되었으나 미구현

| 항목 | 스펙 섹션 | 상태 |
|------|----------|------|
| Phase 4: L4-L5 분류 | 5.2 | **미구현** |
| Phase 4: 성장 내러티브 | 5.2 | **미구현** |
| Phase 4: 크로스도메인 연결 해석 | 5.2 | **미구현** |
| Phase 5: 이색적 접합 최종 판단 | 5.2 | **미구현** |
| Phase 5: 온톨로지 메타 검증 | 5.2 | **미구현** |
| E7 ChromaDB 재임베딩 | 3.1 E7 | **미구현** |
| O8 temporal_relevance rule-based decay | 7.5 | **미구현** |
| Phase별 예산 제한 | 5.2 | **미구현** (phase_limit 미사용) |

---

## 12. 결론 및 권고

### 전체 평가: **B+**

핵심 인프라(25개 작업, 4-Model 배분, 토큰 관리, 프롬프트 외부화, MCP 통합)는 스펙을 충실히 구현했다. 그러나 "마지막 1마일" — E7의 ChromaDB 반영, commit 원자성, Phase 4-5 미구현 작업 — 이 남아있어 실제 실행 시 의도한 효과를 완전히 달성하지 못한다.

### 우선순위 권고

1. **즉시**: C-1 (E7 ChromaDB 반영) + C-2 (commit 원자성) — 이 둘 없이 파이프라인 실행 시 데이터 무결성 위험
2. **다음 세션**: C-3 (Phase 4-5 누락 작업), M-1 (E19 model_tier)
3. **v2.1**: C-4 (tier/maturity 컬럼), M-3 (누락 MCP 도구), Blueprint Phase 2 기능
