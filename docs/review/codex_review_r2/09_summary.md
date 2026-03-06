# Summary Review - Round 2 (Architecture)
> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Architecture
> Files Reviewed: server.py, storage/*.py, tools/*.py, utils/access_control.py, ontology/schema.yaml, config.py, scripts/**/*.py, tests/*.py, docs/05-full-architecture-blueprint.md, docs/ideation/*.md, data/memory.db

## Findings
### CRITICAL
- `C01` `server.py:40`, `server.py:116`, `server.py:232`, `utils/access_control.py:146`: the main security boundary is bypassed. Authorization logic exists, but the primary MCP entrypoints do not use it.

### HIGH
- `H01` there is no single source of truth for schema and ontology. `storage/sqlite_store.py`, `ontology/schema.yaml`, migration/spec docs, and the live DB all describe overlapping but different system states.
- `H02` `storage/hybrid.py:385` makes read paths mutate state. Retrieval, learning, and logging are architecturally fused.
- `H03` tools depend on private storage details such as `sqlite_store._connect()`, so the application boundary is weak.
- `H04` major product logic lives in `scripts/` and is duplicated across enrichment and pruning workflows.

### MEDIUM
- `M01` the test suite is strong locally but lacks a shared fixture and contract-test architecture.
- `M02` naming and audit vocabularies drift across code and specs, especially around deprecated ontology names, action types, and old table names.

### LOW
- `L01` the codebase contains many pragmatic building blocks: explicit validators, an action log, a live ontology table model, and useful separation between some storage and tool modules. The problem is composition, not lack of effort.

### INFO
- `I01` Overall architectural verdict: ambitious but fragmented.

## Coverage
### Architecture Scorecard
| Area | Score | Notes |
| --- | --- | --- |
| Storage | 5/10 | Strong ideas, weak boundary between query and mutation, fragmented schema ownership |
| Tools | 4/10 | Functional API surface, but wrapper drift and private storage coupling |
| Utils/Ontology | 4/10 | Rich ontology model, but three active sources of truth |
| Scripts | 3/10 | Too much core logic in operational entrypoints |
| Spec hygiene | 3/10 | Large corpus with unresolved contradictions |
| Test architecture | 5/10 | Good unit intent, weak shared fixtures and contract coverage |
| Security architecture | 3/10 | Controls exist, but not at the entry boundary |
| Overall | 4/10 | Capable system with substantial architectural debt |

### Coupling Matrix
| Area | storage | tools | utils | ontology | scripts | embedding | ingestion | graph |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| storage | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| tools | 9 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| scripts | 6 | 0 | 5 | 1 | 6 | 2 | 0 | 0 |
| server.py | 1 | 1 | 0 | 1 | 1 | 0 | 1 | 0 |

### Cyclomatic Complexity Report
| Function | Complexity |
| --- | --- |
| `scripts/enrich/node_enricher.py:418` `enrich_batch_combined()` | 43 |
| `tools/analyze_signals.py:10` `analyze_signals()` | 35 |
| `storage/hybrid.py:385` `hybrid_search()` | 28 |
| `scripts/enrich/node_enricher.py:301` `enrich_node_combined()` | 28 |
| `scripts/enrich/node_enricher.py:652` `_apply()` | 28 |
| `storage/hybrid.py:165` `_bcm_update()` | 25 |
| `scripts/session_context.py:14` `get_context_cli()` | 24 |
| `scripts/enrich/relation_extractor.py:592` `run_e14()` | 22 |
| `tools/promote_node.py:167` `promote_node()` | 21 |
| `scripts/build_graph.py:40` `build_vector_edges()` | 21 |

### Duplication Report
- Exact duplicates: `_get_total_recall_count()` in `tools/analyze_signals.py:180` and `tools/promote_node.py:87`.
- Exact duplicates: `_connect()` in `scripts/migrate_v2_ontology.py:157` and `storage/sqlite_store.py:11`.
- Exact duplicates: `_get_node()` in `scripts/enrich/node_enricher.py:632` and `scripts/enrich/relation_extractor.py:157`.
- Exact duplicates: `_get_conn()` in `scripts/hub_monitor.py:25` and `scripts/pruning.py:25`.
- Near duplicates: `client`, `anthropic_client`, and `_call_json()` in the three enrichment classes.
- Near duplicates: pruning archive workflows in `scripts/daily_enrich.py` and `scripts/pruning.py`.

### Naming Consistency Report
- `DB_PATH` is defined in five places.
- `ROOT =` is defined in fifteen files.
- `sys.path.insert` appears twenty-four times.
- The repo still mixes deprecated ontology names (`Heuristic`, `Concept`) with current ones.
- Audit naming drifts between taxonomy-specific forms and generic names like `archive`.
- Test names mix `tc`, `td`, and descriptive English styles.

## Summary
The design is capable but not well consolidated. The system has solid ideas, but they are spread across too many ownership centers: storage owns some schema, scripts own some runtime behavior, specs own alternative truths, and tools reach directly into internals. The top design recommendations are:

1. Establish one canonical schema and ontology source, then generate or migrate everything else from it.
2. Split retrieval from learning side effects so `recall` can be a true query path.
3. Introduce a real application-service and repository layer; stop using `sqlite_store._connect()` from tools.
4. Move enrichment and pruning logic out of `scripts/` into reusable modules, and unify the LLM client scaffolding.
5. Enforce `check_access()` at MCP entrypoints and narrow high-risk tools behind capability gates.
6. Add shared test fixtures plus contract-level integration tests for the public tool surface.
