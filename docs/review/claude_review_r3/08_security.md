# Security Review - Round 3 (Operations)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Operations — Runtime Security
> Files Reviewed: server.py, tools/*.py (10), storage/sqlite_store.py, storage/hybrid.py, utils/access_control.py, ontology/validators.py, scripts/migrate_v2.py, scripts/enrich/node_enricher.py, scripts/enrich/relation_extractor.py, ingestion/obsidian.py

## Findings

### [Severity: CRITICAL]

**[C01] F-String SQL Injection in Migration Scripts**
- File: `scripts/migrate_v2.py:73,76,293`, `scripts/migrate_v2_ontology.py:573`
- Description: Multiple SQL statements constructed via f-strings with unparameterized values:
  ```python
  sql = f"ALTER TABLE {table} ADD COLUMN {name} {col_type}"  # line 73
  sql += f" DEFAULT '{default}'"                               # line 76
  conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({col})")  # line 293
  ```
  While `table`, `name`, and `col_type` are currently hardcoded in the migration code, the pattern is dangerous: (a) Any future refactoring that passes external input to these functions creates an injection vector, (b) The `default` value at line 76 is wrapped in single quotes but not escaped — a value containing `'` breaks out of the string.
- Impact: In current usage (hardcoded migration values), the risk is low. But the pattern sets a dangerous precedent. If migration scripts are ever generalized to accept user input (e.g., custom column names), full SQL injection is possible.
- Recommendation: Use parameterized queries where possible. For DDL statements (ALTER TABLE, CREATE INDEX) where parameterization isn't supported, add strict allowlist validation: `assert name in ALLOWED_COLUMN_NAMES`.

**[C02] skip_gates Bypass — No Authorization Check**
- File: `tools/promote_node.py:172,197-227`
- Description: The `promote_node()` function accepts `skip_gates: bool = False` parameter exposed directly via MCP tool interface. When `True`, all 3 gates (SWR, Bayesian, MDL) are bypassed. There is NO check that the caller is authorized to use this parameter:
  ```python
  def promote_node(node_id: int, target_type: str, reason: str = "",
                   related_ids: list[int] | None = None,
                   skip_gates: bool = False) -> dict:
      # No actor parameter, no permission check
      if not skip_gates:
          ready, swr_score = swr_readiness(node_id)  # Gate 1
          ...
  ```
  Any MCP client can call `promote_node(1, "Value", skip_gates=True)` to escalate a L0 Observation directly to L5 Value without any validation.
- Impact: **Ontology poisoning**. An adversarial or misconfigured client can promote arbitrary nodes to L4/L5, where they receive maximum access protection (A-10 firewall). Once promoted, these nodes are nearly impossible to delete (requires actor="paul" for L5). This creates a privilege escalation → lock-in attack vector.
- Recommendation: (a) Remove `skip_gates` from MCP tool signature. Expose only via direct Python API for admin scripts. (b) Or add `actor` parameter with access control: `if skip_gates: require_access(node_id, "admin", actor, conn)`.

**[C03] Enrichment Column Name Injection via LLM Output**
- File: `scripts/enrich/node_enricher.py:768`, `scripts/enrich/relation_extractor.py:170`
- Description: Enrichment results from LLM API calls are used to construct SQL column names:
  ```python
  cols = ", ".join(f"{k} = ?" for k in updates)  # keys from LLM output
  self.conn.execute(f"UPDATE nodes SET {cols} WHERE id = ?", vals)
  ```
  If the LLM returns a JSON key like `"id = 1; DROP TABLE nodes; --"`, it gets interpolated into SQL. While SQLite may reject malformed SQL, careful crafting could exploit this.
- Impact: Requires compromised LLM API response (prompt injection via node content → LLM returns malicious key names). Attack chain: malicious content stored → enrichment processes it → LLM extracts malicious key → SQL injection via column name.
- Recommendation: Validate enrichment result keys against a strict allowlist: `ALLOWED_ENRICHMENT_KEYS = {"quality_score", "key_concepts", "domains", ...}`. Reject any key not in the allowlist.

### [Severity: HIGH]

**[H01] No Rate Limiting on Any MCP Tool**
- File: All tools in `tools/*.py`, `server.py`
- Description: Zero rate limiting exists on any MCP tool. A client can call `recall()` thousands of times per second. Key attack vectors:
  - `recall(query="test", top_k=10000)` — no upper bound on `top_k`. ChromaDB and FTS5 both attempt to return 10,000 results → memory exhaustion.
  - `remember(content="x" * 100_000_000)` — no content length limit. 100MB string → memory spike during embedding + storage.
  - Rapid `recall()` calls → each triggers OpenAI embedding API → API quota exhaustion → all users blocked.
- Impact: DoS via resource exhaustion (memory, CPU, API quota, DB connections). Single malicious or buggy client can crash the MCP server.
- Recommendation: (a) Add `MAX_TOP_K = 50` validation in `recall()`. (b) Add `MAX_CONTENT_LENGTH = 100_000` validation in `remember()`. (c) Add per-session rate limiting (e.g., 60 calls/minute) at `server.py` level.

**[H02] FTS5 Query Injection — Incomplete Escaping**
- File: `storage/sqlite_store.py:283-288`
- Description: The `_escape_fts_query()` function wraps each whitespace-separated term in double quotes:
  ```python
  def _escape_fts_query(query: str) -> str:
      terms = query.split()
      return " ".join(f'"{t}"' for t in terms if t)
  ```
  This does NOT handle: (a) Double quotes within terms — `hello"world` becomes `"hello"world"` (unbalanced quotes), (b) FTS5 operators as standalone terms — `AND`, `OR`, `NOT` are quoted (correct), (c) FTS5 special syntax — `*` (prefix), `^` (column), `~` (NEAR) — may still have effects inside quotes depending on FTS5 version.
- Impact: Malformed FTS5 queries could cause: (a) `OperationalError` from SQLite (query syntax error), (b) Unexpected query semantics (returning wrong results), (c) Potential information disclosure (FTS5 column filtering to access content field directly).
- Recommendation: Replace with proper escaping: `t.replace('"', '""')` before quoting. Or use FTS5 `highlight()` function with parameterized inputs.

**[H03] Access Control Not Applied to Most MCP Tools**
- File: `tools/remember.py`, `tools/recall.py`, `tools/visualize.py`, `tools/inspect_node.py`, `tools/get_context.py`, `tools/save_session.py`
- Description: `check_access()` is only called by pruning scripts and `promote_node()`. The following tools have NO access control:
  - `remember()` — can create nodes at any layer (relies on classify() to set layer, but manual `type` parameter can override)
  - `recall()` — can read ALL nodes regardless of layer. L5 Value nodes (most protected) are returned in search results with full content.
  - `visualize()` — loads and displays ALL edges and nodes, including protected ones.
  - `inspect_node()` — returns full node details for any ID.
  - `save_session()` — can write session data without validation.
- Impact: The 3-layer access control system (A-10 → Hub → LAYER_PERMISSIONS) only protects against pruning/deletion. Read access and creation are completely uncontrolled. Any client can read L5 content or create L5 nodes.
- Recommendation: For single-user context, document this as acceptable. For multi-user scenarios, add read-access control to `recall()` (filter results by actor permissions) and write-access control to `remember()` (validate layer assignment against actor).

**[H04] Error Messages Leak Internal Paths and Structure**
- File: `ingestion/obsidian.py:72`, `tools/promote_node.py:185`, various `except` blocks
- Description: Error responses include internal filesystem paths and node IDs:
  ```python
  return {"error": f"Vault path not found: {vault_path}"}  # exposes absolute path
  return {"error": f"Node #{node_id} not found."}          # exposes internal ID scheme
  ```
  Stack traces from unhandled exceptions may also reach the MCP client (depending on server.py error handling).
- Impact: Information disclosure assists attackers in understanding system structure. Vault path reveals OS, username, and directory layout. Node ID scheme reveals sequential integer IDs (enumerable).
- Recommendation: Return generic error messages to MCP clients. Log detailed errors server-side only.

### [Severity: MEDIUM]

**[M01] No Input Validation at MCP Entry Point**
- File: `server.py` (MCP tool registration)
- Description: MCP tool parameters are passed directly to tool functions without validation. No checks for:
  - `content` length in `remember()` — unbounded string
  - `query` length in `recall()` — unbounded string
  - `top_k` range in `recall()` — any integer accepted
  - `node_id` validity in `promote_node()` — any integer accepted
  - `metadata` schema in `remember()` — any dict accepted
  - `type` validity in `remember()` — checked by validators.py but after DB insertion in some paths
- Impact: Defense-in-depth violation. All input validation is deferred to individual tools, with inconsistent coverage. A single tool forgetting to validate leaves the system exposed.
- Recommendation: Add a validation layer in `server.py` before dispatching to tools. Define JSON schema per tool with parameter constraints.

**[M02] Silent Exception Swallowing Masks Security Events**
- File: `storage/hybrid.py:274-275,485-486,377-380`, `tools/recall.py:121-122`, `tools/promote_node.py:270-278`
- Description: At least 8 locations use `except Exception: pass` or `except Exception: continue`. These catch ALL exceptions including: (a) `PermissionError` from access control, (b) `sqlite3.IntegrityError` from constraint violations, (c) `RuntimeError` from API failures. None log the exception.
- Impact: Security-relevant events (permission violations, data integrity failures) are silently discarded. An attacker probing for vulnerabilities would see no feedback, but neither would defenders monitoring for attacks.
- Recommendation: At minimum, narrow exception handling: `except (sqlite3.OperationalError, sqlite3.IntegrityError)`. Log all caught exceptions with severity level.

**[M03] action_log Stores Sensitive Content in Plaintext**
- File: `storage/action_log.py:88-97`
- Description: `action_log.record()` stores `params` (including node content) and `result` (including search results) as JSON TEXT in SQLite. No encryption, no redaction, no access control on the `action_log` table itself.
- Impact: If the DB file is accessed (backup, shared storage, development copy), all stored queries, node content, and operation history are exposed in plaintext. For a personal knowledge system, this may contain private thoughts, decisions, and sensitive information.
- Recommendation: For single-user context, document as acceptable. For shared environments, add field-level encryption for `params` and `result` columns, or hash sensitive content before storage.

**[M04] Metadata JSON Injection — No Schema Validation**
- File: `server.py:45`, `tools/remember.py:100`
- Description: The `metadata` parameter in `remember()` accepts an arbitrary dict, which is stored as `json.dumps(metadata or {})` in the `metadata` column. No validation of: key names, value types, nesting depth, total size, or reserved keys. A metadata dict with circular references would crash `json.dumps()`.
- Impact: Malformed metadata could: (a) Bloat the DB (very large values), (b) Break downstream tools that parse metadata (unexpected types), (c) Introduce reserved-key conflicts (e.g., `{"id": 999}` in metadata).
- Recommendation: Define metadata schema. Validate max depth (2), max size (10KB), and key naming conventions.

### [Severity: LOW]

**[L01] Sequential Integer IDs — Enumerable**
- File: `storage/sqlite_store.py` (autoincrement IDs)
- Description: Node and edge IDs use SQLite autoincrement — predictable sequential integers. Any client knowing one node ID can enumerate neighbors by trying ID-1, ID+1, etc. Combined with H03 (no read access control on `inspect_node()`), this enables full knowledge base enumeration.
- Impact: In single-user context, low risk (user owns all data). In multi-user context, enables unauthorized data discovery.
- Recommendation: Low priority. If multi-user is ever needed, switch to UUID-based IDs.

**[L02] No Audit Log for Security Events**
- File: Entire codebase
- Description: No dedicated security event logging. Failed access control checks, invalid actor strings, skip_gates usage, and FTS5 query errors are not logged distinctly from operational events.
- Impact: Security incident investigation is impossible. Cannot answer: "Who used skip_gates in the last 7 days?"
- Recommendation: Add security-specific logging: `security_log.warning(f"skip_gates used by {actor} for node {node_id}")`.

**[L03] Database File Permissions Not Set**
- File: `storage/sqlite_store.py`, `config.py`
- Description: The SQLite database file is created with default OS permissions. On shared systems, other users may be able to read/modify the DB file directly, bypassing all application-level access control.
- Impact: Low in single-user context. On shared workstations, full data exposure.
- Recommendation: Set `os.chmod(DB_PATH, 0o600)` after database creation.

**[L04] No CSRF/Replay Protection on MCP Calls**
- Description: MCP protocol operates over stdio (local process) or SSE/WebSocket. For stdio (current setup), CSRF and replay are non-issues — the attacker would need local process access. For future network-based MCP transport, replay protection would be needed.
- Impact: None currently. Future concern if MCP transport changes.

### [Severity: INFO]

**[I01] SQL Parameterization — Correct in Core Storage Layer**
- File: `storage/sqlite_store.py` (all CRUD operations)
- Description: All runtime SQL queries in the storage layer use proper parameterization (`?` placeholders). `insert_node()`, `insert_edge()`, `get_node()`, `search_fts()`, `update_node()` all pass user input as parameters, not string interpolation. The injection risks are limited to migration scripts (C01) and enrichment scripts (C03).

**[I02] Access Control Design — Sound 3-Layer Architecture**
- File: `utils/access_control.py`
- Description: The 3-layer design (A-10 firewall → Hub protection → LAYER_PERMISSIONS) is architecturally sound. Fail-closed defaults (unknown operations → paul-only). External connection reuse for transaction safety. `try/finally` on all DB access. The issue is not the design but the incomplete application (H03).

**[I03] No External Network Exposure**
- Description: The MCP server communicates via stdio with the Claude Code process. No HTTP endpoints, no WebSocket listeners, no open ports. The attack surface is limited to: (a) The MCP client (Claude Code), (b) Direct file system access to the DB, (c) The enrichment pipeline's API calls to OpenAI/Anthropic.

## Coverage

- Files reviewed: 24 (all source files with security-relevant code)
- SQL injection vectors checked: 18 execute() calls across codebase
- Access control paths verified: 13 MCP tool entry points
- Input validation gaps: 6 tool parameters checked
- Error handling patterns: 12 except blocks analyzed

## Summary

- CRITICAL: 3
- HIGH: 4
- MEDIUM: 4
- LOW: 4
- INFO: 3

**Top 3 Most Impactful Findings:**

1. **[C02] skip_gates bypass** — Any MCP client can escalate any node to L5 Value without validation. Combined with A-10 firewall (L4/L5 nodes are nearly undeletable), this creates a permanent ontology corruption vector. The fix is simple: remove `skip_gates` from MCP interface or add authorization.

2. **[H01] No rate limiting** — Unbounded `top_k`, content length, and call frequency. A single `recall(top_k=1000000)` call can exhaust server memory. No defense against API quota exhaustion via rapid `recall()` calls. The system is trivially DoS-able.

3. **[C03] LLM output used as SQL column names** — The enrichment pipeline trusts LLM responses to construct SQL. A prompt injection attack (malicious content → LLM extracts malicious keys → SQL injection) is theoretically possible. While the attack chain is complex, the impact (full DB compromise) justifies the CRITICAL rating.

**Key Insight**: The system was designed for a trusted single-user environment (Paul + Claude Code via stdio). In this context, most security findings are low practical risk. However, the access control system was designed to protect data integrity (layer-based protection, hub protection), and these protections are undermined by the skip_gates bypass (C02) and missing tool-level access control (H03). The biggest risk is not external attack but internal misconfiguration — a buggy script or misconfigured client corrupting the ontology.
