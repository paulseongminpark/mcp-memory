# Architecture Review: mcp-memory v2.1

## 01. Storage Layer Architecture
- **Layer boundary clarity (storage vs tools):** The storage layer (`sqlite_store.py`, `vector_store.py`) encapsulates all database connections and raw interactions, but tools layer functions often import `sqlite_store` directly. Boundaries are clear in terms of files but there are no abstract interfaces (like a Repository pattern).
- **DB abstraction quality (raw SQL vs ORM patterns):** The project uses raw SQL with `sqlite3` and `execute()` instead of an ORM. This avoids ORM overhead and gives precise control over FTS5 and recursive CTEs, but leaves raw SQL strings spread across the files.
- **Transaction handling patterns:** Most write operations handle transactions inline (`conn.commit()` immediately after executing inserts). In complex operations like `_bcm_update()`, a larger transaction is correctly implemented by executing multiple updates before a single commit.
- **Connection lifecycle management:** The `_connect()` method opens a new connection for almost every function call. While SQLite in WAL mode can handle this, it creates connection churn. Context managers (`with sqlite3.connect(...)`) would make lifecycle management safer and cleaner.
- **Index strategy analysis:** FTS5 is utilized heavily via triggers (`nodes_ai`, `nodes_ad`, `nodes_au`) which is an excellent design to keep text search indexes automatically synchronized. B-tree indexes are well-placed on `type`, `project`, `status`, `layer`, `source_id`, `target_id`.
- **Query performance patterns (N+1, full scans):** N+1 queries are largely avoided in the main recall loop by doing batched updates (e.g., in `_bcm_update` passing multiple IDs instead of single updates).

## 02. Tools Layer Architecture
- **Tool-storage coupling analysis:** Tools are tightly bound to the specific storage implementations (`sqlite_store` and `vector_store`). Testing requires extensive patching of these concrete storage classes.
- **Shared code patterns (DRY compliance):** Good DRY compliance; for instance, the `remember()` top-level API elegantly delegates to shared modular functions (`classify()`, `store()`, `link()`), allowing parts of the pipeline to be tested or invoked independently.
- **Error propagation patterns:** Error handling frequently uses `except Exception: pass` (e.g., in `_bcm_update`, `_sprt_check`). While this intentionally ensures auxiliary features (like BCM logging) do not crash the primary `recall` flow, it hides potential systemic errors. Explicit logging should be used.
- **Response format consistency across tools:** High consistency. Standardized dictionary returns for tools (`recall` always returns `{"results": [...], "count": N, "message": "..."}`).
- **Tool composability:** Tools compose well horizontally; `recall` leverages `hybrid_search`, and `remember` integrates ontology and storage layers fluidly.

## 03. Utils & Ontology Architecture
- **Type system design quality:** The dynamic ontology approach is innovative. Types are primarily validated against a `type_defs` SQLite table, providing a dynamic rule engine.
- **Validator extensibility:** The validator (`validate_node_type`) supports canonical name correction and deprecation tracking (`replaced_by`). It handles missing DB structures by gracefully falling back to `schema.yaml`.
- **Config organization and discoverability:** System constants, weights (e.g., `UCB_C_FOCUS`, `SPRT_ALPHA`), and thresholds are neatly extracted into a `config.py` module.
- **Schema evolution strategy:** Strong schema evolution support via the `ontology_snapshots` table and automatic relation fallback logic in `insert_edge`.
- **Config-code separation quality:** Configuration is well separated into `config.py`, making algorithms easily tunable without modifying core business logic.

## 04. Scripts Architecture
- **Script-library boundary:** Scripts leverage the core tools and storage libraries rather than duplicating logic. Migration scripts explicitly manage state transitions using standard internal APIs.
- **CLI interface design patterns:** While CLI definitions weren't fully parsed, the system relies on structured MCP requests, treating scripts largely as batch offline processors (e.g., daily enrichments).
- **Idempotency guarantees:** Many functions employ idempotency (e.g., `CREATE TABLE IF NOT EXISTS`, FTS triggers using `ON CONFLICT DO UPDATE`). 
- **Dependency on main codebase internals:** Scripts seem to safely depend on the main internal API structures, reducing duplicate query logic.

## 05. Spec Architecture
- **Spec quality: internal consistency:** High adherence to specifications. Comments directly cite spec codes (e.g., "A-10 F3", "B-12 BCM", "C-11 SPRT"), making traceability outstanding.
- **Cross-spec contradictions:** No major contradictions observed, but overlapping complexities (BCM updates and SPRT checks happening simultaneously during a simple `recall` operation) risk cognitive overload.
- **Over-specification (too prescriptive) areas:** The algorithmic precision around UCB graph traversal, BCM reinforcement, and SPRT probability math suggests high-level academic complexity which might be over-specified for a personal memory system context.
- **Under-specification (too vague) areas:** Error handling behaviors and logging strategies are under-specified, leading to silent `pass` catch-all blocks.

## 06. Test Architecture
- **Fixture patterns and quality:** The test suite (`test_remember_v2.py`) uses `unittest.mock` effectively to create simulated DB environments. 
- **Mocking strategy consistency:** Mocking is thorough but tightly coupled to the implementation details of `sqlite_store` (e.g., mocking specific tuple returns from `execute().fetchone()`). 
- **Test isolation:** Excellent test isolation. By decoupling `classify()` from `store()`, tests can validate pure logic functions without involving disk I/O.
- **Assertion quality (precise vs broad):** Assertions are precise (e.g., verifying exact dictionary shapes and specific boolean states like `FIREWALL_PROTECTED_LAYERS == {4, 5}`).
- **`parametrize` usage:** The test suite could greatly benefit from `pytest.mark.parametrize` for data-driven testing (e.g., iterating through different combinations of Types, Layers, and Tiers) instead of writing distinct repetitive methods.

## 07. Data Flow Architecture

```text
       [Content]
           |
           v
      (classify) ------> Type/Layer/Tier rules
           |
           v
       (store) --------> SQLite (nodes/FTS5) & ChromaDB (Vector)
           |
           v
        (link) --------> Vector Search -> Infer Relation -> SQLite (edges)
           |
           +-----------------------------------------------+
                                                           |
       [Query]                                             |
           |                                               |
           v                                               v
       (recall) -------> Hybrid Search (Vector + FTS5 + UCB Graph)
           |
           v
      (activate) ------> Reciprocal Rank Fusion (RRF) Sorting
           |
           v
        (learn) -------> BCM Edge Reinforcement & SPRT Promotion Check
```

- **Identify bottlenecks in the flow:** The synchronous execution of `_bcm_update` and `_sprt_check` inside the main `recall` flow could become a latency bottleneck as the graph scales. 
- **Identify unnecessary indirection:** `recall` acts as a very thin wrapper over `hybrid_search`, passing parameters directly. While not heavily indirect, it borders on boilerplate.
- **Missing short-circuits:** If a user specifies a strict `project` and exact match, skipping the expensive vector/graph traversals might save latency.

## 08. Security Architecture
- **Defense-in-depth analysis:** Excellent. Parameterized queries (`?`) are universally employed, effectively neutralizing SQL injection vectors.
- **Trust boundary diagram:** Input Content -> Ontology Validator -> Sanitized DB/Vector Store. The DB is treated as the source of truth, and unvalidated types are gracefully coerced (`suggest_closest_type`).
- **Principle of least privilege compliance:** The introduction of `FIREWALL_PROTECTED_LAYERS` (L4/L5) strictly enforcing a "no auto-edge" policy is a strong application of privilege separation at the data layer.
- **Safe defaults analysis:** The fallback logic (defaulting unknown relations to `connects_with`, or unknown types to `Unclassified`) establishes very robust, safe defaults.

## 09. Summary
- **Architecture quality score:** 8.5/10
- **Module coupling matrix:**
  - `tools.remember` -> `storage.sqlite_store`, `storage.vector_store`, `ontology.validators`
  - `tools.recall` -> `storage.hybrid`
  - `storage.hybrid` -> `storage.sqlite_store`, `storage.vector_store`, `graph.traversal`
- **Top 5 design improvement recommendations:**
  1. **Connection Management:** Implement standard Context Managers for `sqlite3` to prevent connection churn and ensure reliable cleanup.
  2. **Decouple Storage:** Introduce abstract repository interfaces to decouple the `tools` logic from concrete SQLite/ChromaDB calls, aiding testing and future scalability.
  3. **Address Silent Failures:** Replace `except Exception: pass` with proper application-level logging to ensure background tasks (like SPRT/BCM) do not fail silently.
  4. **Test Parameterization:** Refactor repetitive `unittest` blocks using `pytest.mark.parametrize` to reduce test boilerplate and increase coverage.
  5. **Async/Background Processing:** Offload BCM updates and SPRT checks into a background task/queue so they do not block the primary `recall` latency path.
- **Strengths to preserve:**
  - The clean separation of `classify`, `store`, and `link` pipelines.
  - Automatic FTS5 sync via SQLite triggers.
  - The explicit referencing of specification IDs (A-10, B-12) directly inside the codebase.