# Scripts Review - Round 3 (Operations)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Operations
> Files Reviewed: scripts/pruning.py, scripts/hub_monitor.py, scripts/daily_enrich.py, scripts/safety_net.py, scripts/calibrate_drift.py, scripts/enrich/node_enricher.py, scripts/enrich/prompt_loader.py, scripts/migrate_v2.py, scripts/sprt_simulate.py

## Findings

### [Severity: CRITICAL]

**[C01] Edge Pruning Destroys Pre-Tracking Edges — last_activated=NULL → strength=0**
- File: `scripts/daily_enrich.py:349-357`
- Description: Edge strength formula: `freq * exp(-0.005 * days)`. When `last_activated` is NULL, `days=9999` → `exp(-0.005 * 9999) ≈ 0` → strength ≈ 0 regardless of frequency. ALL edges created before `last_activated` tracking was implemented have NULL `last_activated`. These edges are immediately marked for deletion.
  ```python
  days = (
      (now_utc - datetime.fromisoformat(last_act)).days
      if last_act else 9999  # ← NULL → 9999 days → strength ≈ 0
  )
  strength = freq * math.exp(-0.005 * days)
  ```
  The Bauml diversity check parses `description` as JSON ctx_log (line 366). But most auto-generated edges have plain text descriptions like `"auto: similarity=0.85"` → `json.loads()` fails → `JSONDecodeError` → `unique_queries=0` → diversity check SKIPPED → edge goes to tier/layer decision.
- Impact: Running `daily_enrich.py --phase 6` on the current DB (~6,300 edges) would delete ALL pre-tracking edges in L0/L1 with non-core sources. This could destroy thousands of edges in a single run. The dry-run mode would show the damage but `--execute` has no confirmation step.
- Recommendation: (a) Add `AND last_activated IS NOT NULL` to edge query or use `COALESCE(last_activated, created_at)` as fallback. (b) Add a safety cap: max edges deletable per run (e.g., 10% of total). (c) Require explicit `--confirm-delete N` flag when more than N edges will be deleted.

**[C02] No Enrichment Pipeline Resume — Crash Loses Progress + Budget**
- File: `scripts/daily_enrich.py:568-643`
- Description: The pipeline runs 7 phases sequentially with a single connection. If the process crashes at Phase 4:
  - Phases 1-3 completed work is partially persisted (enrichment_status per node is saved)
  - Token budget consumed by Phases 1-3 is LOST — `budget.save_log()` only runs at line 638 (end of main)
  - Restarting runs all phases again: Phase 1 skips already-enriched nodes (good), but sub-tasks like E7/E13/E14/E16/E17 use different status checks and may re-run, consuming budget again
  - No progress checkpoint file, no resume from specific phase without `--phase N`
- Impact: In a real scenario: run Phase 1-3 consuming $2 API budget → crash → restart → E14 re-runs 6000 edges → another $1+ spent. No way to know what was already spent without manually checking token_log.
- Recommendation: (a) Save `budget.save_log()` after EACH phase, not just at the end. (b) Create a checkpoint file (`data/enrich_checkpoint.json`) recording last completed phase + budget state. (c) `--resume` flag to continue from checkpoint.

### [Severity: HIGH]

**[H01] Node Pruning Uses updated_at — Not Refreshed by Recall**
- File: `scripts/pruning.py:45`, `scripts/daily_enrich.py:419`
- Description: Pruning condition includes `n.updated_at < datetime('now', '-90 days')`. But `updated_at` is only set by explicit node modifications (content change, metadata update, status change). The `recall()` function does NOT update `updated_at`. A node recalled 50 times in the last month but never modified appears as "90 days inactive."
- Impact: Actively used nodes get flagged as pruning candidates. The access_control + low quality_score + low edge_count conditions partially mitigate this, but the `updated_at` criterion is fundamentally wrong for measuring "activity."
- Recommendation: Either: (a) Use `frequency` as an additional activity signal (frequency > 5 → skip pruning), or (b) Add a `last_recalled_at` timestamp updated by recall(), or (c) Replace `updated_at` with `COALESCE(last_activated, updated_at, created_at)` using the edges' activation timestamps as a proxy.

**[H02] Edge "Archive" Decision Has No Effect — Misleading Stats**
- File: `scripts/daily_enrich.py:386-394`
- Description: When an edge's source has `tier=0` or `layer>=2`, the decision is `"archive"`. But there is NO archive operation for edges — the code only executes `DELETE` for `decision=="delete"` (line 392). "Archive" edges are simply kept in place with no status change. Yet the stats report `"archive": N` counts, implying archival happened.
  ```python
  if not dry_run:
      if decision == "delete":
          conn.execute("DELETE FROM edges WHERE id=?", (edge_id,))
  stats[decision] += 1  # "archive" incremented but nothing archived
  ```
- Impact: Operators see "archive=500" in reports and think 500 edges were safely archived. In reality, they remain active. No edge archival mechanism exists in the schema (no `status` column on edges table).
- Recommendation: Either: (a) Add `status` column to edges table and set to 'archived', or (b) Rename the decision to "keep_protected" to accurately describe the behavior.

**[H03] No Concurrent Execution Protection — Double-Run Corruption**
- File: `scripts/daily_enrich.py:568-643`
- Description: No PID file, flock, or advisory lock. If two instances of daily_enrich run simultaneously (e.g., cron overlap, manual + scheduled):
  - Both query the same unenriched nodes → both enrich them → double API spend
  - Both run Phase 6 pruning → both try to delete same edges → potential FK violations
  - Single connection with WAL + busy_timeout=5000ms provides some protection, but 5 seconds is often not enough for heavy writes
- Impact: Task Scheduler runs at 08:00 KST. User manually starts a run at 08:01. Both run against the same DB, doubling API costs and potentially corrupting pruning state.
- Recommendation: Use a lock file (`data/enrich.lock`) with PID check. Or use SQLite advisory lock via `BEGIN EXCLUSIVE TRANSACTION` at pipeline start.

**[H04] Hub Monitor IHS Counts Only Incoming Edges — Incomplete Hub Detection**
- File: `scripts/hub_monitor.py:36-45`
- Description: `compute_ihs()` counts only incoming edges (`e.target_id = n.id`). Outgoing edges are ignored. A node referencing 100 other nodes (high outgoing) but referenced by 0 nodes (zero incoming) has IHS=0 and is never identified as a hub.
- Impact: "Authority" hubs (referenced by many) are detected, but "gateway" hubs (connecting to many) are missed. Deleting a gateway hub could fragment the graph without any warning. In the current graph structure, connect_with/part_of edges create many outgoing connections from organizing nodes (Project, Workflow).
- Recommendation: Add outgoing edge count or total edge count as an alternative metric. Consider PageRank or betweenness centrality for more accurate hub detection.

**[H05] Hub Risk Thresholds Not Adaptive — Will Misfire at Scale**
- File: `scripts/hub_monitor.py:93-98`
- Description: Hard-coded thresholds: `>50 = HIGH`, `>20 = MEDIUM`. With current ~6000 edges across ~3000 nodes (avg 2 incoming/node), these thresholds are reasonable. But at 30K nodes / 100K edges (avg 3.3 incoming), the top nodes could easily exceed 50 naturally, generating false HIGH alerts constantly.
- Impact: At 10x scale, hub_monitor produces excessive HIGH alerts, causing alert fatigue. Operators start ignoring the reports, defeating the purpose.
- Recommendation: Use percentile-based thresholds (e.g., top 1% = HIGH, top 5% = MEDIUM). Or compute threshold as `mean + 3*stdev` of IHS distribution.

### [Severity: MEDIUM]

**[M01] Pruning Code Duplicated Between pruning.py and daily_enrich.py**
- File: `scripts/pruning.py:31-53` vs `scripts/daily_enrich.py:409-425`
- Description: Nearly identical SQL for Stage 1/2/3 candidate identification exists in both files. `pruning.py` is standalone, `daily_enrich.py` Phase 6-B/C reimplements the same logic. A bug fix in one is easily missed in the other.
- Impact: Maintenance risk. The two could diverge silently: e.g., if LIMIT is changed in pruning.py but not in daily_enrich.py.
- Recommendation: Extract shared pruning functions to a common module (e.g., `scripts/pruning_core.py`) imported by both.

**[M02] Edge Pruning Loads ALL Edges Into Memory**
- File: `scripts/daily_enrich.py:340-344`
- Description: `conn.execute("SELECT ... FROM edges").fetchall()` loads all edges. With 6300 edges currently, this is fine. At 100K+ edges, this is a significant memory load and slow query.
- Impact: At scale, Phase 6-A becomes the bottleneck. Memory usage proportional to edge count.
- Recommendation: Use cursor-based iteration (`for edge in conn.execute(...)`) instead of `fetchall()`. Or add batch processing with LIMIT/OFFSET.

**[M03] calibrate_drift.py No Rate Limiting on Embedding API**
- File: `scripts/calibrate_drift.py:88-93`
- Description: Calls `embed_text()` twice per sample in a tight loop. Default 50 samples = 100 API calls with no sleep. OpenAI rate limits for text-embedding-3-large are generous but not infinite.
- Impact: With `--n 500` (1000 API calls), could hit rate limits and fail mid-calibration. No retry logic. Partial results lost.
- Recommendation: Add `time.sleep(0.1)` between samples or use batch embedding API.

**[M04] safety_net.py and calibrate_drift.py Use Independent DB_PATH**
- File: `scripts/safety_net.py:17`, `scripts/calibrate_drift.py:30`
- Description: Both compute `DB_PATH = Path(__file__).parent.parent / "data" / "memory.db"` instead of importing from `config.py`. Same divergence risk identified in 03_utils_ontology.md H03.
- Impact: If config.DB_PATH or project structure changes, these scripts silently point to wrong DB.
- Recommendation: Import from `config.py`.

**[M05] hub_snapshots Table Created On-The-Fly — No Migration**
- File: `scripts/hub_monitor.py:61-64`
- Description: `CREATE TABLE IF NOT EXISTS hub_snapshots` runs each time `take_snapshot()` is called. Table schema has no indexes, no foreign keys, no constraints beyond column types. Not part of init_db() or any migration script.
- Impact: If hub_monitor has never been run, the table doesn't exist → `access_control._get_top10_hub_ids()` fails silently → hub protection disabled (see 03_utils_ontology.md H05). The on-the-fly creation also means schema changes require no migration path — just change the code and restart.
- Recommendation: Add hub_snapshots to init_db() in sqlite_store.py. Add index on `(snapshot_date, ihs_score)`.

**[M06] NodeEnricher API Calls Have No Timeout**
- File: `scripts/enrich/node_enricher.py:108-137`
- Description: `_call_json()` has retry logic for RateLimitError and APIError, but no per-call timeout. Both `openai.OpenAI().chat.completions.create()` and `anthropic.Anthropic().messages.create()` use default timeouts (which may be 10+ minutes).
- Impact: A single hung API call blocks the entire enrichment pipeline. With 7 phases × hundreds of nodes, one hang freezes the process indefinitely. Combined with H03 (no concurrent execution protection), a hung process may prevent the next scheduled run.
- Recommendation: Add `timeout=60` to API client initialization or per-request.

### [Severity: LOW]

**[L01] migrate_v2.py Backup Not Verified**
- File: `scripts/migrate_v2.py:51-59`
- Description: `backup_db()` copies the DB file using `shutil.copy2()`. No checksum verification, no test restore, no integrity check on the backup.
- Impact: If copy fails silently (disk full, permission error), migration proceeds without a valid backup. Recovery impossible.
- Recommendation: Add `conn.execute("PRAGMA integrity_check")` on the backup file after copy.

**[L02] PromptLoader Silent Failure on YAML Parse Error**
- File: `scripts/enrich/prompt_loader.py:28-33`
- Description: `_load_all()` catches all exceptions during YAML loading with `except Exception: continue`. If a prompt file has a syntax error, it's silently skipped. The enrichment task using that prompt will fail later with `KeyError("Prompt not found: E4")` — far from the root cause.
- Impact: Debugging prompt issues is harder because the real error (YAML syntax) is swallowed, and the user sees a misleading error (prompt not found).
- Recommendation: Log the exception with filename: `print(f"Warning: Failed to load {f.name}: {e}")`.

**[L03] daily_enrich.py Phase 6 action_log Failure Silent**
- File: `scripts/daily_enrich.py:517-518`
- Description: `_log_pruning_action()` wraps action_log.record() in `except Exception: pass`. If the action_log recording fails, pruning results are not auditable.
- Impact: Pruning actions (edge deletion, node archival) happen without audit trail. For compliance and rollback purposes, this is problematic.
- Recommendation: At minimum, log to stderr on failure. Consider making action_log a prerequisite for pruning execution.

**[L04] sprt_simulate.py Pure Simulation — No Operational Risk**
- File: `scripts/sprt_simulate.py`
- Description: No DB access, no API calls, no side effects. Pure Monte Carlo simulation. Well-designed for parameter exploration.
- Impact: None (positive).

### [Severity: INFO]

**[I01] daily_enrich.py Has Proper Consecutive Failure Circuit Breaker**
- File: `scripts/daily_enrich.py:606-633`
- Description: `MAX_CONSECUTIVE_FAILURES = 3` — three consecutive phase failures → pipeline stops. This prevents runaway error accumulation. BudgetExhausted triggers immediate stop (line 626). Each successful phase resets the counter (line 621).
- Impact: Positive. Good operational resilience pattern.

**[I02] NodeEnricher Has Retry + Rate Limit Handling**
- File: `scripts/enrich/node_enricher.py:106-156`
- Description: `_call_json()` implements: budget check → rate limiter wait → API call → RateLimitError retry (with retry-after header) → APIError retry (exponential backoff) → budget recording. This is the ONLY code in the entire codebase with proper API retry logic.
- Impact: Positive. Model for storage layer and tools layer API calls.

**[I03] Pruning Uses Access Control — L4/L5 + Hub Protection**
- File: `scripts/pruning.py:70`, `scripts/daily_enrich.py:432`
- Description: Both pruning implementations call `check_access(nid, "write", actor, conn)` before marking candidates. L4/L5 nodes and Top-10 hubs are automatically protected.
- Impact: Positive. Core values and hub nodes cannot be accidentally pruned.

**[I04] Enrichment Status Tracking Enables Idempotent Re-Runs**
- File: `scripts/enrich/node_enricher.py` (enrichment_status pattern)
- Description: Each enrichment task (E1-E12) is tracked in the node's `enrichment_status` JSON field. Re-running the pipeline skips already-completed tasks. Individual phases query `enrichment_status NOT LIKE '%"E7"%'` to filter.
- Impact: Positive. Safe to re-run after partial failure (except for budget loss — see C02).

## Coverage

- Files reviewed: 9/14 key scripts (focused on operational-critical)
- Functions verified: 28/28 in reviewed files
- Key Checks: 4/4 (pruning false positive, hub accuracy, enrichment recovery, scheduling)
- Skipped (low operational impact): graph_analyzer.py, relation_extractor.py, export_to_obsidian.py, dashboard.py, migrate_v2_ontology.py

## Summary

- CRITICAL: 2
- HIGH: 5
- MEDIUM: 6
- LOW: 4
- INFO: 4

**Top 3 Most Impactful Findings:**

1. **[C01] Edge pruning destroys pre-tracking edges** — The `last_activated=NULL → days=9999 → strength=0` formula would delete ALL edges created before activation tracking. With ~6,300 current edges, a single `--execute` run could destroy thousands of legitimate connections. This is the highest blast-radius finding in the entire scripts layer.

2. **[C02] No enrichment pipeline resume** — Token budget (potentially $2-4 per run) is not checkpointed. A crash mid-pipeline loses progress and wastes budget on re-runs. For a daily-scheduled operation, this creates cumulative cost waste.

3. **[H01] Pruning uses updated_at instead of recall activity** — Actively recalled nodes appear "inactive" because recall doesn't update `updated_at`. Combined with C01, this creates a double-jeopardy: edges to frequently-used nodes are pruned (C01), AND the nodes themselves are marked as pruning candidates (H01).

**Cross-Reference with Previous Reports:**
- C01 (edge pruning NULL handling) exploits the same gap as 01_storage.md C01 (connection leak on insert_edge) — edges created through leaked connections may have inconsistent `last_activated` values.
- H03 (no concurrent execution protection) compounds with 01_storage.md H01 (WAL concurrent write limitations). Two enrichment instances fighting for WAL locks → busy_timeout failures.
- M06 (no API timeout in enrichment) is the same class of issue as 02_tools.md H01 (no timeout on any tool). The enrichment pipeline at least has retry logic (I02), unlike the tools layer.
