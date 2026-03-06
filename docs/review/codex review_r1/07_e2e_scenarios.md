# End To End Scenarios Review - Round 1 (Correctness)
> Reviewer: Codex
> Date: 2026-03-06
> Files Reviewed: server.py, tools/remember.py, tools/recall.py, tools/promote_node.py, storage/sqlite_store.py, storage/hybrid.py, utils/access_control.py, ontology/validators.py, config.py

## Findings
### CRITICAL
- Fresh-DB `remember()` is broken. `server.py:342` calls `init_db()`, which creates empty `type_defs`/`relation_defs`; `ontology/validators.py:24-49` only falls back to schema on exception, not on emptiness. Result: a fresh server rejects valid typed memories until the separate ontology migration is run.
- `recall()` returns results but its learning side effects are broken on the bootstrap schema. `storage/hybrid.py:268` updates a nonexistent `nodes.last_activated` column, the exception is swallowed at `storage/hybrid.py:274`, and the BCM/UCB learning transaction does not persist.
- `promote_node()` with gates enabled is effectively non-operational. Gate 1 depends on missing `recall_log` and falls back to a readiness ceiling below threshold; Gate 2 depends on missing `meta` and nonexistent node `frequency`.

### HIGH
- `remember()` only enforces F3 correctly for the few types present in `PROMOTE_LAYER`. High-layer schema types missing from that map, including `Axiom`, `Mental Model`, `Lens`, `Wonder`, and `Aporia`, enter the system with `layer=None` and bypass auto-edge blocking.
- The MCP-exposed `recall()` path in `server.py:116-137` does not expose the `mode` parameter added by B-R3-15, so `focus` / `dmn` search modes are unreachable through the public tool surface.
- `analyze_signals()` and `get_becoming()` can still return output, but the Bayesian side of their ranking is weakened by the same missing `meta` / missing node `frequency` data used by promotion.

### MEDIUM
- `promote_node()` success does not emit the action-log records expected by A-17, so even a forced/internal promotion path leaves incomplete audit data.
- `check_access()` is not part of the public `promote_node()` flow at all; the enforcement path is only used in enrichment/pruning/hub-monitor scenarios.

### LOW
- The read-only parts of the system are in better shape than the write-back parts. `recall()` formatting and `inspect()`-style reads are much less risky than learning/promotion/pruning state changes.

### INFO
- The end-to-end failures are integration failures between otherwise plausible components; they are not algorithmic math errors in UCB/BCM/SPRT themselves.

## Coverage
Remember flow traced:
1. `server.py remember()` validates type via `ontology.validators.validate_node_type()`.
2. `_remember()` in `tools/remember.py` runs `classify() -> store() -> link()`.
3. `store()` writes SQLite and Chroma, then `link()` may auto-create edges.
4. Broken path: fresh DB has empty ontology tables; broken path: many schema types get `layer=None`, so F3 and later access-control logic misclassify them.

Recall flow traced:
1. `server.py recall()` forwards to `tools/recall.py`.
2. `tools/recall.py` calls `storage.hybrid.hybrid_search()`.
3. `hybrid_search()` runs vector search, FTS, graph traversal, `_bcm_update()`, `_sprt_check()`, and recall logging.
4. Broken path: `_bcm_update()` writes `nodes.last_activated`, which the bootstrap schema does not have; learning updates are dropped.
5. Broken path: `_increment_recall_count()` writes to missing `meta`, so recall statistics never persist.

Promote flow traced:
1. `server.py promote_node()` forwards to `tools/promote_node.py`.
2. Gate 1 computes SWR readiness from `recall_log` + cross-project neighbors.
3. Gate 2 computes Bayesian evidence from `meta.total_recall_count` and node `frequency`.
4. Gate 3 computes MDL similarity from embeddings.
5. Broken path: on current schema, Gate 1 and Gate 2 do not have their required data sources, so normal promotion cannot complete.

## Summary
`remember()` can work only on a properly migrated/populated DB, `recall()` mostly works as a read path but fails to persist learning, and `promote_node()` does not work as a normal gated path on the current schema. End-to-end correctness is therefore not achieved.
