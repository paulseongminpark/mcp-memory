# Spec Alignment Review - Round 3 (Operations)

> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Operational Reality
> Files Reviewed: docs/05-full-architecture-blueprint.md, docs/06-enrichment-pipeline-spec.md, docs/implementation/0-impl-phase1.md, docs/implementation/0-impl-phase2.md, docs/implementation/0-impl-index.md, docs/implementation/w3-state.md, server.py, tools/recall.py, tools/promote_node.py, storage/sqlite_store.py

## Already Outdated Versus Reality

### [Severity: CRITICAL]

**C01** The implementation docs say the `last_activated` and `archived_at` schema fixes landed; the live schema says they did not
- File: `docs/implementation/w3-state.md:81-84`, `docs/implementation/0-impl-phase2.md:100-132`
- Reality: the live `nodes` table has no `last_activated`, and the live `edges` table has no `archived_at` or `probation_end`.
- Impact: two major operational assumptions in the spec are false on the current database.

**C02** The docs say recall counting moved to `meta`, but production still has no `meta` table
- File: `docs/implementation/0-impl-phase1.md:109-112`, `tools/recall.py:111-121`
- Reality: `tools.recall` tries to upsert into `meta` and silently skips when it is absent.
- Impact: total recall counting is described as implemented, but the live schema still cannot support it.

**C03** Promotion spec depends on `recall_log`, but the production schema and server never provide it
- File: `tools/promote_node.py:41-53`, `docs/05-full-architecture-blueprint.md:718-723`
- Reality: the live DB has `action_log` and `activation_log`, but no `recall_log` table and no writer for it.
- Impact: SWR readiness is specified around evidence that the current system does not collect.

## Surface Drift

### [Severity: HIGH]

**H01** The tool catalog in the blueprint is ahead of the actual MCP surface
- File: `docs/05-full-architecture-blueprint.md:688-695`, `server.py:39-338`
- Reality: the blueprint lists `search_nodes()`, `get_relations()`, and `get_session()` as available tools. The server exposes none of them.
- Impact: clients built from the spec will fail against the real server.

**H02** `recall(mode)` exists in code and tests but not in the MCP wrapper
- File: `tools/recall.py:11-16`, `tests/test_recall_v2.py:102-126`, `server.py:115-138`
- Reality: the internal tool supports `mode="focus"` and `mode="dmn"`, but the exposed server wrapper hard-codes the legacy signature.
- Impact: part of the advertised search behavior is unreachable in production.

## Which Specs Break First Under Scale

### [Severity: MEDIUM]

**M01** The graph-learning and UCB sections break first because the live implementation does not match the model they describe
- File: `docs/05-full-architecture-blueprint.md:710-717`, `graph/traversal.py:11-21`, `storage/hybrid.py:117-131`
- Reality: the spec assumes visit-count-aware graph traversal, but the cached NetworkX graph is built from edges only and does not load node `visit_count` attributes.
- Impact: the first scale symptom is not subtle drift; it is that the intended exploration-exploitation behavior is not actually what the running system uses.

**M02** The pruning spec promises recoverable edge archiving and activation-aware node pruning, but the implementation uses updated timestamps and fake archive counts
- File: `docs/implementation/0-impl-phase2.md:95-101`, `scripts/daily_enrich.py:352-398`, `scripts/pruning.py:36-50`
- Impact: the operational drift widens as data grows because reports and behavior diverge further over time.

## Summary

- The highest-priority drift is schema drift, not wording drift.
- The next break is tool-surface drift: the server contract is behind the implementation notes.
- Under scale, the first painful failure comes from graph-learning assumptions that are not true in the running system.
