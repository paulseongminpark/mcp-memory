# Scripts Review - Round 1 (Correctness)
> Reviewer: Codex
> Date: 2026-03-06
> Files Reviewed: scripts/daily_enrich.py, scripts/pruning.py, scripts/hub_monitor.py, scripts/calibrate_drift.py, scripts/ontology_review.py, scripts/build_graph.py, scripts/enrich_nodes.py, scripts/query_memory.py, scripts/session_context.py, scripts/migrate_v2.py, scripts/migrate_v2_ontology.py, scripts/enrich/node_enricher.py

## Findings
### CRITICAL
- None.

### HIGH
- `scripts/daily_enrich.py:343,386,392` counts `archive` decisions in Phase 6-A but only persists the `delete` branch. There is no `UPDATE edges ... archived_at/probation_end`; weak edges from important sources remain active while the report claims they were archived.
- `scripts/daily_enrich.py:409-457` and `scripts/pruning.py:43-50` use `updated_at` as the inactivity signal. D-R3-14's Stage 2 formula uses `last_activated` plus an importance score. The implementation changed the meaning of inactivity because the node schema never got `last_activated`.
- `scripts/ontology_review.py:43-45` imports `get_valid_node_types()` from `ontology.validators`, but that function does not exist. The script is broken on import.
- `scripts/build_graph.py:24` and `scripts/enrich_nodes.py:20-21` rely on legacy `enrichment.*` modules whose validator imports are broken. These script entry points are not executable on the current tree.

### MEDIUM
- `scripts/daily_enrich.py:503` logs `action_type="archive"`, which is outside the 25-entry `ACTION_TAXONOMY` declared in `storage/action_log.py`.
- `scripts/daily_enrich.py:457` returns `marked_probation = 0` in dry-run mode even when candidates were found. Dry-run reporting therefore underreports the impact of Stage 2.
- `scripts/session_context.py` still uses manual `sys.argv` parsing instead of `argparse`. It works, but it is the odd one out among the reviewed CLIs and has weaker input validation/documentation.

### LOW
- CLI handling is otherwise reasonable in `pruning.py`, `hub_monitor.py`, `calibrate_drift.py`, `daily_enrich.py`, and `query_memory.py`: arguments are typed by `argparse` and not directly interpolated from raw strings.

### INFO
- `scripts/calibrate_drift.py` is comparatively aligned with D-12.
- The heaviest correctness debt in scripts is integration debt: missing tables, missing columns, and missing helper APIs, not parser or syntax errors.

## Coverage
- Enumerated all top-level `scripts/*.py` files and reviewed their imports/entry points.
- Read the core runtime scripts in full: `daily_enrich.py`, `pruning.py`, `hub_monitor.py`, `calibrate_drift.py`, `ontology_review.py`, `build_graph.py`, `enrich_nodes.py`, `query_memory.py`, and `session_context.py`.
- Read the D-12/D-13/D-14-relevant sections of `scripts/enrich/node_enricher.py`.
- Checked pruning formulas and CLI handling against `d-r3-14` and related Round 3 specs.

## Summary
The script layer is readable and mostly well-structured, but Phase 6 pruning is only partially wired to the Round 3 schema and several maintenance commands fail because the ontology helper API they import does not exist.
