# Scripts Review - Round 2 (Architecture)
> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Architecture
> Files Reviewed: scripts/daily_enrich.py, scripts/pruning.py, scripts/hub_monitor.py, scripts/build_graph.py, scripts/query_memory.py, scripts/session_context.py, scripts/export_to_obsidian.py, scripts/enrich/node_enricher.py, scripts/enrich/relation_extractor.py, scripts/enrich/graph_analyzer.py, enrichment/relation_extractor.py

## Findings
### CRITICAL
- None.

### HIGH
- `H01` `scripts/enrich/node_enricher.py`, `scripts/enrich/relation_extractor.py`, and `scripts/enrich/graph_analyzer.py` are not thin scripts. They are long-lived service-layer modules with internal clients, batching logic, DB access, decision heuristics, and update application code. Keeping this amount of product logic under `scripts/` weakens architectural boundaries because these modules are effectively part of the application core without being treated as such.
- `H02` `scripts/enrich/node_enricher.py:78-94`, `scripts/enrich/relation_extractor.py:72-88`, `scripts/enrich/graph_analyzer.py:65-81`: the LLM client scaffolding is duplicated across three enrichment classes. `client`, `anthropic_client`, and `_call_json` are near-identical implementations. That duplication is already causing drift in helper behavior and makes future provider changes expensive.
- `H03` `scripts/daily_enrich.py` and `scripts/pruning.py` both own pruning-stage logic. The near-duplicate archive flow means the script layer does not have a single reusable pruning library, so behavior can diverge by cron entrypoint.

### MEDIUM
- `M01` the script-library boundary is weak in multiple places. `scripts/build_graph.py` reimplements relation selection instead of using `config.infer_relation()`, `scripts/query_memory.py` reimplements a simplified recall path, and `scripts/session_context.py` overlaps the tool-layer `get_context` behavior. This is classic architecture drift caused by missing reusable service abstractions.
- `M02` CLI design is inconsistent. Some scripts are callable helpers, some are ad hoc entrypoints, some assume direct imports after `sys.path.insert`, and some return values while others print side effects. The scripts are usable, but they do not share a standard command interface.
- `M03` configuration ownership is fragmented. `scripts/export_to_obsidian.py:12` hardcodes an absolute `DB_PATH`, several scripts define their own `ROOT`, and many modify `sys.path` at runtime. That is convenient for local execution but poor architecture because environment wiring is scattered.

### LOW
- `L01` idempotency is uneven. Migration-oriented scripts think in idempotent steps, but enrichment and export flows often rely on caller discipline rather than explicit idempotency contracts.
- `L02` naming consistency is hurt by duplicate module names. There is both `enrichment/relation_extractor.py` and `scripts/enrich/relation_extractor.py`, which makes intent and ownership unclear.

### INFO
- `I01` Exact duplicates: `_get_node()` exists in both `scripts/enrich/node_enricher.py:632` and `scripts/enrich/relation_extractor.py:157`; `_get_conn()` exists in both `scripts/hub_monitor.py:25` and `scripts/pruning.py:25`.
- `I02` Near duplicates: `_call_json()` across all three enrichment classes; `_trunc()` in `scripts/enrich/relation_extractor.py:150` and `scripts/enrich/graph_analyzer.py:143`; pruning archive stages in `scripts/daily_enrich.py` and `scripts/pruning.py`.
- `I03` Structural duplication counts: `sys.path.insert` appears `24` times repo-wide, `ROOT =` appears `15` times, and `DB_PATH =` appears `5` times.
- `I04` Naming consistency check also surfaced stale ontology names in `scripts/export_to_obsidian.py:28-52` and `scripts/session_context.py:43`.

## Coverage
- Key cyclomatic complexity: `scripts/enrich/node_enricher.py:418` `enrich_batch_combined()` = 43, `scripts/enrich/node_enricher.py:301` `enrich_node_combined()` = 28, `scripts/enrich/node_enricher.py:652` `_apply()` = 28, `scripts/enrich/relation_extractor.py:592` `run_e14()` = 22, `scripts/build_graph.py:40` `build_vector_edges()` = 21, `scripts/daily_enrich.py:53` `phase1()` = 20, `scripts/daily_enrich.py:327` `_run_edge_pruning()` = 19, `scripts/migrate_v2.py:299` `check_status()` = 16, `scripts/enrich/graph_analyzer.py:287` `find_similar_pairs()` = 15, `scripts/session_context.py:14` `get_context_cli()` = 24.
- Duplication checked for exact helper reuse, near-duplicate enrichment scaffolding, and overlapping script workflows.
- Naming consistency checked for module names, path/bootstrap helpers, and stale ontology consumers.

## Summary
The script layer carries too much of the system's real architecture. Instead of being thin operational wrappers over reusable libraries, many scripts are the libraries. The design would improve substantially if enrichment, pruning, export, and recall-adjacent logic moved into explicit application modules, with scripts reduced to narrow CLI entrypoints over shared services.
