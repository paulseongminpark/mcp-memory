# Utils and Ontology Review - Round 2 (Architecture)
> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Architecture
> Files Reviewed: utils/access_control.py, ontology/validators.py, ontology/schema.yaml, config.py, data/memory.db, scripts/export_to_obsidian.py, scripts/session_context.py

## Findings
### CRITICAL
- None.

### HIGH
- `H01` `ontology/schema.yaml`, `config.py`, and the live `type_defs` / `relation_defs` tables are all active ontology sources. That is the core architectural weakness in this area. The validator layer reads from the DB first, the config layer still hardcodes ontology decisions, and the schema file continues to describe the system independently. A type system with three active sources of truth is difficult to evolve safely.
- `H02` `config.py` is over-broad. The same file owns DB paths, model names, recall tuning, promotion thresholds, ontology constants, and `infer_relation()` logic. This collapses environment configuration, policy, and domain rules into one module, which makes architecture changes noisy and tightly coupled.

### MEDIUM
- `M01` `ontology/validators.py:6`, `ontology/validators.py:79`, `ontology/validators.py:108`: extensibility is uneven. Validation itself can consult the live ontology tables, but suggestion logic is still heuristic and content-keyword based. Adding or deprecating types therefore has two change paths: the formal schema path and the suggestion heuristic path.
- `M02` `utils/access_control.py:12` defines its own `DB_PATH` instead of importing the canonical path from `config.py:15`. That is a small code choice with architectural cost because security-sensitive code now owns infrastructure configuration locally.
- `M03` schema evolution is doc-led rather than generated. The live database currently has `31` active and `19` deprecated types, plus `48` active and `2` deprecated relations, while scripts such as `scripts/export_to_obsidian.py:28-52` still query deprecated names like `Heuristic` and `Concept`. The architecture supports deprecation metadata, but the rest of the codebase is not forced to consume it.

### LOW
- `L01` `ontology/validators.py:108` is permissive by design: relation validation can fall back instead of failing hard. That is pragmatic, but it weakens the ontology boundary because bad relations degrade into generic behavior instead of surfacing as first-class migration problems.
- `L02` naming consistency across ontology concepts is still in transition. Historical names such as `Trade-off`, `Mental Model`, `Heuristic`, and `Concept` coexist in docs, code, and exports with newer names. The type system direction is clear, but the naming surface is not yet fully consolidated.

### INFO
- `I01` Exact duplication: `DB_PATH` is defined in `config.py`, `utils/access_control.py`, and three scripts. Path ownership is not centralized.
- `I02` `ontology/schema.yaml:4` says `48 relation types`, while `ontology/schema.yaml:272` says `50 relation types`, and the live database also contains `50` rows in `relation_defs`. That contradiction is both a spec issue and an ontology-governance issue.
- `I03` Naming consistency check found five separate `DB_PATH` definitions and hardcoded deprecated ontology names in script-level consumers.

## Coverage
- Key cyclomatic complexity: `config.py:197` `infer_relation()` = 14, `utils/access_control.py:146` `check_access()` = 7, `ontology/validators.py:6` `validate_node_type()` = 6, `utils/access_control.py:126` `_check_layer_permissions()` = 5, `ontology/validators.py:79` `suggest_closest_type()` = 4, `ontology/validators.py:108` `validate_relation()` = 4.
- Live ontology state inspected: `type_defs=50` rows (`31 active`, `19 deprecated`), `relation_defs=50` rows (`48 active`, `2 deprecated`).
- Duplication checked for config constants, ontology references, and deprecated-type consumers.
- Naming consistency checked across schema comments, config constants, validators, and export scripts.

## Summary
The ontology design is conceptually strong, but its operational architecture is fragile because authority is split across YAML, Python, and live tables. The immediate design recommendation is to pick one canonical ontology source and generate or hydrate the others from it. `config.py` should then shrink back to configuration, while ontology policy and relation inference move into a dedicated domain module.
