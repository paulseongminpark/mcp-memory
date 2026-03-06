# Test Operations Review - Round 3 (Operations)

> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Operational Reality
> Files Reviewed: tests/*.py, requirements.txt

## Collection Result

Command run:

```bash
pytest --collect-only -q -p no:cacheprovider
```

Result:
- Collection succeeded
- 117 tests collected in 2.61s
- Bytecode and pytest cache writes were disabled for the check

## Test Counts Per File

| File | Test Count |
|------|------------|
| `tests/test_access_control.py` | 23 |
| `tests/test_action_log.py` | 7 |
| `tests/test_drift.py` | 16 |
| `tests/test_hybrid.py` | 22 |
| `tests/test_recall_v2.py` | 18 |
| `tests/test_remember_v2.py` | 18 |
| `tests/test_validators_integration.py` | 13 |

## Findings

### [Severity: CRITICAL]

**C01** The test schema does not match the production schema on the exact paths that are breaking in production
- File: `tests/test_hybrid.py:21-42`, `tests/test_recall_v2.py:222-231`, `tests/test_access_control.py:48-60`
- Description: `test_hybrid.py` creates a `nodes.last_activated` column that does not exist in the live DB, the recall-count test only verifies graceful skip when `meta` is missing, and access-control tests use a simplified `hub_snapshots` schema.
- Impact: the suite can pass while recall learning, recall counting, and hub protection are broken in production.

**C02** The so-called validator integration suite is mock-only
- File: `tests/test_validators_integration.py:27-55`
- Description: it tests `mock_validate()` and `mock_validate_relation()`, not the real DB-backed validator functions.
- Impact: real-data false positive and false negative rates are unknown.

### [Severity: HIGH]

**H01** There is no regression coverage for the script entrypoints or the MCP wrapper surface
- Evidence: no tests target `daily_enrich.py`, `pruning.py`, `hub_monitor.py`, or `server.py`.
- Impact: schema drift and wrapper drift can ship unnoticed. The missing `recall(mode)` parameter in `server.py` is a good example.

**H02** Concurrency, locking, timeout, and retry behavior are effectively untested
- Description: no tests simulate overlapping recalls, concurrent remember writes, threaded budget accounting, 429 backoff under parallel workers, or duplicate-edge races.
- Impact: the repo has high unit confidence and low operational confidence.

### [Severity: MEDIUM]

**M01** The suite is not parallel-safe even though some failures would only appear under parallel execution
- File: `tests/test_action_log.py:12-20`, `tests/test_hybrid.py:13-20`, `tests/test_hybrid.py:86-96`
- Description: both files use module-global temp directories and file-backed SQLite DBs.
- Impact: `pytest-xdist` or parallel CI could expose file-lock and cleanup flakes that local serial runs never see.

**M02** CI/CD readiness is low
- File: `requirements.txt:1-7`
- Description: there is no `.github/workflows` directory, and `requirements.txt` does not list `pytest`.
- Impact: passing tests remain a local convention instead of an enforced deployment gate.

## Timing-Dependent Tests

- No explicit `sleep`, wall-clock assertions, or timestamp-boundary checks were found in the test bodies.
- Residual timing dependence still exists indirectly through shared temp DB files and Windows file-lock timing in `test_action_log.py` and `test_hybrid.py`.
- Because this review ran collect-only by request, full execution time and runtime flakiness were not measured.

## Summary

- Test discovery works.
- Operational coverage does not.
- The most dangerous gap is that the suite normalizes schema assumptions that the live DB does not satisfy.
