# End-To-End Stress Scenarios - Round 3 (Operations)

> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Operational Reality
> Baseline: 3,299 nodes / 6,329 edges / 26.01 MB DB / 3,206 action_log rows

## Measured Baseline

- `SELECT * FROM edges`: 32.38 ms on the live DB
- NetworkX graph build from all 6,329 edges: 9.92 ms
- Full edge-load plus graph-build cache miss: about 42.30 ms before scoring and formatting
- Max live node degree: 64

## Scenario 1: 10x Data (about 32K nodes)

### [Severity: HIGH]

**H01** Cache-miss recall latency becomes visible first
- File: `storage/hybrid.py:31-44`, `storage/sqlite_store.py:347-351`, `graph/traversal.py:11-21`
- Projection: if edge count grows roughly with nodes, cache-miss graph prep alone moves from about 42 ms to the low hundreds of milliseconds.
- Break mode: cold starts, worker restarts, and TTL expiry become user-visible latency spikes.

**H02** Read-oriented N+1 tools age badly
- File: `tools/get_becoming.py:44-50`, `tools/inspect_node.py:25-53`
- Projection: high-degree nodes and larger result sets turn these tools into multi-query walks rather than bounded reads.

## Scenario 2: 100 Concurrent Recall Calls

### [Severity: CRITICAL]

**C01** Recall flood hits three bottlenecks at once: embeddings, SQLite writes, and log amplification
- File: `storage/vector_store.py:39-56`, `tools/recall.py:25-78`, `storage/hybrid.py:467-495`
- Behavior: each recall can issue an embedding request for vector search, write score-history state, and log one recall plus up to ten node activations.
- Break mode: API quota pressure, serialized writer contention, and a fast-growing `action_log` table.

**C02** Global graph cache is not synchronized
- File: `storage/hybrid.py:26-44`
- Behavior: concurrent cache refresh on restart or TTL expiry can trigger duplicated graph builds and inconsistent read costs.
- Break mode: noisy latency and wasted CPU under burst traffic.

## Scenario 3: Embedding API Rate Limits Or Partial Outage

### [Severity: HIGH]

**H03** Recall degrades functionally, but not predictably
- File: `storage/hybrid.py:406-414`, `embedding/openai_embed.py:17-31`
- Behavior: vector failures are caught and the system can fall back to FTS plus graph. The problem is that there is no explicit request deadline, so the fallback may happen only after an upstream timeout.
- Break mode: users see slow recalls rather than clean and fast degradation.

**H04** Batch enrichment can oversubscribe budget and rate limits under parallel workers
- File: `scripts/enrich/node_enricher.py:483-510`, `scripts/enrich/relation_extractor.py:630-657`, `scripts/enrich/token_counter.py:148-186`
- Behavior: `TokenBudget` and `RateLimiter` are shared across threads but have no locking.
- Break mode: multiple workers can all decide there is budget left, or all miss a recent 429 backoff update.

## Scenario 4: DB File Reaches 1 GB

### [Severity: HIGH]

**H05** Maintenance cost grows faster than query cost
- File: `storage/sqlite_store.py:134-224`, `scripts/dashboard.py:28-117`, `scripts/serve_dashboard.py:21-106`
- Behavior: FTS and indexed point reads will likely stay usable, but backup time, cold copy time, dashboard generation, and full-table operational scripts get much heavier.
- Break mode: ops windows get longer, dashboards get slower, and ad hoc recovery becomes painful.

**H06** File shrink will not happen automatically after cleanup
- File: `config.py:96-98`
- Behavior: there is no runtime `VACUUM`, and live `auto_vacuum=0`.
- Break mode: even successful pruning or merge cleanup does not give disk space back.

## Scenario 5: Restart After Failure

### [Severity: MEDIUM]

**M01** Restart does not self-heal schema drift
- File: `storage/sqlite_store.py:21-226`, `server.py:341-342`
- Behavior: `init_db()` creates missing tables but does not repair existing tables that are missing expected columns.
- Break mode: the same production defects survive every restart.

## What Breaks First

1. Schema-dependent recall learning and promotion logic, because some required schema is already missing.
2. Cache-miss recall latency and write contention under burst traffic.
3. Operational storage growth from `action_log`, because there is no retention or shrink path.
