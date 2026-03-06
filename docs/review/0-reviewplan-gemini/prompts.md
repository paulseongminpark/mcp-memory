# Gemini Review Prompts

> 대화형 세션에서 사용. `gemini -m gemini-3.1-pro-preview --yolo`로 진입 후 프롬프트 붙여넣기.
> 각 프롬프트가 리뷰 파일을 직접 생성한다.
> 작업 디렉토리: `C:\dev\01_projects\06_mcp-memory`

---

## Pre-requisites

```powershell
# Install code-review extension
gemini extensions install https://github.com/gemini-cli-extensions/code-review

# Verify mcp-memory MCP is connected
# Check ~/.gemini/settings.json for mcpServers.memory
```

---

## Round 1: Correctness

아래 프롬프트를 R1 탭의 Gemini 대화형 세션에 붙여넣기:

```
[ABSOLUTE RULES - VIOLATION = INSTANT FAILURE]
1. DO NOT modify ANY file in this repository
2. DO NOT run git commit, git push, git checkout, git reset
3. DO NOT create, edit, or delete any source code files (.py, .yaml, .json)
4. DO NOT run pip install, npm install, or any package management commands
5. You are a READ-ONLY reviewer. You may ONLY create .md files inside docs/review/
6. Write your complete review to: docs/review/gemini review_r1/full_review.md

[CONTEXT]
You are reviewing mcp-memory v2.1 ontology system for CORRECTNESS (Round 1).
Core question: Was this built correctly according to specifications?

Read ALL Python files in /c/dev/01_projects/06_mcp-memory/ (excluding tests/, .venv/, __pycache__/, data/).
Also read ALL Round 3 final specs in /c/dev/01_projects/06_mcp-memory/docs/ideation/:
- 0-orchestrator-round3-final.md
- a-r3-17-actionlog-record.md, a-r3-18-remember-final.md
- b-r3-14-hybrid-final.md, b-r3-15-recall-final.md
- c-r3-11-promotion-final.md, c-r3-12-sprt-validation.md
- d-r3-11-validators-final.md, d-r3-12-drift-final.md
- d-r3-13-access-control.md, d-r3-14-pruning-integration.md

[TASK]
Write a comprehensive correctness review with these sections:

## 01. Storage Layer
- Map every public method in sqlite_store.py, hybrid.py, vector_store.py, action_log.py to their spec references
- Verify function signatures match specs
- Check BCM formula: theta_m update rule vs b-r3-14
- Check UCB formula: arm selection vs b-r3-14
- Check SPRT formula: LLR calculation vs c-r3-11
- Check RRF formula: 1/(k+rank) vs b-r3-14

## 02. Tools Layer
- Map every tool function to its spec
- Verify remember.py: classify->store->link->F3 vs a-r3-18
- Verify recall.py: mode handling, graph_bonus, BCM/UCB update vs b-r3-15
- Verify promote_node.py: 3-gate (SWR/Bayesian/MDL) formulas vs c-r3-11
- Verify analyze_signals.py: _recommend_v2, _bayesian_cluster_score vs c-r3-11

## 03. Utils & Ontology
- Cross-check: schema.yaml types/relations vs config.py NODE_TYPES/RELATION_TYPES
- Verify validators.py type_defs match config.py
- Check access_control.py layers vs d-r3-13
- Check similarity.py drift calculation vs d-r3-12

## 04. Scripts
- Verify daily_enrich.py Phase 6 vs d-r3-14
- Verify pruning.py formulas (strength decay, BSP criteria)
- Verify hub_monitor.py vs d-r3-13
- Check calibrate_drift.py, sprt_simulate.py, ab_test.py correctness

## 05. Spec Alignment
- Create a COMPLETE mapping table: Spec Section -> Implementation File:Line
- List ALL gaps (in spec, not in code)
- List ALL additions (in code, not in spec)
- List orchestrator decisions and verify implementation

## 06. Tests
- For each test file, list what spec features it covers
- Identify spec features with NO test coverage
- Rate test quality per file (1-5)

## 07. E2E Scenarios
- Trace remember() through actual code path
- Trace recall(mode='deep') through actual code path
- Trace promote_node() 3-gate through actual code path
- For each trace, verify data flows correctly between layers

## 08. Security & Errors
- SQL injection analysis in all DB operations
- Input validation analysis in all tool entry points
- Access control bypass analysis
- Error handling consistency

## 09. Summary
- Overall correctness score (1-10)
- CRITICAL/HIGH/MEDIUM/LOW/INFO counts
- Top 5 findings

[OUTPUT FORMAT]
Use markdown with clear headings (## 01, ## 02, etc.)
For each finding: severity, file:line, description, spec reference, recommendation

Write the complete review to: docs/review/gemini review_r1/full_review.md
```

---

## Round 2: Architecture

아래 프롬프트를 R2 탭의 Gemini 대화형 세션에 붙여넣기:

```
[ABSOLUTE RULES - VIOLATION = INSTANT FAILURE]
1. DO NOT modify ANY file in this repository
2. DO NOT run git commit, git push, git checkout, git reset
3. DO NOT create, edit, or delete any source code files
4. DO NOT run pip install, npm install, or any package management commands
5. You are a READ-ONLY reviewer. You may ONLY create .md files inside docs/review/
6. Write your complete review to: docs/review/gemini_review_r2/full_review.md

[CONTEXT]
You are reviewing mcp-memory v2.1 for ARCHITECTURE & DESIGN QUALITY (Round 2).
Core question: Was this well designed?

Read ALL Python files in /c/dev/01_projects/06_mcp-memory/ (excluding .venv/, __pycache__/, data/).
Include tests/ this time for test architecture review.

[TASK]
Write a comprehensive architecture review:

## 01. Storage Layer Architecture
- Layer boundary clarity (storage vs tools)
- DB abstraction quality (raw SQL vs ORM patterns)
- Transaction handling patterns
- Connection lifecycle management
- Index strategy analysis
- Query performance patterns (N+1, full scans)

## 02. Tools Layer Architecture
- Tool-storage coupling analysis (how tightly bound?)
- Shared code patterns (DRY compliance)
- Error propagation patterns (how do errors bubble up?)
- Response format consistency across tools
- Tool composability (can tools call each other?)

## 03. Utils & Ontology Architecture
- Type system design quality
- Validator extensibility (adding new types/relations)
- Config organization and discoverability
- Schema evolution strategy
- Config-code separation quality

## 04. Scripts Architecture
- Script-library boundary (reuse vs duplication)
- CLI interface design patterns
- Idempotency guarantees
- Dependency on main codebase internals

## 05. Spec Architecture
- Spec quality: internal consistency
- Cross-spec contradictions
- Over-specification (too prescriptive) areas
- Under-specification (too vague) areas

## 06. Test Architecture
- Fixture patterns and quality
- Mocking strategy consistency
- Test isolation (shared state between tests?)
- Assertion quality (precise vs broad)
- parametrize usage for combinatorial coverage

## 07. Data Flow Architecture
- Create a data flow diagram (ASCII art):
  remember -> store -> link -> recall -> activate -> learn
- Identify bottlenecks in the flow
- Identify unnecessary indirection
- Missing short-circuits

## 08. Security Architecture
- Defense-in-depth analysis
- Trust boundary diagram
- Principle of least privilege compliance
- Safe defaults analysis

## 09. Summary
- Architecture quality score (1-10)
- Module coupling matrix (which modules depend on which)
- Top 5 design improvement recommendations
- Strengths to preserve

[OUTPUT FORMAT]
Use markdown. Include ASCII diagrams where helpful.
For each finding: severity, location, description, recommendation.

Write the complete review to: docs/review/gemini_review_r2/full_review.md
```

---

## Round 3: Operations

아래 프롬프트를 R3 탭의 Gemini 대화형 세션에 붙여넣기:

```
[ABSOLUTE RULES - VIOLATION = INSTANT FAILURE]
1. DO NOT modify ANY file in this repository
2. DO NOT run git commit, git push, git checkout, git reset
3. DO NOT create, edit, or delete any source code files
4. DO NOT run pip install, npm install, or any package management commands
5. You are a READ-ONLY reviewer. You may ONLY create .md files inside docs/review/
6. Write your complete review to: docs/review/gemini_review_r3/full_review.md

[CONTEXT]
You are reviewing mcp-memory v2.1 for OPERATIONAL REALITY (Round 3).
Core question: What breaks in production?

The system currently has: 3,255 nodes, 6,324 edges, 117 tests passing.
It runs as an MCP server used by Claude Code, Codex CLI, and Gemini CLI simultaneously.

Read ALL Python files in /c/dev/01_projects/06_mcp-memory/ (excluding .venv/, __pycache__/).
Also read: config.py, ontology/schema.yaml, scripts/eval/goldset.yaml

[TASK]
Write a comprehensive operational review:

## 01. Storage Operations
- SQLite concurrent access safety (multiple MCP clients)
- WAL mode: is it enabled? what happens without it?
- Lock contention scenarios (remember + recall + daily_enrich simultaneously)
- Data corruption recovery paths
- Disk space growth projection (current 3K nodes -> 30K nodes)
- Backup/restore procedures

## 02. Tool Operations
- What happens when embedding API times out during remember()?
- What happens when recall() returns 0 results?
- promote_node() partial failure (gate 2 passes but gate 3 DB write fails)
- Memory usage during large recall (1000+ candidate nodes)
- Rate limiting considerations

## 03. Utils/Ontology Operations
- What happens when unknown node_type is encountered?
- Config values that would break the system if changed
- Validator edge cases: empty strings, None values, very long content
- Type system evolution: what happens when adding a 51st node type?

## 04. Script Operations
- Pruning false positive analysis: can important nodes get pruned?
- Hub monitor accuracy at current scale (3255 nodes)
- daily_enrich crash recovery: what if it dies mid-Phase 6?
- Scheduling conflicts: what if two enrichment runs overlap?
- calibrate_drift with insufficient data

## 05. Spec vs Reality
- Which specs are already outdated?
- Implementation decisions that deviated from spec (justified or not)
- Features that exist in code but have no spec coverage
- init_db() vs migration script discrepancies

## 06. Test Operations
- Tests that might be flaky (timing, file system, network)
- Environment assumptions (specific Python version, OS)
- Missing edge case tests for each module
- CI/CD readiness assessment

## 07. Scale Scenarios
- 10x data (32K nodes): which queries become slow?
- 100 concurrent recall calls: threading/locking?
- Embedding API rate limit hit: graceful degradation?
- DB file at 1GB: performance characteristics?
- 10K edges on a single node: graph traversal time?

## 08. Security Operations
- Injection via malicious content in remember()
- Actor spoofing (actor='admin' without verification)
- Privilege escalation via promote_node(skip_gates=True)
- DoS via recall flood
- Data exfiltration via get_context/inspect_node

## 09. Summary
- Operational readiness score (1-10)
- Top 5 production risks (ranked by likelihood * impact)
- Monitoring/alerting recommendations
- Capacity planning guidance

[OUTPUT FORMAT]
Use markdown. Be specific with file paths and line numbers.
For each risk: likelihood (1-5), impact (1-5), combined score, mitigation.

Write the complete review to: docs/review/gemini_review_r3/full_review.md
```
