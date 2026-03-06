# Storage Review - Round 2 (Architecture)
> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Architecture
> Files Reviewed: storage/sqlite_store.py, storage/hybrid.py, storage/vector_store.py, storage/action_log.py, data/memory.db

## Findings
### CRITICAL
- None.

### HIGH
- `H01` `storage/hybrid.py:385`, `storage/hybrid.py:165`, `storage/hybrid.py:289`, `storage/hybrid.py:332`: `hybrid_search()` is not architected as a read-only query path. It ranks results, mutates node learning state, runs promotion checks, and writes recall activations in one call. That couples retrieval, learning, and audit concerns into a single transaction boundary. The result is a hard-to-test path with non-obvious side effects and no clean read-model boundary.
- `H02` `storage/sqlite_store.py:21`: schema ownership is fragmented. `init_db()` creates the core tables, but the live database still has no `meta` table and no `recall_log` table even though `tools/recall.py:111-116` and `tools/promote_node.py:39-45` depend on them. Architecture-wise, startup initialization and migration ownership are split across storage and scripts, so the storage layer is not the canonical source of schema truth.

### MEDIUM
- `M01` `storage/sqlite_store.py:11`, `scripts/migrate_v2_ontology.py:157`, `scripts/hub_monitor.py:25`, `scripts/pruning.py:25`: connection policy is duplicated instead of centralized. The codebase has multiple `_connect()` or `_get_conn()` helpers with slightly different responsibilities. This is a design smell because transaction behavior, pragmas, timeouts, and row factories can drift by entrypoint.
- `M02` `storage/hybrid.py:443-461`, `tools/recall.py:51-72`, `tools/promote_node.py:57-73`: the storage-facing query patterns contain multiple N+1 shapes. `hybrid_search()` fetches candidate nodes one by one after ranking, `recall()` loads edges per result, and `swr_readiness()` loads neighbor projects one row at a time. These are manageable at current scale but indicate that the storage API is too primitive for higher-level use cases.
- `M03` live DB indexes show only single-column indexes on the hot tables: `idx_nodes_type`, `idx_nodes_project`, `idx_nodes_status`, `idx_edges_source`, `idx_edges_target`, `idx_edges_relation`. The active query patterns often combine predicates such as type + status, project + status, or source/target + relation. The index strategy is serviceable for a small dataset, but it is not shaped around real query compositions.
- `M04` `storage/action_log.py:48`: `record()` supports external transactions, but higher layers rarely exploit that capability. The storage layer exposes a useful transactional building block without a consistent unit-of-work pattern above it.

### LOW
- `L01` `storage/vector_store.py:39`: the vector store is a very thin adapter and repeats collection setup plus count-style checks that are effectively infrastructure concerns. The abstraction is not wrong, but it is too narrow to shield callers from backend details.
- `L02` `storage/sqlite_store.py` mixes schema creation, CRUD, and search helpers in one module. The file remains readable at current size, but the design trend is toward a monolithic storage facade rather than explicit repositories.

### INFO
- `I01` Exact duplicate: `_connect()` in `scripts/migrate_v2_ontology.py:157` mirrors the store-level connection bootstrap in `storage/sqlite_store.py:11`.
- `I02` Near duplicate: pruning archive logic appears both in `scripts/daily_enrich.py` and `scripts/pruning.py`, which increases the chance that storage assumptions drift.
- `I03` Naming consistency is mostly stable inside `storage/`, but code outside the layer reintroduces alternate connection helper names (`_connect`, `_get_conn`) for the same concept.

## Coverage
- Live schema inspected: `nodes=3299`, `edges=6329`, `action_log=3206`, `type_defs=50`, `relation_defs=50`, `hub_snapshots=0`, `meta` missing, `recall_log` missing.
- Key cyclomatic complexity: `storage/hybrid.py:385` `hybrid_search()` = 28, `storage/hybrid.py:165` `_bcm_update()` = 25, `storage/hybrid.py:289` `_sprt_check()` = 10, `storage/action_log.py:48` `record()` = 8, `storage/vector_store.py:39` `search()` = 7, `storage/sqlite_store.py:291` `search_fts()` = 4.
- Code duplication checked for exact helper reuse and near-duplicate workflow logic.
- Naming consistency checked for connection helpers, DB path ownership, and storage API verb usage.

## Summary
The storage layer is ambitious but not cleanly bounded. The biggest design issue is that retrieval is also a learning-and-logging pipeline, which makes the storage API do too much in one place. The second issue is schema ownership: the code relies on tables that the canonical store bootstrap does not create. For a better architecture, the project needs one schema authority, one connection policy, and a stricter split between query paths and mutation paths.
