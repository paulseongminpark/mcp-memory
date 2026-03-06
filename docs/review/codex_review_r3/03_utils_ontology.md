# Utils And Ontology Review - Round 3 (Operations)

> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Operational Reality
> Files Reviewed: ontology/validators.py, tools/remember.py, tools/promote_node.py, tools/analyze_signals.py, utils/access_control.py, config.py, tests/test_validators_integration.py, tests/test_remember_v2.py

## Baseline

- `type_defs`: 50 rows total, 31 active and 19 deprecated
- `relation_defs`: 50 rows total, 48 active and 2 deprecated
- Live proxy check: 0 stored node types outside `type_defs`, 0 stored edge relations outside `relation_defs`
- Live quality gap: 84 nodes with `layer IS NULL`, 44 nodes whose stored layer disagrees with `type_defs.layer`

## Findings

### [Severity: CRITICAL]

**C01** Layer assignment during `remember()` ignores the ontology tables
- File: `tools/remember.py:62-69`, `config.py:243-258`, `tests/test_remember_v2.py:68-73`
- Description: `classify()` uses `PROMOTE_LAYER`, which only covers promotion-path types, not the full ontology. The tests explicitly encode `Project -> layer None` as expected behavior.
- Impact: common runtime types such as `Decision`, `Failure`, `Workflow`, and `Goal` can be saved without the correct layer. This directly weakens pruning, access control, and any layer-aware analytics.
- Evidence: live DB has 84 missing-layer nodes, mostly `Decision` (33) and `Failure` (17).

**C02** Promotion readiness logic depends on runtime data that does not exist in production
- File: `tools/promote_node.py:41-53`, `tools/promote_node.py:87-116`, `tools/analyze_signals.py:165-191`
- Description: promotion code expects `recall_log`, `meta.total_recall_count`, and a per-node `frequency` field. The live DB has none of those inputs.
- Impact: SWR and Bayesian gates are fallback-driven rather than evidence-driven. Promotion behavior is effectively disconnected from the design intent.

### [Severity: HIGH]

**H01** Validator false positive and false negative rates are not measurable from the current test suite
- File: `tests/test_validators_integration.py:1-176`
- Description: the file is named as an integration suite, but it tests mock validator functions, not the real DB-backed `validate_node_type()` or `validate_relation()` path.
- Impact: the repo does not have a labeled real-data estimate for misclassification rate.
- Live proxy: storage quality is good after write time (0 invalid stored types and 0 invalid stored relations), but that does not measure classification accuracy.

**H02** `suggest_closest_type()` is narrow and will miss many real inputs
- File: `ontology/validators.py:79-105`
- Description: content hints only cover twelve type families. Many valid ontology types have no lexical path into the suggestion heuristic.
- Impact: unknown inputs collapse into generic buckets or `Unclassified`.
- Evidence: the live DB still has 38 `Unclassified` nodes, including ingestion noise such as license text.

### [Severity: MEDIUM]

**M01** Hot-reload of config or ontology settings is not operationally feasible
- File: `config.py:1-258`, `storage/vector_store.py:9-23`, `embedding/openai_embed.py:7-14`
- Description: thresholds, models, and paths are imported as module constants and cached into singleton clients.
- Impact: changing model IDs, budgets, thresholds, or store paths requires process restart. The `config_changed` action taxonomy exists, but there is no runtime loader.

**M02** Firewall enforcement is inconsistent inside the enrichment path
- File: `scripts/enrich/node_enricher.py:652-660`, `scripts/enrich/node_enricher.py:522-560`
- Description: `_apply()` respects `check_access()`, but `enrich_batch_combined()` writes summaries, tags, facets, and domains directly in its Phase C writeback.
- Impact: new L4/L5 nodes can be enriched through a different code path than the one the firewall actually protects.

## Proxy Metrics

- Stored invalid node-type rate: 0 / 3,299
- Stored invalid relation rate: 0 / 6,329
- Missing-layer rate: 84 / 3,299
- Layer-mismatch rate: 44 / 3,299

## Summary

- The ontology catalog itself is coherent; the operational problem is that runtime writes do not consistently use it.
- Layer handling is the biggest live defect in this area.
- Validator quality is impossible to score credibly without a real labeled corpus or DB-backed integration tests.
