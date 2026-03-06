# E2E Scenarios Review - Round 1 (Correctness)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: End-to-End Code Path Tracing
> Scenarios Traced: 10

## Scenario Traces

### S1: remember() -- New Memory Storage

**Path:** `server.py:40-112` -> `tools/remember.py:232-291`
- classify() -> store() -> link() pipeline

**Trace Results:**
1. **Type validation (server.py:66-95):** `validate_node_type()` queries `type_defs` table. If table missing, falls back to `schema.yaml`. Works correctly.
2. **classify() (remember.py:38-77):** Re-validates type (redundant with server.py validation). Sets `embedding_provisional=true` in metadata. Layer/tier assignment from `PROMOTE_LAYER`. Correct.
3. **store() (remember.py:82-146):** `sqlite_store.insert_node()` inserts all v2.1 columns. `action_log.record("node_created")` fires. `vector_store.add()` calls `embed_text()` for ChromaDB. On embedding failure, returns warning and skips link(). Correct.
4. **link() (remember.py:151-227):** F3 firewall blocks L4/L5 auto-edges. `vector_store.search()` finds similar nodes. `infer_relation()` determines relation type. `insert_edge()` validates against `ALL_RELATIONS`. `action_log.record("edge_auto")` fires per edge. Correct.
5. **Return format:** `{node_id, type, project, auto_edges, message}` -- matches F3 response spec.

**Verdict:** S1 path is INTACT. No broken paths.

---

### S2: recall() -- Hybrid Search

**Path:** `server.py:116-138` -> `tools/recall.py:11-78` -> `storage/hybrid.py:385-496`

**Trace Results:**
1. **server.py recall() lacks `mode` parameter.** The MCP tool signature (line 116-121) has `query, type_filter, project, top_k` only. The `mode` parameter in `tools/recall.py:16` is unreachable from MCP clients. Always defaults to `"auto"`.
2. **hybrid_search (hybrid.py:385-496):**
   - Vector search -> FTS5 search -> seed_ids (top 3 each) -> UCB graph traverse -> RRF merge. Correct flow.
   - RRF formula: `1.0 / (RRF_K + rank)` where `RRF_K=60`. Matches `1/(k+rank)` spec.
   - Graph bonus: flat `GRAPH_BONUS=0.015` added to UCB-discovered neighbors. Correct.
   - Enrichment/tier bonuses added after RRF. Correct.
3. **BCM update (hybrid.py:165-278):** Updates `edges.frequency` (BCM delta_w * 10 scale) and `nodes.theta_m`, `activity_history`, `visit_count`. Single transaction. Correct.
4. **SPRT check (hybrid.py:289-327):** Applied to Signal nodes. Updates `score_history` in nodes. Calculates cumulative LLR. Sets `promotion_candidate=1` if threshold reached. **See finding E2E-01 for critical score range issue.**
5. **Patch switching (recall.py:40-49):** If 75%+ same project, re-searches excluding dominant project. Merges top half original + bottom half alternative. Correct logic.
6. **_increment_recall_count (recall.py:104-122):** Writes to `meta` table. **See finding E2E-02: meta table does not exist.**

**Verdict:** S2 has 2 broken sub-paths (SPRT score range, meta table missing) + 1 unreachable parameter (mode).

---

### S3: recall() -- Edge Cases

**Path:** Same as S2 entry point.

**Trace Results:**
1. **Empty string `recall("")`:** `_escape_fts_query("")` returns `""`. `search_fts` returns `[]`. `vector_store.search("")` calls `embed_text("")` which will embed the empty string -- ChromaDB may return results or empty. `hybrid_search` handles empty gracefully: returns `[]` if no candidates. `recall` returns `{"results": [], "message": "No memories found."}`. **No crash.**
2. **Single char `recall("a")`:** FTS5 trigram tokenizer needs 3+ chars for efficient matching but won't crash. Vector search embeds "a" normally. Returns results or empty. **No crash.**
3. **Long string `recall("x"*1000)`:** `_escape_fts_query` wraps each word in quotes. Single 1000-char word becomes `'"xxx..."'`. FTS5 handles it. Vector embedding truncated by model's token limit. **No crash.** Query truncated in action_log to 200 chars (hybrid.py:369). **No crash.**

**Verdict:** S3 edge cases are handled gracefully. No crashes.

---

### S4: promote_node() -- 3-Gate Pass

**Path:** `server.py:231-255` -> `tools/promote_node.py:167-292`

**Trace Results:**
1. **Node lookup:** `sqlite_store.get_node(node_id)`. Returns full node dict or None. Correct.
2. **VALID_PROMOTIONS check (config.py:244-250):** Verifies `current_type -> target_type` is valid. Correct.
3. **Gate 1 - SWR (promote_node.py:25-80):**
   - `vec_ratio`: Reads from `recall_log` table. **This table does not exist.** The `except` clause catches the error and sets `vec_ratio=0.0`. The `activation_log` VIEW exists (based on action_log) but `recall_log` is a different table that was never created.
   - `cross_ratio`: Reads from `edges` table to find neighbor projects. This works.
   - `readiness = 0.6 * 0.0 + 0.4 * cross_ratio`. With `vec_ratio` always 0, readiness max is `0.4 * cross_ratio`. If `cross_ratio < 1.375` (always true since ratio <= 1.0), then `readiness < 0.55` threshold. **Gate 1 always fails unless skip_gates=True.** See finding E2E-03.
4. **Gate 2 - Bayesian (promote_node.py:101-116):**
   - `k = node.get("frequency") or 0`. **nodes table has NO frequency column.** Always `k=0`.
   - `total_queries`: Reads from `meta` table. **meta table doesn't exist.** Returns 0.
   - `P(real) = (1+0)/(11+0) = 1/11 = 0.0909`. Always < 0.5. **Gate 2 always fails.** See finding E2E-04.
5. **Gate 3 - MDL (promote_node.py:123-160):**
   - Reads embeddings from ChromaDB for related nodes. Computes avg cosine similarity. If < 2 related nodes, passes automatically. Correct logic.
6. **Promotion execution (promote_node.py:242-292):**
   - Updates `nodes.type`, `nodes.layer`, `nodes.metadata` (promotion_history). Creates `realized_as` edges. Returns result dict.
   - **No action_log.record() call.** Confirmed: `action_log` is not imported in promote_node.py. See finding E2E-05.

**Verdict:** S4 is BROKEN. Gates 1 and 2 always fail. Promotion only works with `skip_gates=True`. Action log not recorded.

---

### S5: promote_node() -- Gate Failures

**Path:** Same as S4.

**Trace Results:**
1. **Gate 1 failure:** Returns `{"status": "not_ready", "swr_score": ..., "threshold": 0.55, "message": ...}`. **No partial state change.** Correct isolation.
2. **Gate 2 failure:** Returns `{"status": "insufficient_evidence", "p_real": ..., ...}`. **No partial state change.** Correct.
3. **Gate 3 failure:** Returns `{"status": "mdl_failed", "reason": ..., ...}`. **No partial state change.** Correct.
4. **Invalid promotion path:** Returns `{"error": ..., "valid_targets": [...]}`. Correct.
5. **Node not found:** Returns `{"error": "Node #X not found."}`. Correct.

**Verdict:** S5 gate failures have correct isolation -- no partial state changes. The problem is that gates 1 and 2 *always* fail (see S4), so promotion is effectively disabled.

---

### S6: analyze_signals()

**Path:** `server.py:208-228` -> `tools/analyze_signals.py:10-126`

**Trace Results:**
1. **Signal query (line 22-28):** Queries `nodes WHERE type='Signal' AND status='active'`. Adds domain filter if specified. Uses `conn.execute` with `sqlite3.Row` factory. Correct.
2. **Feature extraction (line 38-57):** Parses `tags`, `key_concepts` (JSON), `domains` (JSON) into feature sets. Handles JSON errors gracefully. Correct.
3. **Clustering (line 59-86):** Connected components via BFS on overlap graph (1+ shared feature = edge). Correct algorithm.
4. **Maturity computation (line 129-136):** `0.5*size_score + 0.3*quality_avg + 0.2*domain_score`. Uses `quality_score` column (not `importance_score`). Correct per v2.1 schema.
5. **Bayesian cluster score (line 165-177):**
   - `_get_total_recall_count()`: Reads from `meta` table. **meta table doesn't exist.** Returns 0.
   - `total_queries=0` causes `_bayesian_cluster_score` to return `0.0` (line 167: `if total_queries <= 0: return 0.0`).
   - This means `bayesian_p` is always 0.0 in recommendations.
6. **SPRT flag count (line 102-105):** Reads `promotion_candidate` from node dict. Since SPRT threshold is unreachable (E2E-01), `sprt_flagged` is always 0.
7. **_recommend_v2 (line 148-162):**
   - `bayesian_p=0.0`, `sprt_flagged=0`. Only `maturity` drives the decision.
   - `maturity > 0.9` -> `auto_promote` requires `bayesian_p > 0.6` (impossible). Falls through.
   - `maturity > 0.6` -> `user_review`. Otherwise `not_ready`.
   - Result: Bayesian and SPRT are decorative. Only maturity matters.

**Verdict:** S6 functional but degraded. Bayesian score always 0.0, SPRT flags always 0. Recommendation reduces to maturity-only logic.

---

### S7: daily_enrich Phase 6

**Path:** `scripts/daily_enrich.py:267-519`

**Trace Results:**
1. **Edge pruning strength formula (line 357):** `strength = freq * math.exp(-0.005 * days)`.
   - `freq` = `edges.frequency` (INTEGER column, BCM writes float values to it).
   - For edges never activated by BCM: `freq=0` -> `strength=0` -> always below threshold (0.05).
   - For BCM-activated edges: `freq` is a BCM-derived float (delta_w * 10 cumulative).
   - **Issue:** New auto-link edges have `frequency=0` and `last_activated=NULL` (days=9999). Strength = 0. These always enter the pruning path. If source is L0/L1 and tier!=0, they get **deleted**. See finding E2E-06.
2. **Bauml ctx_log diversity (line 365-371):**
   - Parses `edge.description` as JSON array. Auto-link edges have description like `"auto: similarity=0.85"` (plain text). `json.loads()` fails -> `unique_queries=0`. Cannot be saved by diversity check.
3. **Edge archive (line 386-393):**
   - `decision = "archive"` but **no actual DB operation for archive**. Only "delete" triggers `DELETE FROM edges`. "archive" is counted in stats but the edge remains unchanged in DB. Confirmed: 04_scripts M-01.
4. **Node BSP Stage 2 (line 402-458):** Uses `check_access()` for L4/L5 + hub protection. Marks `status='pruning_candidate'`. Correct access control integration.
5. **Node BSP Stage 3 (line 461-495):** `pruning_candidate` + 30 days -> `status='archived'`. Correct.
6. **action_log recording (line 498-518):** Records "archive" action_type. Correct.
7. **Dry-run mode:** Correctly skips all DB mutations. Correct.

**Verdict:** S7 has 2 issues: (a) new edges always have strength=0 so are candidates for pruning immediately, (b) "archive" decision is a no-op (edge stays in DB unchanged).

---

### S8: Full Lifecycle (remember -> recall x N -> SPRT -> promote)

**Path:** S1 -> S2 (x N) -> S4

**Trace Results -- Step by Step:**

1. **remember():** Creates Signal node (node_id=X). Embedding stored. Auto-edges created. `visit_count=0`, `score_history='[]'`, `promotion_candidate=0`. Correct.

2. **recall() x N:**
   - Each recall: hybrid_search returns node X with RRF score (typically 0.01-0.4 range).
   - BCM updates: `edges.frequency` adjusted, `nodes.visit_count += 1`, `nodes.theta_m` updated. These work.
   - SPRT check: `_sprt_check(node, score, conn)` appends score to `score_history`. If score > 0.5, adds LLR_POS (~0.847). If <= 0.5, adds LLR_NEG (~-0.847). **Scores are almost always < 0.5** due to RRF range. So LLR accumulates negatively. See E2E-01.
   - `_increment_recall_count()`: Silently fails (no meta table). See E2E-02.

3. **SPRT threshold:**
   - With scores always < 0.5: cumulative LLR after N observations = N * (-0.847).
   - After 2 observations: LLR = -1.694 > _SPRT_B (-1.558). So **SPRT rejects after just 2 observations** with typical RRF scores.
   - `promotion_candidate` stays 0.

4. **promote_node():**
   - Gate 1 (SWR): `vec_ratio=0.0` (recall_log doesn't exist), `readiness = 0.4 * cross_ratio < 0.55`. Fails.
   - Gate 2 (Bayesian): `k=0` (no frequency on nodes), `total_queries=0` (no meta table). `P=1/11=0.09`. Fails.
   - **Promotion impossible without skip_gates=True.**

**Verdict:** S8 full lifecycle is BROKEN. The SPRT -> promote pipeline never triggers organically. Three independent blockers: (1) SPRT score range mismatch, (2) recall_log table missing, (3) meta table missing + nodes.frequency missing.

---

### S9: hub_monitor

**Path:** `scripts/hub_monitor.py:79-143`

**Trace Results:**
1. **compute_ihs (line 32-56):** Counts incoming edges per node (`target_id`). Sorted by IHS score DESC. Correct.
2. **hub_health_report (line 79-102):** Assigns risk levels: >50 HIGH, >20 MEDIUM, else LOW. Correct.
3. **recommend_hub_action (line 105-131):** Calls `check_access(node_id, action, actor, conn)`. If denied, returns `require_human=True`. Correct.
4. **check_access integration:** For hub nodes in Top-10 snapshot, `_check_hub_protection` returns False for "delete"/"write" operations. This correctly blocks automated hub modifications.
5. **take_snapshot (line 59-76):** Creates `hub_snapshots` table if not exists. Inserts today's Top-20. Correct.
6. **Protected hub list:** Comes from `hub_snapshots` table (latest snapshot). If no snapshot exists, `_get_top10_hub_ids()` returns empty set -- no hub protection active until first snapshot. Correct behavior but worth noting.

**Verdict:** S9 path is INTACT. Hub monitor functions correctly as standalone. Depends on snapshot being populated for protection to work.

---

### S10: save_session -> get_context

**Path:** `server.py:153-176` -> `tools/save_session.py:9-50` -> `server.py:141-150` -> `tools/get_context.py:6-38`

**Trace Results:**

1. **save_session (save_session.py:9-50):**
   - Auto-generates `session_id` from UTC timestamp if empty. Correct.
   - UPSERT into `sessions` table. If conflict on `session_id`, updates summary/decisions/unresolved + sets `ended_at`. Correct.
   - Returns `{session_id, summary[:100], decisions_count, unresolved_count, message}`. Correct.

2. **get_context (get_context.py:6-38):**
   - Queries `nodes` for recent Decision (3), Question (3), Insight (2), Failure (2) via `get_recent_nodes()`.
   - `get_recent_nodes` filters by `status='active'`, optional project/type_filter, ordered by `created_at DESC`.
   - **Does NOT read from sessions table.** get_context only reads from nodes, not sessions.
   - If user saves session with decisions via save_session, those decisions are stored in sessions table. But get_context reads Decision-type *nodes*, not session decisions. These are **different data stores**.
   - To retrieve session data, user would need a different tool (not get_context).

3. **Priority ordering:** Results are ordered by `created_at DESC` within each type. No cross-type priority system. See finding E2E-08.

**Verdict:** S10 save_session works correctly. get_context works correctly but **does not retrieve session data**. They operate on different tables -- sessions vs nodes. This is a design gap, not a bug.

---

## Findings

### [Severity: CRITICAL]

**E2E-01** SPRT Score Threshold vs RRF Score Range Mismatch
- Scenario: S2, S8
- Code Path: `hybrid.py:322` (`obs > 0.5`) vs `hybrid.py:433-460` (RRF score computation)
- Description: SPRT classifies recall scores as positive (>0.5) or negative (<=0.5). However, RRF scores have a practical maximum of ~0.4 (computed as: `2/61 + 0.015 + 0.15 + 0.21 = ~0.41`). This means virtually every observation adds LLR_NEG (~-0.847) to the cumulative sum. After 2 observations, cumulative LLR drops below _SPRT_B (-1.558), causing SPRT to reject. No Signal node can reach promotion_candidate=1 through organic recall usage.
- Impact: SPRT promotion detection is completely non-functional. The entire SPRT pipeline (score_history tracking, cumulative LLR, promotion_candidate flag) produces no useful output. analyze_signals() SPRT flag count is always 0.
- Recommendation: Normalize scores before SPRT comparison. Options: (a) use percentile rank (score > median = positive), (b) lower threshold to match RRF range (e.g., 0.02), (c) use score relative to query's top result.

### [Severity: CRITICAL]

**E2E-02** `meta` Table Never Created -- recall_count Always 0
- Scenario: S2, S4, S6, S8
- Code Path: `recall.py:113` (`INSERT INTO meta`) / `promote_node.py:87-98` (`SELECT value FROM meta`) / `analyze_signals.py:180-191`
- Description: `_increment_recall_count()` writes to `meta(key, value, updated_at)` table. `_get_total_recall_count()` reads from it. But `meta` table is never created -- not in `init_db()`, not in any migration script. Both functions silently fail (try/except returns 0). This breaks: (a) Bayesian P(real) in promote_node Gate 2 (total_queries=0 -> P=1/11=0.09), (b) Bayesian cluster score in analyze_signals (returns 0.0), (c) any future recall statistics.
- Impact: Three downstream consumers are broken. Bayesian evidence accumulation is impossible.
- Recommendation: Add `CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)` to `init_db()`.

### [Severity: CRITICAL]

**E2E-03** SWR Gate 1 Always Fails -- `recall_log` Table Missing
- Scenario: S4, S8
- Code Path: `promote_node.py:43-53` (`SELECT source, COUNT(*) FROM recall_log WHERE node_id=?`)
- Description: Gate 1 (SWR readiness) reads `vec_ratio` from `recall_log` table to determine vector vs FTS5 recall distribution. This table does not exist anywhere in the codebase. The `activation_log` VIEW exists (over action_log) but has different schema and semantics. The except clause silently sets `vec_ratio=0.0`. With `vec_ratio=0`, max readiness = `0.4 * cross_ratio` where cross_ratio <= 1.0. Max readiness = 0.4 < 0.55 threshold. **Gate 1 always fails.**
- Impact: No node can pass Gate 1 without `skip_gates=True`. Combined with E2E-04, both gates are broken, making organic promotion impossible.
- Recommendation: Either (a) create recall_log table and populate it during hybrid_search, or (b) rewrite SWR to read from activation_log VIEW which already tracks recall activations.

### [Severity: HIGH]

**E2E-04** Bayesian Gate 2 Always Fails -- `nodes.frequency` Column Missing
- Scenario: S4, S6, S8
- Code Path: `promote_node.py:112` (`k = node.get("frequency") or 0`) / `analyze_signals.py:171`
- Description: Gate 2 reads `node.get("frequency")` to compute Bayesian P(real). The `nodes` table has no `frequency` column -- only `edges` has it. `get_node()` returns `dict(row)` which won't have a "frequency" key. Result: `k` is always 0. With `total_queries` also 0 (E2E-02), `P = 1/11 = 0.0909 < 0.5`. Even if meta table were fixed and total_queries>0, P = 1/(11+n) which decreases as n grows. Gate 2 can never pass.
- Impact: Bayesian evidence gate is completely non-functional. The intended design was BCM recall frequency feeding into Bayesian, but BCM updates `edges.frequency` while Bayesian reads `nodes.frequency`. This is a fundamental data flow disconnect (confirmed: 01_storage H-02).
- Recommendation: Add `frequency` column to nodes table. Increment `nodes.frequency` in `_bcm_update()` alongside `visit_count` update, or use `visit_count` as proxy for recall frequency in Bayesian calculation.

### [Severity: HIGH]

**E2E-05** promote_node() Has No action_log Recording
- Scenario: S4, S8
- Code Path: `tools/promote_node.py` (entire file -- no `action_log` import)
- Description: promote_node.py does not import or call `action_log.record()`. Successful promotions, gate failures, and realized_as edge creation are not tracked in the audit log. The `ACTION_TAXONOMY` in action_log.py defines `"node_promoted"` and `"edge_realized"` types that are never used.
- Impact: Promotion events are invisible in the audit trail. Cannot reconstruct promotion history from action_log. The only record is in node metadata's `promotion_history` JSON field, which is harder to query at scale.
- Recommendation: Add `action_log.record("node_promoted", ...)` after successful promotion and `action_log.record("edge_realized", ...)` for each realized_as edge. Confirmed: 02_tools H-01.

### [Severity: HIGH]

**E2E-06** New Auto-Link Edges Immediately Prunable
- Scenario: S7, S8
- Code Path: `remember.py:199-205` (insert_edge) -> `daily_enrich.py:349-393` (edge pruning)
- Description: Auto-link edges from remember() are created with `strength=max(0, 1.0-distance)`, `frequency=0`, `last_activated=NULL`, and `description="auto: similarity=X.XX"`. In phase 6 pruning: (a) `freq=0` -> `strength=0 * exp(...)=0 < 0.05`, (b) `json.loads("auto: similarity=0.85")` fails -> `unique_queries=0 < 2`. Both checks fail. If source node is L0/L1 and tier!=0, the edge is immediately deleted. This means new auto-link edges can be deleted in the very first daily_enrich run after creation.
- Impact: Newly created relationships are prematurely destroyed. The pruning formula uses `edges.frequency` (BCM metric) but new edges haven't been through any BCM update cycle. The `edges.strength` column (set by remember) is ignored by the pruning formula.
- Recommendation: (a) Use `edges.strength` column in pruning formula as fallback when `frequency=0`, or (b) add grace period (skip edges created < 7 days ago), or (c) initialize `frequency` from `strength` at edge creation.

### [Severity: MEDIUM]

**E2E-07** server.py recall() Does Not Expose `mode` Parameter
- Scenario: S2
- Code Path: `server.py:116-138` (recall MCP tool definition)
- Description: The MCP tool `recall()` in server.py has parameters `query, type_filter, project, top_k` only. The `mode` parameter ("auto"|"focus"|"dmn") defined in `tools/recall.py:16` is unreachable from MCP clients. All external recall calls use `mode="auto"` regardless of intent. This was a deliberate v2.1 feature (B-12) that cannot be activated.
- Impact: Focus mode (strong connections priority, UCB_C=0.3) and DMN mode (exploration priority, UCB_C=2.5) are unusable by MCP clients. The auto mode's word-count heuristic is the only active strategy.
- Recommendation: Add `mode: str = "auto"` parameter to `server.py:recall()` and pass it through to `_recall()`.

### [Severity: MEDIUM]

**E2E-08** Edge Pruning `archive` Decision Is No-Op
- Scenario: S7
- Code Path: `daily_enrich.py:386-393`
- Description: When pruning decides `decision = "archive"` (for edges connected to tier=0 or layer>=2 nodes), no DB operation occurs. The `if not dry_run` block only handles `decision == "delete"`. The edge remains unchanged in the DB -- same strength, same description, same frequency. It will be re-evaluated and re-classified as "archive" on every subsequent run. The stats count it, but no actual archival happens.
- Impact: Edge archival is non-functional. Reported as 04_scripts M-01. In practice, these edges are preserved (which is the safer behavior), but the "archive" count in reports is misleading.
- Recommendation: Either (a) add `archived_at` column to edges and set it for archive decisions, or (b) rename the decision to "keep_protected" to accurately reflect the behavior.

### [Severity: MEDIUM]

**E2E-09** VALID_PROMOTIONS Contains Deprecated "Evidence" Type
- Scenario: S4
- Code Path: `config.py:245` (`"Observation": ["Signal", "Evidence"]`)
- Description: `VALID_PROMOTIONS` allows Observation -> Evidence promotion. If "Evidence" is deprecated in `type_defs`, a user could promote to it, but subsequent operations on the deprecated-type node may behave unexpectedly. The promote_node code does not check if `target_type` is deprecated.
- Impact: Low in practice (requires explicit user action), but violates the principle that deprecated types should not be targets of new operations. Confirmed: 05_spec M-02.
- Recommendation: Filter `VALID_PROMOTIONS` targets against `type_defs` active status, or add a deprecation check in promote_node before gate evaluation.

### [Severity: LOW]

**E2E-10** Double Type Validation in remember() Path
- Scenario: S1
- Code Path: `server.py:66-95` (validate_node_type) -> `remember.py:51-56` (validate_node_type again)
- Description: `server.py:remember()` validates and corrects the type, then passes it to `tools/remember.py:remember()`, which calls `classify()` that validates the type again. Since server.py already corrected it, the second validation always succeeds. The second validation also calls `suggest_closest_type()` on failure, which can produce a different type than server.py's correction.
- Impact: Wasted computation (2 DB queries to type_defs). Potential inconsistency if server.py and classify() have different correction logic (server.py can return error for unknown types, classify silently substitutes).
- Recommendation: Remove type validation from `classify()` since it's already handled at server.py level, or remove from server.py and let classify handle it (choose one authoritative location).

### [Severity: LOW]

**E2E-11** get_context() Does Not Retrieve save_session() Data
- Scenario: S10
- Code Path: `save_session.py` -> `sessions` table vs `get_context.py` -> `nodes` table
- Description: save_session() stores structured session data (summary, decisions, unresolved) in the `sessions` table. get_context() reads from the `nodes` table (Decision, Question, Insight, Failure type nodes). These are completely separate data stores. A decision recorded via save_session(decisions=["use Rust"]) will NOT appear in get_context() unless it was also stored as a Decision-type node via remember().
- Impact: Users may expect get_context to surface session decisions, but it only surfaces node-level memories. Session data is effectively write-only unless queried directly.
- Recommendation: Either (a) document the separation clearly, (b) have get_context also query recent sessions, or (c) have save_session automatically create Decision/Question nodes from its inputs.

### [Severity: LOW]

**E2E-12** BCM Writes Float to INTEGER Column
- Scenario: S2, S7
- Code Path: `hybrid.py:232` (`new_freq = max(0.0, ... + delta_w * 10)`) -> `edges.frequency INTEGER`
- Description: BCM computes `new_freq` as a float (e.g., 0.15, 1.23) and writes it to `edges.frequency` which is defined as `INTEGER DEFAULT 0`. SQLite's type affinity allows this (stores as REAL), but the column definition suggests integer semantics (count of activations). Edge pruning reads `freq = edge["frequency"] or 0` and uses it in `strength = freq * exp(...)`.
- Impact: Works due to SQLite flexibility, but the semantic mismatch between "frequency count" (original design) and "BCM strength delta accumulator" (current usage) can cause confusion.
- Recommendation: Either rename to `bcm_weight REAL` or change BCM to increment an integer counter alongside the float weight.

### [Severity: INFO]

**E2E-13** UCB visit_count Not Loaded into Graph
- Scenario: S2
- Code Path: `graph/traversal.py:11-21` (build_graph) -> `hybrid.py:120` (`graph.nodes[nid].get("visit_count", 1)`)
- Description: `build_graph()` only adds edge attributes (relation, strength, description). Node attributes like `visit_count` are never set on the NetworkX graph. `graph.nodes[nid].get("visit_count", 1)` always returns the default value 1. This means UCB's exploration bonus `c * sqrt(ln(N_i+1)/(N_j+1))` treats all nodes as equally visited. Confirmed: 01_storage H-01.
- Impact: UCB degrades to strength-only ranking. The "exploration vs exploitation" balance is broken -- frequently visited nodes get the same exploration bonus as never-visited ones.
- Recommendation: Load `visit_count` from nodes table in `build_graph()` or `_get_graph()` and set as node attribute.

### [Severity: INFO]

**E2E-14** Scenario S2 Spec Lists mode="deep" But Code Has "auto"/"focus"/"dmn"
- Scenario: S2
- Description: The scenario specification says `recall(query="rust ownership", mode="deep")` but the actual code supports `"auto"`, `"focus"`, `"dmn"` only. If `mode="deep"` were passed, `_auto_ucb_c()` would fall through to the auto logic (word-count based). No error, but spec and implementation don't match.
- Impact: None on code correctness. Spec documentation issue only.
- Recommendation: Update scenario spec to use valid mode values.

### [Severity: INFO]

**E2E-15** Scenario S2 Spec Lists RRF k=30 But Code Uses k=60
- Scenario: S2
- Description: The scenario specification says `rrf_merge(k=30)` but `config.py:22` defines `RRF_K = 60`.
- Impact: None on code correctness. Spec documentation issue only.
- Recommendation: Update scenario spec to reflect `k=60`.

## Coverage

- Scenarios traced: 10/10
- Broken paths identified: 5 (S2 partial, S4 complete, S6 degraded, S7 partial, S8 complete)
- Intact paths: 4 (S1, S3, S9, S10)
- Previously identified issues confirmed in E2E: 5
  - 01_storage H-01 -> E2E-13 (UCB visit_count not loaded)
  - 01_storage H-02 -> E2E-04 (BCM->frequency vs Bayesian nodes.frequency disconnect)
  - 02_tools H-01 -> E2E-05 (promote_node action_log missing)
  - 04_scripts M-01 -> E2E-08 (edge archive no-op)
  - 05_spec M-02 -> E2E-09 (deprecated Evidence in VALID_PROMOTIONS)

## Summary

- CRITICAL: 3
- HIGH: 3
- MEDIUM: 3
- LOW: 3
- INFO: 3

**Top 3 Most Impactful Findings:**
1. **E2E-01 (CRITICAL):** SPRT score threshold (0.5) vs RRF score range (~0.0-0.4) mismatch renders the entire SPRT promotion detection pipeline non-functional. No Signal node can ever reach promotion_candidate=1 through organic recall.
2. **E2E-02 + E2E-03 + E2E-04 (CRITICAL+CRITICAL+HIGH):** Three missing data sources (meta table, recall_log table, nodes.frequency column) cause a cascading failure across the entire promotion pipeline. Both gates in promote_node always fail. Bayesian scores in analyze_signals are always 0. The system can store and search memories but cannot learn which memories are important enough to promote.
3. **E2E-06 (HIGH):** New auto-link edges are immediately prunable because the pruning formula uses `edges.frequency` (always 0 for new edges) instead of `edges.strength` (set at creation). Daily enrichment can destroy newly created relationships before they have a chance to be reinforced by recall.

**The Promotion Pipeline is Dead:**
The v2.1 promotion system (SPRT detection -> 3-gate verification -> type promotion) has zero functional end-to-end paths. Every stage has independent blockers:
- SPRT: score range mismatch (E2E-01)
- Gate 1 SWR: missing recall_log table (E2E-03)
- Gate 2 Bayesian: missing nodes.frequency + missing meta table (E2E-04 + E2E-02)
- Audit: no action_log recording (E2E-05)

Only `skip_gates=True` (admin override) allows promotion. This effectively reduces the system to v2.0 behavior where promotion is manual-only.

**Cumulative Findings (T1-C-01 through T1-C-07):**
- CRITICAL: 3
- HIGH: 9
- MEDIUM: 19
- LOW: 16
- INFO: 46
