# v2.1 Final Diff Analysis

## Scope and Baseline
- Repository: `C:\dev\01_projects\06_mcp-memory`
- Diff range used: `2bc0904^..HEAD`
- Baseline commit (start of v2.1 implementation): `2bc09045abf323c1441ca66132b7ef8ee415f515` (`2026-03-05 20:29:47 +0900`, message: `[W1] P0-W1-01: config.py v2.1 상수 16개 추가`)
- Current HEAD analyzed: `2b4f49f3a11c43acff30b49b7b39c264bc30c978` (`2026-03-06 01:56:06 +0900`)

## Repository-Wide Change Summary
- Total changed files: **34**
- New files: **21**
- Modified files: **13**
- Deleted files: **0**
- Renamed files: **0**
- Net diff: **5781 insertions / 165 deletions**

### Added Files (21)
- `docs/implementation/w1-state.md`
- `docs/implementation/w2-state.md`
- `docs/implementation/w3-state.md`
- `scripts/calibrate_drift.py`
- `scripts/eval/ab_test.py`
- `scripts/eval/goldset.yaml`
- `scripts/hub_monitor.py`
- `scripts/migrate_v2_ontology.py`
- `scripts/pruning.py`
- `scripts/sprt_simulate.py`
- `storage/action_log.py`
- `tests/test_access_control.py`
- `tests/test_action_log.py`
- `tests/test_drift.py`
- `tests/test_hybrid.py`
- `tests/test_recall_v2.py`
- `tests/test_remember_v2.py`
- `tests/test_validators_integration.py`
- `utils/__init__.py`
- `utils/access_control.py`
- `utils/similarity.py`

### Modified Files (13)
- `config.py`
- `ontology/schema.yaml`
- `ontology/validators.py`
- `scripts/daily_enrich.py`
- `scripts/enrich/node_enricher.py`
- `server.py`
- `storage/hybrid.py`
- `storage/sqlite_store.py`
- `storage/vector_store.py`
- `tools/analyze_signals.py`
- `tools/promote_node.py`
- `tools/recall.py`
- `tools/remember.py`

## Requested Key Files: Delta Summary
- Key files analyzed: `storage/hybrid.py`, `storage/action_log.py`, `tools/remember.py`, `tools/recall.py`, `tools/promote_node.py`, `tools/analyze_signals.py`, `utils/access_control.py`, `utils/similarity.py`, `scripts/daily_enrich.py`, `config.py`
- Combined key-file diff size: **1648 insertions / 93 deletions** (`10 files`)

### New Functions in Key Files
- `storage/hybrid.py` (7): `_auto_ucb_c`, `_bcm_update`, `_get_graph`, `_log_recall_activations`, `_sprt_check`, `_traverse_sql`, `_ucb_traverse`
- `storage/action_log.py` (1): `record`
- `tools/remember.py` (4): `classify`, `store`, `link`, `remember` (rewritten orchestration)
- `tools/recall.py` (3): `_is_patch_saturated`, `_dominant_project`, `_increment_recall_count`
- `tools/promote_node.py` (4): `swr_readiness`, `_get_total_recall_count`, `promotion_probability`, `_mdl_gate`
- `tools/analyze_signals.py` (3): `_recommend_v2`, `_bayesian_cluster_score`, `_get_total_recall_count`
- `utils/access_control.py` (6): `_check_a10_firewall`, `_get_top10_hub_ids`, `_check_hub_protection`, `_check_layer_permissions`, `check_access`, `require_access`
- `utils/similarity.py` (1): `cosine_similarity`
- `scripts/daily_enrich.py` (5): `phase6_pruning`, `_run_edge_pruning`, `_run_node_stage2`, `_run_node_stage3`, `_log_pruning_action`
- `config.py`: no new functions

### Removed Functions in Key Files
- `storage/hybrid.py`: `_hebbian_update` removed (replaced by BCM pipeline)
- `tools/remember.py`: old monolithic `remember` removed and replaced by refactored pipeline (`classify/store/link/remember`)

## Breaking and Behaviorally Significant Changes
1. `hybrid_search()` is no longer read-only behaviorally.
- Signature expanded with `excluded_project` and `mode` (`storage/hybrid.py:385-392`).
- Search now mutates DB state: BCM updates, `visit_count`, `score_history`, and potential `promotion_candidate` update (`storage/hybrid.py:165-326`, `storage/hybrid.py:474-483`).
- Impact: callers that assumed pure retrieval now trigger learning and promotion side effects.

2. `recall()` output source distribution can change due patch switching logic.
- New `mode` parameter and patch saturation split/merge flow (`tools/recall.py:11-17`, `tools/recall.py:40-52`).
- Uses `PATCH_SATURATION_THRESHOLD=0.75` (`config.py:37`, `tools/recall.py:93`).
- Impact: same query can intentionally include alternate project results where it previously would not.

3. `promote_node()` now gate-blocks promotion by default.
- Added SWR/Bayesian/MDL gates and new failure statuses (`tools/promote_node.py:197-239`).
- Added `skip_gates` parameter (`tools/promote_node.py:172`).
- Gate thresholds in effect: SWR `>0.55` (`config.py:40`, `tools/promote_node.py:80`), Bayesian `p_real >= 0.5` (`tools/promote_node.py:214`), MDL average cosine `>0.75` (`tools/promote_node.py:158`).
- Impact: previous successful promotions may now return structured non-success statuses.

4. `analyze_signals()` response schema changed.
- Added `bayesian_p`, `sprt_flagged`, and new recommendation logic (`tools/analyze_signals.py:95-111`, `tools/analyze_signals.py:148-162`).
- Impact: consumers parsing old cluster payload shape must handle new fields and possibly shifted recommendations.

5. `daily_enrich.py` now runs a new destructive Phase 6 path.
- Adds pruning/archiving workflow (`scripts/daily_enrich.py:267-517`) and registers phase in main (`scripts/daily_enrich.py:603`).
- Default runtime `dry_run` uses `config.DRY_RUN` and is `False` by default (`config.py:93`, `scripts/daily_enrich.py:578`).
- Impact: running the script without explicit dry-run can delete edges and archive nodes.

## New Dependencies
1. Package manifest changes.
- No new entries were added to `requirements.txt` in this range.

2. Runtime import deltas.
- New optional `numpy` usage introduced (`utils/similarity.py:9`, `tools/promote_node.py:138`).
- `utils/similarity.py` has fallback without numpy (`utils/similarity.py:28-38`).

3. New schema/runtime coupling (non-package dependency).
- New logic depends on `meta`, `recall_log`, `hub_snapshots`, and `action_log` availability in several paths (`tools/recall.py:112-117`, `tools/promote_node.py:43-45`, `utils/access_control.py:99-101`, `storage/action_log.py:89-96`).

## Security and Operational Risk Findings
1. **Gate bypass exposed** (`tools/promote_node.py:172`, `tools/promote_node.py:197`).
- `skip_gates` can bypass SWR/Bayesian/MDL checks.
- No actor/role check is performed inside `promote_node()`.

2. **Actor identity spoofability risk in access checks** (`utils/access_control.py:139-141`).
- Authorization trusts caller-provided `actor` string and allows prefix-based matching (`actor_base`).
- If upstream actor identity is not authenticated, privilege spoofing is possible.

3. **Hub protection fail-open on query failure** (`utils/access_control.py:104`).
- `_get_top10_hub_ids()` returns empty set on exception, disabling hub protection checks for that call.

4. **Broad exception swallowing in state-mutating code paths**.
- Examples: `storage/hybrid.py:274,379,410,485`, `tools/recall.py:121`, `scripts/daily_enrich.py:517`, `storage/action_log.py:105`.
- Risk: silent partial failure, hard-to-audit behavior, and unnoticed degradation.

5. **Audit taxonomy mismatch**.
- `daily_enrich` logs `action_type="archive"` (`scripts/daily_enrich.py:503`) but `ACTION_TAXONOMY` enumerates `node_archived` / `edge_archived` and does not declare `archive` (`storage/action_log.py:42-44`).
- Risk: inconsistent action semantics in logs.

6. **Positive note: SQL injection exposure appears low in reviewed paths**.
- Critical queries are parameterized (`?` binding) across reviewed key files.

## Overall Assessment
- v2.1 introduces substantial functional expansion (UCB/BCM retrieval learning, promotion gates, access control, pruning pipeline).
- Most externally visible API signatures remain backward-compatible at the parameter level (defaults preserve calls), but runtime behavior changed materially in recall, promotion, and enrichment execution.
- Primary risks are operational safety and authorization hardening rather than classic injection flaws.
