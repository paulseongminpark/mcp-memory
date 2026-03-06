# Tooling Review - Round 3 (Operations)

> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Operational Reality
> Files Reviewed: tools/remember.py, tools/recall.py, tools/promote_node.py, tools/save_session.py, tools/analyze_signals.py, tools/get_becoming.py, tools/inspect_node.py, server.py, storage/vector_store.py, embedding/openai_embed.py

## Findings

### [Severity: CRITICAL]

**C01** Tool deadlines are undefined; external calls rely on SDK defaults
- File: `embedding/openai_embed.py:10-31`, `storage/vector_store.py:26-56`, `scripts/enrich/node_enricher.py:94-157`
- Description: neither `remember()` nor `recall()` sets explicit request deadlines for embedding calls. The enrichment stack has retries and rate-limit handling, but no hard timeout either.
- Impact: tool latency can stretch to the client default behavior of upstream SDKs. In production this looks like hung recalls or remembers, not clean failures.

**C02** `remember()` is non-atomic and non-idempotent
- File: `tools/remember.py:96-146`, `tools/remember.py:149-227`
- Description: the node is committed to SQLite before vector insertion and before auto-edge creation. If the embedding step fails, the function returns a warning and leaves a durable partial write behind. A caller retry creates a new node because there is no idempotency key or dedupe check.
- Impact: network or embedding instability turns transient failures into duplicate data.

### [Severity: HIGH]

**H01** `promote_node()` can leave partial graph state and does not enforce access control
- File: `tools/promote_node.py:167-292`
- Description: the node type update happens in the same transaction as realized-as edge insertion, but edge insert exceptions are swallowed individually. The function also never calls `check_access()`.
- Impact: a promotion can succeed while some supporting edges are missing, and any MCP caller with tool access can attempt ontology mutations.

**H02** `save_session()` is only retry-safe if the caller supplies a stable `session_id`
- File: `tools/save_session.py:16-42`
- Description: when `session_id` is omitted, the function generates a timestamp-based ID. That makes client retries create new sessions instead of updating the same one.
- Impact: flaky clients or duplicate deliveries create duplicate sessions and muddy audit history.

**H03** The MCP wrapper does not expose the full tool behavior that the internal modules implement
- File: `tools/recall.py:11-16`, `server.py:115-138`, `docs/05-full-architecture-blueprint.md:688-691`
- Description: `tools.recall()` supports `mode="auto|focus|dmn"`, but `server.py` omits the parameter. The blueprint also lists `search_nodes()`, `get_relations()`, and `get_session()`, but the server exposes none of them.
- Impact: operational documentation and actual MCP behavior diverge. Client integrations cannot reach features that the code and tests imply exist.

### [Severity: MEDIUM]

**M01** Several read-oriented tools scale poorly because they use O(n^2) or N+1 access patterns
- File: `tools/analyze_signals.py:59-67`, `tools/get_becoming.py:44-50`, `tools/inspect_node.py:25-53`
- Description: `analyze_signals()` does pairwise overlap checks across all Signal nodes, `get_becoming()` fetches edges per node, and `inspect_node()` fetches one node per edge endpoint.
- Impact: these tools are fine at the current scale but will get noticeably slower as node and edge counts grow.

**M02** The recall path still pays a full-graph memory cost on cache miss
- File: `storage/hybrid.py:31-44`, `storage/sqlite_store.py:347-351`, `graph/traversal.py:11-21`
- Description: cache miss requires `SELECT * FROM edges` plus a NetworkX build. On the live dataset, that is already about 32.38 ms for edge loading and 9.92 ms for graph construction.
- Impact: process restarts, cache expiry, or multiprocess deployments will make recall latency spiky.

## Idempotency Matrix

- `remember()`: not idempotent
- `recall()`: operationally non-idempotent because it writes activation history and score history on every call
- `promote_node()`: not safely idempotent; retry semantics depend on where the first call failed
- `save_session()`: idempotent only with caller-supplied `session_id`
- `analyze_signals()`, `get_becoming()`, `inspect()`: read-only, but their cost grows with dataset size

## Summary

- Tool behavior is workable for manual use, not for robust automation.
- The first operational failures are timeout ambiguity, partial writes, and wrapper/surface drift.
- The most repair-worthy gaps are idempotency for `remember()` and ACL enforcement for `promote_node()`.
