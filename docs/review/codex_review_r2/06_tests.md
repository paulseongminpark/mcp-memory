# Tests Review - Round 2 (Architecture)
> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Architecture
> Files Reviewed: tests/test_access_control.py, tests/test_action_log.py, tests/test_drift.py, tests/test_hybrid.py, tests/test_recall_v2.py, tests/test_remember_v2.py, tests/test_validators_integration.py

## Findings
### CRITICAL
- None.

### HIGH
- `H01` there is no shared fixture architecture. The repository has no `tests/conftest.py`, so test data, helper objects, and patch scaffolding are recreated at file scope. The tests still run, but the architecture does not scale well because shared contracts and reusable environment setup are missing.
- `H02` `tests/test_recall_v2.py` and `tests/test_remember_v2.py` rely heavily on patching tool-layer dependencies. That gives strong unit isolation, but it weakens architectural confidence because cross-layer contracts are mostly mocked out rather than exercised end to end.

### MEDIUM
- `M01` there is no `@pytest.mark.parametrize` usage anywhere in the suite. Repetitive boundary cases are therefore expanded manually, which increases test file size and reduces consistency.
- `M02` naming conventions are mixed. `tests/test_access_control.py` uses `test_tc...`, `tests/test_drift.py` uses `test_td...`, while other files use descriptive English phrases. None of those are wrong individually, but the suite does not present one clear naming standard.
- `M03` assertion depth is uneven. Many tests verify happy-path output shapes well, but fewer assert cross-component invariants such as schema expectations, logging contracts, or transaction coordination.

### LOW
- `L01` file-local fixtures and helpers are acceptable for a small suite, but the current architecture suggests the suite grew organically rather than from a testing design.

### INFO
- `I01` Test count by file: `test_access_control.py=23`, `test_action_log.py=7`, `test_drift.py=16`, `test_hybrid.py=22`, `test_recall_v2.py=18`, `test_remember_v2.py=18`, `test_validators_integration.py=13`, total `117` tests.
- `I02` Patch density is concentrated in the tool tests: `tests/test_remember_v2.py` has `37` patch decorators/usages, `tests/test_recall_v2.py` has `31`, and `tests/test_drift.py` has `25`.
- `I03` Naming consistency check confirmed the mixed prefixes `tc`, `td`, and descriptive names in the same suite.
- `I04` Useful architectural complexity anchors in tested code: `storage/hybrid.py:385` `hybrid_search()` = 28, `tools/promote_node.py:167` `promote_node()` = 21, `tools/analyze_signals.py:10` `analyze_signals()` = 35, `config.py:197` `infer_relation()` = 14.

## Coverage
- Fixture architecture checked via repository-level test discovery and file layout review.
- Mocking patterns checked via decorator counts and patched dependency targets.
- Assertion style checked across all seven test files.
- Duplication checked for repeated setup and repeated patch stacks.
- Naming consistency checked across test function prefixes and file naming.

## Summary
The suite has solid unit-level intent, but its architecture is local rather than systemic. It verifies behavior inside modules well, yet it has weaker support for cross-layer confidence because shared fixtures, parametrized matrices, and contract-style integration tests are missing. The next improvement is not more mocks; it is a cleaner testing architecture that reflects the actual service boundaries.
