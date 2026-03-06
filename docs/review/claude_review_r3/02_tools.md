# Tools Layer Review - Round 3 (Operations)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Operations
> Files Reviewed: tools/remember.py, tools/recall.py, tools/promote_node.py, tools/analyze_signals.py, tools/get_becoming.py, tools/get_context.py, tools/save_session.py, tools/suggest_type.py, tools/visualize.py, tools/inspect_node.py

## Findings

### [Severity: CRITICAL]

**[C01] remember() Not Idempotent — Retry Creates Duplicate Nodes**
- File: `tools/remember.py:232-291`
- Description: `remember()` has no content deduplication check. Each call creates a new node via `sqlite_store.insert_node()` (auto-increment ID). There is no unique constraint on `content` or any form of "upsert" logic.
- Impact: MCP transport retries (network timeout, client retry), user double-clicks, or any repeated invocation silently creates duplicate nodes with duplicate auto-edges. Over time this corrupts the knowledge graph with redundant data, inflates recall results, and pollutes BCM/UCB/SPRT statistics.
- Recommendation: Add a content-hash dedup check before `store()`. Either: (a) hash(content+type+project) lookup → return existing node_id, or (b) SQLite UNIQUE constraint on content hash with ON CONFLICT IGNORE. The `store()` function should accept an `idempotency_key` parameter.

**[C02] remember() Partial Failure Leaves Orphaned State**
- File: `tools/remember.py:260-291`
- Description: The `classify → store → link` pipeline has no transactional guarantee. Three failure modes:
  1. `store()` succeeds (SQLite node created) → ChromaDB `vector_store.add()` fails → returns with "warning" → node exists in SQLite but NOT in ChromaDB → vector search will never find this node → link skipped
  2. `store()` succeeds fully → `link()` at line 280 throws → node exists with embedding but zero edges → retry creates duplicate (C01)
  3. Within `link()`, `insert_edge()` at line 199 has NO try/except → if one edge fails, remaining edges not created, but already-created edges persist
- Impact: Inconsistent state across SQLite/ChromaDB. Nodes unreachable by vector search. Partial edge sets with no way to distinguish "legitimately zero edges" from "link failed mid-way."
- Recommendation: Wrap `store()` + `link()` in a transaction pattern. If `link()` fails, either roll back the node or record the failure state for later retry. Add try/except around each `insert_edge()` in `link()`.

**[C03] promote_node() Connection Leak in Mutation Path**
- File: `tools/promote_node.py:258-281`
- Description: `conn = sqlite_store._connect()` at line 258, `conn.close()` at line 281 — no `try/finally`. If `conn.execute()` (UPDATE at line 259) or `conn.commit()` (line 280) throws an exception, the connection is never closed. This is the WRITE path — the most dangerous place for a connection leak.
- Impact: Under repeated promotion attempts (especially with skip_gates or batch scripts), leaked connections accumulate. SQLite has a default limit of connections; leaked connections hold WAL locks, blocking other writers.
- Recommendation: Wrap lines 258-281 in `try/finally` with `conn.close()` in `finally`. Model after `swr_readiness()` (line 40-77) which already does this correctly in the same file.

### [Severity: HIGH]

**[H01] No Timeout on Any Tool — Indefinite Blocking**
- File: All 10 tools
- Description: Zero tools implement any form of timeout. MCP protocol has no built-in timeout mechanism. Critical hang points:
  - `remember.link()`: `vector_store.search()` calls OpenAI embedding API → network hang
  - `recall()`: `hybrid_search()` → embedding API + FTS5 + graph traversal → any can hang
  - `promote_node._mdl_gate()`: `vector_store._get_collection().get()` → ChromaDB query → can hang
  - `visualize()`: `get_all_edges()` + N×`get_node()` → DB lock contention → can hang
- Impact: A single hung tool blocks the MCP server's event loop. The client (Claude) waits indefinitely. No way to cancel, retry with smaller scope, or report partial results.
- Recommendation: Add `asyncio.wait_for()` or `signal.alarm()` wrapper at the MCP server level. Define per-tool timeout defaults in `config.py` (e.g., `TOOL_TIMEOUT_SECONDS = {"remember": 30, "recall": 15, ...}`).

**[H02] recall() Double Search on Patch Saturation — Unbounded Latency**
- File: `tools/recall.py:40-50`
- Description: When `_is_patch_saturated()` returns True (>75% same project), `recall()` calls `hybrid_search()` a SECOND time with `excluded_project`. This doubles the total latency. Both searches include: FTS5 query + embedding API call + graph traversal + BCM update + RRF fusion.
- Impact: If a single `hybrid_search()` takes 2-3 seconds (embedding API latency), patch saturation doubles it to 4-6 seconds. No timeout or early termination. The second search result quality depends on how many non-dominant-project nodes exist — could return mostly irrelevant results.
- Recommendation: (a) Cache the first search's embedding vector and reuse for the second search (skip re-embedding). (b) Add a timeout for the second search. (c) Consider async parallel execution of both searches if patch saturation is predicted.

**[H03] Connection Leak in _increment_recall_count()**
- File: `tools/recall.py:110-122`
- Description: `conn = sqlite_store._connect()` at line 111 inside `try` block. `conn.close()` at line 120 is also inside `try`. If `conn.execute()` at line 112 throws, control jumps to `except Exception: pass` at line 121 — `conn.close()` at line 120 is SKIPPED. Connection leaks.
- Impact: Called on EVERY recall invocation. If `meta` table is corrupted or SQL syntax error occurs, every single recall leaks a connection. High frequency = rapid connection exhaustion.
- Recommendation: Change to `try/except/finally` pattern:
  ```python
  try:
      conn = sqlite_store._connect()
      conn.execute(...)
      conn.commit()
  except Exception:
      pass
  finally:
      conn.close()
  ```

**[H04] save_session() Connection Leak**
- File: `tools/save_session.py:20-42`
- Description: `conn = _connect()` at line 20, `conn.close()` at line 42. No `try/finally`. If `conn.execute()` at line 23 or `conn.commit()` at line 41 throws (e.g., disk full, schema mismatch), connection leaks.
- Impact: `save_session()` is called at session boundaries (typically once per session). Lower frequency than recall, but each leaked connection persists until process restart.
- Recommendation: Wrap in `try/finally`.

**[H05] N+1 Query Pattern Across Multiple Tools**
- File: `tools/inspect_node.py:38-52`, `tools/get_becoming.py:45`, `tools/recall.py:58`, `tools/visualize.py:68`
- Description: Multiple tools perform per-result DB queries without batching:
  - `inspect_node()`: `get_node()` per edge (line 38, 46) — node with 50 edges → 50 extra queries
  - `get_becoming()`: `get_edges()` per node (line 45) — 100 promotable nodes → 100 extra queries
  - `recall()`: `get_edges()` per result (line 58) — 10 results → 10 extra queries
  - `visualize()`: `get_node()` per visible node (line 68) — 100 nodes → 100 extra queries
  Each query creates and destroys a new SQLite connection (`_connect()` pattern in sqlite_store).
- Impact: O(n) connection creation for n items. At scale (1000+ nodes/edges), response time degrades linearly. Each connection involves WAL mode setup and busy_timeout configuration.
- Recommendation: Add batch query methods to `sqlite_store`: `get_nodes_batch(ids)` and `get_edges_batch(node_ids)`. Use `WHERE id IN (...)` with a single connection.

### [Severity: MEDIUM]

**[M01] analyze_signals() O(n^2) Clustering Without Bound**
- File: `tools/analyze_signals.py:62-67`
- Description: Pairwise feature comparison: `for i in range(len(id_list)): for j in range(i+1, len(id_list))`. With 1000 Signal nodes → 499,500 set intersection operations. No limit on input size.
- Impact: At ~5000 Signals (plausible after a year of usage), this becomes ~12.5 million comparisons. Likely multi-second blocking. Combined with H01 (no timeout), the tool becomes unusable at scale.
- Recommendation: Either limit input size (e.g., `LIMIT 500` in SQL query) or switch to an index-based approach (inverted index on features → O(n*f) instead of O(n^2)).

**[M02] analyze_signals() Connection Leak**
- File: `tools/analyze_signals.py:21-28`
- Description: `conn = sqlite_store._connect()` at line 21, `conn.close()` at line 28. No `try/finally`. If `conn.execute()` at line 27 throws (e.g., SQL syntax error with domain filter), connection leaks.
- Impact: analyze_signals is called less frequently than recall, but each leak persists.
- Recommendation: Wrap in `try/finally`.

**[M03] get_becoming() Connection Leak**
- File: `tools/get_becoming.py:20-26`
- Description: Same pattern as M02. `conn = _connect()` → `execute` → `fetchall` → `close`, no `try/finally`.
- Impact: Same as M02.
- Recommendation: Wrap in `try/finally`.

**[M04] promote_node() Silent Edge Creation Failure**
- File: `tools/promote_node.py:270-278`
- Description: `realized_as` edge insertion wrapped in `try/except Exception: pass`. If edge creation fails (e.g., foreign key violation, duplicate edge), failure is silently swallowed. The returned `edge_ids` list will be shorter than expected, but caller has no explicit failure signal.
- Impact: Caller (Claude/user) sees "Promoted successfully" with fewer `realized_as_edges` than `related_ids` provided. No way to distinguish "edges intentionally filtered" from "edges failed silently." The promotion itself succeeded, but the graph linkage is incomplete.
- Recommendation: Collect failed edge inserts and include in response: `"failed_edges": [{"related_id": rid, "error": str(e)}]`.

**[M05] visualize() Unbounded Data Load**
- File: `tools/visualize.py:43`
- Description: `get_all_edges()` loads ALL edges into memory (line 43), then iterates ALL edges again for filtering (line 78). With 10K+ edges, this is a memory and performance concern.
- Impact: Memory spike proportional to total edge count. The `max_nodes` parameter limits displayed nodes but NOT edge loading.
- Recommendation: Add `get_edges_for_nodes(node_ids)` query to load only relevant edges, or push edge filtering to SQL.

**[M06] link() No Error Handling on Edge Insert**
- File: `tools/remember.py:199-211`
- Description: `sqlite_store.insert_edge()` at line 199 has no `try/except`. If one edge insert fails (e.g., FK constraint, uniqueness), the entire `link()` function crashes. Already-created edges from previous loop iterations persist (no rollback), but remaining edges are never created.
- Impact: Partial edge creation. The `auto_edges` list returned to `remember()` is incomplete. The `action_log.record()` at line 214 for the failed edge is also skipped.
- Recommendation: Wrap each `insert_edge()` call in `try/except` within the loop. Log failures. Return both successful and failed edges.

### [Severity: LOW]

**[L01] _increment_recall_count() Silent Failure**
- File: `tools/recall.py:121-122`
- Description: `except Exception: pass` — if `meta` table doesn't exist, SQL is malformed, or connection fails, the counter update is silently ignored. The comment says "meta table not created → graceful skip," but this catches ALL exceptions including logic errors.
- Impact: UCB normalization (`total_recall_count`) and usage analytics depend on this counter. Silent loss means UCB exploration scores are calculated with stale data. Bayesian P(real) in `promote_node` uses the same counter — promotion decisions affected.
- Recommendation: Narrow the except clause to `sqlite3.OperationalError`. Log other exceptions.

**[L02] Duplicate _get_total_recall_count() Implementation**
- File: `tools/promote_node.py:87-98`, `tools/analyze_signals.py:180-191`
- Description: Identical function duplicated in two files. Both query `meta` table for `total_recall_count`. Both have the same try/except/finally pattern.
- Impact: Maintenance risk. A bug fix in one copy may not be applied to the other. Different behavior could emerge silently.
- Recommendation: Extract to a shared utility (e.g., `storage/sqlite_store.py::get_total_recall_count()`).

**[L03] get_context() Fixed Limits Not Configurable**
- File: `tools/get_context.py:8-17`
- Description: Hard-coded limits: 3 decisions, 3 questions, 2 insights, 2 failures. Not parameterized.
- Impact: Users cannot adjust context density. For projects with many decisions, 3 may be insufficient. For new projects, even 1 per category may be too many (wasted tokens).
- Recommendation: Accept optional `limit` parameter, defaulting to current values.

**[L04] suggest_type() Inherits All remember() Issues**
- File: `tools/suggest_type.py:19-25`
- Description: Delegates entirely to `remember()`. Inherits C01 (not idempotent), C02 (partial failure), H01 (no timeout).
- Impact: All `remember()` operational risks apply. Additionally, `tags` construction at line 22 (`f"unclassified,needs-review,{tags}".strip(",")`) can produce malformed tags if `tags` starts with a comma.
- Recommendation: Address at the `remember()` level. Consider adding dedup for `suggest_type()` specifically (Unclassified nodes with same content).

### [Severity: INFO]

**[I01] classify() Is a Pure Function — Well-Designed**
- File: `tools/remember.py:38-77`
- Description: No DB, no IO, no resource management. Pure input→output. Returns a dataclass. No operational risk.
- Impact: Positive. Model for other pure-logic functions.

**[I02] save_session() Uses UPSERT — Idempotent by Design**
- File: `tools/save_session.py:23-40`
- Description: `ON CONFLICT(session_id) DO UPDATE` ensures retry safety. The same `session_id` can be saved multiple times without duplication.
- Impact: Positive. Only tool with proper idempotency. Model for `remember()`.

**[I03] swr_readiness() Has Proper try/finally**
- File: `tools/promote_node.py:40-77`
- Description: `conn = _connect()` → `try: ... finally: conn.close()`. The only function in the tools layer with correct connection cleanup pattern.
- Impact: Positive. Proves the pattern is known but inconsistently applied.

**[I04] Defensive JSON Parsing Throughout**
- File: `tools/analyze_signals.py:45-56`, `tools/get_becoming.py:34-39,55-58`, `tools/inspect_node.py:8-16`
- Description: All JSON parsing of node fields (`key_concepts`, `domains`, etc.) wrapped in `try/except (JSONDecodeError, TypeError)`. Graceful degradation on malformed data.
- Impact: Positive. Prevents one corrupted node from crashing analysis tools.

## Coverage

- Files reviewed: 10/10 (all tools/*.py)
- Functions verified: 22/22 (all public + key private)
- Key Checks: 4/4 (timeout, partial failure, idempotency, resource cleanup)

## Summary

- CRITICAL: 3
- HIGH: 5
- MEDIUM: 6
- LOW: 4
- INFO: 4

**Top 3 Most Impactful Findings:**

1. **[C01] remember() not idempotent** — Every MCP retry creates duplicate nodes. This is the most-called write tool. Without dedup, the knowledge graph degrades silently over time. Root cause of data quality issues.

2. **[C02] remember() partial failure** — The classify→store→link pipeline has no transactional guarantee. SQLite+ChromaDB inconsistency creates nodes invisible to vector search. No recovery mechanism exists.

3. **[H01] No timeout on any tool** — Zero tools have timeout protection. A single hung API call (embedding, ChromaDB) blocks the entire MCP server indefinitely. Combined with H02 (double search on patch saturation), worst-case latency is unbounded.

**Cross-Reference with 01_storage.md:**
- H03/H04/M02/M03 (connection leaks) compound with 01_storage C01 (connection leak in sqlite_store). The tools layer adds 5 more leak points on top of the storage layer's existing issues.
- H05 (N+1 queries) creates N×(connection overhead from 01_storage _connect() pattern). Batching would dramatically reduce connection churn.
- C01 (no idempotency) feeds into 01_storage C03 (lost BCM updates): duplicate nodes receive independent BCM/UCB tracking, further fragmenting statistics.
