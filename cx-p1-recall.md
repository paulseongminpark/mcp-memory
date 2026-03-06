============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\pauls\AppData\Local\Programs\Python\Python312\python.exe
rootdir: C:\dev\01_projects\06_mcp-memory
plugins: anyio-4.12.1
collecting ... collected 18 items

tests/test_recall_v2.py::TestIsPatchSaturated::test_less_than_3_results PASSED [  5%]
tests/test_recall_v2.py::TestIsPatchSaturated::test_exact_75_percent PASSED [ 11%]
tests/test_recall_v2.py::TestIsPatchSaturated::test_below_75_not_saturated PASSED [ 16%]
tests/test_recall_v2.py::TestIsPatchSaturated::test_100_percent_saturated PASSED [ 22%]
tests/test_recall_v2.py::TestIsPatchSaturated::test_empty_project_counted PASSED [ 27%]
tests/test_recall_v2.py::TestDominantProject::test_dominant PASSED       [ 33%]
tests/test_recall_v2.py::TestDominantProject::test_single_project PASSED [ 38%]
tests/test_recall_v2.py::TestRecall::test_empty_results PASSED           [ 44%]
tests/test_recall_v2.py::TestRecall::test_basic_format PASSED            [ 50%]
tests/test_recall_v2.py::TestRecall::test_mode_passed_to_hybrid PASSED   [ 55%]
tests/test_recall_v2.py::TestRecall::test_mode_dmn_passed PASSED         [ 61%]
tests/test_recall_v2.py::TestRecall::test_no_patch_when_project_specified PASSED [ 66%]
tests/test_recall_v2.py::TestRecall::test_patch_switch_on_saturation PASSED [ 72%]
tests/test_recall_v2.py::TestRecall::test_patch_no_switch_top_k_2 PASSED [ 77%]
tests/test_recall_v2.py::TestRecall::test_increment_recall_called PASSED [ 83%]
tests/test_recall_v2.py::TestRecall::test_content_truncated_200 PASSED   [ 88%]
tests/test_recall_v2.py::TestRecall::test_related_edges_max_3 PASSED     [ 94%]
tests/test_recall_v2.py::TestIncrementRecallCount::test_graceful_skip_on_exception PASSED [100%]

============================= 18 passed in 1.39s ==============================
