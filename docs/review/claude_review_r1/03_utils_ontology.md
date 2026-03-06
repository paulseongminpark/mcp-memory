# Utils & Ontology Review - Round 1 (Correctness)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Correctness & Completeness
> Files Reviewed: utils/access_control.py, utils/similarity.py, ontology/validators.py, ontology/schema.yaml, config.py

## Findings

### [Severity: HIGH]

**H-01** `get_valid_node_types()` and `get_valid_relation_types()` not defined — ImportError

- File: `ontology/validators.py` (entire file — functions not present)
- Callers:
  - `enrichment/classifier.py:8,13` — `from ontology.validators import get_valid_node_types` → `VALID_TYPES = get_valid_node_types()`
  - `enrichment/relation_extractor.py:8,13` — `from ontology.validators import get_valid_relation_types` → `VALID_RELATIONS = get_valid_relation_types()`
  - `scripts/ontology_review.py:43,45` — `from ontology.validators import get_valid_node_types`
- Description:
  - d-r3-11 spec refactored validators.py from schema.yaml-based to type_defs-based
  - The spec defines 5 functions: `validate_node_type`, `_validate_via_schema_yaml`, `_get_types_from_schema`, `suggest_closest_type`, `validate_relation`
  - Pre-v2.1 validators.py had `get_valid_node_types()` and `get_valid_relation_types()` — these were NOT included in the d-r3-11 spec
  - The v2.1 refactor dropped them, but 3 files still import them
  - These imports are at **module level** (not inside functions) — the files crash on import, not just on call
  - `def get_valid` search across entire codebase: zero results
- Impact: `enrichment/classifier.py` and `enrichment/relation_extractor.py` cannot be imported. The enrichment pipeline's classifier and relation extractor are broken. `scripts/ontology_review.py` also crashes on the import line.
- Recommendation: Add replacement functions to validators.py:
  ```python
  def get_valid_node_types() -> set[str]:
      """type_defs에서 active 타입 목록 반환 (schema.yaml fallback)."""
      from storage import sqlite_store
      conn = sqlite_store._connect()
      try:
          rows = conn.execute(
              "SELECT name FROM type_defs WHERE status = 'active'"
          ).fetchall()
          return {r[0] for r in rows}
      except Exception:
          return _get_types_from_schema()
      finally:
          conn.close()
  ```

---

### [Severity: MEDIUM]

**M-01** PROMOTE_LAYER covers only 12 of 50 node types — 38 types get layer=None

- File: `config.py:253-258` (PROMOTE_LAYER), `tools/remember.py:63` (`PROMOTE_LAYER.get(type)`)
- Spec: `ontology/schema.yaml` defines layers for all 49 non-Unclassified types
- Description:
  - PROMOTE_LAYER maps 12 types: Observation(0), Evidence(0), Signal(1), Pattern(2), Insight(2), Framework(2), Heuristic(2), Concept(2), Principle(3), Belief(4), Philosophy(4), Value(5)
  - schema.yaml defines layers for 49 more types (e.g., Decision=1, Plan=1, Workflow=1, Goal=1, Identity=3, etc.)
  - `classify()` in remember.py: `layer = PROMOTE_LAYER.get(type)` → returns `None` for 38 types
  - Example: `remember(content="...", type="Decision")` → node stored with `layer=NULL` in SQLite
  - schema.yaml says Decision should be layer=1
  - tier assignment also affected: all unmapped types get tier=2 regardless of correct schema layer
- Impact: 38 of 50 node types are stored with incorrect layer=NULL. Layer-dependent features (access_control layer checks, BCM LAYER_ETA lookup, promotion eligibility) operate on stale/null data until manually corrected.
- Recommendation: Either (a) expand PROMOTE_LAYER to cover all 50 types, or (b) use schema.yaml/type_defs as layer source in classify():
  ```python
  layer = PROMOTE_LAYER.get(type)
  if layer is None:
      # Fallback to schema.yaml or type_defs
      layer = _get_layer_from_schema(type)
  ```

---

**M-02** config.py comment says "48개 관계 타입" — actual count is 50

- File: `config.py:113` (`# 48개 관계 타입`)
- Actual: RELATION_TYPES dict contains 50 relations (8+9+6+4+8+5+4+6 = 50)
- Cross-reference: `schema.yaml:272` correctly states "50 relation types"
- Description:
  - The comment was likely correct at an earlier stage and not updated when 2 relations were added
  - ALL_RELATIONS list comprehension (L147) correctly flattens all groups — the runtime value is correct
  - Only the comment is wrong
- Impact: Documentation confusion. A developer reading config.py would believe there are 48 relations when there are actually 50.
- Recommendation: Change comment to `# 50개 관계 타입`.

---

### [Severity: LOW]

**L-01** suggest_closest_type() covers only 12 of 50 types

- File: `ontology/validators.py:88-101`
- Description:
  - Keyword hints defined for 12 types: Decision, Failure, Pattern, Insight, Principle, Framework, Workflow, Goal, Signal, AntiPattern, Experiment, Observation
  - 38 types have no keyword hints — all default to "Unclassified"
  - Missing high-layer types: Value, Belief, Philosophy, Identity, Axiom, etc.
  - Missing common types: Tool, Skill, Project, Agent, Plan, etc.
  - This is consistent with d-r3-11 spec (same 12 types in spec code)
- Impact: When an unknown type is provided and classify() falls back to suggest_closest_type(), only 12 types can be suggested. Content about tools, projects, values, etc. will always be "Unclassified".
- Recommendation: Expand hints dict to cover more types, prioritizing frequently-used types from the ontology.

---

**L-02** validate_relation() exception fallback returns (True, None) — no schema.yaml fallback

- File: `ontology/validators.py:130-132`
- Description:
  - When `relation_defs` table doesn't exist, the except block returns `(True, None)`
  - This means ANY relation string passes validation when the table is missing
  - By contrast, `validate_node_type()` has `_validate_via_schema_yaml()` fallback
  - `validate_relation()` has no equivalent `_validate_via_schema_relations()` fallback
  - d-r3-11 spec has the same code — this is spec-level, justified by "insert_edge fallback이 이미 있으므로"
- Impact: Low — `sqlite_store.insert_edge()` already validates against ALL_RELATIONS and falls back to "connects_with". The validator is redundant. But asymmetric fallback behavior (node types have fallback, relations don't) is inconsistent.
- Recommendation: Add schema.yaml-based relation validation fallback for consistency, or document the asymmetry.

---

### [Severity: INFO]

**I-01** access_control.py exactly matches d-r3-13 spec

- File: `utils/access_control.py` (216 lines)
- Verification:
  - LAYER_PERMISSIONS dict: all 6 layers (L0-L5) × 5 operations — exact match
  - `_check_a10_firewall()`: L4/L5 content ops → paul only, metadata → paul/claude — exact match
  - `_get_top10_hub_ids()`: hub_snapshots query with MAX(snapshot_date) + ORDER BY ihs_score — exact match
  - `_check_hub_protection()`: delete/write blocked for top-10 hubs — exact match
  - `_check_layer_permissions()`: actor prefix matching ("enrichment:E7" → "enrichment") — exact match
  - `check_access()`: 3-layer priority chain (Firewall → Hub → Permissions) — exact match
  - `require_access()`: PermissionError wrapper — exact match
  - Spec note (L428): "F1만 확인, F2-F6은 개별 삽입 코드" — implementation follows this

**I-02** similarity.py cosine_similarity matches d-r3-12 spec exactly

- File: `utils/similarity.py` (41 lines)
- Verification:
  - numpy implementation: `np.dot(a, b) / denom` with zero-vector guard — exact match
  - Pure Python fallback: dot product + sqrt norms — exact match
  - Input validation: empty/mismatched length → 0.0 — exact match
  - `try/except ImportError` structure — exact match

**I-03** validators.py matches d-r3-11 spec exactly

- File: `ontology/validators.py` (136 lines)
- Verification:
  - `validate_node_type()`: type_defs query → case-insensitive fallback → deprecated check — exact match
  - `_validate_via_schema_yaml()`: schema.yaml set + lower_map — exact match
  - `_get_types_from_schema()`: yaml.safe_load, node_types keys — exact match
  - `suggest_closest_type()`: 12-type hint dict, content_lower matching — exact match
  - `validate_relation()`: relation_defs query, deprecated check — exact match

**I-04** schema.yaml ↔ config.py node type layers consistent

- For all 12 types in PROMOTE_LAYER, schema.yaml layers match:
  - Observation=0, Evidence=0, Signal=1, Pattern=2, Insight=2, Framework=2, Heuristic=2, Concept=2, Principle=3, Belief=4, Philosophy=4, Value=5
- Node type count: schema.yaml has 50 (8+18+9+6+4+4+1), config.py VALID_PROMOTIONS covers 5 source types

**I-05** schema.yaml ↔ config.py relation types exact match (50 relations)

- All 50 relations in config.py RELATION_TYPES are present in schema.yaml
- Category grouping matches: causal(8), structural(9), layer_movement(6), diff_tracking(4), semantic(8), perspective(5), temporal(4), cross_domain(6)
- Inverse relations in schema.yaml are correctly symmetric

**I-06** LAYER_PERMISSIONS hierarchy follows principle of least privilege

- L0-L1: broadest access (system, enrichment included for write/modify)
- L2: enrichment excluded from write/modify_content, delete restricted to paul
- L3: further restricted (no system for modify_metadata)
- L4-L5: most restrictive (paul only for content/write/delete, claude only for metadata)
- Progressive restriction correctly reflects ontology importance hierarchy

**I-07** check_access() non-existent node defaults to layer=0

- File: `utils/access_control.py:181`
- `layer = row["layer"] if row and row["layer"] is not None else 0`
- If node doesn't exist (row=None), layer defaults to 0 (most permissive)
- Not a security issue: caller must still find/modify the node after access check
- But semantically imprecise — a non-existent node arguably shouldn't be "accessible"

## Coverage

- Files reviewed: 5/5 (access_control.py, similarity.py, validators.py, schema.yaml, config.py)
- Functions verified: 12 (check_access, require_access, _check_a10_firewall, _check_hub_protection, _check_layer_permissions, _get_top10_hub_ids, validate_node_type, _validate_via_schema_yaml, _get_types_from_schema, suggest_closest_type, validate_relation, cosine_similarity)
- Spec sections checked: 3/3 (d-r3-11, d-r3-12, d-r3-13)
- Cross-file consistency: schema.yaml ↔ config.py (types + relations), config.py ↔ validators.py (PROMOTE_LAYER usage)

## Summary

- CRITICAL: 0
- HIGH: 1
- MEDIUM: 2
- LOW: 2
- INFO: 7

**Top 3 Most Impactful Findings:**

1. **H-01** (Missing get_valid_node_types/get_valid_relation_types): The v2.1 validators.py refactor dropped two functions that 3 files still import at module level. enrichment/classifier.py, enrichment/relation_extractor.py, and scripts/ontology_review.py will crash with ImportError on import. The enrichment pipeline cannot run classifier or relation_extractor.
2. **M-01** (PROMOTE_LAYER incomplete): 38 of 50 node types get layer=NULL when stored via remember(). Schema.yaml defines correct layers for all types, but classify() only consults PROMOTE_LAYER (12 entries). This affects access_control, BCM learning rates, promotion eligibility, and tier-based filtering.
3. **M-02** (Comment says 48, actual is 50): config.py's RELATION_TYPES comment is outdated. Runtime behavior is correct (all 50 used), but documentation mismatch causes confusion.

**Cross-reference with 01_storage and 02_tools findings:** H-01 here (missing validator functions) is independent of storage/tools findings. M-01 (PROMOTE_LAYER incomplete) compounds with 02_tools M-02 (tier not updated on promotion) — nodes can have incorrect both layer AND tier values.
