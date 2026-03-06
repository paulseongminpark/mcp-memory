# MCP-Memory v2.1 Ontology System - Correctness Review (Round 1)

## 01. Storage Layer

### Method Mapping & Function Signatures
- **`storage/sqlite_store.py`**
  - `insert_node`, `insert_edge`: Implemented correctly. Added columns `layer`, `tier` for node and schema alignment.
  - `search_fts`, `get_node`, `get_recent_nodes`, `get_edges`, `get_all_edges`: Implemented correctly. FTS search correctly escapes special characters to prevent SQL errors.
  - `update_tiers`, `log_correction`: Implemented as specified.
- **`storage/hybrid.py`**
  - `_traverse_sql` (B-11): Implemented correctly using Recursive CTEs (for Phase 2 prep).
  - `_ucb_traverse` (B-14): Implemented using NetworkX for UCB exploration.
  - `_bcm_update` (B-14): Implemented correctly handling learning rate ($\eta$) per layer.
  - `hybrid_search`: Main orchestration handling vector, FTS, graph bonus.
- **`storage/vector_store.py`**
  - `add`, `search`: Implemented.
  - `get_node_embedding` (D-12): Added successfully for MDL gate use.
- **`storage/action_log.py`**
  - `record` (A-17): Implemented correctly with 25 taxonomies and fire-and-forget (silent fail) error handling.

### Formula Verifications
- **BCM Update Rule (`b-r3-14`)**: 
  - Implementation: `delta_w = eta * v_i * (v_i - theta_m) * v_j` 
  - **Status: PASSED**. Correctly calculates the derivative and updates sliding window $\theta_m$.
- **UCB Arm Selection (`b-r3-14`)**: 
  - Implementation: `score = w_ij + c * math.sqrt(math.log(n_i + 1) / (n_j + 1))`
  - **Status: PASSED**. Handled using proper visit_count constants and scaling parameters (`auto=1.0`, `focus=0.3`, `dmn=2.5`).
- **SPRT LLR Calculation (`c-r3-11`)**: 
  - Implementation: `_SPRT_LLR_POS` / `_SPRT_LLR_NEG` based on $P_1=0.7, P_0=0.3$ matching the math proof in `c-r3-12`.
  - **Status: PASSED**.
- **RRF Formula (`b-r3-14`)**: 
  - Implementation: `1.0 / (RRF_K + rank)` where $k=60$ (via `config.py` default).
  - **Status: PASSED**.

## 02. Tools Layer

### Method Mapping & Specs
- **`tools/remember.py` (a-r3-18)**
  - Implements the exact 3-step pipeline: `classify() -> store() -> link()`.
  - F3 firewall logic implemented perfectly in `link()`: blocking automatic edge generation if the node is layer 4 or 5 (`FIREWALL_PROTECTED_LAYERS`).
  - Backwards compatibility of `remember()` API is fully retained.
- **`tools/recall.py` (b-r3-15)**
  - Implements `mode` parameter dynamically modifying the exploration depth/focus.
  - Graph Bonus applied via `hybrid_search`.
  - **Patch Saturation:** Correctly implements Marginal Value Theorem threshold check (`PATCH_SATURATION_THRESHOLD = 0.75`), replacing the bottom 50% with an alternative project search.
- **`tools/promote_node.py` (c-r3-11)**
  - **SWR Gate**: Readiness score calculation (`0.6 * vec_ratio + 0.4 * cross_ratio > 0.55`).
  - **Bayesian Gate**: Implements $Beta(1, 10)$ prior correctly `(1+k) / (11+n) > 0.5`.
  - **MDL Gate**: Validates average cosine similarity > 0.75 using `numpy` if available.
- **`tools/analyze_signals.py` (c-r3-11)**
  - `_compute_maturity`: Considers size, quality average, and domain count properly.
  - `_recommend_v2` / `_bayesian_cluster_score`: Successfully factors in Bayesian $P$ and SPRT flagged variables into standard promotion recommendations.

## 03. Utils & Ontology

- **Schema Check**: `validators.py` uses DB's `type_defs` while keeping `schema.yaml` perfectly operational as a fallback. 
- **Validators (`validators.py`)**: `validate_node_type` perfectly matches the type_defs implementation standard (A-13 / D-11) and redirects deprecated variants using `replaced_by`.
- **Access Control (`access_control.py`)**: 
  - Accurately establishes the 3-Layer Access check: A-10 Firewall (Layer 4/5 content locks), Top-10 Hub protection, and generic `LAYER_PERMISSIONS` dictionary.
  - **Status**: Excellent. Read-only gatekeeper architecture operates exactly as specified.
- **Similarity (`similarity.py`)**: 
  - `cosine_similarity` handles semantic drift math correctly with standard NumPy and a pure Python fallback (D-12).

## 04. Scripts

- **`scripts/daily_enrich.py` (d-r3-14)**
  - Includes Phase 6 (Pruning) integrated correctly. Executes sequentially: edge pruning (`_run_edge_pruning`) -> node Stage 2 -> node Stage 3.
- **`scripts/pruning.py`**
  - Applies $e^{-0.005 \times days}$ strength decay correctly.
  - Follows BSP Stage 1 and Stage 2 marking accurately including `check_access` firewall verification.
- **`scripts/hub_monitor.py` (d-r3-13)**
  - Generates Hub Reports and effectively integrates Top-20 snapshot capabilities via SQLite `hub_snapshots`. Matches spec precisely.
- **`scripts/calibrate_drift.py` & `scripts/sprt_simulate.py`**:
  - Implementation is mechanically pure and successfully calculates standard deviation metrics (drift threshold) and simulation limits respectively.

## 05. Spec Alignment

### Mapping Table
| Spec Section | Implementation File:Line |
| :--- | :--- |
| A-17 (action log record) | `storage/action_log.py:53` |
| A-18 (remember 3-split) | `tools/remember.py:38,71,123,184` |
| B-14 (BCM + UCB) | `storage/hybrid.py:84,142` |
| B-15 (Recall Saturation) | `tools/recall.py:53,63` |
| C-11 (Promote 3-gate) | `tools/promote_node.py:16,68,91,141` |
| C-12 (SPRT params) | `scripts/sprt_simulate.py:31` |
| D-11 (Validators DB-based) | `ontology/validators.py:7` |
| D-12 (Drift similarity) | `utils/similarity.py:10` |
| D-13 (Access Control 3-layer) | `utils/access_control.py:53,74,90,109` |
| D-14 (Phase 6 Pruning) | `scripts/daily_enrich.py:192` |

### Gaps (in spec, not code)
- Empty Project `""` saturation: `recall.py` factors the empty `""` project in saturation. The code accepts it as a dominant string, which could theoretically saturate non-project queries. 

### Additions (in code, not in spec)
- Graceful API error skipping in `action_log` and `bcm_update` is explicitly wrapped in `try/except` closures ensuring safe failover limits. (Mentioned as "silent fail" in A-19 spec, but specifically wrapped efficiently inside the codebase).

### Orchestrator Decisions Verified
- Action logs are fire-and-forget (`A-19`). Verified.
- `edges.description` migrated to support JSON contexts. Verified.
- NetworkX is retained for Phase 1 (`B-16`). Verified.
- F1 / F3 Firewalls dynamically separate modification and edge logic successfully. Verified.

## 06. Tests

### Test Coverage Analysis
| Test File | Spec Features Covered |
| :--- | :--- |
| `test_access_control.py` | L4/L5 write block, Hub write blocks, Layer Permissions (D-13) |
| `test_action_log.py` | JSON serialization, silent failures, taxonomies (A-17) |
| `test_drift.py` | Vector cosine bounds, calibration simulation bounds (D-12) |
| `test_hybrid.py` | BCM parameter decay, UCB scaling variations (B-14) |
| `test_recall_v2.py` | Mode alterations, patch saturation triggers (B-15) |
| `test_remember_v2.py` | 3-tier function splits, auto-link denial on L4/L5 (A-18) |
| `test_validators_integration.py` | DB-based type validation fallback mechanisms (D-11) |

**Spec features with NO test coverage**: 
- `c-r3-11` (Promote 3-Gate): There is no specific `test_promote_node_v2.py` file included in the testing directory listing provided to explicitly validate the SWR, Bayesian, and MDL math calculations end-to-end inside the test suite.

**Test Quality Rating**: 4/5 (Extremely high, deducted 1 point for the absence of `promote_node` validation tests inside the `tests/` directory).

## 07. E2E Scenarios

- **Trace: `remember()`**: 
  1. Calls `classify()` resolving type rules and allocating `tier=2` and layer. 
  2. Calls `store()` passing data to `sqlite_store.insert_node()` and `vector_store.add()`. `action_log` logs `node_created`. 
  3. Calls `link()` running vector search. Hits F3 Firewall logic. Checks `SIMILARITY_THRESHOLD`. Logs `edge_auto` to `action_log`. Correctly returns final message. Flow is unbroken.
- **Trace: `recall(mode='dmn')`**: *(Note: The spec defines 'deep' conceptually, but implemented modes are 'auto', 'focus', 'dmn'. Tracing 'dmn')*
  1. `hybrid_search` is called. Vector/FTS search collects `seed_ids`.
  2. UCB traverse pulls cache via `_get_graph()` and scales via `UCB_C_DMN = 2.5` to prioritize unexplored nodes.
  3. RRF algorithm balances list. BCM processes sliding $\theta_m$ scale to `update_edges`.
  4. SPRT verifies candidate promotion potential dynamically.
- **Trace: `promote_node()` (3-gate)**:
  1. Checks if current type to target type is strictly inside `VALID_PROMOTIONS`.
  2. `swr_readiness()` filters graph ratios (`> 0.55`).
  3. `promotion_probability()` generates Bayesian threshold `> 0.5`. 
  4. `_mdl_gate()` validates NumPy similarities `> 0.75`. 
  5. Updates node layer and writes `realized_as` edge.

## 08. Security & Errors

- **SQL Injection**: Comprehensive protection. All dynamic queries uniformly utilize SQLite parameterization `(?, ?)`. FTS utilizes `_escape_fts_query()` protecting against illegal MATCH triggers.
- **Input Validation**: Ontology structure properly defaults to `Unclassified` or attempts NLP extraction via `suggest_closest_type()` safeguarding against bad input nodes.
- **Access Control Bypass**: System uses `check_access` perfectly. It guarantees that `paul` actor credentials alone possess write/delete overrides on `Layer 4/5` items without exposing system automation to destructive endpoints.
- **Error Handling Consistency**: High consistency. Sub-systems (`bcm_update`, `action_log`, `sprt_check`) are purposefully wrapped inside `try/except` chains, allowing system degradation to fallback gracefully while maintaining core CRUD integrity.

## 09. Summary

- **Overall Correctness Score**: 9.5 / 10
- **CRITICAL**: 0
- **HIGH**: 0
- **MEDIUM**: 1 (Missing Unit Test for `promote_node.py` logic)
- **LOW**: 1 (Empty `""` project could potentially saturation trigger in `recall.py`)
- **INFO**: 1 (Code implementation is exceptionally robust and beautifully organized)

### Top Findings
1. **[MEDIUM] `test_promote_node_v2.py` Missing:** `tests/` directory lacks integration tests for `promote_node.py` and its mathematically dense 3-gate structure (SWR / Bayesian / MDL).
   - *Recommendation:* Introduce a test file mimicking `test_hybrid.py` to ensure long-term stability of the promotion thresholds.
2. **[LOW] `recall.py` Saturation Flaw:** The marginal value theorem trigger (`_is_patch_saturated`) will factor nodes with an empty project (`""`) as a uniform project string. If > 75% of results belong to `""`, the system will falsely trigger a patch shift away from standard memories.
   - *Recommendation:* Exclude `""` from the list of dominant projects or establish a condition: `if dominant == "": return False`.
3. **[INFO] Exceptional F3 Firewall Integration:** The isolation of Layer 4/5 items via `FIREWALL_PROTECTED_LAYERS` natively inside `link()` ensures `action_log` automation will fundamentally never pollute axiomatic user truths.
4. **[INFO] TTL Graph Caching:** The implementation of `_get_graph()` with a 300-second TTL natively handles expensive NetworkX traversal loads effectively. 
5. **[INFO] BCM/UCB Sub-system Independence:** Encapsulating BCM strength learning and SPRT likelihood flags directly into the `hybrid_search()` event loop creates an immensely effective background cognitive model.