# Operational Summary - Round 3 (Operations)

> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Operational Reality

## Operational Readiness Score

**4/10**

This repo is usable for a single-user, manually supervised workflow. It is not ready for unattended production because several critical behaviors depend on schema elements that are missing in the live database, and multiple write paths are partial or non-idempotent.

## Top 5 Production Risks

| Rank | Risk | Likelihood | Impact | Score |
|------|------|------------|--------|-------|
| 1 | Silent recall-learning rollback from missing `nodes.last_activated` | 5 | 5 | 25 |
| 2 | Promotion and recall counters depend on missing `meta` and `recall_log` | 5 | 4 | 20 |
| 3 | Concurrent writers can create lock contention, duplicate edges, or oversubscribe quotas | 4 | 4 | 16 |
| 4 | Non-atomic, non-idempotent writes in `remember()`, `promote_node()`, and batch scripts | 4 | 4 | 16 |
| 5 | Unbounded DB growth from `action_log` with no retention, vacuum, or runtime backup | 4 | 4 | 16 |

## Why These Are The Top Risks

1. The recall path is already writing against a missing live column, so this is a present failure, not a future scale concern.
2. Promotion readiness is described as data-driven, but the live DB does not collect the data the gates expect.
3. The repo has multiple write entrypoints, inconsistent SQLite timeouts, and threaded budget accounting without locks.
4. Client retries and partial failures can create durable duplicates or partial graph state.
5. Storage growth will keep increasing operational cost even if correctness bugs are fixed.

## Monitoring And Alerting Recommendations

### Schema Drift

- Alert if `meta`, `recall_log`, or `nodes.last_activated` are missing at startup.
- Alert if `hub_snapshots` is older than 24 hours or empty.
- Run a startup schema check before serving tools.

### Recall Health

- Track `activation_log` row growth versus `nodes.visit_count` changes.
- Alert when recent activations rise but visit-count deltas stay near zero.
- Track cache-miss latency for `SELECT * FROM edges` plus graph build time.

### SQLite Health

- Alert on `database is locked` errors.
- Track p95 write latency for recall, remember, and daily enrichment writes.
- Track DB file size, page count, WAL size, and free-disk headroom.

### External Dependency Health

- Track embedding latency, error rate, and fallback rate from vector search to FTS-only behavior.
- Alert on sustained 429 or 5xx responses from embedding and enrichment providers.

### Batch Safety

- Alert if two `daily_enrich.py` runs overlap.
- Alert if token-log JSON write fails or report generation is skipped.
- Track hub snapshot freshness and daily_enrich phase completion per day.

## Bottom Line

- What breaks now: recall learning, promotion evidence, and hub safety assumptions.
- What breaks next under load: write contention, wrapper drift, and tool latency spikes on cache miss.
- What needs to exist before calling this production-ready: schema drift checks, idempotent writes, runtime backup/retention, and rate-limited/authenticated tool access.
