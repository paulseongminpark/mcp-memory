# Utils And Ontology Review - Round 1 (Correctness)
> Reviewer: Codex
> Date: 2026-03-06
> Files Reviewed: utils/__init__.py, utils/similarity.py, utils/access_control.py, ontology/validators.py, ontology/schema.yaml, config.py

## Findings
### CRITICAL
- `config.py` has no `NODE_TYPES` or full type-to-layer registry. The only runtime layer map is `PROMOTE_LAYER` at `config.py:253-258`, which covers 12 types. `ontology/schema.yaml` defines 50 node types with layers, including `Decision` (`ontology/schema.yaml:52`), `Project` (`ontology/schema.yaml:137`), `Mental Model` (`ontology/schema.yaml:233`), `Lens` (`ontology/schema.yaml:238`), `Axiom` (`ontology/schema.yaml:245`), `Wonder` (`ontology/schema.yaml:255`), and `Aporia` (`ontology/schema.yaml:260`). Runtime code therefore cannot assign correct layers for 38 schema types.
- `ontology/validators.py:24-49` falls back to schema only on exception, not on an empty `type_defs`. `server.py:342` calls `init_db()`, and `storage/sqlite_store.py:163-208` creates empty `type_defs`/`relation_defs`. On a fresh DB, valid types are rejected instead of using schema fallback.

### HIGH
- `config.py:245-248` still allows promotion targets `Evidence`, `Heuristic`, and `Concept`, but `scripts/migrate_v2_ontology.py:62,69,72` marks those types deprecated. The promotion config can generate ontology states that the live `type_defs` model says should no longer be created.
- `enrichment/classifier.py:8,13`, `enrichment/relation_extractor.py:8,13`, and `scripts/ontology_review.py:43,45` import `get_valid_node_types()` / `get_valid_relation_types()` from `ontology.validators`, but those functions do not exist there. Those entry points fail at import time.
- The ontology sources disagree on relation counts/status. `ontology/schema.yaml` says "48 relation types" at line 4, but actually defines 50 total relations from line 272 onward. `scripts/migrate_v2_ontology.py` inserts 48 active + 2 deprecated relations. `config.py:114-147` exposes 50 relation strings with no deprecated status layer.

### MEDIUM
- `utils/access_control.py` correctly implements F1-style L4/L5 content protection, but not the full advertised A-10 F1-F6 firewall surface. The code and tests only cover F1 semantics.
- `utils/access_control.py:177-181` defaults missing nodes to layer 0. That is conservative for read availability but means callers must separately validate node existence before trusting an allow decision.

### LOW
- `utils/similarity.py` is aligned and internally consistent; no correctness issues were found there.

### INFO
- Count comparison from the repo: `ontology/schema.yaml` has 50 node types and 50 total relation types; `scripts/migrate_v2_ontology.py` has 31 active + 19 deprecated types and 48 active + 2 deprecated relations; `config.py` has 50 relation strings and no full node-type registry.
- `RELATION_TYPES` and `ALL_RELATIONS` in `config.py` are internally consistent with each other.

## Coverage
- Read `utils/access_control.py`, `utils/similarity.py`, `ontology/validators.py`, `ontology/schema.yaml`, and `config.py` in full.
- Compared schema counts and sets against `config.py` and `scripts/migrate_v2_ontology.py` constants.
- Checked validator behavior against the bootstrap path triggered by `server.py`.

## Summary
Ontology truth is split three ways across schema, config, and seeded DB tables. The biggest correctness issue is the missing full type registry in `config.py`, which cascades into wrong layers, firewall gaps, and invalid promotions.
