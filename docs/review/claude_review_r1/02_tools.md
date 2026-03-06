# Tools Layer Review - Round 1 (Correctness)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Correctness & Completeness
> Files Reviewed: tools/remember.py, tools/recall.py, tools/promote_node.py, tools/analyze_signals.py, tools/get_becoming.py, tools/get_context.py, tools/inspect_node.py, tools/save_session.py, tools/suggest_type.py, tools/visualize.py, server.py (routing)

## Findings

### [Severity: HIGH]

**H-01** promote_node() never calls action_log.record() — audit trail broken for promotions

- File: `tools/promote_node.py` (entire file — no `action_log` import)
- Spec: `storage/action_log.py:18-20` defines `"node_promoted"` and `"edge_realized"` in ACTION_TAXONOMY
- Description:
  - ACTION_TAXONOMY explicitly defines two action types for promotion:
    - `"node_promoted"`: "promote_node()에서 타입 승격"
    - `"edge_realized"`: "promote_node()에서 realized_as edge 생성"
  - promote_node.py does not import `action_log` at all
  - Neither the node type change (L259-264) nor realized_as edge creation (L271-278) is logged
  - By contrast, `remember.py` correctly logs both `"node_created"` (L110-123) and `"edge_auto"` (L214-225)
  - The c-r3-11 spec code also omits action_log calls — this is a spec-level omission carried into implementation
- Impact: Promotion is arguably the most significant state change in the ontology (permanent type/layer change). Without audit logging, there is no record of when, why, or by whom a node was promoted. Analytics queries on `action_log` for promotion events return nothing.
- Recommendation: Add `action_log.record("node_promoted", ...)` after L264 and `action_log.record("edge_realized", ...)` inside the edge creation loop at L276.

---

### [Severity: MEDIUM]

**M-01** gates_passed always reports all 3 gates even when MDL was skipped

- File: `tools/promote_node.py:290`
- Spec: `docs/ideation/c-r3-11-promotion-final.md:314`
- Description:
  - Code: `"gates_passed": [] if skip_gates else ["swr", "bayesian", "mdl"]`
  - Gate 3 (MDL) only runs when `related_ids` is provided (L227: `if not skip_gates and related_ids:`)
  - If `promote_node(id=123, target_type="Pattern")` is called without `related_ids`, Gates 1+2 run but Gate 3 is skipped
  - The response still claims `gates_passed: ["swr", "bayesian", "mdl"]` — MDL was never evaluated
  - The spec has the same code, so this is a spec-level issue carried into implementation
- Impact: Callers (Claude, dashboards) receive misleading gate pass information. A promotion that only passed 2 of 3 gates appears as fully validated.
- Recommendation: Build `gates_passed` dynamically:
  ```python
  passed = ["swr", "bayesian"]
  if related_ids:
      passed.append("mdl")
  ```

---

**M-02** promote_node() does not update `tier` column on promotion

- File: `tools/promote_node.py:259-264`
- Spec: `docs/ideation/c-r3-11-promotion-final.md:283-288` (same omission)
- Description:
  - Promotion UPDATE sets: `type`, `layer`, `metadata`, `updated_at`
  - `tier` is not updated — a Signal (tier=2) promoted to Principle (layer=3, should be tier=0) keeps tier=2
  - `remember.py:classify()` has the tier logic: `layer >= 3 → tier=0`, `layer == 2 → tier=2`
  - `sqlite_store.update_tiers()` will eventually correct this, but there's a window of incorrect tier
  - The spec also omits tier update, so this is a spec-level omission
- Impact: Between promotion and the next `update_tiers()` batch run, the node has an incorrect tier. Any tier-based filtering (access control, pruning) will treat the promoted node incorrectly.
- Recommendation: Add `tier` to the UPDATE statement, using the same logic as `classify()`:
  ```python
  new_tier = 0 if (new_layer is not None and new_layer >= 3) else 2
  ```

---

**M-03** recall.py writes to `meta` table, spec b-r3-15 says `stats` table

- File: `tools/recall.py:112-118` (`INSERT INTO meta(key, value, ...)`)
- Spec: `docs/ideation/b-r3-15-recall-final.md:170-175` (`INSERT INTO stats(key, value, ...)`)
- Description:
  - b-r3-15 spec defines a `stats` table for `total_recall_count` storage
  - c-r3-11 spec (L494-496) uses `meta` table for the same purpose
  - Implementation follows c-r3-11 convention — all readers (`promote_node.py:91`, `analyze_signals.py:184`) also use `meta`
  - The code is internally consistent (all read/write paths use `meta`)
  - This is a spec-to-spec inconsistency: b-r3-15 says `stats`, c-r3-11 says `meta`
- Impact: Low runtime impact (code works correctly). Documentation/spec confusion — a developer reading b-r3-15 would expect a `stats` table that doesn't exist.
- Recommendation: Update b-r3-15 spec to say `meta` table, matching the actual implementation and c-r3-11.

---

### [Severity: LOW]

**L-01** `_get_total_recall_count()` duplicated across two files

- File: `tools/promote_node.py:87-98`, `tools/analyze_signals.py:180-191`
- Description:
  - Identical function (same SQL, same fallback logic) copy-pasted in both files
  - Both query `meta` table for `total_recall_count`
  - DRY violation — a change to one must be mirrored in the other
- Impact: Maintenance burden. If the table name or key changes, two files need updating.
- Recommendation: Extract to a shared location (e.g., `storage/sqlite_store.py` or a `utils/stats.py`).

---

**L-02** Two different "maturity" formulas with the same name across tools

- File: `tools/get_becoming.py:49-50`, `tools/analyze_signals.py:129-136`
- Description:
  - `get_becoming` maturity: `quality_score * 0.6 + min(1, edge_count/10) * 0.4`
  - `analyze_signals` maturity: `size_score * 0.5 + quality_avg * 0.3 + domain_score * 0.2`
  - Both are returned as `"maturity"` in their respective outputs
  - Different inputs (individual node vs cluster), different weights, different factors
  - `get_becoming` maturity is per-node; `analyze_signals` maturity is per-cluster — arguably valid
- Impact: Calling both tools for the same node/cluster produces different "maturity" values. Confusing for users and analytics.
- Recommendation: Either (a) rename to distinguish (`node_maturity` vs `cluster_maturity`), or (b) document the difference explicitly in tool docstrings.

---

### [Severity: INFO]

**I-01** remember.py exactly matches a-r3-18 spec

- File: `tools/remember.py` (292 lines)
- Verification:
  - `classify()` signature and logic: exact match (L38-77 vs spec L49-88)
  - `ClassificationResult` dataclass: exact match (5 fields)
  - `store()` SQLite+ChromaDB dual write: exact match
  - `link()` F3 firewall: both F3-a (new node L4/L5) and F3-b (similar node L4/L5) implemented
  - `remember()` pipeline: classify→store→link with ChromaDB failure fallback
  - `action_log.record()` at 2 points: `"node_created"` and `"edge_auto"`
  - FIREWALL_PROTECTED_LAYERS = {4, 5}: hardcoded as spec requires
  - `infer_relation()` called with all 6 parameters

**I-02** recall.py matches b-r3-15 spec (with minor table name divergence)

- File: `tools/recall.py` (123 lines)
- Verification:
  - `recall()` signature: `query, type_filter, project, top_k, mode` — exact match
  - `mode` parameter: "auto"/"focus"/"dmn" — matches B-12 spec
  - B-4 patch switching: `_is_patch_saturated()` → 2nd `hybrid_search(excluded_project=...)` → merge
  - PATCH_SATURATION_THRESHOLD from config.py (0.75) — matches spec
  - `_is_patch_saturated()`: len < 3 → False, dominant >= 75% → True
  - `_increment_recall_count()`: UPSERT logic correct (INSERT ON CONFLICT DO UPDATE)
  - Result formatting: content[:200], edges[:3], score rounding — all present

**I-03** promote_node.py 3-gate pipeline matches c-r3-11 spec

- File: `tools/promote_node.py` (293 lines)
- Verification:
  - Gate 1 SWR: `readiness = 0.6 * vec_ratio + 0.4 * cross_ratio > 0.55` — exact match
  - Gate 2 Bayesian: `P = (1+k) / (11+n)`, Prior Beta(1,10) — exact match
  - Gate 3 MDL: `avg_sim > 0.75`, cosine similarity matrix — exact match
  - Gate ordering: SWR → Bayesian → MDL (serial) — exact match
  - `skip_gates` parameter: present, controls all 3 gates — exact match
  - `promotion_history` metadata preservation: append to list — exact match
  - `realized_as` edge creation: for each related_id — exact match
  - `VALID_PROMOTIONS` validation before gates — correct
  - Implementation improvement: `swr_readiness()` adds try/except for recall_log (resilience fallback not in spec)
  - Implementation improvement: `_mdl_gate()` uses imported `np` instead of spec's `__import__("numpy")`

**I-04** analyze_signals.py _recommend_v2 matches c-r3-11 spec

- File: `tools/analyze_signals.py:148-162`
- Verification:
  - auto_promote: maturity > 0.9 AND bayesian_p > 0.6 — exact match
  - user_review: bayesian_p > 0.5 OR sprt_flagged >= 2 — exact match
  - user_review (fallback): maturity > 0.6 — exact match
  - not_ready: default — exact match
  - `_bayesian_cluster_score()`: Beta(1,10) prior, per-node P averaging — exact match
  - Legacy `_recommend()` preserved for backward compatibility

**I-05** server.py correctly routes all 10 tools

- All 10 tool functions imported and exposed via `@mcp.tool()` decorator
- `skip_gates` parameter intentionally NOT exposed in MCP `promote_node()` wrapper (L232-255) — security-by-design: MCP clients cannot bypass gates
- Parameter forwarding verified for all tools

**I-06** Remaining 6 tools functional and well-implemented

- `get_becoming.py`: Queries promotable types via VALID_PROMOTIONS, per-node maturity scoring, domain filtering
- `get_context.py`: 4-category context (decisions, questions, insights, failures), ~200 token budget
- `inspect_node.py`: Full node metadata, incoming/outgoing edge classification, promotion history extraction
- `save_session.py`: UPSERT to sessions table, JSON serialization of decisions/unresolved lists
- `suggest_type.py`: Delegates to remember() with Unclassified type, records attempted_type metadata
- `visualize.py`: pyvis HTML graph generation, type-based coloring, center-node BFS traversal

**I-07** graph_bonus correctly handled at storage layer, not recall layer

- b-r3-15 spec does not mention graph_bonus in recall.py
- graph_bonus (GRAPH_BONUS=0.015) is applied inside `hybrid_search()` at `storage/hybrid.py:438`
- recall.py correctly delegates to hybrid_search without separate graph_bonus application

## Coverage

- Files reviewed: 10/10 tools + server.py routing + 3 spec documents
- Functions verified: 18 public + 10 internal helpers
- Spec sections checked: a-r3-18 (remember), b-r3-15 (recall), c-r3-11 (promote + analyze)

## Summary

- CRITICAL: 0
- HIGH: 1
- MEDIUM: 3
- LOW: 2
- INFO: 7

**Top 3 Most Impactful Findings:**

1. **H-01** (promote_node missing action_log): The most significant state change (type promotion) has zero audit trail. ACTION_TAXONOMY defines the exact action types (`node_promoted`, `edge_realized`) but they are never recorded. This is a spec-level omission carried into implementation.
2. **M-01** (gates_passed misleading): When MDL gate is skipped (no related_ids), the response still claims all 3 gates passed. This gives false confidence in the promotion's validation rigor.
3. **M-02** (tier not updated on promotion): A promoted node retains its old tier until the next batch update_tiers() run, creating a window where tier-based logic (access control, pruning) operates on stale data.

**Cross-reference with 01_storage findings:** H-01 here (missing action_log in promote_node) is independent of storage-layer findings. The BCM/UCB disconnect (01_storage H-01, H-02) does not affect tools-layer correctness, as tools delegate to hybrid_search without manipulating BCM/UCB directly.
