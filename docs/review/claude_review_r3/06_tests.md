# Tests Review - Round 3 (Operations)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Operations — Test Reliability & CI/CD Readiness
> Files Reviewed: tests/test_hybrid.py, tests/test_recall_v2.py, tests/test_remember_v2.py, tests/test_access_control.py, tests/test_action_log.py, tests/test_drift.py, tests/test_validators_integration.py

## Findings

### [Severity: CRITICAL]

**[C01] Zero Concurrency Tests — Race Conditions Completely Untested**
- File: All 7 test files
- Description: No test file contains any concurrency testing. The codebase has at least 8 identified race conditions (01_storage C02/C03, 02_tools H03/H04/M02/M03, 04_scripts H03, 03_utils M04) but zero tests verify thread safety, asyncio safety, or multi-process behavior. Key untested scenarios:
  - `_bcm_update()` concurrent write (C03-Storage: read-modify-write race)
  - `_GRAPH_CACHE` concurrent access (C02-Storage: no lock)
  - `_increment_recall_count()` concurrent update (H03-Tools)
  - `vector_store._get_collection()` singleton race (M04-Storage)
- Impact: The most dangerous class of bugs — silent data corruption under concurrent access — has zero test coverage. All concurrency findings in reports 01-04 are theoretical; no test proves or disproves them.
- Recommendation: Add `test_concurrent.py` with threading-based tests for at least: (a) 10 concurrent `_bcm_update()` calls verifying no lost updates, (b) 2 concurrent `remember()` calls verifying no duplicates, (c) concurrent graph cache access.

**[C02] Zero Large-Scale Tests — Performance Degradation Invisible**
- File: All 7 test files
- Description: All tests use 3-10 sample nodes/edges. No test exercises behavior at current production scale (3,255 nodes, 6,324 edges) or projected 10x scale. Key untested scenarios:
  - UCB traversal with 1000+ nodes (H05-Tools: N+1 queries)
  - O(n^2) signal clustering with 500+ signals (M01-Tools)
  - Graph cache rebuild with 60K edges (C02-Storage: race during rebuild)
  - CTE parameter explosion with 333+ seed IDs (M06-Storage)
- Impact: Performance regressions are invisible until production. The O(n^2) clustering in `analyze_signals()` could freeze the MCP server at 1000+ signals, and no test would catch this before deployment.
- Recommendation: Add parametrized scale tests: `@pytest.mark.parametrize("n_nodes", [10, 100, 1000])` with performance assertions (e.g., `assert elapsed < 5.0`).

### [Severity: HIGH]

**[H01] test_hybrid.py — Graph Cache Global State Leaks Between Tests**
- File: `tests/test_hybrid.py`
- Description: Tests manipulate `hybrid._GRAPH_CACHE` and `hybrid._GRAPH_CACHE_TS` global variables directly. While fixtures reset these, test ordering can affect cache hit/miss behavior. Specifically, `test_get_graph_cache()` sets `_GRAPH_CACHE_TS` to a past timestamp to force rebuild — if this test runs last, the cache state persists for the next test file if pytest doesn't isolate modules.
- Impact: Flaky test failures when test execution order changes (e.g., pytest-randomly plugin). May produce false passes where a test succeeds only because a previous test pre-populated the cache.
- Recommendation: Use `autouse=True` fixture that saves and restores all global state in `hybrid` module.

**[H02] BCM/SPRT Tests Check Direction, Not Correctness**
- File: `tests/test_hybrid.py`
- Description: BCM tests verify `new_freq != old_freq` (change occurred) and `visit_count == 6` (incremented). They do NOT verify the actual BCM formula: `delta_w = eta * v_i * (v_i - theta_m) * v_j`. A bug in the formula (e.g., missing `v_j` term) would pass all tests as long as frequency changes. Similarly, SPRT tests check threshold constants but don't execute actual LLR accumulation through a full accept/reject cycle.
- Impact: Formula bugs — the most critical correctness issue — are not caught by tests. The BCM sliding-window mean, theta_m update, and SPRT LLR calculation could all be wrong and tests would pass.
- Recommendation: Add formula-level tests: given known inputs (v_i=0.8, theta_m=0.5, v_j=0.6, eta=0.02), assert `delta_w == pytest.approx(0.8 * (0.8 - 0.5) * 0.6 * 0.02 * 10)`.

**[H03] test_drift.py — Mock Embedding Dimension Mismatch**
- File: `tests/test_drift.py`
- Description: `patch("embedding.openai_embed.embed_text", return_value=[0.1]*3)` — returns 3-dimensional vectors. Production uses 3072-dimensional vectors (`EMBEDDING_DIM = 3072`). The cosine similarity implementation handles any dimension, so tests pass. But dimension-dependent behaviors (e.g., numerical precision at high dimensions, memory allocation) are untested.
- Impact: Low probability of real bugs, but the mock is unrealistic. If `cosine_similarity()` has a numerical stability issue at 3072 dimensions (e.g., near-zero norms), tests wouldn't catch it.
- Recommendation: Use `[0.1]*EMBEDDING_DIM` or at least `[0.1]*128` for more realistic testing.

**[H04] Error Recovery Tests Only Cover Silent Skip — Not Partial Failure**
- File: `tests/test_remember_v2.py:test_chromadb_failure_graceful()`, `tests/test_action_log.py:test_record_silent_fail()`
- Description: Error tests verify that when ChromaDB fails or action_log table is missing, the function returns gracefully (no crash). They do NOT test: (a) What state remains after partial failure (orphaned SQLite node without ChromaDB embedding), (b) Whether retry would create duplicates, (c) Whether the system can recover from the inconsistent state.
- Impact: Tests give false confidence that error handling is "working". In reality, the graceful skip creates data inconsistency (C02-Tools) that is never tested or verified.
- Recommendation: Add state-verification tests: after ChromaDB failure, assert that SQLite node exists but has a `needs_reindex` flag (or similar recovery marker).

### [Severity: MEDIUM]

**[M01] test_access_control.py — Only Tests In-Memory DB, Not Real DB Path**
- File: `tests/test_access_control.py`
- Description: Uses `:memory:` SQLite database. Production `access_control.py` computes `DB_PATH` from file location and opens a file-based DB. The file-based path resolution (H03-Utils) is never tested. If `access_control.py` is moved to a different directory, `DB_PATH` changes silently — no test catches this.
- Impact: The most dangerous access_control bug (H03-Utils: independent DB_PATH) is architecturally untestable with in-memory DBs.
- Recommendation: Add one integration test that uses `access_control.DB_PATH` resolution and verifies it matches `config.DB_PATH`.

**[M02] test_recall_v2.py — Patch Saturation Edge Cases Missing**
- File: `tests/test_recall_v2.py`
- Description: Tests verify patch saturation detection and switching, but miss key edge cases:
  - Empty 2nd search result (all nodes are from dominant project) → returns empty?
  - `top_k=1` → saturation check with 1 result → threshold 75% of 1 = 0.75 → always saturated?
  - `top_k=2` → 1 dominant = 50% < 75% → never saturated. But spec says top_k < 3 → False.
- Impact: Edge case behavior for small result sets is undefined and untested.
- Recommendation: Add parametrized tests for `top_k` in [1, 2, 3, 5, 20].

**[M03] test_action_log.py — No Large Payload Test**
- File: `tests/test_action_log.py`
- Description: Tests use small, well-formed JSON for `params` and `result` fields. No test sends: (a) Very large JSON (100MB), (b) Deeply nested JSON, (c) Non-serializable objects, (d) Binary data. SQLite TEXT columns have no inherent size limit, but memory allocation during JSON serialization could fail.
- Impact: Production `remember()` could log large content in params → memory spike during `json.dumps()`.
- Recommendation: Add boundary test with `params={"data": "x" * 1_000_000}`.

**[M04] test_validators_integration.py — suggest_closest_type() Determinism Unverified**
- File: `tests/test_validators_integration.py`
- Description: `assert suggestion == "Pattern"` for input containing "패턴 반복". This assumes `suggest_closest_type()` is deterministic keyword matching. If the implementation is ever changed to LLM-based classification, this test becomes flaky. The test doesn't document WHY "Pattern" is the expected result.
- Impact: Test is correct now but fragile against implementation changes. No test verifies that the function is NOT calling an LLM.
- Recommendation: Add comment: `# keyword match: "패턴" → Pattern (deterministic, no LLM)`.

**[M05] No Integration Tests — Components Tested in Isolation Only**
- File: All 7 test files
- Description: Every test mocks its dependencies. No test exercises the full pipeline: `remember() → recall() → promote_node()`. Component interactions (e.g., remember stores node → recall finds it → BCM updates → SPRT triggers → promotion candidate flag) are never verified end-to-end.
- Impact: Integration bugs between components are invisible. Example: `remember()` stores `layer=2` but `access_control.check_access()` expects `layer` as string → type error only in production.
- Recommendation: Add `test_integration.py` with at least one full-pipeline test using a real temporary DB (not mocks).

**[M06] test_hybrid.py — Hardcoded Node IDs Create Implicit Coupling**
- File: `tests/test_hybrid.py`
- Description: Tests use `node_id=1, 2, 3` hardcoded. The `_create_test_db()` fixture creates nodes with autoincrement IDs. If fixture is modified to create additional setup nodes, IDs shift and tests break.
- Impact: Maintenance burden. Tests are brittle to fixture changes.
- Recommendation: Use return values from INSERT to capture actual IDs, or use UUID-based identification.

### [Severity: LOW]

**[L01] test_drift.py — NodeEnricher __new__ Hack**
- File: `tests/test_drift.py`
- Description: Tests override `NodeEnricher.__new__` to bypass constructor. This couples tests to internal class construction mechanics. If `NodeEnricher` switches to a factory pattern or dataclass, the hack breaks silently.
- Impact: Low — only affects test maintainability.
- Recommendation: Use a proper test fixture or subclass instead of `__new__` override.

**[L02] test_action_log.py — Timestamp Format Check Too Loose**
- File: `tests/test_action_log.py:test_record_created_at_populated()`
- Description: Asserts `"T" in created_at` — only checks that the ISO separator exists. Doesn't verify timezone, precision, or format compliance. A value like `"NOT-A-DATE-T-REALLY"` would pass.
- Impact: Very low — `created_at` is auto-generated by SQLite `datetime('now')`, which always produces valid ISO format.
- Recommendation: Use `datetime.fromisoformat(created_at)` assertion for strict validation.

**[L03] Missing Negative Tests for Type Validation**
- File: `tests/test_validators_integration.py`
- Description: Tests cover valid types, deprecated types, case correction, and unknown types. Missing: (a) Empty string type, (b) Very long type name (1000+ chars), (c) Type name with SQL injection attempt, (d) Unicode type name.
- Impact: Low — input validation layer handles these, but no test proves it.
- Recommendation: Add boundary value tests for type names.

**[L04] No Test Execution Time Monitoring**
- File: All test files
- Description: No `@pytest.mark.timeout()` decorators or `conftest.py` timeout configuration. A test that hangs (e.g., due to a real DB lock) blocks the entire test suite indefinitely.
- Impact: CI/CD pipeline could hang without detection.
- Recommendation: Add `pytest-timeout` with default 30-second per-test timeout.

### [Severity: INFO]

**[I01] test_access_control.py — Best Test Quality in Suite**
- File: `tests/test_access_control.py` (19 tests)
- Description: Uses real SQLite (`:memory:`), explicit fixtures, precise boolean assertions with `pytest.raises(PermissionError, match="...")`. Zero flaky risk. Complete test isolation. Model for other test files.

**[I02] test_recall_v2.py — Good Mock Design**
- File: `tests/test_recall_v2.py` (18 tests)
- Description: Clean mock patterns with explicit `side_effect` for multi-call scenarios. Parameter verification via `call_args` inspection. Good coverage of patch saturation logic.

**[I03] CI/CD Self-Sufficiency — All Tests Mock-Based**
- File: All 7 test files
- Description: No test requires real API keys, real database files, or network access. All external dependencies are mocked. Tests can run in any CI/CD environment with just `pip install -r requirements.txt`.

**[I04] Test Count: 117 Across 7 Files — Reasonable Base Coverage**
- Description: 117 tests covering storage, tools, utils, ontology. The count is appropriate for the codebase size (~4,500 lines of production code). The coverage gap is not in quantity but in quality (missing concurrency, scale, integration tests).

## Coverage

- Test files reviewed: 7/7
- Test functions analyzed: 117/117
- Flaky risk assessment: 7/7 files
- CI/CD readiness assessment: 7/7 files
- Missing scenario identification: 7/7 files

## Summary

- CRITICAL: 2
- HIGH: 4
- MEDIUM: 6
- LOW: 4
- INFO: 4

**Top 3 Most Impactful Findings:**

1. **[C01] Zero concurrency tests** — 8 identified race conditions across 4 reports, zero test coverage. The most dangerous class of bugs (silent data corruption) is completely untested. Any fix for concurrency issues cannot be verified without adding these tests first.

2. **[C02] Zero large-scale tests** — All tests use 3-10 items. Performance issues (O(n^2) clustering, CTE parameter explosion, graph cache rebuild time) are invisible until production. Tests provide false confidence that the system "works" when it may collapse at scale.

3. **[H02] BCM/SPRT formula tests check direction, not correctness** — Tests verify that values change, not that they change correctly. A formula bug (wrong coefficient, missing term) would pass all tests. The core learning algorithms — the differentiating feature of v2.1 — have the weakest test assertions.

**Key Insight**: The test suite is well-structured for unit testing (good mocks, good isolation, CI/CD ready) but operationally inadequate. It tests "does it work?" but not "does it work correctly under stress?" The gap between test coverage and operational requirements is the largest risk for v2.1 deployment.
