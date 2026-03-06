# Security Review - Round 3 (Operations)

> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Runtime Security
> Files Reviewed: utils/access_control.py, tools/promote_node.py, tools/remember.py, tools/recall.py, server.py, scripts/enrich/node_enricher.py, scripts/enrich/relation_extractor.py, scripts/enrich/graph_analyzer.py, storage/sqlite_store.py

## Security Baseline

- SQL writes are parameterized throughout the reviewed paths
- FTS queries are escaped in `storage/sqlite_store._escape_fts_query()`
- The larger security risk is not classic SQL injection; it is unauthorized mutation, prompt injection, and service exhaustion

## Findings

### [Severity: CRITICAL]

**C01** Access control is identity-by-string, not authenticated identity
- File: `utils/access_control.py:126-141`, `utils/access_control.py:146-197`
- Description: access decisions trust raw actor strings and simple prefixes such as `enrichment:E7 -> enrichment`.
- Impact: this is authorization without authentication. Any integration layer that can supply actor strings can spoof a privileged identity unless a stronger boundary exists outside this repo.

**C02** `promote_node()` mutates ontology state without any access-control check
- File: `tools/promote_node.py:167-292`, `server.py:231-255`
- Description: the promotion path never calls `check_access()`. The underlying function also contains a `skip_gates` bypass knob.
- Impact: ontology mutation is guarded only by business logic gates, not by actor authorization. Accidental protection from currently missing schema is not a real security control.

### [Severity: HIGH]

**H01** Malicious remember content can prompt-inject the enrichment pipeline
- File: `scripts/enrich/node_enricher.py:167-200`, `scripts/enrich/node_enricher.py:319-338`, `scripts/enrich/relation_extractor.py:503-510`, `scripts/enrich/graph_analyzer.py:598-601`
- Description: raw node content is interpolated into multiple LLM prompts. Some fields are allowlisted, but free-text outputs such as summaries, reasons, descriptions, and suggestions are written back to storage with minimal sanitization.
- Impact: a crafted node can poison downstream metadata, edges, and reports even if it cannot inject SQL.

**H02** Recall flood is a viable denial-of-service vector
- File: `storage/vector_store.py:39-56`, `tools/recall.py:25-78`, `storage/hybrid.py:493-495`, `server.py:115-138`
- Description: there is no authentication, per-client rate limiting, or admission control on the recall surface.
- Impact: a client can trigger repeated embeddings, DB writes, and action-log growth until API quota, CPU, or SQLite write capacity becomes the bottleneck.

**H03** Data exposure is broad to any MCP caller that can reach the server
- File: `tools/recall.py:55-78`, `tools/get_context.py:6-38`, `tools/inspect_node.py:58-90`
- Description: tools return raw content, project names, tags, metadata, and edge context without any sensitivity filtering.
- Impact: once a caller has tool access, the repo does not provide finer-grained data isolation.

### [Severity: MEDIUM]

**M01** Audit data is not authoritative
- File: `storage/action_log.py:48-110`, `tools/remember.py:109-123`
- Description: actors and sources are free-form strings, and logging failures are swallowed silently.
- Impact: audit trails are useful for debugging but weak as security evidence.

**M02** One of the intended safety layers is currently inactive
- File: `utils/access_control.py:95-105`, live `hub_snapshots` row count = 0
- Description: hub protection depends on fresh snapshot rows, but the live table is empty.
- Impact: mutation blocking for top hubs is absent in practice.

## Summary

- SQL injection risk is relatively well controlled.
- Authorization and anti-abuse controls are not.
- The most likely operational attacks are actor spoofing through integration boundaries, recall flooding, and prompt-driven metadata poisoning.
