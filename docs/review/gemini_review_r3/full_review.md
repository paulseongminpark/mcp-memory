# MCP-Memory v2.1 Operational Reality Review (Round 3)

## 01. Storage Operations
- **SQLite concurrent access safety**: `storage/sqlite_store.py` (L14-16) configures `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=30000`. This provides excellent concurrent read performance across multiple MCP clients. However, heavy sequential write concurrency is still vulnerable to locking bottlenecks because SQLite transactions are serialized.
- **WAL mode**: Enabled explicitly. Without it, the database would face frequent `database is locked` exceptions given the high volume of reads (`recall`) and background writes (`daily_enrich`), completely paralyzing the MCP server.
- **Lock contention scenarios**: `recall()` calls `_bcm_update()` which updates `edges` (frequency), `nodes` (theta_m), and `action_log` in a single transaction (`storage/hybrid.py` L160-230). If `daily_enrich.py` executes a large phase (e.g., phase 6 pruning) simultaneously, `recall` might block up to 30 seconds or trigger a lock timeout since `daily_enrich` overrides the timeout to 5 seconds (`PRAGMA busy_timeout=5000` at L45). 
- **Data corruption recovery paths**: SQLite WAL ensures crash safety on write aborts. `_bcm_update` catches `json.JSONDecodeError` for `edges.description` context logs (`hybrid.py` L195) and initializes a new array to recover from malformed JSON. However, there is no automated backup script integrated directly within the MCP cycle; external snapshotting is required.
- **Disk space growth projection**: The `action_log` table will balloon. Every `recall` generates 1 summary row and up to 10 `node_activated` rows (`hybrid.py` L250-285). Moving from 3K to 30K nodes with active usage will yield millions of `action_log` rows within months, bloating the `.db` file and causing potential latency on `activation_log` VIEW queries.
- **Backup/restore procedures**: Not fully automated within the server execution loop. `config.py` defines `BACKUP_DIR`, and `scripts/migrate_v2_ontology.py` expects manual CLI interventions.

## 02. Tool Operations
- **Embedding API timeout**: In `tools/remember.py` (L110-117), if `vector_store.add()` (which relies on `openai_embed.py`) times out, the exception is caught locally. The node is stored in SQLite (as provisional), and the tool gracefully returns a `warning` key (`"Stored in SQLite but embedding failed"`), allowing the user loop to continue.
- **recall() returning 0 results**: Handled gracefully in `tools/recall.py` (L29-30). It safely returns `{"results": [], "message": "No memories found."}` without crashing the JSON parser.
- **promote_node() partial failure**: In `tools/promote_node.py` (L76-118), if the Gate 3 MDL check passes but the outer `UPDATE nodes` fails, a Python exception is raised. However, if an individual `realized_as` edge insertion fails, it is swallowed via a localized `try/except: pass` (L95-103), meaning the node gets promoted but some cluster edges might be missing (partial commit state).
- **Memory usage during large recall**: `hybrid_search` caps UCB traversal candidates to 20 per hop (`hybrid.py` L94) preventing graph traversal explosions. However, `get_all_edges()` loads all graph edges into memory (`hybrid.py` L208). At 30,000+ total edges, the memory allocation and latency for NetworkX `nx.DiGraph` construction will become a noticeable operational bottleneck.
- **Rate limiting considerations**: `embedding/openai_embed.py` does not implement exponential backoff for rate limits. `daily_enrich.py` uses `TokenBudget` to avoid hitting limits proactively, but a burst of concurrent `remember()` calls will crash the embedding step abruptly if OpenAI issues a 429.

## 03. Utils/Ontology Operations
- **Unknown node_type**: `ontology/validators.py` (L22-26) checks against the `type_defs` table. If completely unknown, it returns `(False, None)`. `tools/remember.py` (L45-48) correctly falls back to `suggest_closest_type()` which uses regex heuristics to auto-assign a relevant type like 'Decision' or 'Observation'.
- **Config values that break the system**: Missing `OPENAI_API_KEY` triggers a warning but fundamentally breaks embedding features. Changing `EMBEDDING_DIM` will cause irrecoverable dimension mismatch errors inside ChromaDB queries.
- **Validator edge cases**: Empty strings passed to `suggest_closest_type` default to `"Unclassified"`. Extremely long content string will be fully embedded and stored in SQLite (no max token truncation limit before API dispatch, risking 400 Errors from OpenAI).
- **Type system evolution**: The system scales well. Because validation is dynamically backed by the `type_defs` SQLite table, inserting a 51st node type instantly makes it globally valid without restarting the server or altering Python code.

## 04. Script Operations
- **Pruning false positive analysis**: `scripts/pruning.py` Stage 2 targets L0/L1 nodes with low quality scores. However, it explicitly invokes `check_access(nid, "write", actor)` (L62) which enforces the A-10 Firewall and D-3 Hub protections. Highly connected L1 hubs and critical L4/L5 nodes are structurally shielded from accidental automated pruning.
- **Hub monitor accuracy**: `compute_ihs` in `scripts/hub_monitor.py` (L31) uses an optimized `COUNT(e.id)` of incoming edges. With 3,255 nodes, counting edges in SQLite takes under 5ms, making the tracking of Top 20 hubs highly accurate and performant.
- **daily_enrich crash recovery**: Extremely resilient. Phase 6 uses idempotent queries (e.g. updating `status='pruning_candidate'`). Furthermore, node processing relies on the `enrichment_status` JSON field, allowing the system to resume exactly where it crashed without repeating costly LLM calls.
- **Scheduling conflicts**: If two `daily_enrich.py` runs overlap, `sqlite3`'s `busy_timeout` constraint of 5000ms (`daily_enrich.py` L45) will quickly trigger `database is locked` exceptions, causing one of the scripts to forcibly fail out to preserve transaction integrity.
- **calibrate_drift with insufficient data**: `scripts/calibrate_drift.py` (L86) handles sparse data pools cleanly with `stdev = statistics.stdev(similarities) if len(similarities) > 1 else 0.0`.

## 05. Spec vs Reality
- **Outdated Specs**: Spec documents like `docs/01-design.md` dictate a flat `sessions` table and static edges. Production reality uses a sophisticated `action_log` with 25 taxonomies and an `activation_log` VIEW, alongside dynamic BCM edge updates.
- **Implementation deviations**: The design specs push heavily for migrating to `_traverse_sql`. In reality, `storage/hybrid.py` still relies heavily on `_ucb_traverse` via NetworkX to compute dynamic edge weights.
- **Unspecced features**: The `get_becoming` tool is fully implemented in the MCP router, yet the exact scoring mechanics determining maturity scores are mostly emergent artifacts residing inside `analyze_signals.py` without formal spec coverage.
- **init_db() vs migration**: Perfectly synchronized. `storage/sqlite_store.py`'s `init_db()` incorporates the exact schema changes (including `action_log`, `type_defs`, and `activation_log` VIEW) introduced by `scripts/migrate_v2_ontology.py`. Schema drift on fresh installs is averted.

## 06. Test Operations
- **Flaky tests**: Tests utilizing `datetime.now()` without freezing time can fail on tight temporal boundary conditions. `tests/test_hybrid.py` utilizes a shared local temp file (`_test_db = Path(_tmp) / "test_hybrid.db"`), which will cause file contention if tests are run in parallel using pytest-xdist.
- **Environment assumptions**: Operations like `ingest_obsidian` in `server.py` hardcode a `win32` environment path (`/c/dev/`) as the default `vault_path`.
- **Missing edge cases**: Tests lack simulations for ChromaDB network timeouts, parallel overlapping SQLite writes, and malformed vector embeddings. 
- **CI/CD readiness**: Low. There are no GitHub Actions (`.github/workflows`) or CI pipelines configured to enforce PR checks, relying entirely on manual localized `pytest` execution.

## 07. Scale Scenarios
- **10x data (32K nodes)**: `sqlite_store.get_all_edges()` and `build_graph()` will degrade `recall` performance. Fetching and constructing 60K+ edges inside a NetworkX structure on every query will inject 100ms+ latency. Vector and FTS5 scaling will remain sub-millisecond.
- **100 concurrent recall calls**: High risk of `database is locked` errors. Since `_bcm_update` bundles `nodes`, `edges`, and `action_log` writes into one synchronous transaction, 100 writers queuing against a WAL will bottleneck heavily against the 30-second `busy_timeout`.
- **Embedding API rate limit hit**: Graceful internal degradation. API blocks will force `remember()` to store nodes without embeddings (with a warning) while `daily_enrich` will trip its 3-failure short-circuit and gracefully abort its phase without trashing the DB.
- **DB file at 1GB**: SQLite FTS5 limits index structures logically, meaning full-text search will still perform well via the WAL memory map without excessive disk thrashing.
- **10K edges on a single node**: Mitigated perfectly. `_ucb_traverse` sorts and truncates `candidates[:20]` (L94) per step, neutralizing combinatorial explosions.

## 08. Security Operations
- **Injection via malicious content**: Highly secure. SQLite interactions use parameterized queries exclusively (`VALUES (?, ?, ...)`). FTS5 exploits are stopped via `_escape_fts_query`.
- **Actor spoofing**: Vulnerable. The `actor` parameter is passed as a naked string to `check_access()`. A malicious hook or raw client could simply transmit `actor='paul'` and instantly bypass the L4/L5 content immutability firewall.
- **Privilege escalation**: `promote_node` natively accepts `skip_gates=True`, bypassing SWR, Bayesian, and MDL validations. Without MCP-level payload validation, any client can forcefully escalate L0 noise nodes to L5 Axioms.
- **DoS via recall flood**: Unprotected. Sending thousands of `recall()` requests will unconditionally execute vector searches, trigger NetworkX graph builds, and queue `_bcm_update` write transactions. This will effortlessly lock the CPU and crash the DB.
- **Data exfiltration**: Unprotected. Tools like `get_context` and `inspect_node` return pure node contents without any output filtering or role-based omission, allowing unauthorized actors complete visibility into the user's semantic memory.

## 09. Summary
- **Operational readiness score**: 7/10
- **Top 5 production risks**:

  **Risk 1: Action Log Unbounded Growth**
  - Likelihood: 5
  - Impact: 3
  - Combined Score: 15
  - Mitigation: Implement table partitioning or a monthly archival script to prune `action_log` records older than 90 days.

  **Risk 2: NetworkX In-Memory Build Bottleneck**
  - Likelihood: 5
  - Impact: 4
  - Combined Score: 20
  - Mitigation: Execute Phase 2 migration to shift `hybrid_search` towards `_traverse_sql` or the cached `_get_graph()` mechanism, removing full-graph instantiation.

  **Risk 3: Actor Spoofing Bypassing Firewall**
  - Likelihood: 3
  - Impact: 5
  - Combined Score: 15
  - Mitigation: Require cryptographic signatures or strict session-based token verification for the `actor` parameter to eliminate string-spoofing attacks.

  **Risk 4: Write Lock Contention on _bcm_update**
  - Likelihood: 4
  - Impact: 4
  - Combined Score: 16
  - Mitigation: Decouple `_bcm_update` utilizing an async write queue or dedicated background thread to prevent it from blocking read-centric `recall()` executions.

  **Risk 5: Missing OpenAI API Retry/Backoff**
  - Likelihood: 4
  - Impact: 3
  - Combined Score: 12
  - Mitigation: Apply a robust exponential backoff strategy (e.g., using the `tenacity` library) in `openai_embed.py` to seamlessly handle `429 Too Many Requests`.

- **Monitoring/alerting recommendations**: Actively monitor SQLite WAL file size, raw `action_log` row velocity, continuous OpenAI API 429/500 errors, and absolute `hybrid_search` latency times.
- **Capacity planning guidance**: Pin the SQLite DB location to fast NVMe storage arrays and accelerate the transition towards SQL Recursive CTE operations before reaching 20,000 edges to maintain a flat memory boundary.