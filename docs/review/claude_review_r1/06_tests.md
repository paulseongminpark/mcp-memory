# Tests Review - Round 1 (Correctness)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Test Coverage & Correctness
> Files Reviewed: 7 test files, 117 total tests

## Findings

### [Severity: HIGH]

**H-01** No tests for promote_node.py (3-gate pipeline) or analyze_signals.py

- Missing: `tests/test_promote.py` or equivalent
- Description:
  - promote_node.py contains the most mathematically complex v2.1 code:
    - Gate 1 SWR: `readiness = 0.6 * vec_ratio + 0.4 * cross_ratio > 0.55`
    - Gate 2 Bayesian: `P = (1+k) / (11+n)` with Beta(1,10) prior
    - Gate 3 MDL: `avg_sim > 0.75` cosine similarity matrix
  - analyze_signals.py has `_recommend_v2()` with multi-condition promotion logic
  - These are the core v2.1 differentiators — untested
  - By contrast, remember.py (18 tests), recall.py (18 tests), hybrid.py (22 tests) have extensive coverage
- Impact: Gate formula bugs, threshold errors, or edge cases (e.g., zero related_ids, division by zero in Bayesian calc) would go undetected. The promotion pipeline is the path from Signal→Pattern→Principle — a correctness failure here permanently corrupts the ontology hierarchy.
- Recommendation: Create `tests/test_promote.py` with at minimum:
  - swr_readiness() with varying vec/cross ratios around 0.55 threshold
  - promotion_probability() with k=0, k=n, large n
  - _mdl_gate() with <2 nodes, no embeddings, avg_sim at 0.75 boundary
  - promote_node() full pipeline (all gates pass, each gate fail, skip_gates=True)
  - _recommend_v2() all 4 outcome paths

---

### [Severity: MEDIUM]

**M-01** test_hybrid.py has no test for hybrid_search() end-to-end or RRF merge

- File: `tests/test_hybrid.py` (22 tests)
- Description:
  - Tests cover: UCB_C modes (5), BCM updates (6), graph cache (1), UCB traverse (3), recall logging (1), SPRT (6)
  - Missing: `hybrid_search()` integration test — the main entry point that combines vec, FTS, RRF, graph_bonus, BCM, UCB, SPRT
  - Missing: `_rrf_merge()` formula test — the core ranking fusion formula `1/(RRF_K + rank)`
  - Missing: graph_bonus application test
  - Individual components are tested but never composed
- Impact: Component tests pass but integration could fail (e.g., wrong parameter passing between stages, RRF_K value mismatch).
- Recommendation: Add at least 3 integration tests: (1) hybrid_search with mocked vec+fts, verify RRF ordering, (2) graph_bonus adds correct delta, (3) full pipeline with BCM+UCB side effects.

---

**M-02** test_recall_v2.py doesn't verify graph_bonus or BCM trigger

- File: `tests/test_recall_v2.py` (18 tests)
- Description:
  - Excellent patch switching coverage (5 tests for _is_patch_saturated, 2 for _dominant_project)
  - recall() function tested for modes, formatting, increment
  - Missing: verification that hybrid_search is called with correct `mode` parameter for graph_bonus
  - Missing: BCM update triggered after successful recall
  - Missing: SPRT accumulation after recall results
- Impact: recall() works as a wrapper but its downstream effects (learning, promotion candidacy) are untested.

---

**M-03** Mock pattern inconsistency in test_validators_integration.py

- File: `tests/test_validators_integration.py` (13 tests)
- Description:
  - TC1-TC10 use `mock_validate()` — a custom mock function, NOT the actual `validate_node_type()`
  - TC11-TC13 use actual `suggest_closest_type()` — the real function
  - TC8-TC9 test suggest_closest_type with different content than the validate subject:
    ```python
    mock_validate("FooBar")  # unknown type
    suggest_closest_type("패턴 반복 발견")  # completely different content
    ```
  - The tests never call the real `validate_node_type()` against a database or schema.yaml
  - This means the type_defs query path, case-insensitive SQL, and schema.yaml fallback are all untested
- Impact: If `validate_node_type()` has a SQL bug (e.g., wrong column name, missing LOWER()), tests won't catch it. The mock reimplements the logic separately.
- Recommendation: Add integration tests that use a temporary SQLite DB with type_defs populated, testing the real function.

---

### [Severity: LOW]

**L-01** test_drift.py boundary values near DRIFT_THRESHOLD missing

- File: `tests/test_drift.py` (16 tests)
- Description:
  - Tests use cosine_similarity = 0.1 (drift) and 0.99 (no drift)
  - No test at threshold boundary: 0.49, 0.50, 0.51
  - DRIFT_THRESHOLD = 0.5 from config.py — threshold behavior at exact boundary untested
- Impact: Off-by-one at threshold (< vs <=) would go undetected.

---

**L-02** test_action_log.py only checks ACTION_TAXONOMY count, not contents

- File: `tests/test_action_log.py` test_taxonomy_count
- Description:
  - `assert len(ACTION_TAXONOMY) == 25` — only verifies count
  - Doesn't verify specific action types exist (e.g., "node_promoted", "edge_realized")
  - If a type is renamed or removed while another is added, the count stays 25 but semantics change
- Impact: ACTION_TAXONOMY could drift from spec without detection.

---

**L-03** test_access_control.py missing: hub protection when hub_snapshots table doesn't exist

- File: `tests/test_access_control.py` (23 tests)
- Description:
  - Hub protection tests (tc09, tc10, tc14) pre-populate hub_snapshots
  - No test for when hub_snapshots table doesn't exist at all
  - `_get_top10_hub_ids()` has `except Exception: return set()` for this case
  - The fallback is correct but untested
- Impact: If the except handler changes, tests won't catch the regression.

---

### [Severity: INFO]

**I-01** Test file → Source file coverage mapping

| Test File | Tests | Source File | Spec |
|-----------|-------|------------|------|
| test_hybrid.py | 22 | storage/hybrid.py | b-r3-14, c-r3-11 |
| test_access_control.py | 23 | utils/access_control.py | d-r3-13 |
| test_recall_v2.py | 18 | tools/recall.py | b-r3-15 |
| test_remember_v2.py | 18 | tools/remember.py | a-r3-18 |
| test_drift.py | 16 | utils/similarity.py + enrich | d-r3-12 |
| test_validators_integration.py | 13 | ontology/validators.py | d-r3-11 |
| test_action_log.py | 7 | storage/action_log.py | a-r3-17 |
| **Total** | **117** | | |

**I-02** Source files with ZERO test coverage

| Source File | Role | Criticality |
|------------|------|-------------|
| tools/promote_node.py | 3-gate promotion pipeline | **CRITICAL** |
| tools/analyze_signals.py | Signal cluster analysis | HIGH |
| storage/sqlite_store.py | DB CRUD operations | HIGH |
| storage/vector_store.py | Embedding storage | MEDIUM |
| tools/get_becoming.py | Promotable nodes query | LOW |
| tools/get_context.py | Session context | LOW |
| tools/inspect_node.py | Node inspection | LOW |
| tools/save_session.py | Session saving | LOW |
| tools/suggest_type.py | Type suggestion | LOW |
| tools/visualize.py | Graph visualization | LOW |
| server.py | MCP routing | MEDIUM |

**I-03** test_hybrid.py SPRT coverage is thorough

- 6 SPRT tests cover: non-Signal skip, insufficient observations, promote on high scores, reject on low scores, score_history JSON serialization, constants verification
- All SPRT thresholds (A≈2.773, B≈-1.558) are verified in test_sprt_constants
- MIN_OBS=5 enforcement tested

**I-04** test_remember_v2.py F3 firewall coverage is complete

- F3-a (new node L4/L5): 2 tests (L4, L5 → empty edges)
- F3-b (similar node L4/L5): 1 test (L4 similar → skipped)
- FIREWALL_PROTECTED_LAYERS constant: verified as {4, 5}
- action_log integration: 2 tests (node_created, edge_auto)

**I-05** test_access_control.py is the most comprehensive test file

- 23 tests covering all 3 layers (firewall, hub, permissions)
- Actor prefix matching ("enrichment:E7" → "enrichment")
- require_access() PermissionError verified
- Edge case: non-existent node defaults to L0

**I-06** test_recall_v2.py patch switching well-tested

- _is_patch_saturated: 5 tests (boundary at 75%, <3 results, empty project)
- _dominant_project: 2 tests
- Patch switch triggers second hybrid_search with excluded_project
- Content truncation at 200 chars verified
- Related edges max 3 verified

## Coverage

- Test files reviewed: 7/7
- Total tests: 117 (22+23+18+18+16+13+7)
- Source coverage: 7/18 production files have tests (39%)
- Spec coverage: 7/10 specs have at least one test file
- Untested specs: c-r3-11 promotion (partially via SPRT in test_hybrid), c-r3-10 eval, d-r3-14 pruning

## Summary

- CRITICAL: 0
- HIGH: 1
- MEDIUM: 3
- LOW: 3
- INFO: 6

**Top 3 Most Impactful Findings:**

1. **H-01** (No promote_node tests): The 3-gate promotion pipeline — v2.1's core mathematical engine — has zero tests. Gate formulas (SWR threshold 0.55, Bayesian Beta(1,10), MDL cosine 0.75), the promotion state machine, and the interaction with VALID_PROMOTIONS are all untested. This is the highest-risk gap in the test suite.

2. **M-01** (No hybrid_search integration test): Individual BCM, UCB, SPRT components are tested, but the full hybrid_search pipeline that composes them is never tested end-to-end. RRF merge formula and graph_bonus application are also untested.

3. **M-03** (Mock vs real validators): test_validators_integration.py tests a custom mock function instead of the actual `validate_node_type()`. The real function's SQL queries, type_defs table interaction, and schema.yaml fallback path are never exercised by any test.

**Cumulative Findings (T1-C-01 through T1-C-06):**
- CRITICAL: 0
- HIGH: 6
- MEDIUM: 16
- LOW: 13
- INFO: 43
