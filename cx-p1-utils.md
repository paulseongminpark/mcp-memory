# cx-p1-utils

## Task
Run:
`python -m pytest tests/test_access_control.py tests/test_drift.py -v`

## Environment
- Repo: `C:\dev\01_projects\06_mcp-memory`
- Commit: `564b387`
- Executed: `2026-03-05 23:34:53 +09:00`

## Result Summary
- Status: PASS
- Collected tests: 39
- Passed: 39
- Failed: 0
- Warnings: 1
- Duration: 2.09s

## Warning
- `PytestCacheWarning`: could not create `.pytest_cache\v\cache\nodeids` due to `[WinError 5] Access denied`.

## Raw Output
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\pauls\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: C:\dev\01_projects\06_mcp-memory
plugins: anyio-4.12.1
collecting ... collected 39 items

tests/test_access_control.py::test_tc_firewall_l0_always_passes PASSED   [  2%]
tests/test_access_control.py::test_tc_firewall_l4_content_paul_only PASSED [  5%]
tests/test_access_control.py::test_tc_firewall_l4_meta_paul_claude PASSED [  7%]
tests/test_access_control.py::test_tc_firewall_l4_read_all PASSED        [ 10%]
tests/test_access_control.py::test_tc_firewall_l5_content_paul_only PASSED [ 12%]
tests/test_access_control.py::test_tc_perm_actor_prefix_matching PASSED  [ 15%]
tests/test_access_control.py::test_tc_perm_l2_delete_paul_only PASSED    [ 17%]
tests/test_access_control.py::test_tc_perm_unknown_operation_paul_only PASSED [ 20%]
tests/test_access_control.py::test_tc01_l0_read_all_actors PASSED        [ 23%]
tests/test_access_control.py::test_tc02_l4_write_paul_allowed PASSED     [ 25%]
tests/test_access_control.py::test_tc03_l4_write_claude_blocked PASSED   [ 28%]
tests/test_access_control.py::test_tc04_l4_write_enrichment_blocked PASSED [ 30%]
tests/test_access_control.py::test_tc05_l4_modify_metadata_claude_allowed PASSED [ 33%]
tests/test_access_control.py::test_tc06_l5_delete_paul_allowed PASSED    [ 35%]
tests/test_access_control.py::test_tc07_l5_delete_claude_blocked PASSED  [ 38%]
tests/test_access_control.py::test_tc08_l2_delete PASSED                 [ 41%]
tests/test_access_control.py::test_tc09_hub_top10_write_blocked PASSED   [ 43%]
tests/test_access_control.py::test_tc10_hub_top10_read_allowed PASSED    [ 46%]
tests/test_access_control.py::test_tc11_node_not_in_db_defaults_l0 PASSED [ 48%]
tests/test_access_control.py::test_tc14_hub_top10_write_paul_also_blocked PASSED [ 51%]
tests/test_access_control.py::test_tc15_l0_write_enrichment_allowed PASSED [ 53%]
tests/test_access_control.py::test_tc13_require_access_raises_permission_error PASSED [ 56%]
tests/test_access_control.py::test_tc_require_access_passes_silently PASSED [ 58%]
tests/test_drift.py::test_td01_identical_vectors PASSED                  [ 61%]
tests/test_drift.py::test_td02_orthogonal_vectors PASSED                 [ 64%]
tests/test_drift.py::test_td03_mismatched_length PASSED                  [ 66%]
tests/test_drift.py::test_td04_similarity_range PASSED                   [ 69%]
tests/test_drift.py::test_td04_opposite_vectors PASSED                   [ 71%]
tests/test_drift.py::test_td05_median_length_insufficient_sample PASSED  [ 74%]
tests/test_drift.py::test_td06_median_length_sufficient_sample PASSED    [ 76%]
tests/test_drift.py::test_td07_validate_summary_normal PASSED            [ 79%]
tests/test_drift.py::test_td08_validate_summary_anomaly PASSED           [ 82%]
tests/test_drift.py::test_td09_validate_summary_no_sample PASSED         [ 84%]
tests/test_drift.py::test_td10_e7_drift_blocks_chroma_update PASSED      [ 87%]
tests/test_drift.py::test_td11_e7_no_drift_updates_chroma PASSED         [ 89%]
tests/test_drift.py::test_td12_e7_no_old_embedding_always_updates PASSED [ 92%]
tests/test_drift.py::test_td13_e1_normal_summary_applied PASSED          [ 94%]
tests/test_drift.py::test_td14_e1_anomaly_summary_not_applied PASSED     [ 97%]
tests/test_drift.py::test_td15_combined_e1_anomaly_keeps_old_summary PASSED [100%]

============================== warnings summary ===============================
..\..\..\Users\pauls\AppData\Local\Programs\Python\Python312\Lib\site-packages\_pytest\cacheprovider.py:475
  C:\Users\pauls\AppData\Local\Programs\Python\Python312\Lib\site-packages\_pytest\cacheprovider.py:475: PytestCacheWarning: could not create cache path C:\dev\01_projects\06_mcp-memory\.pytest_cache\v\cache\nodeids: [WinError 5] 액세스가 거부되었습니다: 'C:\\dev\\01_projects\\06_mcp-memory\\.pytest_cache\\v\\cache'
    config.cache.set("cache/nodeids", sorted(self.cached_nodeids))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 39 passed, 1 warning in 2.09s ========================
```
