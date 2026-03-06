# E2E Scenarios Review - Round 2 (Architecture)
> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Architecture
> Files Reviewed: server.py, tools/remember.py, tools/recall.py, tools/promote_node.py, storage/hybrid.py, storage/sqlite_store.py, storage/vector_store.py, config.py, utils/access_control.py

## Findings
### CRITICAL
- None.

### HIGH
- `H01` `server.py -> tools/recall.py -> storage/hybrid.py`: the recall path is overloaded. A single request fans into vector search, FTS search, graph traversal, RRF scoring, candidate hydration, BCM updates, SPRT evaluation, activation logging, global recall counting, and edge formatting. That is too much architecture for one synchronous path. It increases call depth, side effects, and failure coupling for what should primarily be a read operation.
- `H02` `server.py:40-76` and `tools/remember.py:38-232`: the remember path duplicates validation and then performs partial writes across SQLite, vector storage, auto-linking, and action logging. The flow is pragmatic, but it is not built around a clear unit-of-work abstraction, so partial success semantics are encoded implicitly instead of through a deliberate design.

### MEDIUM
- `M01` `tools/promote_node.py:167-291`: `promote_node()` is sequential and chatty. It loads the node, evaluates gate 1 using extra SQL, evaluates gate 2 with another DB read, evaluates gate 3 by hydrating related nodes one by one, then performs updates and edge inserts directly. The function is understandable, but the architecture exposes too many storage round trips to the orchestration layer.
- `M02` `tools/recall.py:51-63`, `storage/hybrid.py:443-461`, `tools/promote_node.py:57-73`: several flows miss obvious short-circuit boundaries and bulk-fetch opportunities. Post-ranking edge hydration, post-ranking node hydration, and neighbor project lookup are all performed incrementally.
- `M03` `utils/access_control.py:146` exists as a dedicated enforcement path, but `server.py:40`, `server.py:116`, and `server.py:232` do not invoke it for the main flows. The access-control architecture therefore sits beside the core flows rather than inside them.

### LOW
- `L01` the server wrappers still create drift because they are not pure pass-through adapters. The wrapper signatures and validations differ from tool internals, which adds one more layer where behavior can diverge.

### INFO
- `I01` Approximate call-depth snapshots:
- `I02` `remember`: `server.remember -> tools.remember.remember -> classify -> store -> sqlite_store.insert_node / action_log.record / vector_store.add -> link -> vector_store.search -> sqlite_store.get_node -> sqlite_store.insert_edge -> action_log.record`.
- `I03` `recall`: `server.recall -> tools.recall.recall -> storage.hybrid.hybrid_search -> vector_store.search + sqlite_store.search_fts + graph traversal -> sqlite_store.get_node per candidate -> _bcm_update -> _sprt_check -> _log_recall_activations -> _increment_recall_count -> sqlite_store.get_edges per result`.
- `I04` `promote_node`: `server.promote_node -> tools.promote_node.promote_node -> sqlite_store.get_node -> swr_readiness -> _get_total_recall_count -> promotion_probability -> sqlite_store.get_node per related_id -> _mdl_gate -> raw SQL update + insert edge loop`.
- `I05` Key cyclomatic complexity: `storage/hybrid.py:385` `hybrid_search()` = 28, `tools/promote_node.py:167` `promote_node()` = 21, `tools/remember.py:151` `link()` = 10, `tools/recall.py:11` `recall()` = 7.
- `I06` Duplication check found exact helper overlap in `_get_total_recall_count()` and repeated post-query hydration patterns.
- `I07` Naming consistency check found transport names stable, but behavior labels drift between "recall", "activation", "promotion", and mixed audit verbs.

## Coverage
- End-to-end code paths traced for `remember()`, `recall()`, and `promote_node()`.
- Short-circuit opportunities, call depth, and round-trip count reviewed from transport through storage.
- Duplication checked in shared helper logic and post-query hydration patterns.
- Naming consistency checked across flow stages and audit verbs.

## Summary
The main flows are pipelines, not cleanly separated services. They work, but they combine orchestration, policy, storage coordination, and logging in the same path. The architecture would improve if query flows were split from learning flows, and if write flows were organized around explicit application services with bulk-aware repository methods.
