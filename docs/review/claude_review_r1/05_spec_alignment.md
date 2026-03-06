# Spec Alignment Review - Round 1 (Correctness)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Spec-Code 1:1 Mapping & Consistency
> Files Reviewed: All 10 R3 final specs ↔ All 24 implementation files + config.py + schema.yaml + migrate_v2_ontology.py

## Findings

### [Severity: HIGH]

**H-01** 3-source layer conflict: Question and Value types have different layers across sources

- Sources:
  - `ontology/schema.yaml` (v2.0 schema definition)
  - `scripts/migrate_v2_ontology.py` (v2.1 type_defs population)
  - `config.py` PROMOTE_LAYER (promotion pathway)
- Conflicts:

  | Type | schema.yaml | migrate_v2_ontology | config.py PROMOTE_LAYER |
  |------|------------|--------------------|-----------------------|
  | Question | **0** | **1** | (not present) |
  | Value | **5** | **4** | **5** |

- Description:
  - **Question**: schema.yaml places it in Layer 0 (원시 경험), migration places it in Layer 1 with super_type="Signal". The migration code wins at runtime (type_defs table), so Question nodes get layer=1.
  - **Value**: schema.yaml and config.py agree on Layer 5, but migration inserts it as Layer 4 (Worldview). Since type_defs table is populated by migration, the runtime layer is 4, not 5. This conflicts with config.py's PROMOTE_LAYER["Value"]=5.
  - The promotion pathway: Principle(L3)→Value should set layer=5 per PROMOTE_LAYER, but type_defs says Value is L4. After promotion, the node's layer (5 from PROMOTE_LAYER) disagrees with its type's canonical layer (4 from type_defs).
- Impact: Layer-dependent features (access_control F1 for L4/L5, BCM LAYER_ETA, tier assignment) behave differently depending on which source determined the layer. Value nodes promoted via promote_node get layer=5, but nodes created via migration have layer=4.
- Recommendation: Resolve the canonical layer for Question (0 or 1?) and Value (4 or 5?) across all 3 sources. Ensure schema.yaml, type_defs, and PROMOTE_LAYER agree.

---

### [Severity: MEDIUM]

**M-01** schema.yaml lists all 50 types as active — migration marks 19 as deprecated

- File: `ontology/schema.yaml` (50 active types), `scripts/migrate_v2_ontology.py:60-81` (19 deprecated)
- Description:
  - schema.yaml v2.0: All 50 types defined as active entries with layers and descriptions
  - migrate_v2_ontology.py type_defs: 31 active + 19 deprecated (with replaced_by mappings)
  - Deprecated types in migration: Evidence→Observation, Trigger→Signal, Context→Conversation, Plan→Goal, Ritual→Workflow, Constraint→Principle, Assumption→Belief, Heuristic→Pattern, Trade-off→Tension, Metaphor→Connection, Concept→Insight, Boundary→Principle, Vision→Goal, Paradox→Tension, Commitment→Decision, Mental Model→Framework, Lens→Framework, Wonder→Question, Aporia→Question
  - validators.py fallback: when type_defs table doesn't exist, `_validate_via_schema_yaml()` treats ALL 50 types as active — deprecated types pass validation
  - This creates a behavioral split: type_defs present → 31 active types, type_defs absent → 50 active types
- Impact: In a fresh database without migration, all 50 types are valid. After migration, only 31 are active. This means a test environment (no migration) and production (with migration) behave differently for 19 types.
- Recommendation: Either (a) update schema.yaml to mark deprecated types, or (b) add a `status` field to schema.yaml's node_types, or (c) document that schema.yaml is the v2.0 reference and type_defs is the v2.1 authority.

---

**M-02** VALID_PROMOTIONS allows promotion to "Evidence" — a deprecated type

- File: `config.py:245` (`"Observation": ["Signal", "Evidence"]`)
- Spec: `migrate_v2_ontology.py:62` (Evidence status=deprecated, replaced_by=Observation)
- Description:
  - VALID_PROMOTIONS defines: `"Observation": ["Signal", "Evidence"]`
  - Evidence is deprecated (replaced by Observation)
  - promote_node.py checks VALID_PROMOTIONS but does NOT validate target_type against type_defs
  - If `promote_node(id=X, target_type="Evidence")` is called, it passes VALID_PROMOTIONS check
  - The node would be promoted to a deprecated type
  - PROMOTE_LAYER["Evidence"]=0, so it gets layer=0 — same as its replacement Observation
- Impact: A node could be promoted to a deprecated type. While functionally equivalent (Evidence is at the same layer as Observation), it's semantically incorrect and creates type inconsistency.
- Recommendation: Remove "Evidence" from VALID_PROMOTIONS for Observation. Only active types should be promotion targets.

---

**M-03** Two relations deprecated in migration but active in config.py ALL_RELATIONS

- File: `config.py:136-137` (viewed_through, interpreted_as in perspective list)
- Migration: `scripts/migrate_v2_ontology.py:126-127` (both status="deprecated")
- Description:
  - `viewed_through` and `interpreted_as` are marked deprecated in RELATION_DEFS
  - But config.py RELATION_TYPES["perspective"] includes both
  - ALL_RELATIONS (generated from RELATION_TYPES) includes them
  - `sqlite_store.insert_edge()` validates against ALL_RELATIONS — deprecated relations pass as valid
  - No auto-correction for deprecated relations in the edge insertion path (unlike node types which have replaced_by)
  - Config.py comment "48개 관계 타입" may have intended to count only active relations (48), but the dict has all 50
- Impact: New edges can be created with deprecated relation types. Unlike deprecated node types (which get auto-corrected via validators.py), deprecated relations silently persist.
- Recommendation: Either (a) remove deprecated relations from RELATION_TYPES, or (b) add deprecated-relation handling to insert_edge() similar to how validators.py handles deprecated types.

---

**M-04** PROMOTE_LAYER includes 3 deprecated types as dead entries

- File: `config.py:253-258` (PROMOTE_LAYER)
- Description:
  - PROMOTE_LAYER includes: `"Evidence": 0`, `"Heuristic": 2`, `"Concept": 2`
  - All 3 are deprecated in type_defs (Evidence→Observation, Heuristic→Pattern, Concept→Insight)
  - validators.py auto-corrects these types before classify() reaches PROMOTE_LAYER.get()
  - So these entries are dead code — never reached at runtime
  - Not harmful, but inconsistent with the v2.1 deprecation model
- Impact: None (dead code). Confusing for developers who see deprecated types in the promotion layer map.
- Recommendation: Remove deprecated types from PROMOTE_LAYER.

---

### [Severity: LOW]

**L-01** Spec correction_log uses `event_type` column, implementation uses `created_at`

- Spec: `d-r3-14-pruning-integration.md:256-262`
- Implementation: `scripts/daily_enrich.py:444-451`
- Description:
  - Spec INSERT: `corrected_by, event_type) VALUES (?, ..., 'prune_stage2')`
  - Implementation INSERT: `corrected_by, created_at) VALUES (?, ..., datetime('now'))`
  - Already noted in 04_scripts.md L-02 — the correction_log table schema determines which is correct
- Impact: One of the two will fail depending on actual table schema.

---

### [Severity: INFO]

**I-01** Spec → Code Mapping Table (10 specs, all mapped)

| Spec | Implementation | Match |
|------|---------------|-------|
| a-r3-17 (action_log) | storage/action_log.py | Exact (01_storage I-04) |
| a-r3-18 (remember) | tools/remember.py | Exact (02_tools I-01) |
| b-r3-14 (hybrid) | storage/hybrid.py | Formula match, BCM/UCB disconnect (01_storage H-01,H-02) |
| b-r3-15 (recall) | tools/recall.py | Match with table name divergence (02_tools M-03) |
| c-r3-11 (promotion) | tools/promote_node.py, tools/analyze_signals.py | Formula match, missing action_log (02_tools H-01) |
| c-r3-12 (SPRT validation) | scripts/sprt_simulate.py | Exact (04_scripts I-08) |
| d-r3-11 (validators) | ontology/validators.py | Exact (03_utils I-03) |
| d-r3-12 (drift) | utils/similarity.py, scripts/calibrate_drift.py | Exact (03_utils I-02, 04_scripts I-07) |
| d-r3-13 (access control) | utils/access_control.py, scripts/hub_monitor.py | Exact (03_utils I-01, 04_scripts I-06) |
| d-r3-14 (pruning) | scripts/daily_enrich.py (Phase 6), scripts/pruning.py | Partial — edge archive gap (04_scripts M-01) |

**I-02** Features in spec but NOT in code (gaps)

| Gap | Spec | Status |
|-----|------|--------|
| Edge `archived_at`/`probation_end` columns | d-r3-14 | Schema missing (04_scripts M-01) |
| `importance_score` 3-factor formula | d-r3-14 | Simplified to quality_score only (04_scripts M-02) |
| Pruning constants in config.py | d-r3-14 | Hardcoded (04_scripts M-03) |
| action_log in promote_node | c-r3-11 | Not implemented (02_tools H-01) |
| Dynamic `gates_passed` list | c-r3-11 | Hardcoded ["swr","bayesian","mdl"] (02_tools M-01) |
| `tier` update on promotion | c-r3-11 | Missing from UPDATE (02_tools M-02) |
| UCB `visit_count` loading | b-r3-14 | Not loaded into graph (01_storage H-01) |
| BCM→UCB strength propagation | b-r3-14 | BCM updates `frequency`, UCB reads `strength` (01_storage H-02) |
| `get_valid_node_types()`/`get_valid_relation_types()` | pre-v2.1 | Dropped in refactor (03_utils H-01) |

**I-03** Features in code but NOT in any spec (extras/improvements)

| Extra | File | Assessment |
|-------|------|------------|
| `swr_readiness()` try/except fallback | promote_node.py | Improvement — resilience |
| `_mdl_gate()` uses `import numpy` | promote_node.py | Improvement — cleaner than `__import__` |
| `hub_health_report()` risk levels | hub_monitor.py | Addition — useful operational feature |
| `compute_ihs()` IHS formula | hub_monitor.py | Addition — spec only described check_access integration |
| Phase 1-5 orchestration with budget | daily_enrich.py | v2.0 infrastructure — not spec'd in v2.1 |
| `run_forbidden_params()` | sprt_simulate.py | Matches c-r3-12 Section 6 |
| `print_status()` | pruning.py | Useful CLI feature |
| `require_access()` PermissionError wrapper | access_control.py | Matches spec exactly |

**I-04** Deprecated type mapping (19 types, all with replaced_by)

| Deprecated | Layer | Replaced By | Category |
|-----------|-------|-------------|----------|
| Evidence | 0 | Observation | Experience merge |
| Trigger | 0 | Signal | Signal merge |
| Context | 0 | Conversation | Session merge |
| Plan | 1 | Goal | Goal merge |
| Ritual | 1 | Workflow | Process merge |
| Constraint | 1 | Principle | Abstraction merge |
| Assumption | 1 | Belief | Abstraction merge |
| Heuristic | 2 | Pattern | Pattern merge |
| Trade-off | 2 | Tension | Conflict merge |
| Metaphor | 2 | Connection | Connection merge |
| Concept | 2 | Insight | Insight merge |
| Boundary | 3 | Principle | Principle merge |
| Vision | 3 | Goal | Goal merge |
| Paradox | 3 | Tension | Conflict merge |
| Commitment | 3 | Decision | Action merge |
| Mental Model | 4 | Framework | Framework merge |
| Lens | 4 | Framework | Framework merge |
| Wonder | 5 | Question | Question merge |
| Aporia | 5 | Question | Question merge |

**I-05** Deprecated relation mapping (2 relations)

| Deprecated | Category | Notes |
|-----------|----------|-------|
| viewed_through | perspective | Still in config.py ALL_RELATIONS |
| interpreted_as | perspective | Still in config.py ALL_RELATIONS |

**I-06** RELATION_CORRECTIONS (5 old→new mappings in migration)

| Old | New | Applied During |
|-----|-----|---------------|
| strengthens | supports | Step 5 migration |
| validated_by | validates | Step 5 migration |
| extracted_from | derived_from | Step 5 migration |
| instance_of | instantiated_as | Step 5 migration |
| evolves_from | evolved_from | Step 5 migration |

## Coverage

- Specs mapped: 10/10 R3 final specs
- Implementation files checked: 24 source files + 3 config/schema/migration files
- Cross-references: All findings from 01-04 reviews incorporated
- Deprecation analysis: 19 types + 2 relations + 5 corrections

## Summary

- CRITICAL: 0
- HIGH: 1
- MEDIUM: 4
- LOW: 1
- INFO: 6

**Top 3 Most Impactful Findings:**

1. **H-01** (Layer conflicts for Question and Value): Three authoritative sources (schema.yaml, migration, config.py) disagree on the layer for Question (0 vs 1) and Value (4 vs 5). Since layer determines access control behavior, BCM learning rates, and tier assignment, this inconsistency creates unpredictable behavior depending on which source was used to set the layer.

2. **M-01** (schema.yaml vs type_defs deprecation): schema.yaml says all 50 types are active, but migration creates 19 as deprecated. The validators.py fallback uses schema.yaml when type_defs is absent, creating a behavioral split between fresh/migrated databases. Test environments without migration would accept types that production rejects.

3. **M-03** (Deprecated relations in ALL_RELATIONS): `viewed_through` and `interpreted_as` are deprecated in migration but still active in config.py's relation validation. New edges can be created with deprecated relation types without any warning or correction. The config.py comment "48개" may have been attempting to count only active relations but the dict includes all 50.

**Cumulative Findings (T1-C-01 through T1-C-05):**
- CRITICAL: 0
- HIGH: 5
- MEDIUM: 13
- LOW: 10
- INFO: 37
