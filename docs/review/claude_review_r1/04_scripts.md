# Scripts Review - Round 1 (Correctness)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Correctness & Completeness
> Files Reviewed: daily_enrich.py (Phase 6), pruning.py, hub_monitor.py, calibrate_drift.py, sprt_simulate.py, eval/ab_test.py

## Findings

### [Severity: MEDIUM]

**M-01** Edge pruning "archive" decision is a no-op — spec expects `archived_at`/`probation_end` columns

- File: `scripts/daily_enrich.py:384-394` (`_run_edge_pruning`)
- Spec: `docs/ideation/d-r3-14-pruning-integration.md:176-189`
- Description:
  - Spec code: archive decision triggers `UPDATE edges SET archived_at=?, probation_end=? WHERE id=?`
  - Implementation code: archive decision has **no DB operation** — only increments `stats["archive"]`
  - Implementation comment L384: `"스키마에 archived_at 없음"` — explicitly acknowledges the schema gap
  - For "delete" decision, both spec and implementation correctly call `DELETE FROM edges WHERE id=?`
  - Result: edges marked as "archive" in stats are actually untouched in the database
  - The spec envisions 30-day edge probation with `probation_end` date, but this is not implemented
- Impact: Edge archiving with probation recovery is non-functional. Edges that should be archived (important source, weak strength) remain fully active instead. The "archive" count in stats is misleading — it counts edges that *should* have been archived but weren't.
- Recommendation: Either (a) add `archived_at` and `probation_end` columns to edges table and implement the archive logic, or (b) rename "archive" to "keep_protected" to reflect actual behavior.

---

**M-02** Phase 6-B Node Stage 2 missing `importance_score` formula from spec

- File: `scripts/daily_enrich.py:409-423` (`_run_node_stage2` SQL)
- Spec: `docs/ideation/d-r3-14-pruning-integration.md:210-233` (STAGE1_SQL)
- Description:
  - Spec SQL includes weighted importance score:
    ```sql
    (quality_score * 0.4 + obs_ratio * 0.3 + recency_score * 0.3) AS importance_score
    ORDER BY importance_score ASC
    ```
  - Implementation SQL:
    ```sql
    ORDER BY COALESCE(n.quality_score, 0) ASC
    ```
  - The spec's 3-factor score (quality + observation count + temporal recency) ensures the least-important nodes are pruned first
  - Implementation only considers quality_score, ignoring observation count and recency
  - Additionally: spec uses `n.last_activated` for 90-day check, implementation uses `n.updated_at`
- Impact: Pruning candidate ordering differs from spec. Nodes with low quality but recent activity or high observation count may be pruned before truly dormant nodes. The `updated_at` vs `last_activated` difference means any metadata update resets the 90-day clock.
- Recommendation: Add the importance_score formula to the SQL and use `last_activated` for the 90-day inactivity check.

---

**M-03** Pruning constants hardcoded — spec says config.py

- File: `scripts/daily_enrich.py:335-336` (hardcoded values)
- Spec: `docs/ideation/d-r3-14-pruning-integration.md:477` (config.py section)
- Description:
  - Implementation hardcodes in function body:
    ```python
    PRUNE_STRENGTH_THRESHOLD = 0.05
    PRUNE_MIN_CONTEXT_DIVERSITY = 2
    ```
  - Spec states these should be in config.py: `"PRUNE_STRENGTH_THRESHOLD=0.05, PRUNE_MIN_CONTEXT_DIVERSITY=2 추가"`
  - config.py has no PRUNE_* constants
  - This means changing thresholds requires modifying source code instead of configuration
- Impact: Operational inflexibility. Cannot tune pruning thresholds without code changes.
- Recommendation: Add `PRUNE_STRENGTH_THRESHOLD = 0.05` and `PRUNE_MIN_CONTEXT_DIVERSITY = 2` to config.py and import them.

---

### [Severity: LOW]

**L-01** Edge pruning queries all edges — spec filters by `archived_at IS NULL`

- File: `scripts/daily_enrich.py:340-344`
- Spec: `docs/ideation/d-r3-14-pruning-integration.md:124-129`
- Description:
  - Spec: `FROM edges WHERE archived_at IS NULL` (only active edges)
  - Implementation: `FROM edges` (all edges, no filter)
  - Since `archived_at` column doesn't exist in the schema, filtering is impossible
  - Currently all edges are active, so there's no practical difference
  - If `archived_at` is added later (per M-01 fix), this filter becomes necessary
- Impact: None currently. Future issue if edge archiving is implemented.

---

**L-02** correction_log INSERT column mismatch between daily_enrich and spec

- File: `scripts/daily_enrich.py:444-451` vs spec `d-r3-14:256-262`
- Description:
  - Spec INSERT: `..., corrected_by, event_type) VALUES (?, ..., 'system:daily_enrich', 'prune_stage2')`
  - daily_enrich.py INSERT: `..., corrected_by, created_at) VALUES (?, ..., 'system:daily_enrich', datetime('now'))`
  - Column names differ: spec uses `event_type`, implementation uses `created_at`
  - If correction_log table has `event_type`, the implementation INSERT fails; if it has `created_at`, the spec code fails
  - The actual table schema determines which is correct
- Impact: Potential INSERT failure depending on actual table schema. Pruning metadata either misses event classification (`event_type`) or timestamp (`created_at`).

---

**L-03** pruning.py duplicates Phase 6-B/C logic from daily_enrich.py

- File: `scripts/pruning.py` (196 lines) vs `scripts/daily_enrich.py:402-495`
- Description:
  - `stage1_identify_candidates()` ≈ `_run_node_stage2()` SQL (identical WHERE clause)
  - `stage2_mark_candidates()` ≈ `_run_node_stage2()` logic (check_access loop)
  - `stage3_archive_expired()` ≈ `_run_node_stage3()` (same SQL and update)
  - Both use `check_access()` identically
  - The standalone script provides `--status` mode and `--actor` parameter
  - But the core pruning logic is copy-pasted
- Impact: Maintenance burden. A change to pruning logic must be applied in two places.
- Recommendation: Extract shared pruning functions to a module (e.g., `utils/pruning.py`) and import from both.

---

### [Severity: INFO]

**I-01** daily_enrich.py Phase 6 structure matches d-r3-14

- 4-step pipeline: Edge pruning (6-A) → Node Stage 2 (6-B) → Node Stage 3 (6-C) → action_log (6-D)
- Execution order correct: edges before nodes (spec rationale: avoid orphaned edges from deleted nodes)
- dry_run parameter controls all DB writes

**I-02** Edge strength formula matches spec: `freq * exp(-0.005 * days)`

- File: `scripts/daily_enrich.py:357`
- Decay constant 0.005 matches spec
- Threshold 0.05 matches spec (both spec and implementation)
- `days = 9999` fallback for NULL last_activated — correct (forces low strength)

**I-03** Bäuml ctx_log diversity check matches spec

- File: `scripts/daily_enrich.py:365-375`
- `ctx_log` parsed from `edge["description"]` (JSON array)
- `unique_queries >= 2` → keep (contextually diverse)
- JSON parse error → `unique_queries = 0` (conservative)

**I-04** Node BSP conditions match spec

- `quality_score < 0.3 AND observation_count < 2 AND 90-day inactive AND edge_count < 3 AND layer IN (0, 1)`
- All 5 conditions present in both spec and implementation

**I-05** check_access() integration correct in both daily_enrich and pruning.py

- daily_enrich: `check_access(c["id"], "write", "system:daily_enrich", conn)` — L4/L5 + Top-10 hub protection
- pruning.py: `check_access(nid, "write", actor, conn)` — same protection with configurable actor

**I-06** hub_monitor.py matches d-r3-13 spec

- `compute_ihs()`: IHS = incoming edge count (simple but functional)
- `take_snapshot()`: hub_snapshots table with `CREATE TABLE IF NOT EXISTS` + daily UPSERT
- `hub_health_report()`: risk thresholds (HIGH>50, MEDIUM>20, LOW) — reasonable for current scale
- `recommend_hub_action()`: check_access integration — exact match with d-r3-13
- `print_hub_actions()`: access control display for HIGH-risk hubs — exact match

**I-07** calibrate_drift.py matches d-r3-12 exactly

- `measure_embedding_stability()`: same-text 2x embedding → cosine_similarity
- Threshold suggestion: `mean - 2 * stdev` — matches spec formula
- dry_run mode: skips API calls — correct
- Error handling: 3-error print limit + total error count
- Uses `embed_text()` from `embedding.openai_embed` — correct

**I-08** sprt_simulate.py SPRT formula correct

- `A = log((1-beta)/alpha)` — promote threshold (spec: ≈2.773 for default params) ✓
- `B = log(beta/(1-alpha))` — reject threshold (spec: ≈-1.558) ✓
- `llr_pos = log(p1/p0)`, `llr_neg = log((1-p1)/(1-p0))` — observation LLR ✓
- `min_obs` enforcement: decisions before min_obs are deferred ✓
- `max_obs` cap: undecided after max_obs observations ✓
- `run_forbidden_params()`: c-r3-12 Section 6 forbidden parameter simulation ✓
  - low separation (p1=0.6, p0=0.4), high alpha (0.20), min_obs=1

**I-09** eval/ab_test.py NDCG implementation correct

- DCG@k: `sum(rel_score / log2(i+2))` — standard formula ✓
- IDCG@k: ideal ordering of all relevance scores ✓
- Graded relevance: `relevant=1.0`, `also_relevant=0.5` — goldset support ✓
- RRF_K patching: `hybrid_mod.RRF_K = rrf_k` with restore in finally — correct for testing
- Difficulty breakdown (easy/medium/hard) — useful analytics
- Default comparison: k=30 vs k=60 (matching config.py RRF_K=60)

**I-10** Phase 6-D action_log record matches spec

- `action_type="archive"` — from ACTION_TAXONOMY ✓
- `actor="system:daily_enrich"` — correct prefix format ✓
- `result` JSON includes all 7 stat fields ✓
- `Exception` → `pass` — graceful degradation ✓

## Coverage

- Files reviewed: 6/14 scripts (focused on spec-critical files)
- Spec sections checked: d-r3-14 (pruning), d-r3-13 (hub_monitor), d-r3-12 (calibrate_drift), c-r3-12 (sprt_simulate), c-r3-10 (ab_test)
- Remaining 8 scripts (safety_net, export_to_obsidian, migrate_v2, migrate_v2_ontology, enrich/node_enricher, enrich/prompt_loader, enrich/graph_analyzer, dashboard) are v2.0 infrastructure with no v2.1 spec — functional review only

## Summary

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 3
- LOW: 3
- INFO: 10

**Top 3 Most Impactful Findings:**

1. **M-01** (Edge archive no-op): The edge pruning spec envisions a probation/recovery mechanism via `archived_at`/`probation_end` columns, but the implementation treats "archive" as "keep" with no DB change. Edge pruning only has two real outcomes: keep or delete. The 30-day edge probation feature from the spec is completely absent.
2. **M-02** (Missing importance_score): Node pruning candidate ordering uses only `quality_score` instead of the spec's 3-factor weighted score (quality + observations + recency). This can lead to suboptimal pruning order — recently active low-quality nodes may be pruned before truly dormant ones.
3. **M-03** (Hardcoded constants): Pruning thresholds are hardcoded in the function body instead of config.py, preventing operational tuning without code changes. Both constants are small enough that minor adjustments could significantly affect pruning behavior.

**Cross-reference with previous findings:**
- M-01 here reveals the edge schema gap — edges table lacks `archived_at` and `probation_end` columns. This is a schema-level omission that affects the entire edge lifecycle design.
- The `check_access()` integration (I-05) correctly uses the access_control module reviewed in 03_utils_ontology.md (I-01 there confirmed spec compliance).
- The SPRT parameters in sprt_simulate.py (I-08) match the SPRT implementation in storage/hybrid.py reviewed in 01_storage.md (I-01 there).
