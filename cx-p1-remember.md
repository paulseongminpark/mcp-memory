============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\pauls\AppData\Local\Programs\Python\Python312\python.exe
rootdir: C:\dev\01_projects\06_mcp-memory
plugins: anyio-4.12.1
collecting ... collected 18 items

tests/test_remember_v2.py::TestClassify::test_classify_no_db PASSED      [  5%]
tests/test_remember_v2.py::TestClassify::test_classify_type_correction_deprecated PASSED [ 11%]
tests/test_remember_v2.py::TestClassify::test_classify_case_correction PASSED [ 16%]
tests/test_remember_v2.py::TestClassify::test_classify_value_layer5_tier0 PASSED [ 22%]
tests/test_remember_v2.py::TestClassify::test_classify_observation_tier2 PASSED [ 27%]
tests/test_remember_v2.py::TestClassify::test_classify_unknown_type_no_layer PASSED [ 33%]
tests/test_remember_v2.py::TestLinkFirewall::test_f3a_l4_no_auto_edges PASSED [ 38%]
tests/test_remember_v2.py::TestLinkFirewall::test_f3a_l5_no_auto_edges PASSED [ 44%]
tests/test_remember_v2.py::TestLinkFirewall::test_f3_protected_layers_constant PASSED [ 50%]
tests/test_remember_v2.py::TestLinkFirewall::test_f3b_skips_l4_similar_node PASSED [ 55%]
tests/test_remember_v2.py::TestLinkFirewall::test_link_vector_failure_returns_empty PASSED [ 61%]
tests/test_remember_v2.py::TestRemember::test_basic_return_format PASSED [ 66%]
tests/test_remember_v2.py::TestRemember::test_invalid_type_correction PASSED [ 72%]
tests/test_remember_v2.py::TestRemember::test_chromadb_failure_graceful PASSED [ 77%]
tests/test_remember_v2.py::TestRemember::test_action_log_node_created PASSED [ 83%]
tests/test_remember_v2.py::TestRemember::test_action_log_edge_auto PASSED [ 88%]
tests/test_remember_v2.py::TestRemember::test_store_independent PASSED   [ 94%]
tests/test_remember_v2.py::TestRemember::test_link_returns_list PASSED   [100%]

============================= 18 passed in 1.26s ==============================
