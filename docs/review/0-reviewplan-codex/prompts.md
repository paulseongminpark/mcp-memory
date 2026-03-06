# Codex Review Prompts

> Copy-paste each command into PowerShell.
> Each command produces 9 review report files in the corresponding folder.
> Run from: `cd C:\dev\01_projects\06_mcp-memory`

---

## Pre-requisites

```powershell
# Install code-review skill (if available)
# codex skill install code-review

# Verify mcp-memory MCP is connected
codex mcp list
```

---

## Round 1: Correctness

```powershell
codex --full-auto --sandbox workspace-write exec "
[ABSOLUTE RULES - VIOLATION = INSTANT FAILURE]
1. DO NOT modify ANY source code files (.py, .yaml, .json, .toml, config files)
2. DO NOT run git commit, git push, git checkout, git reset, or any git write commands
3. DO NOT run pip install, npm install, or any package management commands
4. You MAY ONLY create/write .md files inside docs/review/ folder
5. You MAY read any file in the repository

[CONTEXT]
You are reviewing mcp-memory v2.1 ontology system for CORRECTNESS (Round 1).
Core question: Was this built correctly according to specs?

The system implements:
- BCM (Bienenstock-Cooper-Munro) learning in hybrid.py
- UCB (Upper Confidence Bound) arm selection in hybrid.py
- SPRT (Sequential Probability Ratio Test) promotion in hybrid.py
- 3-gate promotion (SWR/Bayesian/MDL) in promote_node.py
- Hybrid search (vector + FTS5 + RRF + graph bonus) in hybrid.py + recall.py
- Access control (A10 firewall + Hub + RBAC) in access_control.py
- Phase 6 pruning pipeline in daily_enrich.py + pruning.py

Key specs are in docs/ideation/ (Round 3 final specs):
- a-r3-17 (action_log), a-r3-18 (remember)
- b-r3-14 (hybrid), b-r3-15 (recall)
- c-r3-11 (promotion/SPRT), c-r3-12 (SPRT validation)
- d-r3-11 (validators), d-r3-12 (drift), d-r3-13 (access control), d-r3-14 (pruning)

[TASK]
Create 9 review files:

1. docs/review/codex review_r1/01_storage.md
   - Read storage/*.py (sqlite_store.py, hybrid.py, vector_store.py, action_log.py)
   - Static analysis: undefined references, unused imports, dead code, type errors
   - Compare function signatures against specs in docs/ideation/
   - Check all SQL statements for correctness

2. docs/review/codex review_r1/02_tools.md
   - Read tools/*.py (10 files)
   - Static analysis for all tool files
   - Verify remember.py flow matches a-r3-18
   - Verify recall.py modes match b-r3-15
   - Verify promote_node.py gates match c-r3-11

3. docs/review/codex review_r1/03_utils_ontology.md
   - Read utils/*.py, ontology/validators.py, ontology/schema.yaml, config.py
   - Verify NODE_TYPES in config.py matches schema.yaml (50 types)
   - Verify RELATION_TYPES in config.py matches schema.yaml (48 types)
   - Check validators.py type_defs consistency

4. docs/review/codex review_r1/04_scripts.md
   - Read scripts/*.py (daily_enrich, pruning, hub_monitor, calibrate_drift, etc.)
   - Verify pruning formulas match d-r3-14
   - Check CLI argument handling

5. docs/review/codex review_r1/05_spec_alignment.md
   - Read ALL Round 3 final specs in docs/ideation/
   - For each spec section, find corresponding implementation
   - List gaps (spec not implemented) and additions (implemented not in spec)

6. docs/review/codex review_r1/06_tests.md
   - Read tests/*.py (7 files, 117 tests)
   - List every test function and what it verifies
   - Identify untested code paths
   - Check mock correctness

7. docs/review/codex review_r1/07_e2e_scenarios.md
   - Trace remember() flow through actual code
   - Trace recall() flow through actual code
   - Trace promote_node() flow through actual code
   - Identify any broken code paths

8. docs/review/codex review_r1/08_security.md
   - Check ALL SQL operations for injection vulnerabilities
   - Check input validation in all tool entry points
   - Check access_control.py for bypass scenarios
   - Check error messages for information leakage

9. docs/review/codex review_r1/09_summary.md
   - Aggregate all findings with severity (CRITICAL/HIGH/MEDIUM/LOW/INFO)
   - Top 5 most impactful findings

[OUTPUT FORMAT]
Each file must follow this structure:
# [Category] Review - Round 1 (Correctness)
> Reviewer: Codex
> Date: 2026-03-06
> Files Reviewed: [list]
## Findings
### CRITICAL
### HIGH
### MEDIUM
### LOW
### INFO
## Coverage
## Summary
"
```

---

## Round 2: Architecture

```powershell
codex --full-auto --sandbox workspace-write exec "
[ABSOLUTE RULES - VIOLATION = INSTANT FAILURE]
1. DO NOT modify ANY source code files (.py, .yaml, .json, .toml, config files)
2. DO NOT run git commit, git push, git checkout, git reset, or any git write commands
3. DO NOT run pip install, npm install, or any package management commands
4. You MAY ONLY create/write .md files inside docs/review/ folder
5. You MAY read any file in the repository

[CONTEXT]
Same system as Round 1. Now reviewing for ARCHITECTURE & DESIGN QUALITY.
Core question: Was this well designed?

[TASK]
Create 9 review files in docs/review/codex_review_r2/:

1. 01_storage.md - Storage layer: DB abstraction quality, transaction handling, connection management, index strategy, query patterns (N+1 problems)

2. 02_tools.md - Tools layer: tool-storage coupling, shared code patterns, error propagation, response format consistency, tool composability

3. 03_utils_ontology.md - Utils/Ontology: validator extensibility, config organization, schema evolution strategy, type system design quality, config-code separation

4. 04_scripts.md - Scripts: script-library boundary, code reuse with main codebase, CLI interface design, idempotency, error handling

5. 05_spec_alignment.md - Spec quality review: are specs self-consistent? contradictions between different specs? over/under-specification?

6. 06_tests.md - Test architecture: fixture quality, mocking patterns, test isolation, assertion quality, test naming conventions, parametrize usage

7. 07_e2e_scenarios.md - Flow architecture: are the code paths optimally structured? unnecessary indirection? missing short-circuits? function call depth

8. 08_security.md - Security architecture: defense-in-depth? trust boundaries clear? least privilege? secrets management? safe defaults?

9. 09_summary.md - Architecture scorecard, coupling matrix, cyclomatic complexity report, top design recommendations

For each file, calculate cyclomatic complexity for key functions.
Identify code duplication (exact and near-duplicate).
Check naming consistency across the codebase.

Same output format as Round 1 but with perspective: Architecture.
"
```

---

## Round 3: Operations

```powershell
codex --full-auto --sandbox workspace-write exec "
[ABSOLUTE RULES - VIOLATION = INSTANT FAILURE]
1. DO NOT modify ANY source code files (.py, .yaml, .json, .toml, config files)
2. DO NOT run git commit, git push, git checkout, git reset, or any git write commands
3. DO NOT run pip install, npm install, or any package management commands
4. You MAY ONLY create/write .md files inside docs/review/ folder
5. You MAY read any file in the repository
6. You MAY run pytest in read-only mode (pytest --co to collect, NOT execute)

[CONTEXT]
Same system. Now reviewing for OPERATIONAL REALITY.
Core question: What breaks in production?

[TASK]
Create 9 review files in docs/review/codex_review_r3/:

1. 01_storage.md - Storage operations: concurrent DB writes safety, WAL mode, lock contention, data corruption scenarios, backup/restore, disk space growth

2. 02_tools.md - Tool operations: timeout behavior, partial failure handling, idempotency on retry, resource cleanup on exception, memory usage during large recalls

3. 03_utils_ontology.md - Runtime failures: type system edge cases, config hot-reload feasibility, validator false positive/negative rates with real data

4. 04_scripts.md - Script operations: pruning false positive risk (deleting important nodes), hub monitor accuracy at scale, enrichment pipeline recovery after crash, cron scheduling safety

5. 05_spec_alignment.md - Spec drift: which specs are already outdated vs implementation? which will break first under scale? implementation decisions that deviated from spec

6. 06_tests.md - Test reliability: potential flaky tests, timing dependencies, environment assumptions, missing edge case tests, CI/CD readiness, test execution time

7. 07_e2e_scenarios.md - Stress scenarios: what happens at 10x data (32K nodes)? 100 concurrent recall calls? embedding API rate limits hit? DB file grows to 1GB?

8. 08_security.md - Runtime security: injection via malicious remember content, privilege escalation via promote_node, DoS via recall flood, actor spoofing

9. 09_summary.md - Operational readiness score (1-10), top 5 production risks ranked by likelihood*impact, monitoring/alerting recommendations

Run pytest --co (collect only) to verify test discovery works.
Count test functions per file.
Check for any tests that might be timing-dependent.

Same output format with perspective: Operations.
"
```
