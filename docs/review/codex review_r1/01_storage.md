# Storage Review - Round 1 (Correctness)
> Reviewer: Codex
> Date: 2026-03-06
> Files Reviewed: storage/sqlite_store.py, storage/hybrid.py, storage/vector_store.py, storage/action_log.py

## Findings
### CRITICAL
- `storage/hybrid.py:263-274` updates `nodes.last_activated` at line 268, but `storage/sqlite_store.py:24-55` does not define that column on `nodes`. The exception is swallowed at `storage/hybrid.py:274`, so `_bcm_update()` can roll back the whole learning transaction. On the bootstrap schema, `visit_count`, `theta_m`, edge `frequency`, and reconsolidation `description` updates do not persist.

### HIGH
- `storage/sqlite_store.py:163-208` creates `type_defs` and `relation_defs` but seeds no rows. The only population logic lives in `scripts/migrate_v2_ontology.py:285-359`. The storage bootstrap is therefore incomplete for any fresh DB that relies on `init_db()` alone.
- Round 3 readers expect `meta`, `recall_log`, `hub_snapshots`, and edge archival columns (`archived_at`, `probation_end`), but `storage/sqlite_store.py` never creates them. Repo-wide search found readers in `tools/recall.py`, `tools/promote_node.py`, `tools/analyze_signals.py`, `utils/access_control.py`, and `scripts/daily_enrich.py`, with no matching bootstrap `CREATE TABLE` in the storage layer.

### MEDIUM
- `storage/sqlite_store.py:262-279` corrects invalid relations to `connects_with` and writes `correction_log`, but A-17 also requires `action_log.record("edge_corrected")`. That telemetry hook is missing.
- `storage/action_log.py:48-100` accepts any `action_type` and never validates against `ACTION_TAXONOMY`. The contract has already drifted: `scripts/daily_enrich.py:503` logs `action_type="archive"`, which is not one of the 25 declared actions.
- `storage/sqlite_store.py:374-395` converts missing `node_id` to `0` inside `log_correction()`. With foreign keys enabled, edge-only corrections can fail insert and then be silently dropped.

### LOW
- `storage/vector_store.py:5` imports `EMBEDDING_DIM` but never uses it.
- `storage/sqlite_store.py:6` imports `Path` but never uses it.
- `storage/hybrid.py:49-86` defines `_traverse_sql()`, but the Phase 1 runtime never calls it.

### INFO
- Runtime SQL is generally parameterized correctly. `insert_node()`, `insert_edge()`, `search_fts()`, `get_node()`, `get_recent_nodes()`, and `_traverse_sql()` all bind variable values rather than interpolating user strings.
- All four storage files parsed cleanly under AST; no syntax errors were found.

## Coverage
- Read all four storage files in full.
- Checked function signatures against `a-r3-17`, `b-r3-14`, `c-r3-12`, and `d-r3-12`.
- Reviewed every SQL statement in these files for schema compatibility, missing tables/columns, and parameterization.
- Ran a static pass for dead code and obviously unused imports.

## Summary
The storage layer mirrors the Round 3 file shapes, but the bootstrap schema is not the schema that higher-level code actually expects. The main blocker is the missing `nodes.last_activated` column, which breaks hybrid learning updates on the default schema.
