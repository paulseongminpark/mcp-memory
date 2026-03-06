# Storage Layer Review - Round 1 (Correctness)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Correctness & Completeness
> Files Reviewed: storage/sqlite_store.py, storage/hybrid.py, storage/vector_store.py, storage/action_log.py, graph/traversal.py

## Findings

### [Severity: HIGH]

**H-01** UCB visit_count not loaded into graph — exploration degenerates to constant

- File: `graph/traversal.py:11-21`, `storage/hybrid.py:31-44` (`_get_graph`), `storage/hybrid.py:120,130` (`_ucb_traverse`)
- Spec: `docs/ideation/b-r3-14-hybrid-final.md` UCB formula
- Description:
  - UCB formula reads `graph.nodes[nid].get("visit_count", 1)` (L120, L130)
  - `_bcm_update()` correctly writes `visit_count` to DB (L266-268): `UPDATE nodes SET visit_count = COALESCE(visit_count,0)+1`
  - However, `build_graph()` in `graph/traversal.py` only loads **edge attributes** (strength, relation, description) — **no node attributes** are loaded
  - Result: `visit_count` always defaults to 1 for all nodes
  - UCB score degenerates to: `w_ij + c * sqrt(ln(2)/2)` = `w_ij + c * 0.589` (constant for all neighbors)
  - The exploration/exploitation tradeoff — UCB's core value proposition — is completely lost
- Impact: UCB cannot distinguish between frequently-visited and rarely-visited nodes. All neighbor exploration scores receive identical UCB bonus, making the "Upper Confidence Bound" mechanism ineffective. Graph traversal becomes a simple edge-strength ranking.
- Recommendation: Modify `_get_graph()` to load node attributes (at minimum `visit_count`) after `build_graph()`, or modify `build_graph()` to accept and attach node data.

---

**H-02** BCM updates `frequency` but UCB reads `strength` — learning doesn't propagate

- File: `storage/hybrid.py:231-241` (`_bcm_update`), `storage/hybrid.py:124-129` (`_ucb_traverse`)
- Spec: `docs/ideation/b-r3-14-hybrid-final.md` BCM formula dw/dt
- Description:
  - BCM learning rule computes: `delta_w = eta * v_i * (v_i - theta_m) * v_j` (L231)
  - This delta is applied to `edges.frequency`: `new_freq = max(0.0, freq + delta_w * 10)` (L232)
  - UPDATE SQL: `UPDATE edges SET frequency=?, last_activated=? WHERE id=?` (L238-241)
  - But UCB traversal reads `edges.strength`: `w_ij = graph.edges[nid,nbr].get("strength", 0.1)` (L125)
  - `edges.strength` is never modified by BCM — it stays at its initial value
  - BCM's theoretical purpose (strengthening/weakening synaptic connections based on co-activation) has no effect on subsequent graph traversal
- Impact: The Hebbian/BCM learning loop (a core v2.1 feature) does not influence search quality over time. Edges that are frequently co-activated with successful recalls don't become stronger in graph traversal.
- Recommendation: Either (a) BCM should update `strength` instead of `frequency`, or (b) UCB should read a combined metric of `strength` and `frequency`, or (c) if `frequency` is intentionally separate from `strength`, document this design decision and explain how BCM learning is meant to propagate.

---

### [Severity: MEDIUM]

**M-01** BCM delta_w * 10 undocumented scaling factor

- File: `storage/hybrid.py:232`
- Spec: `docs/ideation/b-r3-14-hybrid-final.md` BCM formula
- Description:
  - Code: `new_freq = max(0.0, (edge.get("frequency") or 0) + delta_w * 10)`
  - The `* 10` multiplier is not present in the BCM mathematical formula `dw = eta * v_i * (v_i - theta_m) * v_j`
  - This changes the effective learning rate by 10x from what LAYER_ETA values suggest
  - Example: L2 eta=0.010 becomes effectively 0.10 per update
- Impact: Actual learning dynamics differ from what LAYER_ETA values imply. If a developer tunes LAYER_ETA based on BCM theory, the `*10` hidden multiplier would cause unexpected behavior.
- Recommendation: Either remove the `*10` and adjust LAYER_ETA values, or document the scaling factor as a deliberate design choice.

---

### [Severity: LOW]

**L-01** action_log.record() accepts arbitrary action_type strings

- File: `storage/action_log.py:48-61`
- Spec: `docs/ideation/a-r3-17-actionlog-record.md`
- Description:
  - `record()` does not validate `action_type` against `ACTION_TAXONOMY` before INSERT
  - Any arbitrary string can be stored as `action_type`
  - The spec doesn't explicitly require validation, but defines ACTION_TAXONOMY as the canonical list
- Impact: Typos or undefined action types silently persist in the action_log table, reducing data quality for analytics queries.
- Recommendation: Add optional validation: `if action_type not in ACTION_TAXONOMY: log warning` (without blocking).

---

**L-02** RRF_K=60 in config vs k=30 in master plan E2E scenarios

- File: `config.py:22` (`RRF_K = 60`)
- Spec: Master plan Section 5, S1 states `_rrf_merge() -> k=30`
- Description:
  - config.py defines `RRF_K = 60` (standard value from original RRF paper)
  - Master plan E2E scenario S1 incorrectly describes `k=30`
  - The b-r3-14 spec imports RRF_K from config without specifying a value
- Impact: Documentation inconsistency only. Code uses the academically standard k=60.
- Recommendation: Update master plan E2E scenario descriptions to reflect actual k=60.

---

### [Severity: INFO]

**I-01** SPRT implementation matches spec exactly

- File: `storage/hybrid.py:283-286,289-327,474-491`
- Verification:
  - Signal-only double guard: caller check (L478) + internal check (L298)
  - SPRT_MIN_OBS=5 enforced (L316)
  - A = log((1-0.2)/0.05) = log(16) ≈ 2.773 ✓
  - B = log(0.2/0.95) ≈ -1.558 ✓
  - LLR_POS = log(0.7/0.3) ≈ 0.847 ✓
  - LLR_NEG = log(0.3/0.7) ≈ -0.847 ✓
  - score_history JSON serialization + 50-observation cap ✓
  - promotion_candidate=1 on SPRT pass ✓

**I-02** UCB formula correctly implements spec

- File: `storage/hybrid.py:131`
- `score = w_ij + c * math.sqrt(math.log(n_i + 1) / (n_j + 1))` matches `w_ij + c * sqrt(ln(N_i+1)/(N_j+1))`
- UCB_C values: FOCUS=0.3, AUTO=1.0, DMN=2.5 match spec

**I-03** BCM theta_m sliding squared mean matches theory

- File: `storage/hybrid.py:234-236`
- `sum(h**2 for h in history) / len(history)` correctly computes E[v^2] over sliding window
- BCM_HISTORY_WINDOW=20 matches spec

**I-04** action_log fully matches a-r3-17 spec

- 25 ACTION_TAXONOMY types: exact match
- 12-parameter record() signature: exact match
- Graceful degradation (Exception → None): exact match
- External transaction support (conn parameter): exact match

**I-05** vector_store.get_node_embedding() matches d-r3-12 spec

- File: `storage/vector_store.py:59-74`
- Signature: `(node_id: int) -> list[float] | None` ✓
- Error handling: Exception → None ✓
- ChromaDB collection: cosine distance (`hnsw:space: cosine`) ✓

**I-06** insert_edge relation validation well-implemented

- File: `storage/sqlite_store.py:253-280`
- Undefined relation → `connects_with` fallback ✓
- correction_log entry for original vs fallback ✓
- ALL_RELATIONS from config.py used as canonical set ✓

**I-07** LAYER_ETA placement diverges from spec (minor)

- Spec (b-r3-14) defines LAYER_ETA inside hybrid.py code section
- Implementation places it in config.py (line 34)
- This is arguably an improvement (centralized config) but diverges from spec letter

## Coverage

- Files reviewed: 4/4 storage + 1 dependency (graph/traversal.py)
- Functions verified: 16/16 (all public functions + key internal: _bcm_update, _ucb_traverse, _sprt_check, _get_graph, _auto_ucb_c, build_graph)
- Spec sections checked: 4/4 (a-r3-17, b-r3-14, c-r3-11, d-r3-12)

## Summary

- CRITICAL: 0
- HIGH: 2
- MEDIUM: 1
- LOW: 2
- INFO: 7

**Top 3 Most Impactful Findings:**

1. **H-01** (UCB visit_count not loaded): UCB's exploration/exploitation mechanism is dead — all nodes get identical exploration bonus, defeating the purpose of the Upper Confidence Bound algorithm.
2. **H-02** (BCM→frequency, UCB→strength): BCM learning loop is disconnected from graph traversal — the system learns but the learned weights are never used, making the neural plasticity feature non-functional.
3. **M-01** (delta_w * 10): Hidden scaling factor changes effective learning dynamics from what LAYER_ETA values suggest, creating a mismatch between documented and actual behavior.

**Note for Round 2**: H-01 and H-02 together mean that the BCM+UCB learning pipeline — the core differentiator of v2.1's "neural-inspired" search — is effectively non-functional. The search still works (via RRF + static edge strength), but the adaptive learning that should improve with use is broken. This is a critical architectural issue to be further analyzed in Round 2.
