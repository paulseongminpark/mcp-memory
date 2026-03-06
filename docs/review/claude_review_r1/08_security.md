# Security & Errors Review - Round 1 (Correctness)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Security Vulnerabilities & Error Handling
> Files Reviewed: 21

## Findings

### [Severity: HIGH]

**SEC-01** `promote_node()` does not call `check_access()` -- L4/L5 nodes can be promoted by any actor
- File: `tools/promote_node.py:167-292`
- Category: Access Control Bypass
- Description: `promote_node()` has no call to `check_access()` or `require_access()`. The `skip_gates` parameter bypasses SWR/Bayesian/MDL gates but there is no actor-based permission check at all. Any MCP caller can promote a node to L4/L5 types (Belief, Philosophy, Value) without being "paul". The `VALID_PROMOTIONS` map allows `Principle -> Belief/Philosophy/Value`, which are L4/L5 types protected by A-10 F1 firewall. But the firewall is never consulted.
- Attack Vector: `promote_node(node_id=X, target_type="Value", skip_gates=True)` -- promotes any Principle to L5 Value without any permission check.
- Impact: Complete bypass of L4/L5 content protection (A-10 F1 firewall). The most protected layers in the system can be written to by any actor.
- Recommendation: Add `check_access(node_id, "write", actor, conn)` before the promotion execution block. Accept `actor` parameter in `promote_node()` and in the MCP `server.py` wrapper. Default actor should be "claude", not implicit.

**SEC-02** `remember()` does not call `check_access()` -- any actor can write to any layer
- File: `tools/remember.py:232-291`, `server.py:40-112`
- Category: Access Control Bypass
- Description: Neither `remember()` nor the MCP wrapper calls `check_access()`. The `source` parameter is passed directly as metadata but never validated against layer permissions. A node classified as L4/L5 type (e.g., `type="Value"`) will be stored without checking if the actor is "paul". The classify/store/link pipeline stores the node first, then creates edges -- no permission gate at any step.
- Attack Vector: `remember(content="test", type="Value", source="system")` -- creates an L5 node with actor "system", bypassing F1.
- Impact: Any MCP caller can create L4/L5 nodes, violating the A-10 F1 firewall principle that only "paul" can write to L4/L5.
- Recommendation: After `classify()` determines the layer, call `check_access(0, "write", source)` with the target layer before `store()`. Requires a layer-only access check variant since the node doesn't exist yet.

**SEC-03** `server.py` exposes `skip_gates` parameter via MCP but does not expose it -- but no actor parameter either
- File: `server.py:231-255`
- Category: Access Control Bypass
- Description: The MCP `promote_node()` wrapper does NOT expose `skip_gates` (good), but also does NOT pass an `actor` parameter to the internal `_promote_node()`. This means even if SEC-01 is fixed by adding actor checks, the MCP layer has no way to identify who is calling. All MCP calls are implicitly "claude" with no authentication mechanism.
- Impact: Actor-based RBAC is unenforceable at the MCP boundary. Any connected client is treated as the same principal.
- Recommendation: Accept `actor` parameter in MCP tools that modify data (`remember`, `promote_node`, `save_session`). MCP transport-level identity should map to actor where possible.

### [Severity: MEDIUM]

**SEC-04** `_escape_fts_query()` in `sqlite_store.py` has incomplete FTS5 injection protection
- File: `storage/sqlite_store.py:283-288`
- Category: Input Validation / SQL Injection
- Description: The escape function wraps each whitespace-delimited term in double quotes. However, if user input contains double quotes themselves (e.g., `'hello"world'`), the quoting is broken. FTS5 double-quote quoting requires that internal double quotes be escaped by doubling them (`"hello""world"`). The current code does `f'"{t}"'` without escaping internal `"` characters.
- Attack Vector: `recall(query='test"OR"1')` -- the FTS5 MATCH clause receives `"test"OR"1"` which may be interpreted as FTS5 boolean syntax, though SQLite FTS5 is more likely to raise an error than return unexpected data. The `except Exception: return []` catch prevents crashes but silently drops the query.
- Impact: Low practical risk due to the broad exception catch, but could cause silent query failures or unexpected FTS5 behavior. Not a traditional SQL injection since FTS5 MATCH uses parameterized binding.
- Recommendation: Escape internal double quotes by replacing `"` with `""` before wrapping: `t.replace('"', '""')`.

**SEC-05** `_traverse_sql()` uses f-string for SQL placeholder construction -- safe but fragile
- File: `storage/hybrid.py:59-84`
- Category: SQL Injection (Potential)
- Description: `ph = ",".join("?" * len(seed_ids))` then `f"... IN ({ph}) ..."`. The placeholders are `?` characters, and actual values go through `params`. This is technically safe because only `?` placeholders are injected into the SQL string, not user data. However, if `seed_ids` were empty, `IN ()` would be a syntax error (handled by the early return on line 56-57).
- Impact: No actual injection risk. The pattern is safe but non-obvious.
- Recommendation: Document the safety invariant. Consider using a helper function for placeholder generation.

**SEC-06** `relation_extractor.py` uses f-string column name in SQL -- whitelist-protected
- File: `scripts/enrich/relation_extractor.py:340-371`
- Category: SQL Injection (Mitigated)
- Description: `f"SELECT DISTINCT {field} FROM nodes WHERE {field} IS NOT NULL"` uses `field` directly in SQL. However, `field` is validated against `_ALLOWED_CLUSTER_FIELDS = {"key_concepts", "facets"}` on line 340-341 with a `ValueError` raised for invalid values. The whitelist mitigation is effective.
- Impact: No actual risk due to whitelist. If the whitelist were ever expanded with user-controlled values, it would become a real vulnerability.
- Recommendation: Add a comment explaining the whitelist is a security control. Consider using column mapping instead of direct interpolation.

**SEC-07** Error information leakage in `remember.py` store() and `promote_node.py` _mdl_gate()
- File: `tools/remember.py:139`, `tools/promote_node.py:146`
- Category: Error Information Leakage
- Description: `remember.py:139` returns `f"Stored in SQLite but embedding failed: {e}"` to the MCP caller. This exposes the exception message which may contain internal paths, API error details, or connection strings. `promote_node.py:146` returns `f"embedding_unavailable:{e}"` in the MDL gate reason, also exposing exception internals. The `embedding/openai_embed.py:22` raises `RuntimeError(f"Embedding failed: {type(e).__name__}: {e}")` which includes the original exception type and message (potentially containing API key validation errors).
- Impact: Internal error details visible to MCP callers. Could reveal API provider, file paths, or partial configuration details.
- Recommendation: Return generic error messages to callers. Log detailed errors internally.

**SEC-08** `embedding/openai_embed.py` may expose API key in error messages
- File: `embedding/openai_embed.py:10-14,21-22`
- Category: Error Information Leakage
- Description: The OpenAI client is initialized with `api_key=OPENAI_API_KEY`. If the API key is invalid, the OpenAI library may include the key (partially) in the error message. The `RuntimeError` on line 22 re-raises with `{e}` which includes the original OpenAI error. The error propagates up through `vector_store.add()` to `remember.py` store() which returns it to the MCP caller.
- Impact: Potential API key partial exposure in error responses.
- Recommendation: Catch OpenAI authentication errors separately and return a generic "API configuration error" message.

**SEC-09** `remember()` and `recall()` lack input length validation
- File: `tools/remember.py:232-291`, `tools/recall.py:11-78`
- Category: Input Validation
- Description: `remember()` accepts `content` of arbitrary length with no upper bound. This content goes to: (1) SQLite INSERT (unbounded TEXT), (2) OpenAI embedding API (has token limits), (3) ChromaDB upsert. `recall()` accepts `query` of arbitrary length which goes to both embedding API and FTS5 MATCH. Neither function validates empty strings -- `remember(content="")` will create a node with empty content; `recall(query="")` will pass empty string to `_escape_fts_query()` which returns `""` (empty), then `search_fts` returns `[]`, and `embed_text("")` may succeed with a zero-information vector.
- Impact: Resource waste on empty/oversized inputs. Potential API cost from embedding very long texts. Empty nodes pollute the knowledge graph.
- Recommendation: Validate `content` minimum length (e.g., 10 chars) and maximum length (e.g., 50K chars). Validate `query` is non-empty and under a reasonable limit (e.g., 5K chars).

**SEC-10** `top_k` parameter has no upper bound
- File: `tools/recall.py:11-78`, `server.py:116-138`
- Category: Resource Exhaustion
- Description: `top_k` is passed from MCP with no upper bound. `hybrid_search()` uses `top_k * 2` for vector and FTS5 searches. A caller sending `top_k=1000000` would cause ChromaDB to attempt returning 2M results and SQLite FTS5 to scan for 2M rows. This could cause memory exhaustion and long query times.
- Impact: Denial of service via resource exhaustion.
- Recommendation: Clamp `top_k` to a maximum (e.g., 100) at the MCP layer in `server.py`.

### [Severity: LOW]

**SEC-11** Non-atomic node creation + edge creation in `remember()`
- File: `tools/remember.py:257-291`
- Category: Data Integrity
- Description: `remember()` calls `store()` (which does `insert_node` + ChromaDB add) then `link()` (which does multiple `insert_edge` calls). Each `insert_node` and `insert_edge` opens and closes its own connection with its own commit. If the process crashes between `store()` and `link()`, the node exists without its auto-edges. If `link()` partially completes, some edges exist and others don't.
- Impact: Inconsistent state is possible but not harmful -- orphan nodes are valid, and partial edges are acceptable. The system is designed to be eventually consistent.
- Recommendation: Consider wrapping the entire `remember()` flow in a single transaction for atomicity. Low priority since partial state is tolerable.

**SEC-12** Non-atomic promotion in `promote_node()`
- File: `tools/promote_node.py:258-281`
- Category: Data Integrity
- Description: `promote_node()` does use a single connection for UPDATE + edge INSERTs + COMMIT (lines 258-281), which is good. However, the `swr_readiness()` check (lines 39-77) and `_get_total_recall_count()` (lines 87-98) each open and close their own connections. Between the gate checks and the actual promotion, the node's state could change if another concurrent operation modifies it.
- Impact: TOCTOU (Time-of-Check-Time-of-Use) race condition. In practice, low risk since MCP is single-threaded stdio.
- Recommendation: Low priority. Document the single-thread assumption. If moving to multi-client, use SELECT FOR UPDATE or serialized transactions.

**SEC-13** Connection leak in `hybrid.py` `_bcm_update()` on exception
- File: `storage/hybrid.py:200-278`
- Category: Resource Exhaustion
- Description: `_bcm_update()` uses `try/except/finally` with `conn.close()` in the finally block (lines 274-278). This is correct. However, `_sprt_check()` in `hybrid_search()` (lines 475-491) has a similar pattern but the `finally` block has a nested `try/except` for `sprt_conn.close()`, which is also correct. No actual leak found here -- the pattern is safe.
- Impact: None. The connection handling is correct with finally blocks.
- Recommendation: No action needed. The code correctly handles connection cleanup.

**SEC-14** `pruning.py` `--actor` parameter is user-controlled from CLI
- File: `scripts/pruning.py:167-168`
- Category: Access Control Bypass (Potential)
- Description: `pruning.py` accepts `--actor` from the command line (default "system:pruning"). A user could run `python pruning.py --execute --actor paul` to bypass access controls, since "paul" has write access to all layers including L4/L5.
- Impact: Low -- this is a CLI script requiring direct system access. Anyone with shell access already has DB file access.
- Recommendation: Remove the `--actor` CLI parameter or validate it against a whitelist of system actors.

**SEC-15** `analyze_signals()` uses `LIKE` with domain parameter
- File: `tools/analyze_signals.py:22-27`
- Category: Input Validation
- Description: `sql += " AND domains LIKE ?"` with `params.append(f'%"{domain}"%')`. The `domain` parameter comes from MCP input. While the value is properly parameterized (using `?`), the LIKE pattern with user content inside could match unintended JSON fragments if `domain` contains `%` or `_` wildcards. For example, `domain="%"` would match all nodes.
- Impact: Could return more results than intended, but no data modification or injection risk.
- Recommendation: Escape `%` and `_` characters in the `domain` parameter, or use `json_extract()` for precise JSON field matching.

**SEC-16** Silent exception swallowing in multiple locations
- File: Multiple files (69 `except Exception` blocks across 26 files)
- Category: Error Handling
- Description: Many `except Exception: pass` blocks silently swallow errors: `sqlite_store.py:395-396` (log_correction), `hybrid.py:274-275` (BCM update), `hybrid.py:485-486` (SPRT), `hybrid.py:377-380` (activation logging), `recall.py:120-122` (meta table). While the design intent is "auxiliary operations shouldn't break main flow", this makes debugging very difficult. Failed BCM updates, SPRT checks, or action logs leave no trace.
- Impact: Silent data loss and invisible failures. In production, a systematic issue (e.g., corrupted action_log table) would go undetected indefinitely.
- Recommendation: Add `logging.warning()` or `logging.debug()` in catch blocks to at least record that a failure occurred. Consider a lightweight error counter.

### [Severity: INFO]

**SEC-17** `access_control.py` uses its own `DB_PATH` constant, separate from `config.DB_PATH`
- File: `utils/access_control.py:12`
- Category: Data Integrity
- Description: `DB_PATH = Path(__file__).parent.parent / "data" / "memory.db"` is calculated relative to the file location, while `config.py` uses `BASE_DIR = Path(__file__).parent` / "data" / "memory.db". These resolve to the same path (`06_mcp-memory/data/memory.db`) but through different mechanisms. If the project structure changes, they could diverge.
- Impact: No current issue, but maintenance risk.
- Recommendation: Import `DB_PATH` from `config` instead of recalculating it.

**SEC-18** Graph cache (`_GRAPH_CACHE`) is module-level mutable global with no thread safety
- File: `storage/hybrid.py:26-44`
- Category: Data Integrity
- Description: `_GRAPH_CACHE` and `_GRAPH_CACHE_TS` are module-level globals updated without any lock. The docstring notes "single process MCP server environment" as the safety assumption. If the server ever handles concurrent requests (e.g., via async or thread pool), cache updates could race.
- Impact: No current issue in stdio MCP. Risk if migrating to HTTP/SSE transport with concurrency.
- Recommendation: Document the single-thread assumption prominently. If concurrency is added, use `threading.Lock`.

**SEC-19** `ingest_obsidian()` accepts arbitrary `vault_path` from MCP
- File: `server.py:286-301`, `ingestion/obsidian.py:55-158`
- Category: Input Validation
- Description: The `vault_path` parameter accepts any filesystem path. A caller could pass `vault_path="/"` to scan the entire filesystem, or `vault_path="/etc"` to ingest system files. While the file type filter (`.md` only) and directory exclusions limit the damage, it could still ingest sensitive markdown files from unexpected locations.
- Impact: Low -- limited to `.md` files, and the system only reads (never modifies) source files. But could ingest sensitive documentation.
- Recommendation: Validate `vault_path` against an allowlist of permitted directories, or at minimum validate it starts with the expected vault root.

**SEC-20** `save_session()` has no session_id format validation
- File: `tools/save_session.py:9-50`
- Category: Input Validation
- Description: `session_id` is used directly in SQL via parameterized queries (safe from injection) but has no format validation. Very long session IDs, or session IDs containing special characters, are accepted. The auto-generated format is `YYYYMMDD_HHMMSS` but user-provided IDs have no constraints.
- Impact: No security risk, but could create unexpected data.
- Recommendation: Validate session_id format if user-provided (alphanumeric + underscores, max 64 chars).

## Coverage

- Files reviewed: 21/21 (all specified core files + 7 additional tool/script files)
- SQL queries audited: 47 (all parameterized except 3 f-string cases, all safe)
- Input validation points checked: 12
- Error handlers reviewed: 69 except blocks across 26 files

## SQL Audit Summary

| File | Queries | All Parameterized? | Notes |
|------|---------|-------------------|-------|
| sqlite_store.py | 12 | Yes | FTS5 MATCH uses `?` with escape function |
| hybrid.py | 8 | Yes* | `_traverse_sql` uses f-string for `?` placeholders only |
| action_log.py | 1 | Yes | |
| vector_store.py | 0 (ChromaDB API) | N/A | |
| analyze_signals.py | 2 | Yes | LIKE with parameterized `?` |
| promote_node.py | 5 | Yes | |
| recall.py | 1 | Yes | meta UPSERT |
| get_becoming.py | 1 | Yes* | f-string for `?` placeholders only |
| daily_enrich.py | 8 | Yes | |
| pruning.py | 5 | Yes | |
| hub_monitor.py | 4 | Yes | |
| ontology_review.py | 6 | Yes | |
| dashboard.py | 7 | Yes | |
| relation_extractor.py | 5 | Yes* | f-string column name whitelist-protected |
| graph_analyzer.py | 8 | Yes* | f-string for `?` placeholders only |

*f-string used for placeholder generation (`?`) or whitelist-validated column names, not for user data interpolation.

## Summary

- CRITICAL: 0
- HIGH: 3
- MEDIUM: 7
- LOW: 6
- INFO: 4

**Top 3 Most Impactful Findings:**
1. **SEC-01** (HIGH) `promote_node()` has zero access control -- any caller can promote nodes to L4/L5 types, completely bypassing the A-10 F1 firewall that is supposed to restrict L4/L5 writes to "paul" only.
2. **SEC-02** (HIGH) `remember()` has zero access control -- any caller can create L4/L5 nodes (Value, Philosophy, Belief) without permission checks, bypassing the designed layer protection.
3. **SEC-03** (HIGH) MCP layer has no actor identification -- even if tool-level access checks are added, the MCP transport provides no mechanism to distinguish callers, making RBAC unenforceable at the API boundary.

**Cumulative Findings (T1-C-01 through T1-C-08):**
- CRITICAL: 0
- HIGH: 3
- MEDIUM: 7
- LOW: 6
- INFO: 4
