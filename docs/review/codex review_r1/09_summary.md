# Summary Review - Round 1 (Correctness)
> Reviewer: Codex
> Date: 2026-03-06
> Files Reviewed: storage/*.py, tools/*.py, utils/*.py, ontology/validators.py, ontology/schema.yaml, config.py, scripts/*.py, scripts/enrich/node_enricher.py, tests/*.py, docs/ideation/*Round 3 final specs*

## Findings
### CRITICAL
- `storage/hybrid.py` writes `nodes.last_activated`, but the bootstrap `nodes` schema does not have that column. Hybrid search returns results, but BCM/UCB learning side effects can roll back silently.
- `tools/promote_node.py` is effectively non-functional on the current schema. Gate 1 depends on missing `recall_log`; Gate 2 depends on missing `meta` and nonexistent node `frequency`.
- `config.py` lacks a full node-type registry. Runtime code uses a 12-entry `PROMOTE_LAYER` map against a 50-type ontology, so 38 schema types lose their correct layer.

### HIGH
- Fresh boot via `server.py` + `init_db()` creates empty ontology tables. Because validators only fall back to schema on exception, a fresh DB can reject valid node types until the migration script is run.
- `scripts/daily_enrich.py` Phase 6 counts edge archives without persisting them and substitutes `updated_at` for the `last_activated`-based pruning formula described in D-R3-14.
- `ontology.validators` is missing helper APIs that existing scripts import, breaking `scripts/ontology_review.py` and legacy enrichment entry points.
- Round 3 action logging is partial: several required insertion sites from A-17 are missing.

### MEDIUM
- The public MCP surface does not expose recall `mode`, so B-R3-15 is only partially reachable.
- The recall counter path exists in code but no matching storage table exists, so long-run promotion/search statistics do not accumulate.
- Tests are numerous and useful, but they miss the bootstrap schema problems and do not exercise the real promotion path.

### LOW
- There are several small static issues such as unused imports and dead helper functions, but they are secondary to the integration defects.

### INFO
- The repo frequently matches spec snippets at the file level. Most failures are cross-file integration failures rather than missing algorithms.

## Coverage
- Reviewed the 5 storage files and 10 tool files in scope.
- Reviewed the ontology/config/access-control layer and the core scripts related to drift, pruning, and hub control.
- Read all 117 tests across 7 files and mapped them to covered behavior.
- Compared implementation against the Round 3 final specs and the Round 3 orchestrator integration document.

## Summary
Answer to the core question: no, this was not built correctly according to the full Round 3 integrated spec set.

Top 5 most impactful findings:
1. `storage/hybrid.py` cannot persist learning updates on the bootstrap schema because `nodes.last_activated` is missing.
2. `tools/promote_node.py` cannot complete normal gated promotions because its data sources (`recall_log`, `meta`, node `frequency`) do not exist or are never maintained.
3. `config.py` does not carry the full ontology layer map, so 38 of 50 schema types are stored with the wrong layer or no layer.
4. Fresh server boot creates empty ontology definition tables, and validator fallback does not recover from that state.
5. Phase 6 pruning does not persist edge archival decisions and does not use the activity signal described in D-R3-14.
