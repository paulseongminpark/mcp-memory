# Utils & Ontology Review - Round 3 (Operations)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Operations
> Files Reviewed: ontology/validators.py, utils/access_control.py, utils/similarity.py, config.py, ontology/schema.yaml

## Findings

### [Severity: CRITICAL]

**[C01] Double Fallback Cascade — Unhandled Exception When Both type_defs AND schema.yaml Fail**
- File: `ontology/validators.py:47-49`
- Description: `validate_node_type()` has a two-tier fallback: type_defs table → schema.yaml. The `except Exception` at line 47 catches type_defs failures and calls `_validate_via_schema_yaml()`. But if schema.yaml is ALSO broken (malformed YAML, missing file after initial check race, permission error), the `yaml.YAMLError` propagates OUT of the `except` block — it is NOT caught by any handler.
  - Flow: `conn.execute()` throws OperationalError → `except` block → `_validate_via_schema_yaml()` → `_get_types_from_schema()` → `yaml.safe_load()` throws YAMLError → propagates up → `finally: conn.close()` runs but exception escapes
  - Result: `validate_node_type()` throws unhandled exception → `classify()` in remember.py crashes → `remember()` fails completely
- Impact: If the DB is freshly created (no type_defs table yet) AND schema.yaml has a syntax error (e.g., bad merge during update), ALL remember() calls fail. No node can be stored. The system is fully inoperable.
- Recommendation: Wrap `_validate_via_schema_yaml()` call in its own try/except. On double failure, return `(True, None)` with logging (accept any type rather than crash) or return `(False, None)` to force Unclassified.

**[C02] Config Immutable at Runtime — No Hot-Reload Mechanism**
- File: `config.py:1-259`
- Description: ALL configuration values are module-level constants set once at import time:
  - `OPENAI_API_KEY = os.getenv(...)` (line 10) — captured once
  - `API_PROVIDER = os.getenv(...)` (line 56) — captured once
  - `ENRICHMENT_MODELS` (line 74-77) — computed from API_PROVIDER at import
  - All numeric constants (BCM, UCB, SPRT, drift thresholds) — plain assignments
  - Python module caching ensures re-import returns the same object
  No file watcher, no SIGHUP handler, no reload API exists. The MCP server is a long-running process (starts when Claude Code launches, runs for hours/days).
- Impact: Changing ANY configuration requires full MCP server restart. This includes:
  - API key rotation (security-critical)
  - Threshold tuning during NDCG optimization (currently requires restart per experiment)
  - Adding new projects to DOMAINS_ALLOWLIST (line 107-111)
  - Switching API_PROVIDER between anthropic/openai
  No graceful degradation: if API key expires mid-session, all embedding calls fail until restart.
- Recommendation: For v2.1 scope, at minimum: (a) Re-read API keys from env on each use, not at import. (b) For constants, accept current behavior (restart required) but document it. (c) Long-term: config reload via MCP tool or SIGHUP handler.

### [Severity: HIGH]

**[H01] validate_relation() Returns (True, None) on Missing relation_defs — All Relations Pass**
- File: `ontology/validators.py:130-132`
- Description: When `relation_defs` table doesn't exist, `except Exception` catches the error and returns `(True, None)`. This means ANY relation string is treated as valid: `"INVALID_RELATION"`, `"drop table nodes"`, or `""` all pass validation.
- Impact: Without `relation_defs` table, relation validation is effectively disabled. The `insert_edge()` function in sqlite_store has its own fallback (defaults to "connects_with"), so the impact is mitigated at the storage layer. But the validator API contract — "I validate relations" — is silently broken. Callers trusting validator results get false assurance.
- Recommendation: Return `(False, None)` on table missing, or fall back to config.ALL_RELATIONS in-memory check (similar to how validate_node_type falls back to schema.yaml).

**[H02] suggest_closest_type() Covers Only 12/50 Types — 76% Miss Rate**
- File: `ontology/validators.py:88-105`
- Description: Keyword hints defined for only 12 types: Decision, Failure, Pattern, Insight, Principle, Framework, Workflow, Goal, Signal, AntiPattern, Experiment, Observation. The remaining 38 types (76%) have NO keywords. Content about "boundaries" → Unclassified (Boundary type has no hints). Content about "values" → Unclassified (Value type has no hints). Content about "tools" → Unclassified (Tool type has no hints).
- Impact: When `validate_node_type()` fails (typo, unknown type), `suggest_closest_type()` is called. For 76% of intended types, it returns "Unclassified" — a false negative. Users must manually reclassify. Over time, Unclassified nodes accumulate, defeating the ontology system.
- Recommendation: Add keyword hints for at least L2-L5 types (the most important ones): Tool, Skill, Boundary, Identity, Belief, Value, Axiom, etc. Consider embedding-based type suggestion as a future enhancement.

**[H03] access_control.py Uses Its Own DB_PATH — Divergence Risk**
- File: `utils/access_control.py:12`
- Description: `DB_PATH = Path(__file__).parent.parent / "data" / "memory.db"` — computed from file location. Meanwhile, `config.py` has `DB_PATH = BASE_DIR / "data" / "memory.db"` (line 15). Both resolve to the same path under normal conditions. But if either file is moved, symlinked, or if the project structure changes, they diverge silently.
- Impact: access_control could check permissions against a different (or nonexistent) database while sqlite_store operates on the correct one. Permissions would either fail-open (no nodes found → layer=0 → permissive) or throw errors.
- Recommendation: Import `DB_PATH` from `config.py` instead of computing independently.

**[H04] None Layer Defaults to L0 — Minimum Protection**
- File: `utils/access_control.py:131`
- Description: `layer_key = min(layer, 5) if layer is not None else 0`. Nodes without a `layer` value get L0 permissions (most permissive: anyone can write/modify). This applies to all `Unclassified` nodes and any nodes created before layer assignment was implemented.
- Impact: Any node with `layer=NULL` in the DB gets L0 protection regardless of actual content sensitivity. A manually created L4-equivalent node without layer field gets no A-10 firewall protection.
- Recommendation: Default to a middle layer (e.g., L2 or L3) for None layers, or refuse access with an error ("layer not set").

**[H05] Hub Protection Silently Disabled on Missing Table**
- File: `utils/access_control.py:97-105`
- Description: `_get_top10_hub_ids()` catches ALL exceptions and returns empty set. If `hub_snapshots` table doesn't exist (new installation, migration not run), hub protection is completely disabled. No logging, no warning.
- Impact: Hub nodes (high-connectivity nodes critical to graph structure) can be freely deleted or modified without any protection. The D-3 protection layer is silently absent.
- Recommendation: Log a warning on first failure. Consider caching the "table exists" check to avoid repeated silent failures.

### [Severity: MEDIUM]

**[M01] suggest_closest_type() Order-Dependent Keyword Matching**
- File: `ontology/validators.py:102-104`
- Description: `for type_name, keywords in hints.items()` — iterates dict in insertion order (Python 3.7+). First matching keyword wins. Examples of ambiguity:
  - "관찰된 패턴" → matches Pattern ("패턴") before Observation ("관찰") due to dict order
  - "실패한 실험" → matches Failure ("실패") before Experiment ("실험")
  - "문제 해결 패턴" → matches AntiPattern ("문제") instead of Pattern ("패턴")
  Substring matching (`kw in content_lower`) is overly broad: "결정적 순간" → matches Decision ("결정").
- Impact: Misclassification when content contains keywords for multiple types. The "first match wins" behavior is non-obvious and produces inconsistent results depending on content phrasing.
- Recommendation: Use a scoring system (count matching keywords per type, pick highest). Add word boundary detection for Korean/English keywords.

**[M02] LAYER_PERMISSIONS and RELATION_RULES Hard-Coded — Require Code Changes**
- File: `utils/access_control.py:19-62`, `config.py:152-194`
- Description: Both are defined as Python dict literals. Adding a new actor, changing permissions, or adding new relation rules requires editing source code and restarting the MCP server. No DB-based or file-based override exists.
- Impact: Operational changes (e.g., granting a new CLI tool access, adjusting relation rules after ontology update) require developer intervention. Not operable by end users.
- Recommendation: For v2.1: document that these are code-level configs. Long-term: move to DB-based permissions with admin tool.

**[M03] config.py Dead Constants — BACKUP_DIR, MAX_RETRIES/RETRY_BACKOFF in Storage**
- File: `config.py:89-90,97`
- Description:
  - `BACKUP_DIR = DATA_DIR / "backup"` (line 97) — defined but NO backup code exists in the codebase. Dead constant.
  - `MAX_RETRIES = 3` and `RETRY_BACKOFF = 2.0` (lines 89-90) — defined but NOT used by storage layer or tools. Only enrichment scripts reference them. Yet their names suggest they should apply to all API calls.
- Impact: False sense of resilience. A reader sees `MAX_RETRIES = 3` and assumes API calls are retried. In reality, storage layer has ZERO retry logic (see 01_storage.md H03).
- Recommendation: Either implement retry in storage/embedding layer using these constants, or rename to `ENRICHMENT_MAX_RETRIES` to clarify scope. Remove or comment `BACKUP_DIR`.

**[M04] validate_node_type() Broad Exception Catch — Logic Bugs Hidden**
- File: `ontology/validators.py:47-49`
- Description: `except Exception:` catches ALL exceptions from the type_defs query — including `TypeError`, `KeyError`, `AttributeError` from logic bugs — and silently falls back to schema.yaml. A coding error in the SQL query or row access would be masked as "table doesn't exist."
- Impact: Bugs in the validation logic are hidden by the catch-all. The validator appears to work (via fallback) but is actually running degraded without anyone knowing.
- Recommendation: Narrow to `except (sqlite3.OperationalError, sqlite3.DatabaseError):` for table-not-found scenarios. Let other exceptions propagate.

**[M05] Enrichment Actor Prefix Matching — Overly Broad**
- File: `utils/access_control.py:139`
- Description: `actor_base = actor.split(":")[0]` — any actor string starting with "enrichment:" matches the "enrichment" permission entry. Similarly, "system:" matches "system". No validation of the suffix.
- Impact: In the current single-user context, this is low risk. But if the system is ever exposed to multi-user or external tool access, `actor="enrichment:malicious"` would get enrichment-level permissions (modify_content on L0/L1, modify_metadata on L0-L2).
- Recommendation: Define valid enrichment task names (E1-E14) and validate suffix against the list.

**[M06] DOMAINS_ALLOWLIST and FACETS_ALLOWLIST Hard-Coded**
- File: `config.py:101-111`
- Description: `FACETS_ALLOWLIST` (9 items) and `DOMAINS_ALLOWLIST` (10 items) are hard-coded Python lists. Adding a new project (e.g., "new-project") or facet requires editing config.py and restarting the server.
- Impact: Enrichment pipeline uses these to validate extracted facets/domains. A new project's nodes get enriched but domains outside the allowlist are filtered out. The user won't know their project's domain is being silently dropped.
- Recommendation: Move to a config file (JSON/YAML) that can be updated without code changes. Or add a `domains` table to the DB.

### [Severity: LOW]

**[L01] cosine_similarity() Pure Python Fallback — Performance at 3072 Dimensions**
- File: `utils/similarity.py:31-40`
- Description: When numpy is not installed, the pure Python fallback computes cosine similarity with `sum(a * b for a, b in zip(vec_a, vec_b))` for 3072-dimensional vectors. This is ~100x slower than numpy for large vectors.
- Impact: In practice, numpy is almost certainly installed (ChromaDB depends on it). But if somehow absent, MDL gate computations in `promote_node._mdl_gate()` (which computes a full similarity matrix) would be extremely slow.
- Recommendation: Low priority. Consider adding a startup check that warns if numpy is missing.

**[L02] schema.yaml as Fallback Only — Not the Source of Truth**
- File: `ontology/schema.yaml` (439 lines), `ontology/validators.py:55-76`
- Description: schema.yaml is only loaded when `type_defs` table doesn't exist. Once the DB is populated (via migration), schema.yaml is never read again. If schema.yaml is updated but `type_defs` table is not migrated, they diverge silently.
- Impact: schema.yaml becomes documentation rather than runtime config. Developers may update schema.yaml thinking it affects validation, but it has no effect if type_defs exists.
- Recommendation: Document that type_defs is the runtime SoT. Consider a migration script that syncs schema.yaml → type_defs.

**[L03] infer_relation() reverse_map Incomplete**
- File: `config.py:210-222`
- Description: `reverse_map` at line 210 has 14 entries mapping forward relations to their inverses. But `RELATION_RULES` has 30+ entries. Some forward relations have no reverse mapping: e.g., `"led_to"` maps to `"triggered_by"`, but `"part_of"` maps to `"contains"` and `"contains"` maps back to `"part_of"` — these are correct. However, `"supports"`, `"parallel_with"`, `"exemplifies"` used in same-layer fallback (lines 234-237) have no reverse entries.
- Impact: When relation inference encounters a reverse match for an unmapped relation, it falls through to layer-based fallback (less specific). The inferred relation may be less accurate but is never wrong (still a valid relation type).
- Recommendation: Complete the reverse_map or generate it programmatically from schema.yaml inverse definitions.

**[L04] DRY_RUN Global Flag — No Per-Operation Granularity**
- File: `config.py:93`
- Description: `DRY_RUN = False` — single global boolean. If set to True (via monkey-patching or env var), ALL operations become dry-run. No way to dry-run only enrichment while keeping remember/recall live.
- Impact: Limited operational flexibility. DRY_RUN is currently only used by enrichment scripts, but its global nature is a footgun if referenced elsewhere.
- Recommendation: Pass dry_run as a parameter to individual functions rather than using a global flag.

### [Severity: INFO]

**[I01] access_control.py check_access() — Well-Structured 3-Layer Design**
- File: `utils/access_control.py:146-197`
- Description: Clean separation of concerns: A-10 firewall → Hub protection → LAYER_PERMISSIONS. Each layer is an independent function. `try/finally` with conditional `conn.close()`. Accepts external connection for transaction reuse. Fail-closed design (unknown operations default to paul-only).
- Impact: Positive. The most defensively coded module in the codebase. Model for other access-sensitive operations.

**[I02] validators.py try/finally on All DB Access**
- File: `ontology/validators.py:21-52,117-135`
- Description: Both `validate_node_type()` and `validate_relation()` use `try/finally` with `conn.close()`. No connection leaks possible from these functions.
- Impact: Positive. Contrasts sharply with tools layer where most functions lack try/finally.

**[I03] Type System Consistency: schema.yaml (50 types) vs config.py Subsets**
- File: `ontology/schema.yaml`, `config.py:244-258`
- Description: schema.yaml defines 50 node types across 6 layers. config.py defines subsets:
  - `VALID_PROMOTIONS`: 5 source types (Observation, Signal, Pattern, Insight, Principle)
  - `PROMOTE_LAYER`: 12 types (promotion targets + sources)
  - `suggest_closest_type()`: 12 types with keywords
  These are INTENTIONAL subsets — not all types are promotable or need layer assignments. The three subsets overlap correctly: all VALID_PROMOTIONS sources appear in PROMOTE_LAYER, all PROMOTE_LAYER types exist in schema.yaml.
- Impact: Informational. The subset relationship is correct but undocumented. Future type additions must update all three locations.

## Coverage

- Files reviewed: 5/5
- Functions verified: 15/15 (all public + key private)
- Spec sections checked: d-r3-11 (validators), d-r3-12 (similarity/drift), d-r3-13 (access control)

## Summary

- CRITICAL: 2
- HIGH: 5
- MEDIUM: 6
- LOW: 4
- INFO: 3

**Top 3 Most Impactful Findings:**

1. **[C01] Double fallback cascade** — When both type_defs table AND schema.yaml fail, validate_node_type() throws an unhandled exception that crashes remember(). This is the only path that can make the entire system inoperable from a configuration error alone.

2. **[C02] Config immutable at runtime** — No hot-reload mechanism for ANY configuration. API key rotation, threshold tuning, and allowlist updates all require MCP server restart. For a long-running MCP process, this is a significant operational limitation.

3. **[H02] suggest_closest_type() 76% miss rate** — 38 of 50 types have no keyword hints. When type validation fails (typo, unknown), the fallback classifier returns "Unclassified" for 76% of valid types. This silently degrades ontology quality over time.

**Cross-Reference with Previous Reports:**
- C02 (no hot-reload) compounds with 01_storage.md H03 (OpenAI API zero resilience): if API key expires, the system cannot recover without restart. No retry, no key refresh.
- H01 (validate_relation returns True on missing table) means 02_tools.md M06 (link() partial edge creation) uses unvalidated relation strings — any infer_relation() output is accepted without check.
- H04 (None layer → L0) interacts with 02_tools.md C02 (remember partial failure): if store() succeeds but classify() returned layer=None, the node gets minimum protection AND access_control treats it as L0.
