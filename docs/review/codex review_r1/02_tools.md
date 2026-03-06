# Tools Review - Round 1 (Correctness)
> Reviewer: Codex
> Date: 2026-03-06
> Files Reviewed: tools/visualize.py, tools/suggest_type.py, tools/save_session.py, tools/remember.py, tools/recall.py, tools/promote_node.py, tools/inspect_node.py, tools/get_context.py, tools/get_becoming.py, tools/analyze_signals.py

## Findings
### CRITICAL
- `tools/promote_node.py:44-80` makes Gate 1 depend on `recall_log`. When that table is missing, the code falls back to `vec_ratio = 0.0` at `tools/promote_node.py:52-53`. Because readiness is `0.6 * vec_ratio + 0.4 * cross_ratio`, the score tops out at `0.4`, below `PROMOTION_SWR_THRESHOLD = 0.55`. On the current schema, `promote_node()` cannot pass SWR without `skip_gates`.
- `tools/promote_node.py:92-113,218` makes Gate 2 depend on `meta.total_recall_count` and `node.get("frequency")`. There is no `meta` table in the repo bootstrap, and nodes do not have a `frequency` column. Bayesian evidence therefore collapses to a near-zero prior and blocks promotion even if Gate 1 were fixed.
- `tools/remember.py:63,165` derives `layer` from `PROMOTE_LAYER` only. Types outside that 12-entry map get `layer=None`, so `link()`'s F3 check never fires for schema-defined high-layer types such as `Axiom`, `Mental Model`, `Lens`, `Wonder`, and `Aporia`. A-18 says L4/L5 auto-edge creation must be blocked; this implementation can auto-link those types.

### HIGH
- `tools/recall.py:104-120` writes recall counts to `meta`, but no `CREATE TABLE meta` exists anywhere in the repo. The counter silently no-ops, so later UCB/Bayesian inputs never accumulate.
- `tools/analyze_signals.py:165-191` repeats the same integration bug as `promote_node()`: it reads node `frequency` and `meta.total_recall_count`, neither of which is actually maintained. Cluster Bayesian scores are systematically wrong.
- `tools/promote_node.py` does not emit A-17 logging on the success path. There is no `action_log.record("node_promoted")` and no `edge_realized` logging, despite both actions being part of the declared taxonomy/spec.

### MEDIUM
- `tools/get_becoming.py:17-24` ranks candidates purely by `quality_score` at query time. It does not integrate Bayesian/SPRT evidence from the Round 3 promotion model, so the output only partially reflects the intended readiness model.
- `tools/visualize.py:3` imports `Path` but never uses it.
- `tools/promote_node.py:10` imports `math` but never uses it.

### LOW
- `tools/analyze_signals.py:139-146` defines `_recommend()` but only `_recommend_v2()` is used.

### INFO
- `tools/remember.py` otherwise matches A-18 structurally: `ClassificationResult`, `classify()`, `store()`, `link()`, `remember()`, and `node_created`/`edge_auto` logging are all present.
- `tools/recall.py` matches B-R3-15 structurally at the file level: mode support, patch saturation helpers, formatting, and graceful failure behavior are implemented.

## Coverage
- Read all 10 tool files in full.
- Traced `remember()`, `recall()`, and `promote_node()` through their callees.
- Checked `remember.py` against `a-r3-18`, `recall.py` against `b-r3-15`, and `promote_node.py` against `c-r3-11`.
- Ran a static pass for dead code, missing integrations, and obviously unused imports.

## Summary
The tool layer looks close to the Round 3 specs on paper, but the promotion path is effectively non-operational and `remember()`'s firewall depends on an incomplete type-to-layer map. The failures are mostly cross-file integration failures, not missing function bodies.
