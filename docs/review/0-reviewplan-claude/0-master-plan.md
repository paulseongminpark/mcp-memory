# mcp-memory v2.1 Ontology Full Review Plan

> **Goal**: v2.1 온톨로지 시스템의 정확성, 설계 품질, 운영 안정성을 3 Rounds x 3 CLIs로 병렬 검증
> **Output**: 81개 리뷰 보고서 (9 folders x 9 categories) + 1 메타리뷰
> **Execution**: 9 병렬 트랙 + 1 메타리뷰 트랙

---

## 0. Absolute Rules

| Rule | Applies To |
|------|-----------|
| 소스코드(.py, .yaml, config 등) 수정 **절대 금지** | Codex, Gemini |
| git commit/push/checkout 실행 금지 | Codex, Gemini |
| `docs/review/` 폴더 내 .md 파일 생성만 허용 | Codex, Gemini |
| 읽기 → Sonnet agent, 매칭/탐색 → Haiku agent 위임 | Claude |
| 설계 로직/정합성/코어 로직 → Opus 직접 수행 | Claude |

---

## 1. Review Scope

### 1.1 Source Code (24 files)

**storage/ (4)**

| File | Role | Key Specs |
|------|------|-----------|
| `sqlite_store.py` | DB CRUD, init_db | a-r3-17, d-r3-12 |
| `hybrid.py` | Hybrid search, BCM, UCB, SPRT, RRF | b-r3-14, c-r3-11 |
| `vector_store.py` | Embedding store, drift detection | d-r3-12 |
| `action_log.py` | Action logging | a-r3-17 |

**tools/ (10)**

| File | Role | Key Specs |
|------|------|-----------|
| `remember.py` | classify->store->link->F3 | a-r3-18 |
| `recall.py` | hybrid search + graph bonus + BCM update | b-r3-15 |
| `promote_node.py` | 3-gate promotion (SWR/Bayesian/MDL) | c-r3-11 |
| `analyze_signals.py` | Cluster analysis + SPRT + Bayesian | c-r3-11 |
| `get_becoming.py` | Becoming patterns | (no spec) |
| `get_context.py` | Session context | (no spec) |
| `inspect_node.py` | Node inspection | (no spec) |
| `save_session.py` | Session saving | (no spec) |
| `suggest_type.py` | Type suggestion | (no spec) |
| `visualize.py` | Graph visualization | b-r2-11 |

**utils/ (2)**

| File | Role | Key Specs |
|------|------|-----------|
| `access_control.py` | A10 firewall + Hub protection + RBAC | d-r3-13 |
| `similarity.py` | Cosine similarity, drift calc | d-r3-12 |

**ontology/ + config (3)**

| File | Role |
|------|------|
| `validators.py` | Type/relation validation (type_defs based) |
| `schema.yaml` | 50 node types, 48 relation types |
| `config.py` | All constants (BCM, UCB, SPRT, RRF, etc.) |

**server.py** — MCP server entry point, tool routing

### 1.2 Scripts (14 files)

| File | Role | Key Specs |
|------|------|-----------|
| `daily_enrich.py` | Phase 6 pruning pipeline | d-r3-14 |
| `pruning.py` | Node/edge pruning logic | d-r3-14 |
| `hub_monitor.py` | Hub node detection + recommendations | d-r3-13 |
| `calibrate_drift.py` | Drift threshold auto-measurement | d-r3-12 |
| `sprt_simulate.py` | SPRT parameter simulation | c-r3-12 |
| `eval/ab_test.py` | NDCG A/B testing | c-r3-10 |
| `migrate_v2.py` | v2.0 migration | a-r3-16 |
| `migrate_v2_ontology.py` | v2.1 ontology migration | - |
| `safety_net.py` | Safety net | - |
| `export_to_obsidian.py` | Obsidian export | - |
| `enrich/node_enricher.py` | Node enrichment | - |
| `enrich/prompt_loader.py` | Prompt loader | - |
| `enrich/graph_analyzer.py` | Graph analysis | - |
| `dashboard.py` | Dashboard | - |

### 1.3 Tests (7 files, 117 total)

| File | Target | ~Count |
|------|--------|--------|
| `test_hybrid.py` | BCM, UCB, SPRT, RRF, hybrid_search | ~30 |
| `test_recall_v2.py` | Recall modes, graph bonus | ~20 |
| `test_remember_v2.py` | Classify, store, link, F3 | ~20 |
| `test_access_control.py` | A10, hub, RBAC | ~15 |
| `test_action_log.py` | Record, query | ~10 |
| `test_drift.py` | Drift detection | ~10 |
| `test_validators_integration.py` | Type/relation validation | ~12 |

### 1.4 Ideation — Round 3 Final Specs (10 key docs)

| Doc | Content |
|-----|---------|
| `0-orchestrator-round3-final.md` | Final architecture decisions |
| `a-r3-17-actionlog-record.md` | action_log final spec |
| `a-r3-18-remember-final.md` | remember final spec |
| `b-r3-14-hybrid-final.md` | hybrid search final spec |
| `b-r3-15-recall-final.md` | recall final spec |
| `c-r3-11-promotion-final.md` | 3-gate promotion final spec |
| `c-r3-12-sprt-validation.md` | SPRT validation spec |
| `d-r3-11-validators-final.md` | validators final spec |
| `d-r3-12-drift-final.md` | drift detection final spec |
| `d-r3-13-access-control.md` | access control final spec |
| `d-r3-14-pruning-integration.md` | pruning final spec |

### 1.5 Implementation Docs (6)

`0-impl-index.md`, `0-impl-phase0~3.md`, `0-impl-ontology-guide.md`

---

## 2. Review Categories (9)

| # | Category | Target Files | Output Filename |
|---|----------|-------------|-----------------|
| 01 | Storage Layer | storage/*.py (4) | `01_storage.md` |
| 02 | Tools Layer | tools/*.py (10) | `02_tools.md` |
| 03 | Utils & Ontology | utils/, ontology/, config.py | `03_utils_ontology.md` |
| 04 | Scripts | scripts/ (14) | `04_scripts.md` |
| 05 | Spec Alignment | ideation/ <-> code mapping | `05_spec_alignment.md` |
| 06 | Tests | tests/ (7, 117 tests) | `06_tests.md` |
| 07 | E2E Scenarios | 10 scenarios | `07_e2e_scenarios.md` |
| 08 | Security & Errors | Entire codebase | `08_security.md` |
| 09 | Summary | Round aggregate | `09_summary.md` |

---

## 3. Round Perspectives

### Round 1: Correctness & Completeness

> Core question: "Was this built correctly according to specs?"

1. Every spec function/method is implemented
2. Function signatures (params, returns) match specs
3. Algorithm logic matches spec formulas/descriptions
4. config.py constants match spec-decided values
5. Type/relation defs consistent: schema.yaml <-> config.py <-> validators.py
6. Tests actually verify spec functionality
7. Missing features (in spec, not in code)
8. Extra features (in code, not in spec)

### Round 2: Architecture & Design Quality

> Core question: "Was this well designed?"

1. Layer coupling appropriate (storage <-> tools <-> utils)
2. Module cohesion high (single responsibility)
3. Error handling consistent and adequate
4. Abstraction levels appropriate (over/under)
5. Code duplication
6. DB query performance (indexes, N+1)
7. Extensibility (adding new types/relations)
8. Security design (input validation, SQL injection, access control)
9. Config-code separation

### Round 3: Operational Reality

> Core question: "What breaks in production?"

1. Edge cases (empty input, huge input, unicode, special chars)
2. Concurrent access data integrity (multiple Claude sessions)
3. Failure modes (DB lock, embedding API failure, network disconnect)
4. Recovery mechanisms (retry, rollback)
5. Real data scale performance (3255 nodes, 6324 edges)
6. Observability (logging sufficiency, debuggability)
7. Migration safety (v2.0->v2.1 data preservation)
8. Long-term data growth (pruning effectiveness, index performance)
9. External dependency failures (OpenAI API, Anthropic API)

---

## 4. CLI Assignments

### 4.1 Claude (Opus)

- **Env**: Warp pane (interactive)
- **Strength**: Design logic reasoning, system-level coherence, insights
- **Delegation**: Read -> Sonnet agent, Search -> Haiku agent
- **Direct**: Logic verification, architecture critique, synthesis

| Round | Focus |
|-------|-------|
| R1 | Algorithm logic line-by-line, formula/condition correctness, spec compliance |
| R2 | Design pattern evaluation, coupling/cohesion, abstraction critique, extensibility |
| R3 | Failure scenario simulation, concurrency analysis, recovery paths, edge cases |

### 4.2 Codex

- **Env**: PowerShell (`codex exec`)
- **Strength**: Code-level static analysis, diff, automated testing
- **Constraint**: Source code modification ABSOLUTELY FORBIDDEN

| Round | Focus |
|-------|-------|
| R1 | Static analysis (undefined refs, dead code, unused imports, type mismatches) |
| R2 | Cyclomatic complexity, duplicate detection, dependency graph, naming consistency |
| R3 | Test coverage gaps, error path tracing, resource leaks, boundary values |

### 4.3 Gemini

- **Env**: PowerShell (`gemini` CLI)
- **Strength**: Large-scale cross-file analysis, pattern matching
- **Constraint**: Source code modification ABSOLUTELY FORBIDDEN

| Round | Focus |
|-------|-------|
| R1 | Spec-code 1:1 mapping, signature verification, API contracts, missing features |
| R2 | Cross-file patterns, data flow tracing, config consistency, architecture diagrams |
| R3 | Schema-runtime mismatches, migration safety, real data statistics analysis |

---

## 5. E2E Scenarios (10)

### S1: remember() — New Memory Storage

**Input**: `remember(content="Rust ownership은 RAII 패턴의 확장이다", source="conversation", actor="claude")`

**Code Path**:
```
server.py -> handle_tool_call("remember")
  -> tools/remember.py::remember()
    -> Step 1: classify_content(content)
      -> ontology/validators.py::validate_node_type()
      -> config.py NODE_TYPES -> type="Insight", layer=2
    -> Step 2: store_node()
      -> storage/sqlite_store.py::insert_node(type, content, layer, ...)
      -> storage/vector_store.py::store_embedding(node_id, content)
    -> Step 3: auto_link()
      -> storage/hybrid.py::hybrid_search(content, limit=5)
        -> _vec_search() -> cosine similarity
        -> _fts_search() -> FTS5 match
        -> _rrf_merge() -> k=30
      -> For each match: sqlite_store.insert_edge(source, target, relation)
    -> Step 4: action_log.record("remember", node_id, ...)
    -> Step 5: Format F3 response -> return
```

**Verify**: classify accuracy, node columns, embedding created, auto-link edges, action_log entry, F3 format

### S2: recall() — Deep Mode Search

**Input**: `recall(query="rust ownership", mode="deep")`

**Code Path**:
```
server.py -> handle_tool_call("recall")
  -> tools/recall.py::recall()
    -> storage/hybrid.py::hybrid_search(query, mode="deep")
      -> _vec_search(query) -> top-N cosine
      -> _fts_search(query) -> top-N FTS5 BM25
      -> _rrf_merge(vec, fts, k=30)
      -> _graph_bonus(merged, GRAPH_BONUS)
        -> graph/traversal.py CTE -> neighbor bonus
      -> BCM: _update_bcm(result_nodes) -> theta_m sliding
      -> UCB: _update_ucb_arms() -> vec/fts arm reward
      -> SPRT: _sprt_check(nodes) -> LLR accumulate
    -> meta.total_recall_count += 1
    -> recall_log entry
    -> Format results -> return
```

**Verify**: vec/fts results correct, RRF formula (1/(k+rank)), graph_bonus application, BCM theta update, UCB arm update, SPRT LLR accumulation, result ordering

### S3: recall() — Edge Cases

**Inputs**: `recall("")`, `recall("a")`, `recall("가" * 1000)`

**Verify**: Empty query -> error or empty (no crash), 1-char -> FTS5 handles, Very long -> API/DB limits, Unicode/special chars -> encoding ok

### S4: promote_node() — 3-Gate Pass

**Input**: `promote_node(id=123, target_type="Principle", reason="confirmed", related_ids=[124,125])`

**Code Path**:
```
-> tools/promote_node.py::promote_node()
  -> Get current node (sqlite_store.get_node)
  -> Gate 1 (SWR): recall_log vec/fts ratio + cross-project diversity
    -> readiness = 0.6*vec_ratio + 0.4*cross_ratio > 0.55
  -> Gate 2 (Bayesian): hit count k, total n from recall_log
    -> posterior = (1+k)/(11+n) > 0.5 [Beta(1,10) prior]
  -> Gate 3 (MDL): related_nodes embedding cosine sim avg
    -> avg_sim > 0.75 (skip if <2 nodes or no embeddings)
  -> All PASS: update_node(type, layer) + action_log.record("promote")
```

**Verify**: Each gate formula, gate ordering (SWR->Bayesian->MDL), skip_gates=True bypass, post-promotion type/layer change

### S5: promote_node() — Gate Failures

**Scenarios**: Gate 1 fail (readiness<0.55), Gate 2 fail (posterior<0.5), Gate 3 fail (avg_sim<0.75)

**Verify**: Correct failure message per gate, actual numbers included in response, no partial state change on failure

### S6: analyze_signals()

**Code Path**:
```
-> tools/analyze_signals.py::analyze_signals()
  -> _recommend_v2(): promotion_candidate=1 nodes
  -> _bayesian_cluster_score(): per-cluster Bayesian confidence
  -> Return: {recommendations, bayesian_p, sprt_flagged}
```

**Verify**: SPRT candidate consumption, Bayesian calculation, cluster grouping logic

### S7: daily_enrich Phase 6

**Input**: `python scripts/daily_enrich.py --phase 6 --dry-run`

**Code Path**:
```
-> Phase 6-A: Edge pruning
  -> strength = freq * exp(-0.005 * days) < 0.05 -> candidate
  -> Bauml ctx_log diversity >= 2 -> keep
  -> source tier=0 or layer>=2 -> archive
  -> else -> delete
-> Phase 6-B: Node BSP
  -> quality_score<0.3 AND observation_count<2 AND last_activated<-90d AND edge_count<3
  -> check_access() -> L4/L5 + hub protection
-> Phase 6-C: 30-day candidates -> archived
-> Phase 6-D: action_log records
```

**Verify**: Strength formula, Bauml diversity check, access control integration, dry-run produces no DB changes

### S8: remember -> recall x N -> SPRT -> promote

**Sequence**:
1. `remember()` -> new node X
2. `recall()` x N -> node X in results -> SPRT LLR accumulates
3. LLR > A=2.773 -> promotion_candidate=1
4. `promote_node(X, "Pattern")` -> 3-gate execution

**Verify**: SPRT LLR correct per recall, threshold A triggers candidate, threshold B (-1.558) rejects

### S9: hub_monitor

**Code Path**:
```
-> hub_monitor.py::main()
  -> recommend_hub_action() -> edge count top nodes
  -> Hub threshold check -> split/protect recommendations
  -> print_hub_actions() -> markdown table
```

**Verify**: Hub detection threshold, recommendation types, protected hub list

### S10: save_session -> get_context

**Sequence**:
1. `save_session(summary="...", decisions=[...], insights=[...])`
2. (new session) `get_context()`

**Verify**: Session data persisted correctly, get_context retrieves most recent, priority ordering with multiple sessions

---

## 6. Claude Atomic Tasks

### Round 1: Correctness

| ID | Category | Key Checks | Output |
|----|----------|-----------|--------|
| T1-C-01 | Storage | All public methods vs a-r3-17/d-r3-12; BCM formula vs b-r3-14; UCB formula vs b-r3-14; SPRT LLR vs c-r3-11; RRF k vs config; drift calc vs d-r3-12; action_log.record() sig vs a-r3-17 | `claude review_r1/01_storage.md` |
| T1-C-02 | Tools | remember classify->store->link vs a-r3-18; recall modes vs b-r3-15; graph_bonus vs b-r3-15; promote 3-gate formulas vs c-r3-11; analyze _recommend_v2 vs c-r3-11; remaining 6 tools function check | `claude review_r1/02_tools.md` |
| T1-C-03 | Utils/Onto | access_control 3-layer vs d-r3-13; similarity drift vs d-r3-12; validators type_defs vs d-r3-11; config constants vs spec values; schema.yaml <-> config.py consistency | `claude review_r1/03_utils_ontology.md` |
| T1-C-04 | Scripts | daily_enrich Phase 6 vs d-r3-14; pruning formulas; hub_monitor vs d-r3-13; calibrate_drift vs d-r3-12; eval scripts correctness | `claude review_r1/04_scripts.md` |
| T1-C-05 | Spec Align | Map ALL R3 final spec sections -> implementation files:lines; identify gaps (spec not impl); identify additions (impl not spec); verify orchestrator decisions followed | `claude review_r1/05_spec_alignment.md` |
| T1-C-06 | Tests | Each test file: does it test the spec feature? Missing scenarios? Mock correctness? Edge case coverage? | `claude review_r1/06_tests.md` |
| T1-C-07 | E2E | Trace all 10 scenarios through actual code; verify each step produces expected results; identify broken paths | `claude review_r1/07_e2e_scenarios.md` |
| T1-C-08 | Security | SQL injection vectors in all DB operations; access control bypass scenarios; input validation gaps; error info leakage | `claude review_r1/08_security.md` |
| T1-C-09 | Summary | Aggregate: Critical/High/Medium/Low counts; top 5 most impactful findings; coverage metrics | `claude review_r1/09_summary.md` |

### Round 2: Architecture

| ID | Category | Key Checks | Output |
|----|----------|-----------|--------|
| T2-C-01 | Storage | Layer boundary clarity; DB abstraction quality; transaction handling; connection management; index strategy | `claude_review_r2/01_storage.md` |
| T2-C-02 | Tools | Tool-storage coupling; shared code patterns; error propagation; response format consistency; tool composition | `claude_review_r2/02_tools.md` |
| T2-C-03 | Utils/Onto | Validator extensibility; config organization; schema evolution strategy; type system design quality | `claude_review_r2/03_utils_ontology.md` |
| T2-C-04 | Scripts | Script-library boundary; code reuse with main code; CLI interface design; idempotency | `claude_review_r2/04_scripts.md` |
| T2-C-05 | Spec Align | Spec quality: are specs self-consistent? contradictions between specs? over-specification? under-specification? | `claude_review_r2/05_spec_alignment.md` |
| T2-C-06 | Tests | Test architecture: fixtures, mocking patterns, test isolation, assertion quality, test naming | `claude_review_r2/06_tests.md` |
| T2-C-07 | E2E | Flow architecture: are the 10 paths optimally structured? unnecessary indirection? missing short circuits? | `claude_review_r2/07_e2e_scenarios.md` |
| T2-C-08 | Security | Security architecture: defense-in-depth? trust boundaries clear? principle of least privilege? | `claude_review_r2/08_security.md` |
| T2-C-09 | Summary | Architecture score card; coupling matrix; top design recommendations | `claude_review_r2/09_summary.md` |

### Round 3: Operations

| ID | Category | Key Checks | Output |
|----|----------|-----------|--------|
| T3-C-01 | Storage | Concurrent DB writes; WAL mode effectiveness; lock contention; data corruption scenarios; backup/restore | `claude_review_r3/01_storage.md` |
| T3-C-02 | Tools | Tool timeout behavior; partial failure handling; idempotency on retry; resource cleanup on exception | `claude_review_r3/02_tools.md` |
| T3-C-03 | Utils/Onto | Type system runtime failures; config hot-reload feasibility; validator false positive/negative rates | `claude_review_r3/03_utils_ontology.md` |
| T3-C-04 | Scripts | Pruning false positive risk; hub monitor accuracy at scale; enrichment pipeline recovery; scheduling | `claude_review_r3/04_scripts.md` |
| T3-C-05 | Spec Align | Spec vs reality drift: which specs are already outdated? which will break first under scale? | `claude_review_r3/05_spec_alignment.md` |
| T3-C-06 | Tests | Test reliability: flaky tests? timing dependencies? environment assumptions? CI/CD readiness? | `claude_review_r3/06_tests.md` |
| T3-C-07 | E2E | Scenario stress testing: what happens under 10x data? 100 concurrent recalls? API rate limits? | `claude_review_r3/07_e2e_scenarios.md` |
| T3-C-08 | Security | Runtime security: injection via malicious content; privilege escalation via promote; DoS via recall flood | `claude_review_r3/08_security.md` |
| T3-C-09 | Summary | Operational readiness score; top 5 production risks; monitoring recommendations | `claude_review_r3/09_summary.md` |

---

## 7. Codex Tasks (Summary)

See `docs/review/0-reviewplan-codex/prompts.md` for copy-pasteable PowerShell commands.

| Round | Focus | Command Count |
|-------|-------|--------------|
| R1 | Static analysis, undefined refs, dead code, type mismatches, spec compliance | 1 |
| R2 | Complexity, duplication, dependency graph, naming, error handling patterns | 1 |
| R3 | Test coverage gaps, error paths, resource leaks, boundary values | 1 |

Each command produces 9 report files in the corresponding review folder.

---

## 8. Gemini Tasks (Summary)

See `docs/review/0-reviewplan-gemini/prompts.md` for copy-pasteable PowerShell commands.

| Round | Focus | Command Count |
|-------|-------|--------------|
| R1 | Spec-code mapping, signature verification, API contracts, missing features | 1 |
| R2 | Cross-file patterns, data flow tracing, config consistency, architecture | 1 |
| R3 | Schema-runtime mismatches, migration safety, real data analysis | 1 |

Each command produces a combined review file in the corresponding review folder.

---

## 9. Meta-Review

**Separate track** — Opus pane (`rv-meta`)

**Input**: 3 files in `docs/0-imp-guide-review-by-ais/`:
- `gemini_review.md`
- `gpt_review.md`
- `perplexity_sonnet4.6_review.md`

**Tasks**:
1. Read all 3 review documents
2. Per-document analysis: strengths, weaknesses, limitations, blind spots
3. Cross-comparison: agreements vs disagreements between reviewers
4. Synthesis: what do all reviewers agree on? what does each uniquely identify?
5. Implications for our v2.1 implementation: which concerns are addressed? which remain?
6. Assessment of ideation quality: were the original specs sound?
7. Write report to `docs/review/0-meta-review/meta-review-report.md`

---

## 10. Execution Setup

### Pane Configuration

**New Warp window** (review dedicated):

| Pane | CLI | Round | Prompt Source |
|------|-----|-------|---------------|
| `rv-c1` | Claude (Opus) | Round 1: Correctness | This plan Section 6 R1 |
| `rv-c2` | Claude (Opus) | Round 2: Architecture | This plan Section 6 R2 |
| `rv-c3` | Claude (Opus) | Round 3: Operations | This plan Section 6 R3 |
| `rv-meta` | Claude (Opus) | Meta-Review | This plan Section 9 |

**Existing Warp window**:

| Pane | Status | Action |
|------|--------|--------|
| W1 | GRAPH_BONUS tuning pending | Keep (follow up) |
| W2 | Work complete | Close or repurpose |
| W3 | Work complete | Close or repurpose |

**PowerShell windows**:

| Window | CLI | Rounds | Execution |
|--------|-----|--------|-----------|
| PS-1 | Codex | R1, R2, R3 | 3 sequential commands (or 3 tabs parallel) |
| PS-2 | Gemini | R1, R2, R3 | 3 sequential commands (or 3 tabs parallel) |

### Total Parallel Tracks: 10

```
Warp (review):  rv-c1 | rv-c2 | rv-c3 | rv-meta
PowerShell 1:   Codex R1 | Codex R2 | Codex R3
PowerShell 2:   Gemini R1 | Gemini R2 | Gemini R3
```

### Claude Pane Launch Prompts

**rv-c1 (Round 1: Correctness)**:
```
너는 mcp-memory v2.1 온톨로지 시스템의 Round 1 (Correctness) 리뷰어다.
모델: Opus 200K. 컨텍스트 관리가 중요하다.

마스터 플랜을 먼저 읽어라: docs/review/0-reviewplan-claude/0-master-plan.md

핵심 질문: "이것이 스펙대로 맞게 만들어졌는가?"

태스크 T1-C-01 ~ T1-C-09를 순차 실행한다.
각 태스크의 보고서를 docs/review/claude review_r1/XX_filename.md 에 작성한다.

[위임 규칙]
- 파일 읽기: Explore 에이전트에 위임 (컨텍스트 절약)
- 패턴 검색/매칭: Explore quick 에이전트에 위임
- 설계 로직 판단, 정합성 검증, 결론 도출: 너가 직접 수행

[컨텍스트 관리 — 반드시 준수]
- 각 카테고리(01~08) 보고서 작성 완료 후 반드시 /compact 실행
- compact 후 다음 카테고리 시작 전에 마스터 플랜을 다시 참조
- 카테고리 09 (Summary) 작성 시: 01~08 보고서를 다시 Read로 읽어서 종합
- 한 카테고리 내에서 파일을 다 읽은 뒤 분석 → 보고서 작성 → /compact 순서

[출력 형식]
마스터 플랜 Section 11 참조.

T1-C-01 (Storage Layer)부터 시작하라.
```

**rv-c2 (Round 2: Architecture)**:
```
너는 mcp-memory v2.1 온톨로지 시스템의 Round 2 (Architecture) 리뷰어다.
모델: Opus 200K. 컨텍스트 관리가 중요하다.

마스터 플랜을 먼저 읽어라: docs/review/0-reviewplan-claude/0-master-plan.md

핵심 질문: "이것이 잘 설계되었는가?"

태스크 T2-C-01 ~ T2-C-09를 순차 실행한다.
각 태스크의 보고서를 docs/review/claude_review_r2/XX_filename.md 에 작성한다.

[위임 규칙]
- 파일 읽기: Explore 에이전트에 위임 (컨텍스트 절약)
- 패턴 검색/매칭: Explore quick 에이전트에 위임
- 아키텍처 판단, 설계 비평, 결론 도출: 너가 직접 수행

[컨텍스트 관리 — 반드시 준수]
- 각 카테고리(01~08) 보고서 작성 완료 후 반드시 /compact 실행
- compact 후 다음 카테고리 시작 전에 마스터 플랜을 다시 참조
- 카테고리 09 (Summary) 작성 시: 01~08 보고서를 다시 Read로 읽어서 종합
- 한 카테고리 내에서 파일을 다 읽은 뒤 분석 → 보고서 작성 → /compact 순서

[출력 형식]
마스터 플랜 Section 11 참조.

T2-C-01 (Storage Layer)부터 시작하라.
```

**rv-c3 (Round 3: Operations)**:
```
너는 mcp-memory v2.1 온톨로지 시스템의 Round 3 (Operations) 리뷰어다.
모델: Opus 200K. 컨텍스트 관리가 중요하다.

마스터 플랜을 먼저 읽어라: docs/review/0-reviewplan-claude/0-master-plan.md

핵심 질문: "실제 운영에서 어떤 문제가 발생하는가?"

태스크 T3-C-01 ~ T3-C-09를 순차 실행한다.
각 태스크의 보고서를 docs/review/claude_review_r3/XX_filename.md 에 작성한다.

[위임 규칙]
- 파일 읽기: Explore 에이전트에 위임 (컨텍스트 절약)
- 패턴 검색/매칭: Explore quick 에이전트에 위임
- 장애 시나리오 추론, 엣지케이스 분석, 결론 도출: 너가 직접 수행

[컨텍스트 관리 — 반드시 준수]
- 각 카테고리(01~08) 보고서 작성 완료 후 반드시 /compact 실행
- compact 후 다음 카테고리 시작 전에 마스터 플랜을 다시 참조
- 카테고리 09 (Summary) 작성 시: 01~08 보고서를 다시 Read로 읽어서 종합
- 한 카테고리 내에서 파일을 다 읽은 뒤 분석 → 보고서 작성 → /compact 순서

[출력 형식]
마스터 플랜 Section 11 참조.

T3-C-01 (Storage Layer)부터 시작하라.
```

**rv-meta (Meta-Review)**:
```
너는 mcp-memory에 대한 기존 AI 리뷰들의 메타리뷰어다.
모델: Opus 200K.

docs/0-imp-guide-review-by-ais/ 의 모든 파일을 읽어라:
- gemini_review.md
- gpt_review.md
- perplexity_sonnet4.6_review.md

각 문서에 대해:
1. 이 리뷰가 잘 식별한 것은?
2. 이 리뷰가 놓친 것은?
3. 이 리뷰의 한계/맹점은?

교차 비교: 합의 사항, 분기 사항, 각 리뷰의 고유 인사이트.
아이디에이션 평가: 원래 설계 스펙이 건전했는가?
시사점: v2.1 구현에서 어떤 우려가 해결되었고, 어떤 것이 남아있는가?

보고서 작성: docs/review/0-meta-review/meta-review-report.md

이 작업은 문서 3개뿐이므로 compact 불필요. 한 번에 읽고 분석하고 작성한다.
```

---

## 11. Output Format (Standard)

Every review report follows this structure:

```markdown
# [Category] Review - Round [N] ([Perspective])

> Reviewer: [Claude/Codex/Gemini]
> Date: YYYY-MM-DD
> Perspective: [Correctness/Architecture/Operations]
> Files Reviewed: [list]

## Findings

### [Severity: CRITICAL]

**[ID]** [Title]
- File: `path/to/file.py:line`
- Spec: `docs/ideation/spec-file.md:section` (if applicable)
- Description: ...
- Impact: ...
- Recommendation: ...

### [Severity: HIGH]
...

### [Severity: MEDIUM]
...

### [Severity: LOW]
...

### [Severity: INFO]
...

## Coverage

- Files reviewed: N/N
- Functions verified: N/N
- Spec sections checked: N/N

## Summary

- CRITICAL: N
- HIGH: N
- MEDIUM: N
- LOW: N
- INFO: N

**Top 3 Most Impactful Findings:**
1. ...
2. ...
3. ...
```

---

## 12. Completion Criteria

```
[ ] Round 1 x 3 CLIs: 27 category reports completed
[ ] Round 2 x 3 CLIs: 27 category reports completed
[ ] Round 3 x 3 CLIs: 27 category reports completed
[ ] Meta-Review: 1 synthesis report completed
[ ] Cross-round synthesis: Critical findings from all rounds aggregated
[ ] Final action items: Prioritized fix list created
```
