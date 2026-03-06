# Security Review - Round 1 (Correctness)
> Reviewer: Codex
> Date: 2026-03-06
> Files Reviewed: server.py, storage/sqlite_store.py, storage/hybrid.py, tools/remember.py, tools/recall.py, tools/promote_node.py, utils/access_control.py, scripts/daily_enrich.py, scripts/pruning.py, scripts/build_graph.py, scripts/query_memory.py, scripts/enrich/node_enricher.py, scripts/enrich/relation_extractor.py

## Findings
### CRITICAL
- `tools/remember.py:63,165` plus `config.py:253-258` create a logic-layer security bypass. High-layer schema types missing from `PROMOTE_LAYER` are stored with `layer=None`; `utils/access_control.py:181` later treats missing layers as `0`. Intended L4/L5 protections and F3 auto-edge blocking can therefore be bypassed for types such as `Axiom`, `Mental Model`, `Lens`, `Wonder`, and `Aporia`.

### HIGH
- `utils/access_control.py:177-181` defaults nonexistent nodes to layer 0. Any caller that forgets to verify existence first can get an allow decision for a bad node id.
- `server.py:232-255` exposes `promote_node()` without any actor/authorization context and does not consult `check_access()`. The access-control system is therefore not on the public promotion path.
- Tool entry points have weak input validation. `server.py remember()` does not bound `confidence` or sanitize large `metadata`; `server.py recall()` does not bound `top_k`; `tools/recall.py` accepts any `mode` string internally and treats unknown values as auto.

### MEDIUM
- No direct SQL injection vulnerability was found in the core runtime path. Most user-controlled values are parameterized. The remaining dynamic SQL appears in maintenance/admin code such as `scripts/build_graph.py:128-134`, `scripts/migrate_v2.py:64,176,293`, `scripts/enrich/node_enricher.py:768`, and `scripts/enrich/relation_extractor.py:170`, where identifiers come from internal code or typed argparse inputs.
- Error messages leak internal details more than necessary. `embedding/openai_embed.py:18-30` raises provider/type names verbatim; `tools/remember.py:125` returns embedding exception text; `tools/promote_node.py` includes raw MDL embedding errors in rejection reasons; `scripts/calibrate_drift.py:88` prints API errors to stdout.
- `scripts/daily_enrich.py:503` logs `action_type="archive"` even though the declared action taxonomy does not define that action. It is not SQL injection, but it weakens audit consistency.

### LOW
- `storage/sqlite_store.py:283-308` escapes FTS query terms and still binds the final MATCH string as a parameter, which is the safer pattern for this SQLite path.
- Unknown access-control operations default to `paul` only, which is conservative.

### INFO
- The dominant security risk in this repo is logic-layer bypass caused by bad layer assignment and incomplete enforcement, not classic SQL injection.

## Coverage
- Reviewed all SQL operations in the core storage/tool/runtime path for parameterization and interpolated identifiers.
- Checked public MCP entry points in `server.py` for argument validation and access-control coverage.
- Checked `utils/access_control.py` for bypass scenarios and mismatch with caller behavior.
- Checked error-returning paths for internal-detail leakage.

## Summary
The main security issue is not injected SQL; it is that ontology-layer mistakes degrade the access-control model. Several high-layer types can lose their layer at ingest time, and the public promotion path bypasses the access-control layer entirely.
