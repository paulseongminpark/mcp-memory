# Spec Alignment Review - Round 1 (Correctness)
> Reviewer: Codex
> Date: 2026-03-06
> Files Reviewed: docs/ideation/0-orchestrator-round3-final.md, docs/ideation/a-r3-17-actionlog-record.md, docs/ideation/a-r3-18-remember-final.md, docs/ideation/b-r3-14-hybrid-final.md, docs/ideation/b-r3-15-recall-final.md, docs/ideation/c-r3-11-promotion-final.md, docs/ideation/c-r3-12-sprt-validation.md, docs/ideation/d-r3-11-validators-final.md, docs/ideation/d-r3-12-drift-final.md, docs/ideation/d-r3-13-access-control.md, docs/ideation/d-r3-14-pruning-integration.md

## Findings
### CRITICAL
- The integrated Round 3 schema described in `0-orchestrator-round3-final.md` is not realized in the bootstrap path. Expected pieces such as `meta`, `recall_log`, `nodes.last_activated`, `nodes.access_level`, `nodes.replaced_by`, `edges.archived_at`, and `edges.probation_end` are missing from `storage/sqlite_store.py`, even though later code depends on them.
- `a-r3-18` and `d-r3-11` assume runtime access to the ontology layer map for the full type system, but implementation only uses the 12-entry `PROMOTE_LAYER` map. This breaks layer assignment and firewall behavior for most of the 50 schema types.

### HIGH
- `a-r3-17` is only partially implemented. `remember()` and recall activation logging exist, but `promote_node()` success logging, `insert_edge()` `edge_corrected` logging, hybrid `bcm_update`/`reconsolidation` logging, and enrichment `enrichment_done`/`enrichment_fail` logging are missing.
- `b-r3-15` and `0-orchestrator-round3-final` resolve the recall counter to `meta`, but implementation creates neither `stats` nor `meta`. The SQL path exists in `tools/recall.py`, but the storage contract it depends on does not.
- `c-r3-11` is implemented almost line-for-line, but its dependent tables/fields are absent. The result is a spec-shaped file with a broken runtime path.
- `d-r3-14` expects edge archival state and `last_activated`-based inactivity. Implementation omits archival columns and substitutes `updated_at`, so the pruning formula no longer matches the written spec.

### MEDIUM
- `d-r3-12` says `SUMMARY_LENGTH_MIN_SAMPLE = 5`; `config.py` and the tests use `10`. This is a direct constant mismatch between spec text and implementation.
- `d-r3-13` access control core is implemented, but caller integration is partial. `scripts/enrich/node_enricher.py` returns immediately on denied E1/E2/E3 writes instead of following the spec's "allowed fields / F2" handling.
- `server.py` does not expose recall `mode`, so one of the visible B-R3-15 additions is unreachable from the MCP surface.

### LOW
- Some Phase 2 / adjacent additions are present even though the surrounding data plumbing is incomplete: graph TTL caching in `storage/hybrid.py`, `_recommend_v2()` in `tools/analyze_signals.py`, hub action helpers in `scripts/hub_monitor.py`, and Phase 7 reporting in `scripts/daily_enrich.py`.

### INFO
- Many implementation files are clearly copied from the Round 3 specs; the dominant issue is cross-file integration, not absence of intended algorithms.

## Coverage
| Spec | Corresponding implementation | Status |
|---|---|---|
| `0-orchestrator-round3-final.md` | `storage/sqlite_store.py`, `server.py`, `scripts/migrate_v2_ontology.py` | Partial; integrated schema not bootstrapped |
| `a-r3-17-actionlog-record.md` | `storage/action_log.py`, `tools/remember.py`, `storage/hybrid.py`, `tools/promote_node.py`, `storage/sqlite_store.py`, `scripts/enrich/node_enricher.py` | Partial |
| `a-r3-18-remember-final.md` | `tools/remember.py` | Partial; F3 depends on incomplete layer map |
| `b-r3-14-hybrid-final.md` | `storage/hybrid.py`, `config.py`, `storage/sqlite_store.py` | Partial; schema mismatch blocks learning side effects |
| `b-r3-15-recall-final.md` | `tools/recall.py`, `server.py` | Partial; counter storage missing, `mode` not exposed |
| `c-r3-11-promotion-final.md` | `tools/promote_node.py`, `config.py` | Partial; gates depend on missing data |
| `c-r3-12-sprt-validation.md` | `config.py`, `storage/hybrid.py`, `scripts/sprt_simulate.py` | Mostly implemented for constants/math |
| `d-r3-11-validators-final.md` | `ontology/validators.py`, `server.py` | Partial; empty-table bootstrap issue |
| `d-r3-12-drift-final.md` | `utils/similarity.py`, `storage/vector_store.py`, `scripts/enrich/node_enricher.py`, `scripts/calibrate_drift.py`, `config.py` | Partial; sample-size constant mismatch |
| `d-r3-13-access-control.md` | `utils/access_control.py`, `scripts/hub_monitor.py`, `scripts/pruning.py`, `scripts/enrich/node_enricher.py` | Partial |
| `d-r3-14-pruning-integration.md` | `scripts/daily_enrich.py`, `scripts/pruning.py`, `storage/action_log.py` | Partial |

Implemented additions not directly required by the requested final specs:
- `storage/hybrid.py` graph TTL cache from B-16.
- `tools/analyze_signals.py` Bayesian cluster scoring helpers.
- `scripts/daily_enrich.py` Phase 7 report generation.
- `scripts/hub_monitor.py` action recommendation helpers.

## Summary
The codebase often matches the Round 3 spec snippets file-by-file, but it is not integrated correctly end-to-end. The biggest gaps are the missing integrated schema, the missing full type registry, and the promotion pipeline's dependence on tables/fields that are never bootstrapped.
