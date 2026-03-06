# Script Operations Review - Round 3 (Operations)

> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Operational Reality
> Files Reviewed: scripts/pruning.py, scripts/hub_monitor.py, scripts/daily_enrich.py, scripts/enrich/node_enricher.py, scripts/enrich/relation_extractor.py, scripts/enrich/graph_analyzer.py, scripts/enrich/token_counter.py

## Baseline

- Live `hub_snapshots` rows: 0
- Live `nodes` status distribution: 3,299 active / 0 pruning_candidate / 0 archived
- Live `edges` with `frequency > 0`: 62
- Live `nodes` with `enriched_at IS NULL`: 52

## Findings

### [Severity: CRITICAL]

**C01** Hub snapshot generation is incompatible with the live schema, so hub protection is effectively off
- File: `scripts/hub_monitor.py:61-75`, `utils/access_control.py:95-105`, `utils/access_control.py:187-189`
- Description: `take_snapshot()` inserts only `(node_id, snapshot_date, ihs_score)`. The live `hub_snapshots` table also requires `created_at` and includes extra metric columns.
- Impact: the snapshot writer is not compatible with the current production table, and the access-control layer sees no protected hubs because the table is empty.

**C02** Phase 6 edge "archive" is only a counter, not a persisted state change
- File: `scripts/daily_enrich.py:384-398`
- Description: `_run_edge_pruning()` increments `stats['archive']`, but only `delete` performs a DB write. The code comment explicitly notes that the schema has no `archived_at`.
- Impact: operational reports can claim thousands of archived edges while the DB still contains the same active edges.

### [Severity: HIGH]

**H01** Pruning false positives are driven by `updated_at`, not real activation
- File: `scripts/pruning.py:36-50`, `scripts/daily_enrich.py:409-425`, `docs/implementation/0-impl-phase2.md:95-101`
- Description: both pruning paths select stale nodes by `updated_at < now - 90 days`. The implementation doc says this should be based on `last_activated`.
- Impact: frequently recalled but untouched nodes can still be marked as pruning candidates. Fresh metadata edits also reset the pruning clock even when the node is semantically dead.

**H02** Stage 3 archive does not re-check hub protection or fresh activity before archiving
- File: `scripts/pruning.py:107-139`, `scripts/daily_enrich.py:466-495`
- Description: once a node enters `pruning_candidate`, the archive step does not re-run `check_access()` and does not verify whether the node became active again.
- Impact: a node can age into archive even if it became important after Stage 2.

**H03** Overlapping scheduled runs are unsafe for both DB traffic and observability files
- File: `scripts/daily_enrich.py:568-643`, `scripts/enrich/token_counter.py:237-264`, `scripts/daily_enrich.py:523-563`
- Description: there is no lock file, leader election, or singleton guard. `save_log()` appends the same JSON file without a file lock, and `generate_report()` overwrites the same dated report path.
- Impact: overlapping cron runs can race on SQLite, token logs, and daily reports.

### [Severity: MEDIUM]

**M01** Crash recovery is partial, not end-to-end
- File: `scripts/enrich/node_enricher.py:418-565`, `scripts/daily_enrich.py:618-642`
- Description: node enrichment can resume from `enrichment_status`, but edge pruning, hub snapshots, report generation, and token-log writes have no resumable checkpoint.
- Impact: mid-run crashes produce partial operational state with no authoritative resume marker.

**M02** Hub-health metrics are not scale-aware and do not match the richer schema the DB already has
- File: `scripts/hub_monitor.py:31-56`, `scripts/hub_monitor.py:79-102`
- Description: the script measures only inbound edge count and uses hard-coded thresholds `>50` and `>20`, while the live schema already reserves fields for degree, betweenness, NC score, and risk level.
- Impact: the script reports a narrow and potentially misleading view of hub risk, especially as graph size changes.

**M03** Several GraphAnalyzer counters overstate what actually happened
- File: `scripts/enrich/graph_analyzer.py:767-777`, `scripts/enrich/graph_analyzer.py:836-847`, `scripts/enrich/graph_analyzer.py:884-895`
- Description: `orphans_resolved`, `contradictions_found`, and `assemblages_found` are incremented per analyzed item, not per inserted or resolved item.
- Impact: operational dashboards and daily reports can overstate effectiveness.

## Summary

- The most operationally dangerous script issue is the empty `hub_snapshots` table, because it disables one of the intended safety layers.
- The most misleading script issue is Phase 6 edge "archive", because the metric changes but the data does not.
- Scheduling safety is not in place for unattended multi-run environments.
