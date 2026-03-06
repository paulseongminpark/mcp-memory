# Tests Review - Round 1 (Correctness)
> Reviewer: Codex
> Date: 2026-03-06
> Files Reviewed: tests/test_access_control.py, tests/test_action_log.py, tests/test_drift.py, tests/test_hybrid.py, tests/test_recall_v2.py, tests/test_remember_v2.py, tests/test_validators_integration.py

## Findings
### CRITICAL
- None.

### HIGH
- There are no tests for the real `promote_node()` runtime path, `get_becoming()`, `get_context()`, `inspect_node()`, `save_session()`, `suggest_type()`, `visualize()`, `sqlite_store.init_db()`, `server.py` MCP wrappers, `scripts/pruning.py`, `scripts/daily_enrich.py`, or `scripts/hub_monitor.py`. Large parts of the Round 3 surface are untested.
- `tests/test_hybrid.py:17-56` uses a custom fixture schema that includes `nodes.last_activated`, even though the bootstrap schema in `storage/sqlite_store.py` does not. The test suite therefore misses the production failure that rolls back `_bcm_update()`.
- `tests/test_recall_v2.py` patches `_increment_recall_count()`, so the missing `meta`/`stats` storage integration is never verified end-to-end.
- `tests/test_validators_integration.py:27-48` mostly tests `mock_validate()` / `mock_validate_relation()`. The real `validate_node_type()` query path, empty-table behavior, and schema fallback logic are effectively untested.
- `tests/test_remember_v2.py:71-72` encodes `Project -> layer is None` as expected behavior, which bakes the broken type map into the suite instead of catching it.

### MEDIUM
- Access-control tests cover the implemented F1 rules well, but they do not test the broader A-10/F2-F6 intent. They also explicitly treat missing-node access as acceptable layer-0 behavior.

### LOW
- Unit coverage is strong for `access_control`, `hybrid` internals, drift handling, recall formatting, and remember decomposition.

### INFO
- Counted 117 test functions across 7 files, matching the stated suite size.

## Coverage
### `tests/test_access_control.py`
| Test | Verifies |
|---|---|
| `test_tc_firewall_l0_always_passes` | L0-L3 bypass F1 firewall |
| `test_tc_firewall_l4_content_paul_only` | L4 content ops are paul-only |
| `test_tc_firewall_l4_meta_paul_claude` | L4 metadata ops allow paul and claude |
| `test_tc_firewall_l4_read_all` | L4 reads allow all actors |
| `test_tc_firewall_l5_content_paul_only` | L5 content ops are paul-only |
| `test_tc_perm_actor_prefix_matching` | `enrichment:E7` prefix handling in permissions |
| `test_tc_perm_l2_delete_paul_only` | L2 delete is paul-only |
| `test_tc_perm_unknown_operation_paul_only` | Unknown ops default to paul-only |
| `test_tc01_l0_read_all_actors` | End-to-end L0 read access |
| `test_tc02_l4_write_paul_allowed` | L4 write allowed for paul |
| `test_tc03_l4_write_claude_blocked` | L4 write blocked for claude |
| `test_tc04_l4_write_enrichment_blocked` | L4 write blocked for enrichment |
| `test_tc05_l4_modify_metadata_claude_allowed` | L4 metadata write allowed for claude |
| `test_tc06_l5_delete_paul_allowed` | L5 delete allowed for paul |
| `test_tc07_l5_delete_claude_blocked` | L5 delete blocked for claude |
| `test_tc08_l2_delete` | L2 delete allows paul and blocks enrichment |
| `test_tc09_hub_top10_write_blocked` | Hub top-10 write/delete are blocked |
| `test_tc10_hub_top10_read_allowed` | Hub top-10 reads are allowed |
| `test_tc11_node_not_in_db_defaults_l0` | Missing node defaults to layer 0 |
| `test_tc14_hub_top10_write_paul_also_blocked` | Hub block also applies to paul |
| `test_tc15_l0_write_enrichment_allowed` | L0 write allowed for enrichment |
| `test_tc13_require_access_raises_permission_error` | `require_access()` raises on deny |
| `test_tc_require_access_passes_silently` | `require_access()` is silent on allow |

### `tests/test_action_log.py`
| Test | Verifies |
|---|---|
| `test_record_basic` | Minimal `record()` insert works |
| `test_record_full_params` | Full parameter set is stored correctly |
| `test_record_with_external_conn` | Logging can join an external transaction |
| `test_record_silent_fail` | DB failure returns `None` without raising |
| `test_record_default_params_result` | Default `params` and `result` are `{}` |
| `test_taxonomy_count` | Taxonomy size is 25 |
| `test_record_created_at_populated` | `created_at` is auto-filled |

### `tests/test_drift.py`
| Test | Verifies |
|---|---|
| `test_td01_identical_vectors` | Cosine similarity is `1.0` for identical vectors |
| `test_td02_orthogonal_vectors` | Cosine similarity is `0.0` for orthogonal vectors |
| `test_td03_mismatched_length` | Mismatched vector lengths return `0.0` |
| `test_td04_similarity_range` | Similarity stays in `[-1, 1]` |
| `test_td04_opposite_vectors` | Opposite vectors return `-1.0` |
| `test_td05_median_length_insufficient_sample` | Summary median returns `None` under min sample |
| `test_td06_median_length_sufficient_sample` | Summary median is computed with enough samples |
| `test_td07_validate_summary_normal` | Normal summary length passes validation |
| `test_td08_validate_summary_anomaly` | Overlong summary is rejected |
| `test_td09_validate_summary_no_sample` | No-sample case skips summary validation |
| `test_td10_e7_drift_blocks_chroma_update` | Drift blocks `vector_store.add()` |
| `test_td11_e7_no_drift_updates_chroma` | No drift updates Chroma |
| `test_td12_e7_no_old_embedding_always_updates` | Missing old embedding still updates Chroma |
| `test_td13_e1_normal_summary_applied` | E1 applies a normal summary |
| `test_td14_e1_anomaly_summary_not_applied` | E1 anomaly logs correction and keeps old summary |
| `test_td15_combined_e1_anomaly_keeps_old_summary` | Combined enrichment preserves old summary on anomaly |

### `tests/test_hybrid.py`
| Test | Verifies |
|---|---|
| `test_auto_ucb_c_focus_mode` | Explicit `focus` returns `UCB_C_FOCUS` |
| `test_auto_ucb_c_dmn_mode` | Explicit `dmn` returns `UCB_C_DMN` |
| `test_auto_ucb_c_long_query_auto` | Long query auto-switches to focus |
| `test_auto_ucb_c_short_query_auto` | Short query auto-switches to dmn |
| `test_auto_ucb_c_medium_query_auto` | Medium query auto-stays balanced |
| `test_bcm_update_frequency_changes` | BCM changes edge frequency |
| `test_bcm_update_theta_m_changes` | BCM changes `theta_m` |
| `test_bcm_update_visit_count_incremented` | BCM increments node `visit_count` |
| `test_bcm_update_reconsolidation` | BCM appends reconsolidation context |
| `test_bcm_update_empty_ids` | Empty BCM input is a no-op |
| `test_bcm_update_no_query_skips_reconsolidation` | Empty query skips reconsolidation |
| `test_get_graph_cache` | Graph cache avoids rebuild on second call |
| `test_ucb_traverse_basic` | UCB traversal reaches 1-hop and 2-hop neighbors |
| `test_ucb_traverse_empty_seeds` | Empty seeds return an empty set |
| `test_ucb_traverse_dmn_prefers_unvisited` | High-`c` traversal prefers unvisited nodes |
| `test_log_recall_activations` | Recall logging writes recall and node activations |
| `test_sprt_check_non_signal_skipped` | Non-signal nodes skip SPRT |
| `test_sprt_check_insufficient_obs` | Fewer than min observations do not promote |
| `test_sprt_check_promote_high_scores` | High score history promotes |
| `test_sprt_check_reject_low_scores` | Low score history rejects |
| `test_sprt_check_updates_score_history` | SPRT persists score history |
| `test_sprt_constants` | SPRT thresholds match expected math |

### `tests/test_recall_v2.py`
| Test | Verifies |
|---|---|
| `test_less_than_3_results` | Saturation is false for fewer than 3 results |
| `test_exact_75_percent` | Saturation is true at exactly 75 percent |
| `test_below_75_not_saturated` | Saturation is false below threshold |
| `test_100_percent_saturated` | Saturation is true at 100 percent |
| `test_empty_project_counted` | Empty project names count toward saturation |
| `test_dominant` | Dominant project is selected correctly |
| `test_single_project` | Single-project result returns that project |
| `test_empty_results` | Empty recall returns the no-results payload |
| `test_basic_format` | Recall response shape and count |
| `test_mode_passed_to_hybrid` | `mode` is forwarded to `hybrid_search()` |
| `test_mode_dmn_passed` | `dmn` mode is forwarded |
| `test_no_patch_when_project_specified` | Explicit project disables patch switching |
| `test_patch_switch_on_saturation` | Saturation triggers second search with exclusion |
| `test_patch_no_switch_top_k_2` | `top_k=2` disables patch switching |
| `test_increment_recall_called` | Recall counter helper is called |
| `test_content_truncated_200` | Content is truncated to 200 chars |
| `test_related_edges_max_3` | Related edge preview is capped at 3 |
| `test_graceful_skip_on_exception` | Counter helper suppresses storage exceptions |

### `tests/test_remember_v2.py`
| Test | Verifies |
|---|---|
| `test_classify_no_db` | `classify()` handles Principle with layer 3 / tier 0 |
| `test_classify_type_correction_deprecated` | Invalid type is corrected via content suggestion |
| `test_classify_case_correction` | Case-only type correction works |
| `test_classify_value_layer5_tier0` | Value maps to layer 5 / tier 0 |
| `test_classify_observation_tier2` | Observation maps to tier 2 |
| `test_classify_unknown_type_no_layer` | Project is currently expected to get `layer=None` |
| `test_f3a_l4_no_auto_edges` | Layer-4 node blocks auto edges |
| `test_f3a_l5_no_auto_edges` | Layer-5 node blocks auto edges |
| `test_f3_protected_layers_constant` | Protected layer set is `{4, 5}` |
| `test_f3b_skips_l4_similar_node` | Protected similar targets are skipped |
| `test_link_vector_failure_returns_empty` | Vector failure yields empty auto edges |
| `test_basic_return_format` | `remember()` response shape |
| `test_invalid_type_correction` | Unknown type is corrected before storing |
| `test_chromadb_failure_graceful` | Chroma failure returns warning and no auto edges |
| `test_action_log_node_created` | `node_created` logging occurs |
| `test_action_log_edge_auto` | `edge_auto` logging occurs |
| `test_store_independent` | `store()` works with a `ClassificationResult` |
| `test_link_returns_list` | `link()` always returns a list |

### `tests/test_validators_integration.py`
| Test | Verifies |
|---|---|
| `test_tc1_exact_match` | Mock exact-match node type validation |
| `test_tc2_unclassified_default` | Mock `Unclassified` acceptance |
| `test_tc3_lowercase` | Mock lowercase-to-canonical correction |
| `test_tc4_allcaps` | Mock uppercase-to-canonical correction |
| `test_tc5_mixed_case` | Mock mixed-case correction |
| `test_tc6_deprecated_with_replacement` | Mock deprecated type replacement |
| `test_tc7_deprecated_case_insensitive` | Mock deprecated replacement with case-insensitive lookup |
| `test_tc8_completely_unknown` | Mock unknown type rejection plus suggestion |
| `test_tc9_typo` | Mock typo rejection plus suggestion |
| `test_tc10_edge_relation_fallback` | Mock relation deprecation and unknown-relation fallback |
| `test_suggest_decision` | Keyword suggestion returns Decision |
| `test_suggest_failure` | Keyword suggestion returns Failure |
| `test_suggest_unclassified` | Non-matching content suggests Unclassified |

Untested code paths:
- Real `promote_node()` gate behavior and success path.
- Real `validate_node_type()` / `validate_relation()` against populated and empty ontology tables.
- `sqlite_store.init_db()` bootstrap correctness.
- Public MCP wrappers in `server.py`.
- Phase 6 pruning, hub monitoring, and ontology review scripts.
- Remaining tool modules: `get_context`, `get_becoming`, `inspect_node`, `save_session`, `suggest_type`, `visualize`.

Mock correctness notes:
- `tests/test_hybrid.py` uses a fixture schema that is richer than production bootstrap and therefore hides the missing-column defect.
- `tests/test_recall_v2.py` intentionally mocks out counter persistence, so storage integration is not asserted.
- `tests/test_validators_integration.py` validates mock helpers more than production validator behavior.
- `tests/test_remember_v2.py` codifies `Project -> layer=None`, which reflects current code rather than the ontology spec.

## Summary
The suite is large and useful, but it is strongest on local unit behavior and weakest on bootstrap, migration, and end-to-end integration. The most important production failures in this review are either untested or actively masked by mocks/fixture schemas.
