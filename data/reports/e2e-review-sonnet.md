# mcp-memory v2.0 E2E Review (Sonnet)
> Date: 2026-03-04
> Reviewer: Claude Sonnet 4.6
> Scope: 설계 문서 3개 vs 구현 코드 전체

---

## 1. Executive Summary

mcp-memory v2.0 enrichment pipeline 구현은 설계 문서(04, 05, 06)의 핵심 요소를 충실히 반영하였으며, 특히 4-Model 토큰 예산 배분, 25개 enrichment 작업(E1-E25), 7단계 Phase 오케스트레이션, migration 스키마, MCP 도구 4개 신규 등록이 구조적으로 올바르게 구현되었다. 그러나 다음 범주에서 설계-구현 간 불일치 및 미구현 항목이 발견되었다: (1) Phase 2의 GA 메서드 시그니처 불일치로 인한 런타임 크래시 가능성, (2) 프롬프트 품질 — 핵심 YAML들이 지나치게 간결하여 45개 타입 온톨로지 컨텍스트 없이 GPT가 판단해야 함, (3) E24와 E21이 동일한 `find_similar_pairs()` 로직을 공유하여 중복 처리 가능성, (4) `nodes.maturity` 및 `nodes.observation_count` 컬럼이 설계에는 있지만 migrate_v2.py에 없음, (5) `promote_node()`이 metadata JSON에 이력을 저장하지만 `nodes.promotion_history` 전용 컬럼이 없어 쿼리 불가. 전체 완성도는 약 78/100로 평가되며, 아래 Critical 항목 3개를 먼저 수정해야 첫 실행이 안전하다.

---

## 2. 스펙 준수 매트릭스

### 06-spec Step (구현 순서)

| Step | 스펙 항목 | 구현 파일 | 상태 | 비고 |
|------|-----------|-----------|------|------|
| Step 1 | migrate_v2.py (C4, C8, S8, S10) | scripts/migrate_v2.py | OK | 7단계 내부 로직 일치 |
| Step 2 | config.py enrichment 설정 (S7) | config.py | OK | 모든 required 필드 존재 |
| Step 3 | token_counter.py (C1, S9) | scripts/enrich/token_counter.py | OK | reasoning_tokens 추적, adaptive backoff |
| Step 4 | node_enricher.py (E1-E12) | scripts/enrich/node_enricher.py | PARTIAL | E4 union 정책 OK, E12 충돌 해소 OK. 단 dry_run 시 enrichment_status 미기록 |
| Step 5 | relation_extractor.py (E13-E17) | scripts/enrich/relation_extractor.py | PARTIAL | 3-strategy clustering OK. E17 dry_run 시 sentinel -1 반환 후 count에 포함될 가능성 |
| Step 6 | graph_analyzer.py (E18-E25) | scripts/enrich/graph_analyzer.py | PARTIAL | 모든 E 구현됨. `_insert_edge`에 base_strength/direction/reason 미설정 |
| Step 7 | daily_enrich.py (오케스트레이터) | scripts/daily_enrich.py | PARTIAL | Phase 2 GA 메서드 시그니처 불일치(아래 Critical #1) |
| Step 8 | codex_review.py | scripts/codex_review.py | OK | 4개 리뷰 대상, subprocess 오류 처리 완비 |
| Step 9 | 프롬프트 25개 + 테스트 | scripts/enrich/prompts/*.yaml, scripts/test_prompts.py | PARTIAL | 25개 YAML 존재. 단 프롬프트 품질 문제 있음(섹션 5 참조) |
| Step 10 | MCP 도구 통합 (S5) | storage/hybrid.py, tools/*.py, server.py | OK | recall() 가중치 반영, provisional embedding 플래그 구현 |

### 06-spec 리스크 항목

| 리스크 | 설명 | 해결 여부 | 파일 | 비고 |
|--------|------|-----------|------|------|
| C1 | o3 추론 토큰 예측 불가 | OK | token_counter.py | reasoning_tokens 별도 추적, estimate_remaining_o3_calls() |
| C2 | API 실패 시 토큰 낭비 | OK | daily_enrich.py | MAX_CONSECUTIVE_FAILURES=3, Phase 스킵 로직 |
| C3 | 프롬프트 품질이 파이프라인 결정 | PARTIAL | prompts/*.yaml | 50개 표본 테스트 프레임 있음. 하지만 프롬프트 자체가 너무 간결(섹션 5) |
| C4 | SQLite 스키마 마이그레이션 전략 부재 | OK | migrate_v2.py | ALTER TABLE + FTS5 재구축 + 트랜잭션 |
| C5 | enrichment 결과 간 충돌 해소 없음 | OK | node_enricher.py _apply() | facets=union, layer=gpt>0.8, secondary=layer변경시 미재실행(Minor 이슈) |
| C6 | 파이프라인 크래시 시 부분 기록 | OK | node_enricher.py | enrichment_status JSON으로 작업별 완료 추적 |
| C7 | ChromaDB 재임베딩 동시성 | PARTIAL | node_enricher.py _apply() | E7 결과가 DB에 저장 안 됨(ChromaDB 직접 접근 코드 없음) - 미구현 |
| C8 | 신규 노드 판별 기준 미정의 | OK | migrate_v2.py, daily_enrich.py | enriched_at IS NULL = 미처리 기준, UTC 통일 |
| S1 | 배치 처리 순서 의존성 | OK | daily_enrich.py phase1() | E7은 E1,E2 완료 후 별도 실행 |
| S2 | 소형 모델 환각 위험 | OK | node_enricher.py | FACETS_ALLOWLIST, DOMAINS_ALLOWLIST 필터 |
| S3 | 크로스도메인 클러스터링 전략 | OK | relation_extractor.py | 3-strategy (concept, facet, random) |
| S4 | Day 1-3 마이그레이션 실패 시 복구 | OK | migrate_v2.py | enrichment_status JSON + 멱등성 |
| S5 | recall/remember 통합 설계 부재 | OK | hybrid.py, remember.py | quality_score/temporal_relevance 가중치, provisional 플래그 |
| S6 | 순환 의존 embedding↔edge↔graph | OK | relation_extractor.py 주석 | 1-pass 제한: E7 결과는 다음 실행의 E13 입력 |
| S7 | config.py enrichment 설정 부재 | OK | config.py | ENRICHMENT_MODELS, TOKEN_BUDGETS, BATCH_SIZE 등 완비 |
| S8 | edges 테이블 direction/reason/updated_at 없음 | OK | migrate_v2.py step2_edges_schema() | 3개 컬럼 추가됨 |
| S9 | Rate Limiting 전략 불충분 | OK | token_counter.py | RateLimiter 클래스, 429 retry-after 파싱 |
| S10 | correction_log 테이블 미정의 | OK | migrate_v2.py step3_correction_log() | CREATE TABLE IF NOT EXISTS |
| S11 | 기존 enrichment/와 신규 scripts/enrich/ 관계 불명확 | PARTIAL | server.py, tools/remember.py | 역할 분리는 구현되었으나 docs에 명시 없음 |

---

## 3. 온톨로지 일치 검증

### 04-dialogue 대비 차이점

**타입 수**
- 설계(05-blueprint Part 4): 45개 활성 + 7개 예약 = 52개
- migrate_v2.py TYPE_TO_LAYER: 45개 활성 타입 매핑됨 (일치)
- 7개 예약 타입(Thesis, Argument, Passage, Style, Voice, Composition, Influence): TYPE_TO_LAYER에 없음 — 설계 의도대로 schema 정의만 되어 있어야 하지만, 현재 schema.yaml 파일을 직접 확인하지 못함. config.py에도 예약 타입 목록 없음. (Minor — 실제 분류에 사용 안 하면 문제 없음)

**레이어 매핑 정확도**
- 05-blueprint Layer 배정과 migrate_v2.py TYPE_TO_LAYER 비교:
  - Layer 0 (8개): Observation, Evidence, Trigger, Context, Conversation, Narrative, Question, Preference — 일치
  - Layer 1 (18개): Decision, Plan, Workflow, Experiment, Failure, Breakthrough, Evolution, Signal, Goal, Ritual, Tool, Skill, AntiPattern, Constraint, Assumption, SystemVersion, Agent, Project — 일치
  - Layer 2 (9개): Pattern, Insight, Framework, Heuristic, Trade-off, Tension, Metaphor, Connection, Concept — 일치 (Concept에 *표시 있지만 활성으로 포함됨)
  - Layer 3 (6개): Principle, Identity, Boundary, Vision, Paradox, Commitment — 일치
  - Layer 4 (4개): Belief, Philosophy, Mental Model, Lens — 일치 ("Mental Model"이 TYPE_TO_LAYER에 "Mental Model"(공백 포함)으로 저장됨 — SQLite WHERE 절에서 정확 매칭 필요)
  - Layer 5 (4개): Axiom, Value, Wonder, Aporia — 일치

**관계 타입 (48개)**
- 05-blueprint Part 5 vs config.py RELATION_TYPES:
  - 인과 8개: 일치
  - 구조적 8개: 일치
  - 레이어 이동 6개: 일치 (realized_as, crystallized_into 등)
  - 차이 추적 4개: 일치
  - 의미론적 8개: 일치
  - 관점 4개: 일치
  - 시간적 4개: 일치
  - 크로스도메인 6개: 일치
  - 합계 48개 — 완전 일치

**승격 경로 (VALID_PROMOTIONS)**
- config.py에 정의된 경로: Observation→Signal/Evidence, Signal→Pattern/Insight, Pattern→Principle/Framework/Heuristic, Insight→Principle/Concept
- 05-blueprint Part 6 시나리오 및 04-dialogue 대화 12와 일치
- 단, 04-dialogue에서 언급된 Principle→Philosophy 승격 경로가 VALID_PROMOTIONS에 없음 — 설계 문서의 "4c. Principle → Philosophy 승격" 시나리오가 코드로 지원 안 됨 (Minor)

**nodes 스키마 불일치**
- 05-blueprint Part 2에 정의된 노드 필드:
  - `maturity` (0.0~1.0): migrate_v2.py nodes ALTER에 없음 (MISSING)
  - `observation_count` (유사 관찰 횟수): 없음 (MISSING)
  - `promotion_history` (JSON 배열): migrate_v2.py에 컬럼으로 없음. promote_node.py는 metadata JSON 내부에 저장. 설계는 전용 컬럼 또는 JSON 배열로 명시 (불일치)
  - `tier` (0/1/2): migrate_v2.py nodes ALTER에 없음 (MISSING)
  - `source` (체크포인트 출처): 기존 컬럼으로 존재하는지 확인 필요

- 05-blueprint Part 3 Edge 스키마:
  - `effective_strength` (계산된 강도): 설계에서는 실시간 계산값으로 언급되지만 저장 컬럼으로는 정의 안 됨 — 코드도 저장 안 함 (허용 가능, 계산 필드)
  - 실제 스키마에 `last_activated` 컬럼이 migrate_v2.py에 추가됨 — 일치
  - `frequency`, `decay_rate`, `layer_distance`, `layer_penalty` — 모두 일치

---

## 4. 아키텍처 일치 검증 (05-blueprint Part 1-12)

| Part | 내용 | 구현 상태 | 비고 |
|------|------|-----------|------|
| Part 1: 전체 구조도 | Paul → Claude → MCP → SQLite/ChromaDB/NetworkX | OK | server.py 13개 도구 등록, hybrid.py 3중 검색 |
| Part 2: 노드 스키마 | 다면 분류, facets, tier, maturity, promotion_history | PARTIAL | maturity, observation_count, tier 컬럼 누락 |
| Part 3: Edge 스키마 | frequency, last_activated, decay_rate, effective_strength | OK | migrate_v2.py에 모두 추가됨 (effective_strength는 계산 필드) |
| Part 4: 6레이어 45+7 타입 | TYPE_TO_LAYER 매핑 | OK | "Mental Model" 공백 이슈 주의 |
| Part 5: 48개 관계 타입 | config.RELATION_TYPES | OK | 완전 일치 |
| Part 6: 데이터 흐름 시나리오 | remember → auto edge → recall → 헤비안 → Becoming | PARTIAL | 헤비안 강화 코드(recall 시 edge.frequency +1)가 hybrid.py에 없음 (MISSING) |
| Part 7: 얻는 것 6가지 | 이색적 접합, 기억 성장 등 | OK | 설계 목적, 구현 방향 일치 |
| Part 8: 리스크 10개 | R1-R10 | PARTIAL | R1-R3 해결됨, R4-R5 ChromaDB 동시성 및 전파 폭발은 partial |
| Part 9: 치명적 리스크 해결 | 2단계 분류, 헤비안, 전파 제한 | PARTIAL | propagate() 함수 미구현 (리좀적 전파 핵심 기능) |
| Part 10: Claude의 지속적 역할 | 5가지 관여 지점 | OK | analyze_signals, promote_node, get_becoming, inspect 구현됨 |
| Part 11: 구현 순서 Phase 1-6 | Phase 1-6 로드맵 | PARTIAL | Phase 1-5 Enrichment 구현됨. Phase 4 (대시보드), Phase 6 (미래 데이터) 미구현 |
| Part 12: 4-Model Enrichment Pipeline | 25개 작업, 토큰 배분, 스케줄 | OK | daily_enrich.py Phase 1-7 구현됨 |

**Critical 미구현: 헤비안 학습 (Part 6, Part 9)**
- 05-blueprint에서 "recall() 시 통과한 edge의 frequency +1" (헤비안 강화)이 핵심으로 명시됨
- hybrid.py의 `hybrid_search()` 함수에 edge 강화 코드가 없음
- 이것이 빠지면 "살아있는 edge" 개념 자체가 동작하지 않음

**Critical 미구현: propagate() 리좀적 전파 (Part 6)**
- 05-blueprint Part 8 R3에서 구체적인 propagate() 의사코드 제시됨
- 현재 graph/traversal.py의 `traverse()`가 있지만 seed-based BFS 방식으로, 헤비안 강화/층 페널티/tier 가중치를 적용하는 propagate() 함수가 별도로 구현되지 않음
- hybrid_search의 그래프 탐색 단계가 이를 대체하나 설계 의도와 차이 있음

---

## 5. 프롬프트 품질 검증 (25개 YAML)

### 공통 문제

**문제 A: 시스템 프롬프트에 온톨로지 컨텍스트 없음**
- E6 (secondary_types): 45개 타입 목록이 system/user 어디에도 없음. GPT가 어떤 보조 타입이 가능한지 모름.
- E12 (layer_verify): layer 정의는 약어로만 제공 ("L0=원시경험..."). 45개 타입과 레이어 매핑 없음.
- 결과: GPT가 온톨로지에 없는 타입을 보조 타입으로 생성할 가능성 높음.

**문제 B: 한국어/영어 혼용 불일치**
- E1, E2, E3, E9, E10, E11: user 프롬프트는 한국어, system은 영어
- E13, E14, E15, E16, E17, E18, E19, E20, E21, E22, E23, E24, E25: 전부 영어
- 일관성 없음. 동일 작업에 다른 언어 → 응답 품질 편차 발생 가능

**문제 C: JSON 응답 포맷 지시 유무**
- 모든 프롬프트가 response_format={"type": "json_object"} 사용 (코드에서) → JSON 강제됨
- 단, 각 키의 타입 명세가 없는 프롬프트 다수: E9는 `{"level": 0.0}` 예시 있지만 E10은 `{"relevance": 0.0}` 예시만 — float 범위 지시 없음

### 개별 YAML 검증

| Task | 상태 | 문제 |
|------|------|------|
| E1 (summary) | PARTIAL | 응답 키 이름 명시됨(`summary`). 100자 제한 지시 있음. 단 언어 지시 없음(한국어 시스템 프롬프트인데 영어 반환 가능성) |
| E2 (key_concepts) | PARTIAL | 응답 키 `concepts`. 1-3단어 제한 OK. 언어 지시 없음 |
| E3 (tags) | PARTIAL | 중복 제거 지시 없음. 기존 태그 포함 금지 명시 없음 |
| E4 (facets) | OK | allowlist 전달, 응답 포맷 명시. 단 시스템에 allowlist 예시 없음 (사용자 프롬프트에 없음) |
| E5 (domains) | OK | allowlist 전달, project/source 컨텍스트 제공 |
| E6 (secondary_types) | CRITICAL | 45개 타입 목록 없음. GPT가 임의 타입 생성 가능. 주타입 목록도 없음 |
| E7 (embedding_text) | OK | 입력 필드 5개 명시, 150-200자 제한, 자연스러운 텍스트 지시 |
| E8 (quality_score) | OK | 3점 앵커(1.0/0.5/0.0) 명시, 응답 키 2개(`score`, `reason`) |
| E9 (abstraction_level) | PARTIAL | 점수 범위 OK. 단 `reason` 필드 없어 디버깅 불가 |
| E10 (temporal_relevance) | PARTIAL | 날짜 컨텍스트 제공 OK. `reason` 없음 |
| E11 (actionability) | PARTIAL | 3점 앵커 OK. `reason` 없음 |
| E12 (layer_verify) | PARTIAL | layer 정의 6개 모두 제공. 단 `confidence` 기준 명시 없음 (어떤 기준으로 0.8 이상?) |
| E13 (cross_domain) | OK | relations_list 변수로 48개 관계 전달, 출력 포맷 명시. 0-5개 제한 명시 |
| E14 (refine_relation) | OK | all_relations 변수, source/target 컨텍스트 4필드, changed bool 지시 |
| E15 (direction) | OK | 4가지 direction 정의와 의미 명확히 설명됨 |
| E16 (strength) | OK | 3점 앵커 명확, 현재 강도 컨텍스트 제공 |
| E17 (merge_duplicates) | PARTIAL | action 값을 "merge|keep-both"로 명시. 단 `delete_ids` 키가 응답 포맷에 없음 — 코드는 keep_id만으로 delete_ids를 계산하므로 OK |
| E18 (cluster_theme) | OK | 4개 응답 키 명시, framework_type 예시 제공 |
| E19 (missing_links) | PARTIAL | relation_list 앞 20개만 전달 (나머지 28개 누락). 고립 노드가 실제 연결 대상인 neighbor인지 명확성 부족 |
| E20 (temporal_chain) | OK | 4가지 chain_type 정의, 최소 3개 노드 지시 |
| E21 (contradiction) | OK | 4가지 contradiction_type 명시, confidence 반환 지시 |
| E22 (assemblage) | OK | assemblage_type 예시 제공, components 구조 명시 |
| E23 (promotion) | OK | 승격 조건 3가지 명확, 5개 응답 키 모두 정의, 판단 질문 4개 |
| E24 (merge_candidate) | OK | 3가지 action 정의, key_difference 조건부 요구 |
| E25 (knowledge_gap) | PARTIAL | all_types 변수에 15개 예시만 전달. 실제 45개 활성 타입 중 일부만 참조 가능 |

---

## 6. 에러 처리 검증

### node_enricher.py
- BudgetExhausted: 별도 Exception 클래스 정의, enrich_batch에서 break 처리 — OK
- RateLimitError: parse_retry_after → record_429 → adaptive backoff — OK
- APIError + JSONDecodeError: 동일 except 블록에서 재시도 — OK (단 JSONDecodeError가 API 에러와 동일 처리됨 — 일부 경우 재시도보다 로깅이 나을 수 있음)
- 단일 태스크 실패: `except Exception as e: stats["errors"] += 1; results[tid] = {"error": str(e)}` — 전체 노드 중단 없이 계속 진행. OK
- **문제**: `_call_json`의 마지막 `return {}` 이후 도달 불가 (unreachable). 이 경우 호출부에서 빈 dict가 반환되어 `r.get("summary")` 등이 None → 빈 문자열 처리는 됨. 실용적으로 문제없음.
- **문제**: float 변환 실패 (E8, E9, E10, E11): `float(r.get("score", 0.5))` — 문자열 반환 시 ValueError 미처리. 코드에 try/except가 있으나 E8은 없음.

### relation_extractor.py
- E13: API 실패 시 빈 배열 반환 — OK (노드 없음 방어)
- E14, E15, E16: BudgetExhausted re-raise, 일반 Exception fallback — OK
- E17: `e17_merge_duplicates` dry_run 확인 — 단 `find_duplicate_edges()`에 limit 없음 → 전체 edges GROUP BY 쿼리가 대용량에서 느릴 수 있음
- **문제**: `_insert_edge` dry_run=True 시 sentinel -1 반환 → `run_e13`에서 `if edge_id is not None` 체크 통과 → `total_new += 1` 실행 → dry_run 중에 카운터 증가. dry_run 정확도 문제.

### graph_analyzer.py
- 모든 run_* 메서드에 BudgetExhausted, Exception 개별 catch — OK
- `_insert_edge`에서 duplicate 체크 — OK
- **문제**: `_insert_edge`가 relation_extractor._insert_edge와 다른 시그니처: 후자는 direction, reason 파라미터를 받지만 graph_analyzer._insert_edge는 그 두 필드를 저장하지 않음. 새로 삽입된 edge의 direction, reason이 NULL로 남음.
- **문제**: `run_e19_all(limit=30)` 호출 시 `run_e19_all`의 시그니처는 `def run_e19_all(self) -> list[dict]` — `limit` 파라미터 없음. daily_enrich.py phase4에서 `ga.run_e19_all(limit=30)` 호출 → TypeError 런타임 크래시.

### daily_enrich.py
- `phase2()`에서 `ga.run_e21_all(limit=30)`, `ga.run_e22_all(limit=40)` 호출
- `run_e21_all`, `run_e22_all` 시그니처: `def run_e21_all(self)`, `def run_e22_all(self)` — limit 파라미터 없음 → TypeError 런타임 크래시
- BudgetExhausted 외 Exception 처리 — consecutive_failures 카운터. OK
- Phase 스킵 로직: 두 풀 모두 소진 시 중단. OK

### token_counter.py
- 에러 처리: save_log 시 기존 파일 파싱 실패 시 미처리 (json.loads on existing file — try/except 없음) — Minor
- pool_for: 알 수 없는 모델 시 ValueError raise. OK

---

## 7. 보안 검증

### SQL Injection
- node_enricher.py, graph_analyzer.py: 모든 SQL 파라미터화 (`?` placeholder) 사용 — OK
- `relation_extractor._cluster_by_shared_field()`: `f"SELECT DISTINCT {field} FROM nodes WHERE {field} IS NOT NULL"` — `field` 변수가 "key_concepts" 또는 "facets" 하드코딩된 문자열 → 외부 입력 아님. 안전.
- `graph_analyzer.find_dense_clusters()`: `f"SELECT * FROM nodes WHERE id IN ({placeholders})"` — placeholders는 `"?" * len(cluster_ids)` → 안전.
- `get_becoming.py`: `f"WHERE type IN ({placeholders})"` — config.VALID_PROMOTIONS 키 목록에서 생성. 안전.
- **문제**: `analyze_signals.py`: `sql += " AND domains LIKE ?"` — 파라미터화 사용. OK. 단 `domains` 컬럼이 JSON 배열이므로 LIKE 검색은 부분 문자열 오탐 가능 (예: "orchestration" 검색 시 "neo-orchestration"도 매칭). 보안 문제는 아니지만 데이터 정확성 문제.

### 입력 검증 / Allowlist
- facets, domains: config.FACETS_ALLOWLIST, DOMAINS_ALLOWLIST 필터 적용 — OK
- relation 타입: `config.ALL_RELATIONS` 검증 — E13, E14, E19에 적용됨 — OK
- E6 secondary_types: 반환된 타입에 대해 allowlist 검증 없음 — GPT가 임의 타입 반환 가능 (보안보다 데이터 품질 문제)
- node_type 필드: `validate_node_type()` 호출 (remember.py) — OK

### API Key 노출
- `.env` 로드 방식 — OK. config.py에서 `load_dotenv` 사용

---

## 8. 데이터 흐름 검증

### Phase 1 → 2 → 3 → 4 → 5 순서

```
Phase 1 (gpt-5-mini):
  new_ids → E1,E2,E3,E4,E5,E8,E9,E10,E11 → enrichment_status 기록
  → E7 (summary,key_concepts 완료 후) ← 의존성 체크 OK
  → E13 (크로스도메인)
  → E14 (generic edge 정밀화)
  → E17 (중복 병합)
  → E16 (strength 재계산)

Phase 2 (o3-mini):
  → E21 (모순) ← 의존성 없음 OK
  → E22 (Assemblage) ← E13 완료 후가 이상적이나 선행 요건 강제 없음
  → E20 (시간 체인) ← OK
  → E15 (방향) ← OK

Phase 3 (gpt-4.1):
  → E12 (layer 검증) ← E1,E2 완료 후가 이상적. 별도 체크 없음
  → E6 (secondary_types) ← layer 확정 후가 이상적. 강제 없음

Phase 4 (gpt-5.2):
  → E18 (클러스터 테마) ← dense clusters 쿼리 OK
  → E25 (지식 공백) ← OK
  → E19 (missing links) ← limit 파라미터 오류

Phase 5 (o3):
  → E23 (승격 후보) ← OK
```

**문제**: Phase 3의 E12 → E6 순서가 같은 Phase 내에서 명시되지 않음. E12에서 layer가 바뀌어도 E6 실행 시 재분류 안 됨 (C5 해결책으로 "secondary=layer변경시재실행" 명시되었지만 코드에 없음).

**문제**: E22 Assemblage는 E13 크로스도메인 관계 추출 이후에 실행해야 더 정확하지만, Phase 1의 E13과 Phase 2의 E22 사이에 명시적 의존성 검사 없음. 실질적 영향은 낮음.

**S1 해결 확인**: E7이 E1,E2 완료 여부를 `enrichment_status NOT LIKE '%"E7"%'` 와 `summary IS NOT NULL AND key_concepts IS NOT NULL`로 체크 — OK.

---

## 9. MCP 통합 검증

### server.py 도구 목록 (13개)

| 도구 | 내부 함수 | 시그니처 일치 | docstring |
|------|-----------|---------------|-----------|
| remember() | tools/remember.py | OK | 타입 목록이 26개로 설명됨(구버전). v2.0의 45개 타입 미반영 |
| recall() | tools/recall.py (미읽음, 간접 확인) | OK | type_filter, project, top_k 파라미터 |
| get_context() | tools/get_context.py | OK | 간결한 설명 |
| save_session() | tools/save_session.py | OK | |
| suggest_type() | tools/suggest_type.py | OK | "26 node types" 언급 — 구버전 설명 |
| analyze_signals() | tools/analyze_signals.py | OK | maturity 임계값 명시(0.9/0.6) |
| promote_node() | tools/promote_node.py | OK | valid paths 명시. 단 Principle→Philosophy 누락 |
| get_becoming() | tools/get_becoming.py | OK | analyze_signals()와의 관계 설명 |
| inspect() | tools/inspect_node.py | OK | 전체 메타 조회 |
| ingest_obsidian() | ingestion/obsidian.py | OK | |
| visualize() | tools/visualize.py | OK | |
| ontology_review() | scripts/ontology_review.py | OK | |
| dashboard() | scripts/dashboard.py | OK | |

**docstring 문제**:
- `remember()`: 타입 목록에 26개 구버전 타입 명시. v2.0의 45개 타입에 맞게 업데이트 필요. (Minor)
- `suggest_type()`: "26 node types" 언급 — 구버전 (Minor)
- `promote_node()`: valid paths 설명에 Principle→Philosophy 없음

**MCP 도구 수 불일치**:
- 05-blueprint Part 10 목표: 11개 도구
- 실제 구현: 13개 도구 (ingest_obsidian, visualize, ontology_review, dashboard 추가됨)
- 4개가 더 많음 — 문제 아님, 기능 추가로 해석

**server.py instructions 필드**:
- "26 node types" 기반의 오래된 설명. 새 아키텍처 설명 없음. (Minor)

---

## 10. 발견된 문제 (Critical → Minor)

| # | 심각도 | 파일 | 문제 | 제안 |
|---|--------|------|------|------|
| 1 | **Critical** | scripts/daily_enrich.py, scripts/enrich/graph_analyzer.py | `phase4()`에서 `ga.run_e19_all(limit=30)` 호출, `phase2()`에서 `ga.run_e21_all(limit=30)`, `ga.run_e22_all(limit=40)` 호출 — 세 메서드 모두 `limit` 파라미터 없음 → TypeError 런타임 크래시 | graph_analyzer.py의 `run_e19_all`, `run_e21_all`, `run_e22_all`에 `limit: int` 파라미터 추가, 또는 daily_enrich.py에서 limit 인자 제거 |
| 2 | **Critical** | storage/hybrid.py | 헤비안 학습 미구현. recall() 결과 노출 시 `edge.frequency += 1` 강화 코드 없음. 05-blueprint의 핵심 메커니즘 부재 | `hybrid_search()` 내 그래프 탐색 직후 통과한 edge의 frequency, last_activated 업데이트 로직 추가 |
| 3 | **Critical** | scripts/enrich/node_enricher.py | E7 (_apply 메서드): `pass` — "ChromaDB용, DB 컬럼 없음. daily_enrich에서 처리"라고 되어 있지만 daily_enrich.py phase1()에도 ChromaDB upsert 코드 없음. embedding_text 생성은 되지만 ChromaDB 재임베딩이 실제 일어나지 않음 | daily_enrich.py phase1()에 E7 결과를 받아 ChromaDB에 upsert하는 로직 추가 |
| 4 | **High** | scripts/migrate_v2.py | 노드 스키마에 `maturity` (REAL), `observation_count` (INTEGER), `tier` (INTEGER) 컬럼 없음. 05-blueprint Part 2에 명시된 핵심 필드 | migrate_v2.py step1_nodes_schema()에 3개 컬럼 추가 |
| 5 | **High** | scripts/enrich/graph_analyzer.py | `_insert_edge` 메서드에 `direction`, `reason` 파라미터와 저장 코드 없음. E19, E21, E22, E24가 이 메서드로 edge 삽입 시 direction/reason NULL로 저장 | relation_extractor._insert_edge와 시그니처 통일하거나, graph_analyzer._insert_edge에 direction/reason 파라미터 추가 |
| 6 | **High** | scripts/enrich/prompts/e06_secondary_types.yaml | 시스템 프롬프트에 45개 유효 타입 목록 없음. GPT가 온톨로지에 없는 타입을 반환할 가능성 높음. node_enricher.py E6 결과에 allowlist 검증도 없음 | E6 system 프롬프트에 TYPE_TO_LAYER 키 목록 삽입, 또는 node_enricher E6 결과에 TYPE_TO_LAYER 기반 필터 추가 |
| 7 | **High** | scripts/enrich/relation_extractor.py | dry_run=True 시 `_insert_edge` 반환값이 -1 (sentinel) → `run_e13()`에서 `if edge_id is not None` 통과 → `total_new += 1` — dry_run 중 삽입 카운터가 잘못 증가 | dry_run 시 `edge_id == -1` 감지 로직 추가 또는 sentinel을 None으로 변경 |
| 8 | **High** | config.py, migrate_v2.py | VALID_PROMOTIONS에 Principle→Philosophy 승격 경로 없음. 05-blueprint Part 6 시나리오에서 Principle→Philosophy 사례 명시됨 | VALID_PROMOTIONS에 `"Principle": ["Belief", "Philosophy", "Value"]` 추가 및 PROMOTE_LAYER 업데이트 |
| 9 | **Medium** | scripts/enrich/node_enricher.py | E12 실행 후 layer 변경 시 같은 노드의 E6 (secondary_types) 재실행 코드 없음. C5 해결책으로 명시된 "secondary=layer변경시재실행" 미구현 | E12 결과에서 `changed=True`이면 E6 재실행 로직 추가 |
| 10 | **Medium** | scripts/enrich/token_counter.py | `save_log()` 내 `path.read_text()` 후 `json.loads()` — 기존 파일 파싱 실패 시 try/except 없음. 로그 파일 손상 시 save_log() 크래시 | try/except 추가 후 손상 파일은 새로 시작 |
| 11 | **Medium** | tools/promote_node.py | promotion_history가 `metadata` JSON 내부에 저장됨. `inspect_node()`에서 `metadata.get("promotion_history")`로 접근 — 쿼리 기반 조회(예: 이력이 많은 노드 찾기) 불가. 05-blueprint Part 2는 전용 컬럼 또는 별도 테이블 암시 | migrate_v2.py에 promotion_log 테이블 추가, 또는 nodes.promotion_history TEXT 컬럼 추가 |
| 12 | **Medium** | scripts/daily_enrich.py | `phase1()`: `stats["edges"] += len(getattr(re, '_last_inserted', []))` — `_last_inserted` 속성이 RelationExtractor에 없음. 항상 0 반환 | `re.stats["e13_new_edges"]` 사용으로 수정 |
| 13 | **Minor** | server.py | `remember()` docstring의 타입 목록이 v0.1.0 기준 26개. v2.0의 45개 활성 타입 미반영 | docstring 업데이트 |
| 14 | **Minor** | scripts/enrich/prompts/e19_missing_links.yaml | `relation_list` 변수에 `config.ALL_RELATIONS[:20]` — 48개 중 20개만 전달. 나머지 28개 관계 타입 참조 불가 | 전체 48개 전달하거나, 카테고리별로 분류하여 전달 |
| 15 | **Minor** | scripts/enrich/prompts/e25_knowledge_gap.yaml | `all_types` 변수에 15개 예시 타입만 전달. 실제 45개 활성 타입 중 일부 누락 (Framework, Heuristic, Trade-off 등) | graph_analyzer.py에서 TYPE_TO_LAYER 전체 키 리스트 전달 |
| 16 | **Minor** | TYPE_TO_LAYER, config.py | `"Mental Model"` 타입 이름에 공백 포함. SQLite WHERE type='Mental Model' 동작하지만, JSON serialization 및 Python dict 키로 혼용 시 주의 필요 | 공백 없는 "MentalModel"로 통일 또는 일관성 문서화 |
| 17 | **Minor** | scripts/enrich/prompts/ | E1, E2, E8, E9, E10, E11: user 프롬프트 한국어, system 영어 혼용. E13-E25: 전부 영어. 일관성 없음 | 언어 정책 결정 후 통일 |

---

## 11. 누락/미구현 항목

설계 문서에 있지만 구현에 없거나 미완성인 항목:

| 항목 | 설계 문서 위치 | 구현 상태 | 비고 |
|------|---------------|-----------|------|
| 헤비안 학습 (recall 시 edge 강화) | 05-blueprint Part 6, Part 9 R2 | 없음 | hybrid.py에 코드 없음 |
| propagate() 리좀적 전파 함수 | 05-blueprint Part 8 R3 코드 | 없음 | graph/traversal.py의 traverse()가 부분 대체 |
| nodes.maturity 컬럼 | 05-blueprint Part 2 | migrate_v2.py에 없음 | get_becoming()이 quality_score+edge_count로 대체 계산 |
| nodes.observation_count 컬럼 | 05-blueprint Part 2 | 없음 | |
| nodes.tier 컬럼 | 05-blueprint Part 2, 04-dialogue | 없음 | remember.py의 tier 지정 기능 없음 |
| ChromaDB E7 재임베딩 | 06-spec E7, C7 | daily_enrich.py에 없음 | node_enricher._apply("E7") = pass |
| E12 후 E6 재실행 | 06-spec C5 해결책 | 없음 | |
| Principle→Philosophy 승격 경로 | 05-blueprint Part 6 Step 4c | VALID_PROMOTIONS에 없음 | |
| 탐험 모드 (recall 10% 약한 edge) | 05-blueprint Part 9 R2 코드 | 없음 | hybrid.py에 explore_weak_edges() 없음 |
| correction_log 활용 코드 | 06-spec 경로 3 | 테이블만 생성, 실제 write 코드 없음 | node_enricher가 correction_log에 삽입하지 않음 |
| effective_strength 실시간 계산 | 05-blueprint Part 3 | 없음 | base_strength만 저장, 감쇠 계산 코드 없음 |
| 시간 감쇠 (decay_rate 적용) | 05-blueprint Part 9, 대화 9 | 없음 | decay_rate 컬럼은 있지만 daily decay 계산 스크립트 없음 |
| base_strength × 0.5 하한선 | 05-blueprint Part 9 R2 | 없음 | |
| 대시보드 v2.0 (레이어별 뷰 등) | 05-blueprint Part 11 Phase 4 | 미구현 | Phase 4 미완성 |
| 과거 데이터 ingestion (Phase 6) | 05-blueprint Part 11 Phase 6 | 미구현 | 설계 Phase 6 자체가 미래 계획 |

---

## 12. 결론 및 권고

### 종합 평가

구현은 25개 Enrichment 작업, 4-Model 토큰 배분, migration 스키마, MCP 신규 도구 4개, 프롬프트 25개 YAML, test_prompts.py, codex_review.py 전반에 걸쳐 설계 문서의 약 78%를 충실히 반영하였다. 구현의 뼈대와 흐름은 올바르다.

### 즉시 수정 필요 (첫 실행 전)

1. **Critical #1** — `graph_analyzer.py` 3개 메서드에 `limit` 파라미터 추가
   - `run_e19_all`, `run_e21_all`, `run_e22_all`
   - 수정하지 않으면 Phase 2, Phase 4 실행 시 TypeError로 크래시

2. **Critical #2** — `storage/hybrid.py`에 헤비안 강화 로직 추가
   - recall 시 통과한 edge의 `frequency += 1`, `last_activated` 업데이트
   - 시스템의 핵심 가치인 "살아있는 edge"가 동작하지 않음

3. **Critical #3** — `daily_enrich.py` + `node_enricher.py`에 ChromaDB E7 재임베딩 추가
   - embedding_text를 생성하지만 ChromaDB에 반영하지 않음
   - recall() 벡터 검색 품질이 enrichment 전과 동일

### 다음 우선순위 (High)

4. `migrate_v2.py`에 `maturity`, `observation_count`, `tier` 컬럼 추가
5. `graph_analyzer._insert_edge`에 `direction`, `reason` 저장 추가
6. E6 프롬프트 또는 코드에 타입 allowlist 검증 추가
7. VALID_PROMOTIONS에 Principle→Philosophy 경로 추가

### 중기 개선 (설계 완성도)

- 시간 감쇠(decay_rate 적용) 스크립트 추가
- 탐험 모드(10% weak edge recall) 구현
- correction_log 실제 write 연결
- `effective_strength` 실시간 계산 함수 추가
