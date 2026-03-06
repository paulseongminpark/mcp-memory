# Tools Review - Round 2 (Architecture)
> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Architecture
> Files Reviewed: server.py, tools/remember.py, tools/recall.py, tools/promote_node.py, tools/analyze_signals.py, tools/get_becoming.py, tools/inspect_node.py, tools/save_session.py, tools/visualize.py

## Findings
### CRITICAL
- None.

### HIGH
- `H01` `server.py:29-30`, `server.py:342`: the tool boundary is not a clean service boundary. `server.py` imports script modules directly for `ontology_review` and `dashboard`, and it also runs `init_db()` at import time. That means MCP startup performs infrastructure mutation implicitly and depends on non-tool code paths. A well-designed tool layer should expose application services, not mix transport wiring with startup side effects and script adapters.
- `H02` `server.py:40-76`, `tools/remember.py:38-56`: `remember` validates node types twice, once in the MCP wrapper and again inside the tool pipeline. The duplicate validation logic is not just redundant; it means API behavior can drift when only one side is updated.
- `H03` `server.py:116-138`, `tools/recall.py:11-16`: the transport contract already drifted. `tools.recall.recall()` supports `mode="auto|focus|dmn"`, but the MCP entrypoint does not expose `mode` at all. That is a direct sign that the tool layer is not acting as the single stable public contract.
- `H04` `tools/recall.py:111`, `tools/promote_node.py:39`, `tools/analyze_signals.py:21`, `tools/get_becoming.py:20`: multiple tools reach into `sqlite_store._connect()` and write raw SQL rather than calling explicit storage services. This couples tool behavior to private storage details and makes it harder to evolve schema or transaction boundaries safely.

### MEDIUM
- `M01` response formats are inconsistent across tools. `tools/remember.py:232` returns `node_id/type/project/auto_edges/message`, `tools/recall.py:68-72` returns `results/count/message`, `tools/analyze_signals.py` returns `clusters`, `tools/visualize.py:30` returns a file-oriented dict, and `scripts/ontology_review.py` is surfaced as a raw report string. The layer works, but it is not composable because consumers cannot rely on shared envelope semantics.
- `M02` tool composability is limited by embedded side effects. `remember()` writes to SQLite, vector storage, and action logs; `recall()` both reads and increments recall counters; `promote_node()` both evaluates gates and performs updates. The absence of a command/query split makes orchestration reuse harder.
- `M03` there are additional N+1 patterns at tool level. `tools/recall.py:51-63` fetches related edges per result; `tools/promote_node.py:57-73` fetches neighbor projects one by one; visualization and inspection tools gather graph detail incrementally. This suggests the tool layer is compensating for missing service APIs.

### LOW
- `L01` audit naming is not centralized. `scripts/daily_enrich.py:503` records `action_type="archive"` even though the taxonomy elsewhere prefers specific names such as `node_archived` or `edge_archived`. The tool layer does not enforce those conventions.
- `L02` `suggest_type()` inherits much of the `remember` storage behavior instead of being a separate review queue abstraction. That keeps implementation simple but weakens conceptual separation.

### INFO
- `I01` Exact duplicate: `_get_total_recall_count()` exists in both `tools/analyze_signals.py:180` and `tools/promote_node.py:87`.
- `I02` Naming consistency is mixed. Public tool names are clear, but internal helper names oscillate between domain terms (`swr_readiness`, `promotion_probability`) and storage-style procedural names (`_increment_recall_count`, `_get_total_recall_count`).
- `I03` File-level coupling count: tools import `storage` from 9 files, `ontology` from 1 file, and `graph` from 1 file. That is a strong sign that tools are leaning on internals rather than a narrow application facade.

## Coverage
- Key cyclomatic complexity: `tools/analyze_signals.py:10` `analyze_signals()` = 35, `tools/promote_node.py:167` `promote_node()` = 21, `tools/get_becoming.py:9` `get_becoming()` = 16, `tools/visualize.py:30` `visualize()` = 14, `tools/inspect_node.py:19` `inspect_node()` = 11, `tools/remember.py:151` `link()` = 10, `tools/recall.py:11` `recall()` = 7, `tools/save_session.py:9` `save_session()` = 6.
- Duplication checked for helper reuse, raw SQL access patterns, and repeated transport logic.
- Naming consistency checked for public API verbs, audit action names, and helper terminology.

## Summary
The tools layer is functional but not architecturally clean. The main problems are boundary drift between `server.py` and the tool modules, direct dependence on private storage internals, and inconsistent response contracts. The system would be better designed if MCP wrappers were thin transport adapters over a real application-service layer with stable request and response models.
