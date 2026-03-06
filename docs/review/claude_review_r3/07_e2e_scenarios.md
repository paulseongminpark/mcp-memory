# E2E Scenarios Review - Round 3 (Operations)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Operations — Stress Testing
> Scenarios: 10 E2E paths under 10x data, concurrent load, API rate limits

## Methodology

Each of the 10 master-plan scenarios is analyzed under three stress dimensions:
- **Scale**: 10x current data (30K nodes, 60K edges) and 100x (300K/600K)
- **Concurrency**: 2-10 simultaneous MCP tool invocations
- **External failures**: OpenAI API rate limits (429), timeouts, partial outages

Findings reference issues discovered in reports 01-04.

---

## Scenario Analysis

### S1: remember() — New Memory Storage

**Normal path**: classify → store(SQLite+ChromaDB) → link(hybrid_search→insert_edge) → action_log

**Under 10x scale (30K nodes)**:
- `link()` calls `hybrid_search()` to find related nodes. Vector search scales O(n) with ChromaDB collection size. At 30K nodes with 3072-dim embeddings, search latency increases ~3x (linear scan within HNSW partitions).
- `insert_edge()` auto-creates edges for top-5 similar nodes. Edge count grows quadratically if unchecked — current 6,324 edges at 3,255 nodes → projected ~60K edges at 30K nodes.
- FTS5 index performance remains O(log n) — no concern.

**Under concurrency (5 simultaneous remembers)**:
- **[BREAKS]** C01-Storage: Connection leak in `insert_node()` — if any of 5 calls fails mid-transaction, leaked connections block subsequent writers.
- **[BREAKS]** C01-Tools: No idempotency — MCP transport retry creates duplicate nodes. 5 concurrent remembers with identical content = 5 duplicate nodes + 25 duplicate edges.
- **[BREAKS]** C02-Tools: Partial failure — `store()` succeeds but `link()` fails = node in SQLite but edges missing. No rollback mechanism.
- SQLite WAL mode supports concurrent reads, but writes serialize. 5 concurrent `insert_node()` calls queue behind `busy_timeout=30s`. First 4 complete; 5th may timeout.

**Under API failure**:
- **[BREAKS]** H03-Storage: OpenAI embedding API failure during `store()` → `vector_store.add()` fails → node exists in SQLite but NOT in ChromaDB → node invisible to future vector searches permanently.
- No retry on embedding failure. No fallback (e.g., skip embedding, store with flag).

**Stress verdict**: FRAGILE. Concurrent remembers + API instability = data corruption (duplicates, orphaned nodes, missing embeddings).

---

### S2: recall() — Deep Mode Search

**Normal path**: hybrid_search(vec+FTS5+graph) → RRF merge → BCM update → UCB arm update → SPRT check → format results

**Under 10x scale**:
- Vector search: O(n) at 30K nodes → ~200-400ms (up from ~50-100ms). Acceptable.
- FTS5: O(log n) — negligible impact.
- Graph traversal CTE: **[BREAKS]** M06-Storage: `WHERE id NOT IN (...)` with seed_ids repeated 3x. At 100+ seeds → 300+ placeholders → approaches `SQLITE_MAX_VARIABLE_NUMBER` (999). At 333+ seeds → query failure.
- Graph cache rebuild: `get_all_edges()` loads ALL 60K edges into memory → NetworkX DiGraph build takes ~2-5 seconds (up from ~0.5s).
- BCM update: N+1 queries per result node (M01-Storage). 20 results × 3 edges avg = 60 extra queries. At 30K scale, each query is slightly slower.
- **Total latency**: ~1-2 seconds at 10x (up from ~0.3-0.5s). Still operational.

**Under 100x scale (300K nodes)**:
- Vector search: ~2-4 seconds. ChromaDB HNSW may need segment-level optimization.
- Graph cache: 600K edges → build time ~30+ seconds. Cache TTL expiry during a recall → 30s hang.
- **[BREAKS]** H01-Tools: No timeout. A single recall could block MCP server for 30+ seconds during graph rebuild.

**Under concurrency (100 concurrent recalls)**:
- **[BREAKS]** C02-Storage: Graph cache race. Two coroutines detect stale cache → both rebuild → inconsistent DiGraph state during iteration.
- **[BREAKS]** C03-Storage: BCM lost updates. 100 recalls updating same popular nodes → read-modify-write race → theta_m values randomly overwritten.
- **[BREAKS]** H03-Tools: `_increment_recall_count()` connection leak. 100 concurrent calls → if `meta` table has any issue → 100 leaked connections → system freeze.

**Under API failure**:
- OpenAI embedding required for vector arm. API failure → `embed_text()` throws RuntimeError → entire recall fails. No fallback to FTS-only mode.

**Patch saturation (H02-Tools)**:
- If >75% results from same project → second `hybrid_search()` triggered → latency doubles. At 10x scale with 2-second base latency → 4 seconds. At 100x → 60+ seconds (graph rebuild × 2).

**Stress verdict**: CRITICAL. 100 concurrent recalls = BCM corruption + cache race + potential 30-60s hangs. No graceful degradation.

---

### S3: recall() — Edge Cases

**Empty query `recall("")`**:
- `embed_text("")` → OpenAI API returns a valid embedding (zero-ish vector) → cosine similarity with everything → returns essentially random nodes. Not an error, but misleading results.
- FTS5 `MATCH ""` → may throw `OperationalError` depending on SQLite version. No explicit handling.

**Single char `recall("가")`**:
- FTS5 handles Korean characters but may not find meaningful matches. Vector embedding of single character is valid but low quality.

**Very long `recall("가" * 1000)` (3000 bytes)**:
- **[RISK]** OpenAI `text-embedding-3-large` has 8191 token limit. 1000 Korean characters ≈ 500-1000 tokens → within limit. But `"가" * 10000` (30KB) would hit token limit → API error → recall fails completely.
- No input length validation exists in `recall()`.
- FTS5 query with 3000 bytes is valid but performance degrades with very long match strings.

**Unicode/special chars**:
- SQL parameterization prevents injection. SQLite handles UTF-8 natively.
- FTS5 tokenizer: default `unicode61` handles Korean. But special chars like `"`, `'`, `*`, `AND`, `OR`, `NOT` are FTS5 operators → may change query semantics unexpectedly. No FTS5 input sanitization found.

**Stress verdict**: MEDIUM. Empty/short queries return noisy results (not crash). Very long queries risk API token limits. FTS5 special chars are a silent correctness issue.

---

### S4: promote_node() — 3-Gate Pass

**Normal path**: get_node → Gate 1 (SWR readiness) → Gate 2 (Bayesian posterior) → Gate 3 (MDL cosine sim) → update_node → create realized_as edges

**Under 10x scale**:
- Gate 1 (SWR): Queries `action_log` for recall history. At 10x recalls (100K+ action_log entries), unindexed queries become slow. `action_log` has no index on `(action_type, timestamp)`.
- Gate 2 (Bayesian): Uses `total_recall_count` from `meta` table → O(1). No scale concern.
- Gate 3 (MDL): `vector_store._get_collection().get(ids=related_ids)` → ChromaDB batch get. At 100+ related_ids, ChromaDB performance is fine.
- **[BREAKS]** C03-Tools: Connection leak in mutation path (lines 258-281). If `conn.execute(UPDATE)` throws → connection never closed. Repeated promotions with transient DB errors → connection exhaustion.

**Under concurrency (2 concurrent promotes of same node)**:
- Both read current type/layer → both compute gates → both succeed → both write UPDATE. Second write overwrites first, but since they're promoting to the same target, the result is correct (idempotent by accident).
- Edge creation: Both create `realized_as` edges → duplicate edges. No unique constraint on (source_id, target_id, relation_type).

**Under API failure**:
- Gate 3 (MDL) uses embeddings from ChromaDB (local). No external API dependency in promotion path itself. HOWEVER, if embeddings were never stored (due to earlier remember() failure per S1), Gate 3 skips with `"MDL: skipped (insufficient embeddings)"` → easier promotion → potential false promotion.

**Stress verdict**: MEDIUM. Connection leak is the primary risk. Duplicate promotions create duplicate edges but don't corrupt data.

---

### S5: promote_node() — Gate Failures

**Gate 1 fail (SWR readiness < 0.55)**:
- Returns clear failure message with actual readiness score. No side effects. Clean.

**Gate 2 fail (Bayesian posterior < 0.5)**:
- Returns failure with actual posterior value. No side effects. Clean.
- **[ISSUE]** H04-Storage: SPRT `promotion_candidate` flag is NOT reset on gate failure. Node remains `promotion_candidate=1` after failed promotion attempt → `analyze_signals()` keeps recommending it → Claude keeps trying → infinite failed-promotion loop.

**Gate 3 fail (MDL avg_sim < 0.75)**:
- Returns failure with actual similarity. No side effects for the node.
- BUT: If `skip_gates=True` was not used and the user retries with `skip_gates=True`, all gates are bypassed → problematic nodes get promoted without validation.

**Scale concern**: With 30K nodes, more nodes hit SPRT candidate threshold → more promotion attempts → more gate failures → more `promotion_candidate=1` flags stuck on → `analyze_signals()` returns increasingly noisy recommendations.

**Stress verdict**: LOW direct risk, but MEDIUM indirect risk from promotion_candidate flag accumulation.

---

### S6: analyze_signals()

**Normal path**: Query promotion_candidate=1 nodes → cluster by key_concepts → pairwise similarity → Bayesian cluster score → recommendations

**Under 10x scale (300 Signal nodes)**:
- **[BREAKS]** M01-Tools: O(n²) pairwise comparison. 300 signals → 44,850 comparisons. With set intersection per pair, ~1-2 seconds.
- At 1000 signals → 499,500 comparisons → ~10-20 seconds.
- At 5000 signals → ~12.5M comparisons → multi-minute. Combined with H01-Tools (no timeout) → MCP server hangs.

**Under concurrency**:
- M02-Tools: Connection leak in `analyze_signals()`. Two concurrent calls → if SQL fails → 2 leaked connections.
- Read-only analysis — no data corruption risk from concurrent calls.

**Under API failure**:
- No external API calls. Pure DB + Python computation. Resilient.

**Stress verdict**: HIGH at scale due to O(n²) clustering. No timeout protection → MCP server hang at ~1000+ signals.

---

### S7: daily_enrich Phase 6

**Normal path**: Edge pruning (6-A) → Node BSP (6-B) → 30-day archive (6-C) → action_log (6-D)

**Under 10x scale (60K edges)**:
- **[BREAKS]** M02-Scripts: `fetchall()` loads ALL 60K edges into memory. At 100 bytes/edge metadata → ~6MB. Manageable but inefficient.
- **[BREAKS]** C01-Scripts: `last_activated=NULL → days=9999 → strength≈0`. ALL pre-tracking edges (potentially 50%+ of edges) marked for deletion in a single run.
- Strength calculation loop: 60K iterations × exp() + JSON parse per edge → ~5-10 seconds. Acceptable.
- Phase 6-B node pruning: Queries with multiple conditions. Without indexes on `(quality_score, layer, updated_at)`, full table scan on 30K nodes → ~1-2 seconds.

**Under concurrency (cron + manual overlap)**:
- **[BREAKS]** H03-Scripts: No lock file or advisory lock. Two instances run simultaneously → both query same unenriched nodes → double API spend + both try to delete same edges → FK violations or double-delete.

**Under API failure**:
- Phase 6 itself makes no API calls (pure DB operations). But if enrichment phases 1-5 fail mid-run:
  - **[BREAKS]** C02-Scripts: No checkpoint. Budget consumed but `budget.save_log()` only runs at end. Restart re-runs all phases.
  - Token budget for completed phases is LOST and will be re-spent.

**Stress verdict**: CRITICAL. C01-Scripts (mass edge deletion) is the highest blast-radius finding. A single `--execute` run without safeguards could destroy thousands of edges.

---

### S8: remember → recall × N → SPRT → promote (Full Pipeline)

**Full lifecycle test under stress**:

1. **remember()** creates node X → works but may create duplicates (C01-Tools)
2. **recall() × N** where node X appears → SPRT LLR accumulates
   - Each recall updates theta_m (BCM) and visit_count (UCB) for node X
   - Under concurrency: BCM updates lost (C03-Storage) → theta_m incorrect → node X may be ranked too high or too low in future recalls
   - SPRT LLR accumulation: `log(P(d|P1)/P(d|P0))` per recall. If BCM is corrupted, the "hit" signal for X may be wrong → SPRT reaches wrong conclusion
3. **LLR > A=2.773** → `promotion_candidate=1`
   - **[ISSUE]** This is a one-way flag (H04-Storage). Even if subsequent recalls show X is noise (LLR should decrease), the flag persists.
4. **promote_node(X, "Pattern")** → 3-gate execution
   - Gate 1 (SWR) depends on action_log data → if action_log records were silently lost (H02-Storage `except Exception: pass`) → SWR readiness calculated from incomplete data
   - Gate 3 (MDL) depends on embeddings → if X's embedding was lost during remember (S1 API failure scenario) → Gate 3 skips → easier promotion

**Cascade failure scenario**:
```
remember(X) → embedding API fails → X has no vector embedding
→ recall("related") → X never appears in vector results (no embedding)
→ X only appears via FTS5 → fewer hits → SPRT never triggers
→ X permanently stuck as un-promotable
```

Alternatively:
```
remember(X) × 3 (MCP retries) → 3 duplicate nodes X₁, X₂, X₃
→ recall() hits X₁ → SPRT LLR for X₁ grows
→ recall() hits X₂ → SPRT LLR for X₂ grows
→ Neither X₁ nor X₂ reaches threshold (split signal)
→ Both become low-confidence noise → pruning candidates
→ Valid knowledge permanently lost
```

**Stress verdict**: CRITICAL. The full pipeline has compounding failure modes. Duplicate nodes split SPRT signals. Missing embeddings permanently block promotion. BCM corruption feeds wrong data to SPRT.

---

### S9: hub_monitor

**Normal path**: compute_ihs() → snapshot → recommend_hub_action()

**Under 10x scale**:
- IHS counts incoming edges per node. At 60K edges, `SELECT COUNT(*) FROM edges WHERE target_id = ?` per node → 30K queries without index on `target_id`.
- **[BREAKS]** H04-Scripts: Only counts incoming edges. Gateway hubs (high outgoing) are invisible. At 10x scale with more organizing nodes (Project, Workflow), these become significant.
- **[BREAKS]** H05-Scripts: Hard-coded thresholds (>50=HIGH, >20=MEDIUM). At 10x scale, top nodes naturally exceed 50 → constant false HIGH alerts → alert fatigue.

**Under concurrency**:
- Read-only analysis. No data corruption risk. Multiple concurrent runs waste CPU but are safe.

**Hub protection dependency**:
- **[BREAKS]** H05-Utils: `hub_snapshots` table created on-the-fly (M05-Scripts). If hub_monitor has NEVER been run, the table doesn't exist → `access_control._get_top10_hub_ids()` catches exception → returns empty set → hub protection disabled → critical hub nodes can be pruned/deleted without warning.

**Stress verdict**: MEDIUM. Incorrect hub detection at scale + disabled protection on fresh installs.

---

### S10: save_session → get_context

**Normal path**: save_session(UPSERT) → get_context(SELECT recent)

**Under 10x scale**:
- Sessions table grows linearly. `get_context()` queries `ORDER BY created_at DESC LIMIT 3` → needs index on `created_at`. Without it, full table scan at 10K sessions.

**Under concurrency**:
- save_session uses UPSERT (I02-Tools) → idempotent. Safe under retry.
- **[ISSUE]** H04-Tools: Connection leak if `conn.execute()` throws during save_session. But UPSERT is unlikely to fail under normal conditions.
- get_context is read-only. Multiple concurrent calls are safe.

**Under API failure**:
- No external API calls. Pure DB operations. Fully resilient.

**Stress verdict**: LOW. The most operationally robust scenario. UPSERT provides idempotency. No API dependency.

---

## Cross-Scenario Compound Failures

### CF1: Enrichment + Recall Collision
```
Timeline:
T+0:  daily_enrich starts Phase 1 (CONCURRENT_WORKERS=10 API calls)
T+1s: User triggers recall() → hybrid_search → embedding API call
T+2s: OpenAI rate limit (429) → enrichment's node_enricher retries (I02-Scripts)
T+3s: recall()'s embed_text() also gets 429 → NO retry → RuntimeError → recall fails
```
Impact: Enrichment pipeline's retry logic consumes the API quota, leaving MCP tools with zero resilience (H03-Storage).

### CF2: Pruning + Recall Race
```
Timeline:
T+0:  daily_enrich Phase 6 starts edge pruning
T+1s: Prune deletes edge (A→B) with strength < 0.05
T+2s: User recall() → graph traversal finds A → traverses to B via cached edge → gets B
T+3s: Graph cache refreshes → edge A→B gone → B no longer reachable via graph
```
Impact: Recall results become inconsistent during pruning windows. Cached graph shows edges that no longer exist.

### CF3: Remember Duplicate + Promote Split
```
Timeline:
T+0:  remember("X") → node X₁ created (network timeout before response)
T+1s: MCP retry → remember("X") → node X₂ created (duplicate)
T+N:  recall() returns X₁ sometimes, X₂ sometimes → SPRT LLR split
T+M:  Neither reaches promotion threshold
T+M+90: Both pruned as low-activity nodes (H01-Scripts: updated_at not refreshed by recall)
```
Impact: Valuable knowledge permanently lost through duplication → split signal → pruning.

---

## Coverage

- Scenarios traced: 10/10
- Stress dimensions: 3/3 (scale, concurrency, API failure)
- Compound failures identified: 3

## Summary

- CRITICAL scenarios (system breaks): S1, S2, S7, S8
- HIGH risk scenarios: S6
- MEDIUM risk scenarios: S3, S4, S5, S9
- LOW risk scenarios: S10

**Top 3 Most Dangerous Stress Paths:**

1. **S8 (Full Pipeline) under concurrency** — Duplicate nodes split SPRT signals, BCM corruption feeds wrong data to promotion gates, missing embeddings permanently block promotion. The entire knowledge lifecycle degrades silently.

2. **S7 (daily_enrich Phase 6) at scale** — Mass edge deletion of pre-tracking edges (`last_activated=NULL → strength=0`). A single unguarded `--execute` run could destroy thousands of legitimate connections. No undo mechanism.

3. **S2 (recall) under 100 concurrent calls** — Graph cache race condition + BCM lost updates + connection leak cascade. At 100x scale, graph rebuild takes 30+ seconds with no timeout → MCP server frozen.

**Key Insight**: The system was designed for single-user, low-frequency operation. Its failure modes emerge specifically under the conditions that production use introduces: concurrent sessions, API instability, and data growth. The most dangerous pattern is **silent degradation** — data quality drops (BCM corruption, SPRT signal splitting, edge pruning) without any visible error, making diagnosis extremely difficult.
