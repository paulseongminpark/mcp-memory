# Spec Alignment Review - Round 2 (Architecture)
> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Architecture
> Files Reviewed: docs/05-full-architecture-blueprint.md, docs/ideation/*.md, ontology/schema.yaml, storage/sqlite_store.py, tools/recall.py, tools/promote_node.py, scripts/daily_enrich.py, data/memory.db

## Findings
### CRITICAL
- None.

### HIGH
- `H01` `ontology/schema.yaml:4` says the schema has `48 relation types`, while `ontology/schema.yaml:272` says `50 relation types`, and the live database also has `50` rows in `relation_defs`. The specs are not self-consistent even inside the canonical schema artifact.
- `H02` major schema documents still require structures that the implementation baseline does not create. Across `docs/ideation/c-index.md:43-45`, `docs/ideation/c-r2-7-promotion-integration.md:233-248`, and `docs/ideation/0-orchestrator-round3-final.md:128-156`, the architecture expects `meta`, `recall_log`, `edges.archived_at`, and `edges.probation_end`. The live database has none of those tables or columns, and `storage/sqlite_store.py:21` does not create them. That means the written architecture and the running architecture have already diverged.

### MEDIUM
- `M01` `docs/05-full-architecture-blueprint.md:40` still documents a `connect()` tool, but `server.py` does not expose that tool. The blueprint is lagging behind the implemented public surface.
- `M02` `docs/05-full-architecture-blueprint.md:215` still describes `45 active + 7 reserved = 52` node types, while the current schema and DB both operate on `50` total node-type rows. The spec set preserves older ontology states instead of consolidating them.
- `M03` `docs/ideation/b-r3-15-recall-final.md` and earlier integration docs still refer to the old `stats` table lineage, even though `docs/ideation/0-orchestrator-round3-final.md:92-99` resolves that conflict in favor of `meta`. This is a self-contradiction across the spec stack, not just missing implementation.
- `M04` the spec corpus is over-specified on algorithms and under-specified on ownership. Documents explain BCM, UCB, SPRT, SWR, MDL, and pruning formulas in detail, but they do not settle who owns migrations, who owns schema truth, or which layer is allowed to perform raw SQL.

### LOW
- `L01` terminology drift remains visible across the docs: old names such as `Heuristic`, `Concept`, `stats`, and `connect()` persist alongside newer replacements. This increases review and onboarding cost.

### INFO
- `I01` copied code blocks recur across ideation rounds, especially for raw SQL snippets and helper functions. That made the spec set broad, but it also made it easy for contradictions to survive round-to-round.
- `I02` Naming consistency review across the docs found multiple parallel vocabularies for the same concepts: `stats` vs `meta`, `archive` vs `node_archived` / `edge_archived`, and deprecated vs replacement ontology names.
- `I03` Implementation-side complexity most exposed to spec drift: `storage/hybrid.py:385` `hybrid_search()` = 28, `tools/promote_node.py:167` `promote_node()` = 21, `scripts/daily_enrich.py:53` `phase1()` = 20, `config.py:197` `infer_relation()` = 14.

## Coverage
- Spec corpus reviewed against current schema, current tool API, and live DB state.
- Self-consistency checked across blueprint docs, orchestrator summaries, ideation rounds, and schema comments.
- Duplication checked for copied SQL and helper fragments reused across multiple documents.
- Naming consistency checked for tool names, table names, action names, and ontology terminology.

## Summary
The architecture is over-documented but under-consolidated. The biggest design problem is not lack of thought; it is lack of canonicalization. Multiple spec layers continue to describe different versions of the system, so implementation drift is almost inevitable. The project needs one authoritative architecture document plus generated or explicitly versioned derivatives, otherwise the specs will keep competing with each other.
