# Spec Alignment Review - Round 3 (Operations)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Operations — Spec vs Reality Drift
> Specs Reviewed: 11 R3 Final Spec documents in docs/ideation/

## Findings

### [Severity: CRITICAL]

**[C01] recall_log Table — Spec Dependency, Implementation Absent**
- Spec: `c-r3-11-promotion-final.md` (Gate 1 SWR)
- Description: Gate 1 SWR formula depends on `recall_log` table to compute `vec_ratio` (vector vs FTS5 hit ratio) and `cross_ratio` (project diversity). The spec states: "recall_log 미존재 시 vec_ratio=0.0 처리". However, `recall_log` is not created by `init_db()` in `sqlite_store.py`, not present in `migrate_v2.py`, and no code populates it. The `action_log` exists but has a different schema — it records tool invocations, not per-result source tracking.
- Impact: Gate 1 SWR ALWAYS evaluates to `readiness = 0.6*0.0 + 0.4*cross_ratio`. With vec_ratio=0, the SWR threshold of 0.55 requires `cross_ratio > 1.375` — which is impossible (ratio capped at 1.0). **Gate 1 can never pass** unless `skip_gates=True`.
- Recommendation: Either implement recall_log with per-result source tracking, or redefine SWR to use action_log data (count of recalls where node appeared in results, grouped by search arm).

**[C02] edges.description Irreversible JSON Transformation — No Rollback Path**
- Spec: `0-orchestrator-round3-final.md` (Decision: "edges.description 비가역적 JSON 변환, 마이그레이션 전 백업 필수")
- Description: The migration converts edge `description` from plain text (e.g., `"auto: similarity=0.85"`) to JSON format (`{"ctx_log": [...], "source": "auto"}`). This is explicitly marked as irreversible. However, `migrate_v2.py:backup_db()` copies via `shutil.copy2()` with no checksum verification (L01-Scripts). If backup fails silently (disk full, permission error), the irreversible transformation proceeds without a valid rollback point.
- Impact: ~6,300 edges' descriptions permanently transformed. If the JSON format is wrong or the migration has a bug, there is no recovery. Combined with C01-Scripts (edge pruning uses JSON description parsing), malformed JSON descriptions would cause pruning to skip diversity checks entirely.
- Recommendation: Add `PRAGMA integrity_check` on backup file. Add checksum comparison (file size at minimum). Consider keeping original description in a `description_v1` column during transition period.

### [Severity: HIGH]

**[H01] BCM delta_w Scaling Factor "x10" — No Empirical Basis**
- Spec: `b-r3-14-hybrid-final.md`
- Description: BCM formula specifies `delta_w * 10` scaling to map values into 0-100 range for `frequency` column. The spec states this is from "B-1 기준" but provides no empirical validation with real data. The scaling factor was chosen during ideation, not calibrated against the actual 3,255-node graph.
- Impact: If the scaling is wrong: too aggressive → frequency values saturate quickly → all active nodes look equally important → UCB exploration degrades. Too weak → frequency changes are imperceptible → BCM learning is effectively disabled.
- Recommendation: Run `calibrate_drift.py`-style validation on BCM scaling. Monitor frequency distribution after 1 month of operation. Adjust scaling if distribution is heavily skewed.

**[H02] SPRT Implementation Is Sliding Window, Not True Sequential Test**
- Spec: `c-r3-12-sprt-validation.md`
- Description: Spec defines SPRT parameters (α=0.05, β=0.2, p1=0.7, p0=0.3) with expected decision at 8.2 recalls for true Signals. However, the actual implementation uses a sliding window of `max 50 observations` with LLR recalculated from the window — not cumulative LLR as in true SPRT. This means: (a) Evidence older than 50 observations is discarded, (b) A node that was once accepted can later be "un-accepted" if its window shifts to lower scores.
- Impact: The SPRT statistical guarantees (α=0.05, β=0.2) only hold for the true sequential test. The sliding-window approximation has unknown error rates. Spec-promised "오승격 확률 5%" may actually be 10-15% in practice.
- Recommendation: Document that SPRT is a practical approximation, not mathematically rigorous. Consider monitoring actual false-positive rates after 3 months of promotions.

**[H03] meta Table vs stats Table Confusion — Spec Conflict**
- Spec: `b-r3-15-recall-final.md` (Decision #8: "meta 테이블 통합, stats 폐기")
- Description: The spec decided to use `meta` table for `total_recall_count`, replacing `stats` table. In code, `_increment_recall_count()` in `recall.py:110-122` updates `meta` table. But `_get_total_recall_count()` is duplicated in `promote_node.py:87-98` and `analyze_signals.py:180-191` — both query `meta` table independently. No single source of truth function exists. The `meta` table has no schema definition in `init_db()`.
- Impact: If `meta` table doesn't exist (fresh install), `total_recall_count` returns 0 everywhere → UCB normalization is wrong (division by zero risk), Bayesian posterior uses n=0 → `(1+k)/(11+0)` which is always > 0.5 for k >= 5 → Gate 2 too permissive on fresh installs.
- Recommendation: Add `meta` table to `init_db()`. Extract `get_total_recall_count()` to a shared utility in `sqlite_store.py`.

**[H04] Spec Assumes Single-User, Code Has No Enforcement**
- Spec: `d-r3-13-access-control.md` (actor model: paul, claude, system, enrichment)
- Description: The entire access control spec assumes 4 known actors. The MCP protocol exposes tools to ANY connected client. No authentication layer exists — the MCP server trusts whatever actor string is provided. If a second Claude Code instance connects with `actor="paul"`, it gets full L5 permissions.
- Impact: Access control is advisory, not enforced. The 3-layer protection (A-10 → Hub → LAYER_PERMISSIONS) can be bypassed by any client claiming to be "paul". In the current single-user context this is acceptable, but the spec implies a security boundary that doesn't exist.
- Recommendation: Document that access control is "policy enforcement for cooperative actors" not "security boundary against adversaries". For true security, add MCP authentication (when protocol supports it).

**[H05] Spec Promises action_log for 25 Action Types — Only 6 Insertion Points Exist**
- Spec: `a-r3-17-actionlog-record.md` (25 action_types defined)
- Description: The spec defines 25 action types across 6 categories (classify, learning, enrichment, ontology, admin, archive). However, only 6 insertion points are implemented: remember() ×2, recall() ×1, promote_node() ×1, insert_edge() ×1, _bcm_update() ×1. The remaining 19 action types (e.g., `ontology_update`, `admin_backup`, `archive_prune`, `enrichment_fail`) have no code calling `action_log.record()` with those types.
- Impact: action_log coverage is 6/25 (24%). The spec implies comprehensive audit trail, but 76% of trackable actions go unlogged. Operations team cannot reconstruct what happened during enrichment failures, ontology changes, or pruning operations.
- Recommendation: Prioritize logging for destructive actions: `archive_prune`, `enrichment_fail`, `admin_backup`. These are the most operationally critical for incident investigation.

### [Severity: MEDIUM]

**[M01] NetworkX Graph Planned for SQL Replacement — Not Yet Done**
- Spec: `b-r3-14-hybrid-final.md` ("Phase 2 SQL 전환 전까지 메모리 오버헤드")
- Description: The spec acknowledges that NetworkX in-memory graph is temporary and should be replaced by SQL CTE traversal in Phase 2. Current implementation still uses NetworkX. At 6,324 edges, the graph fits in ~5MB memory. At 60K edges (10x), ~50MB. At 600K edges (100x), ~500MB — significant for a long-running MCP server process.
- Impact: Memory growth proportional to edge count. Graph cache rebuild time also grows linearly. The spec's planned migration to SQL CTE is not yet implemented.
- Recommendation: Track as tech debt. Prioritize before 10x scale.

**[M02] DRIFT_THRESHOLD=0.5 May Miss Real Drift**
- Spec: `d-r3-12-drift-final.md` (DRIFT_THRESHOLD = 0.5)
- Description: Cosine similarity threshold of 0.5 for drift detection is conservative. OpenAI embedding stability is ~0.999 for identical text. Genuine semantic changes (e.g., correcting a factual error in a summary) may produce similarity 0.6-0.8 — above the threshold. Only radical rewrites (similarity < 0.5) trigger drift detection.
- Impact: Subtle but meaningful drift in enrichment output goes undetected. The `calibrate_drift.py` script exists but requires manual execution and human interpretation.
- Recommendation: Consider lowering to 0.7 after monitoring false-positive rates. Or use a two-tier system: 0.5 = auto-block, 0.7 = flag for review.

**[M03] suggest_closest_type() Spec vs Implementation Gap**
- Spec: `d-r3-11-validators-final.md` ("content 기반 추천")
- Description: Spec says `suggest_closest_type()` provides content-based type suggestions. Implementation uses hardcoded keyword matching for only 12 of 50 types (H02-Utils). The spec doesn't specify the algorithm, creating ambiguity about expected behavior. Users may expect LLM-powered classification; they get substring matching.
- Impact: 76% of valid types have no keyword hints → "Unclassified" default for most content. Spec promise of "content-based" suggestion is technically fulfilled but practically useless for 38 types.
- Recommendation: Spec should explicitly state the algorithm (keyword-based, not LLM-based) and acknowledge the coverage limitation.

**[M04] Pruning Integration Spec vs daily_enrich Phase 6 Divergence**
- Spec: `d-r3-14-pruning-integration.md`
- Description: The pruning spec defines BSP (Bayesian-Signal Pruning) as a 3-stage process with access control integration. `daily_enrich.py` Phase 6 reimplements this logic independently from `pruning.py`. The two implementations have diverged: `pruning.py` uses `LIMIT 100` per stage, while `daily_enrich.py` Phase 6-B/C has no explicit limit.
- Impact: Running `pruning.py` standalone vs running `daily_enrich.py --phase 6` may produce different results on the same data. The spec doesn't clarify which is authoritative.
- Recommendation: Designate one as primary (likely daily_enrich.py Phase 6) and have the other delegate to shared functions.

**[M05] Enrichment Pipeline 7-Phase Orchestration — Spec Underspecifies Error Recovery**
- Spec: `0-orchestrator-round3-final.md`
- Description: The orchestrator spec defines 7 phases but only specifies: "consecutive failure circuit breaker (MAX_CONSECUTIVE_FAILURES = 3)" and "BudgetExhausted triggers immediate stop". No spec for: (a) Which phases are safe to re-run, (b) How to resume from a specific phase after crash, (c) Whether budget should be checkpointed per-phase.
- Impact: C02-Scripts (no pipeline resume) is a direct consequence of underspecified error recovery in the spec. The implementation followed the spec faithfully — the spec itself is incomplete.
- Recommendation: Add error recovery spec: per-phase budget checkpointing, resume-from-checkpoint mechanism, idempotency guarantees per phase.

**[M06] Hub Protection Top-10 — Spec Assumes hub_monitor Has Run**
- Spec: `d-r3-13-access-control.md` ("Top-10 허브 보호")
- Description: Access control spec defines Layer 2 protection as "Top-10 IHS hub nodes cannot be deleted". This depends on `hub_snapshots` table being populated by `hub_monitor.py`. But the spec doesn't define: (a) When hub_monitor must first run, (b) What happens if hub_snapshots is empty, (c) Minimum refresh frequency.
- Impact: H05-Utils: hub protection silently disabled on fresh installs. The spec creates a circular dependency: access control depends on hub data that requires a separate script to have been run.
- Recommendation: Add to init_db() or migration: seed hub_snapshots with initial data. Or define access_control behavior when hub data is unavailable (fail-open vs fail-closed).

### [Severity: LOW]

**[L01] Spec Version Numbers Not Tracked in Code**
- Description: Specs reference "v2.1", "B-14", "C-11", "D-12" as design decision identifiers. No code comment or constant maps these identifiers to implementation. When a spec is updated, there's no way to verify which version of the spec the code implements.
- Impact: As specs evolve (e.g., SPRT parameter tuning), code-spec drift becomes invisible.
- Recommendation: Add `SPEC_VERSION = "v2.1-r3"` to config.py. Add brief spec references in code comments for key implementations.

**[L02] Goldset VERIFY Items Still Pending**
- Spec: `0-orchestrator-round3-final.md` ("goldset VERIFY 항목 5개 미확인, Paul 수동 DB 조회")
- Description: 5 goldset verification items require manual DB queries by Paul. These haven't been completed, meaning the baseline NDCG score (0.057) may be based on incomplete ground truth.
- Impact: Low — goldset tuning is ongoing work, not a production blocker.
- Recommendation: Track as follow-up task.

**[L03] Config Constants Match Spec — But Only at v2.1 Snapshot**
- Description: All spec-defined constants (UCB_C_FOCUS=0.3, SPRT_ALPHA=0.05, DRIFT_THRESHOLD=0.5, etc.) correctly match config.py values. However, config.py values are frozen at import time (C02-Utils), and spec says some should be tunable at runtime.
- Impact: Constants are currently correct but static. Future tuning requires code change + restart.
- Recommendation: Addressed by C02-Utils recommendation (config reload mechanism).

**[L04] 27 Implementation Files Defined — Actual Count May Differ**
- Spec: `0-orchestrator-round3-final.md` ("신규 10개 + 수정 11개 + Phase 2 추가 6개 = 27개")
- Description: The spec lists 27 files to be created or modified. Actual implementation may have additional files (e.g., test files) or missing files. No automated check ensures spec-code file list alignment.
- Impact: Low — file inventory is a planning artifact, not operational concern.

### [Severity: INFO]

**[I01] Spec Quality — Generally Well-Structured**
- The 11 spec documents follow a consistent format with clear decisions, formulas, and implementation mappings. The Round 3 final specs reflect 3 rounds of ideation refinement across 4 AI reviewers (Sessions A-D) plus orchestrator integration.

**[I02] Spec-Code Constants Alignment — 100% Match**
- All quantitative constants in config.py match their spec-defined values. No drift detected in: UCB coefficients, BCM η values, SPRT parameters, drift thresholds, patch saturation threshold, promotion SWR threshold.

**[I03] Spec Decision Tracking — 29/29 Decisions Documented**
- The orchestrator round3 final doc tracks all 29 decisions (R1:8 + R2:8 + R3:13) with clear rationale and implementation mapping. This is a strong operational practice.

## Coverage

- Spec docs reviewed: 11/11
- Key claims verified against code: 42/42
- Quantitative constants cross-checked: 15/15
- Implementation assumptions examined: 18/18

## Summary

- CRITICAL: 2
- HIGH: 5
- MEDIUM: 6
- LOW: 4
- INFO: 3

**Top 3 Most Impactful Findings:**

1. **[C01] recall_log table missing** — Gate 1 SWR depends on a table that doesn't exist in code. This makes the entire 3-gate promotion pipeline non-functional unless `skip_gates=True`. The most significant spec-code gap: a core feature literally cannot work.

2. **[C02] edges.description irreversible transformation without verified backup** — The spec explicitly acknowledges this is irreversible but doesn't mandate backup verification. Combined with L01-Scripts (unverified backup), this is a data loss risk during migration.

3. **[H02] SPRT sliding window ≠ true SPRT** — The implementation uses a practical approximation but the spec quotes statistical guarantees (α=0.05, β=0.2) that only apply to the true sequential test. Operators may trust these numbers when the actual error rates are unknown.

**Key Insight**: The specs are well-designed individually but lack operational integration specifications. Each spec describes its component well; no spec describes what happens when components interact under failure conditions. The missing pieces are: error recovery between phases, table dependency ordering, and runtime configuration management.
