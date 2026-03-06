# P0 Validators Integration Test Report

- Command: `python -m pytest tests/test_validators_integration.py -v`
- Run date: 2026-03-05
- Exit code: 0

## Output

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\pauls\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: C:\dev\01_projects\06_mcp-memory
plugins: anyio-4.12.1
collecting ... collected 13 items

tests/test_validators_integration.py::test_tc1_exact_match PASSED        [  7%]
tests/test_validators_integration.py::test_tc2_unclassified_default PASSED [ 15%]
tests/test_validators_integration.py::test_tc3_lowercase PASSED          [ 23%]
tests/test_validators_integration.py::test_tc4_allcaps PASSED            [ 30%]
tests/test_validators_integration.py::test_tc5_mixed_case PASSED         [ 38%]
tests/test_validators_integration.py::test_tc6_deprecated_with_replacement PASSED [ 46%]
tests/test_validators_integration.py::test_tc7_deprecated_case_insensitive PASSED [ 53%]
tests/test_validators_integration.py::test_tc8_completely_unknown PASSED [ 61%]
tests/test_validators_integration.py::test_tc9_typo PASSED               [ 69%]
tests/test_validators_integration.py::test_tc10_edge_relation_fallback PASSED [ 76%]
tests/test_validators_integration.py::test_suggest_decision PASSED       [ 84%]
tests/test_validators_integration.py::test_suggest_failure PASSED        [ 92%]
tests/test_validators_integration.py::test_suggest_unclassified PASSED   [100%]

============================= 13 passed in 0.07s ==============================
```
