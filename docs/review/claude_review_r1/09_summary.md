# Round 1 Summary - Correctness & Completeness

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Aggregate across T1-C-01 through T1-C-08
> Scope: 24 source files + config.py + schema.yaml + migration + 14 scripts + 7 test files (117 tests) + 10 E2E scenarios

---

## Grand Totals

| Severity | 01 Storage | 02 Tools | 03 Utils | 04 Scripts | 05 Spec | 06 Tests | 07 E2E | 08 Security | **Total** |
|----------|-----------|----------|----------|-----------|---------|----------|--------|------------|-----------|
| CRITICAL | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | **3** |
| HIGH | 2 | 1 | 1 | 0 | 1 | 1 | 3 | 3 | **12** |
| MEDIUM | 1 | 3 | 2 | 3 | 4 | 3 | 3 | 7 | **26** |
| LOW | 2 | 2 | 2 | 3 | 1 | 3 | 3 | 6 | **22** |
| INFO | 7 | 7 | 7 | 10 | 6 | 6 | 3 | 4 | **50** |
| **Subtotal** | **12** | **13** | **12** | **16** | **12** | **13** | **15** | **20** | **113** |

**Total findings: 113** (3 CRITICAL + 12 HIGH + 26 MEDIUM + 22 LOW + 50 INFO)

---

## Cross-Report Confirmations

5 findings in E2E (07) confirmed earlier findings from other reports:

| E2E Finding | Confirms | Category |
|-------------|----------|----------|
| E2E-13 (UCB visit_count) | 01-H-01 | Storage |
| E2E-04 (nodes.frequency disconnect) | 01-H-02 | Storage |
| E2E-05 (promote_node no action_log) | 02-H-01 | Tools |
| E2E-08 (edge archive no-op) | 04-M-01 | Scripts |
| E2E-09 (deprecated Evidence) | 05-M-02 | Spec |

**Unique findings (deduped): ~108** (113 total - 5 confirmations)

---

## Systemic Themes

### Theme 1: v2.1 Promotion Pipeline is Non-Functional (8 findings)

The entire Signal → Pattern → Principle promotion pathway — v2.1's core differentiator — has zero functional end-to-end paths.

| Stage | Blocker | Finding |
|-------|---------|---------|
| SPRT Detection | Score threshold 0.5 vs RRF range ~0.0-0.4 | E2E-01 (CRITICAL) |
| SPRT Detection | `meta` table never created, recall_count always 0 | E2E-02 (CRITICAL) |
| Gate 1 (SWR) | `recall_log` table missing, vec_ratio always 0.0 | E2E-03 (CRITICAL) |
| Gate 2 (Bayesian) | `nodes.frequency` column missing, k always 0 | E2E-04 (HIGH) |
| Gate 2 (Bayesian) | `meta` table missing, total_queries always 0 | E2E-02 (CRITICAL) |
| Learning (BCM→UCB) | BCM writes `frequency`, UCB reads `strength` | 01-H-02 (HIGH) |
| Learning (UCB) | `visit_count` not loaded into graph | 01-H-01 (HIGH) |
| Audit | `action_log.record()` never called | 02-H-01 (HIGH) |
| Test Coverage | promote_node + analyze_signals: 0 tests | 06-H-01 (HIGH) |

**Impact**: Only `skip_gates=True` (admin override) enables promotion. The system can store and search memories but cannot learn which memories are important enough to promote. v2.1's "neural-inspired adaptive" features are effectively inert, reducing the system to v2.0 manual-promotion behavior.

### Theme 2: Access Control Not Enforced at MCP Boundary (3 findings)

`access_control.py` is well-designed with 3-layer protection (A-10 firewall, Hub, RBAC), but is **never called** from MCP tool entry points.

| Tool | Protection | Finding |
|------|-----------|---------|
| `promote_node()` | No `check_access()` — any caller can promote to L4/L5 | SEC-01 (HIGH) |
| `remember()` | No `check_access()` — any caller can create L4/L5 nodes | SEC-02 (HIGH) |
| All MCP tools | No actor identification mechanism at transport level | SEC-03 (HIGH) |

**Impact**: The A-10 F1 firewall (L4/L5 content protection for "paul" only) is a paper wall. Only batch scripts (`daily_enrich.py`, `pruning.py`) actually call `check_access()`. The primary user-facing tools bypass it entirely.

### Theme 3: Ontology Layer Inconsistencies (4 findings)

Three authoritative sources for node type layers disagree:

| Source | Question Layer | Value Layer | Authority |
|--------|---------------|------------|-----------|
| `schema.yaml` | 0 | 5 | v2.0 reference |
| `migrate_v2_ontology.py` | 1 | 4 | Runtime (type_defs table) |
| `config.py PROMOTE_LAYER` | (absent) | 5 | Used by classify() |

Additionally, `PROMOTE_LAYER` maps only 12 of 50 types — 38 types get `layer=NULL` when stored via `remember()`.

| Finding | Issue |
|---------|-------|
| 05-H-01 | 3-source layer conflict (Question/Value) |
| 03-M-01 | PROMOTE_LAYER covers 12/50 types |
| 05-M-01 | schema.yaml all 50 active vs migration 19 deprecated |
| 05-M-04 | PROMOTE_LAYER contains 3 deprecated dead entries |

### Theme 4: Missing Infrastructure (3 findings)

| Missing | Expected By | Impact | Finding |
|---------|------------|--------|---------|
| `meta` table | recall.py, promote_node.py, analyze_signals.py | Recall counting + Bayesian gates broken | E2E-02 (CRITICAL) |
| `recall_log` table | promote_node.py Gate 1 | SWR readiness always 0.0 | E2E-03 (CRITICAL) |
| `get_valid_node_types()` / `get_valid_relation_types()` | 3 files (module-level import) | enrichment pipeline ImportError crash | 03-H-01 (HIGH) |

### Theme 5: Pruning System Deviations (4 findings)

| Finding | Issue |
|---------|-------|
| E2E-06 (HIGH) | New auto-link edges (frequency=0) immediately prunable |
| 04-M-01 | Edge "archive" decision is no-op (schema lacks `archived_at`) |
| 04-M-02 | BSP importance_score simplified to quality_score only |
| 04-M-03 | Pruning constants hardcoded instead of config.py |

### Theme 6: Deprecated Type Handling Incomplete (3 findings)

| Finding | Issue |
|---------|-------|
| 05-M-02 | VALID_PROMOTIONS allows promotion TO "Evidence" (deprecated) |
| 05-M-03 | `viewed_through`, `interpreted_as` deprecated but in ALL_RELATIONS |
| 05-M-04 | PROMOTE_LAYER maps 3 deprecated types (dead entries) |

---

## Top 5 Most Impactful Findings

### 1. Promotion Pipeline Dead (Theme 1)

**Severity**: CRITICAL system failure
**Findings**: E2E-01, E2E-02, E2E-03, E2E-04, 01-H-01, 01-H-02, 02-H-01
**What**: Every stage of the v2.1 promotion pipeline (SPRT detection → 3-gate verification → audit) has independent blockers. Missing tables (`meta`, `recall_log`), missing columns (`nodes.frequency`), wrong threshold (SPRT 0.5 vs RRF ~0.4), and disconnected data flows (BCM→frequency vs UCB→strength) make organic promotion impossible.
**Fix Priority**: P0 — this is v2.1's raison d'etre.

### 2. Access Control Bypass at MCP Boundary (Theme 2)

**Severity**: HIGH security gap
**Findings**: SEC-01, SEC-02, SEC-03
**What**: L4/L5 firewall protection exists in code but is never enforced for user-facing operations. Any MCP caller can create Value/Philosophy/Belief nodes or promote to these types without restriction.
**Fix Priority**: P1 — security boundary is open.

### 3. Missing Infrastructure Tables/Columns (Theme 4)

**Severity**: CRITICAL infrastructure gap
**Findings**: E2E-02, E2E-03, 03-H-01
**What**: `meta` table, `recall_log` table, and `get_valid_node_types()`/`get_valid_relation_types()` functions don't exist. Multiple modules depend on them. Two cause silent failures (try/except → 0), one causes ImportError crash.
**Fix Priority**: P0 — prerequisites for promotion pipeline fix.

### 4. BCM/UCB Learning Loop Disconnected (from Theme 1)

**Severity**: HIGH design disconnect
**Findings**: 01-H-01, 01-H-02
**What**: BCM learning updates `edges.frequency` but UCB reads `edges.strength` (never updated). `visit_count` is written to DB but never loaded into the graph. The "neural-inspired adaptive search" feature — BCM synaptic plasticity + UCB exploration — is inert.
**Fix Priority**: P1 — core v2.1 adaptive mechanism.

### 5. Ontology Layer Inconsistency (Theme 3)

**Severity**: HIGH data integrity risk
**Findings**: 05-H-01, 03-M-01
**What**: Three sources disagree on node type layers. 38 of 50 types stored with `layer=NULL`. Layer-dependent features (access control, BCM learning rates, tier assignment) operate on incorrect or missing data.
**Fix Priority**: P1 — affects all layer-dependent features.

---

## Coverage Metrics

| Metric | Value |
|--------|-------|
| Source files reviewed | 24/24 + config.py + schema.yaml + migration |
| Script files reviewed | 6/14 (spec-critical) |
| Test files reviewed | 7/7 (117 tests) |
| Spec documents checked | 10/10 R3 final specs |
| E2E scenarios traced | 10/10 |
| SQL queries audited | 47 (security review) |
| Error handlers reviewed | 69 except blocks |
| Functions verified | 46+ public + internal |

### Source Coverage

| Area | Tested | Untested (source files with 0 tests) |
|------|--------|---------------------------------------|
| storage/ | hybrid, action_log | sqlite_store, vector_store |
| tools/ | remember, recall | promote_node **(CRITICAL)**, analyze_signals **(HIGH)**, 6 others |
| utils/ | access_control, similarity | — |
| ontology/ | validators (mock only) | — |
| scripts/ | — | All scripts untested |
| server.py | — | Untested |

**Test coverage by file: 7/18 production files (39%)**

---

## What Works Well

Despite the critical findings above, significant portions of the v2.1 implementation are correctly built:

1. **remember() pipeline** (S1): classify→store→link→action_log works end-to-end. F3 firewall correctly protects L4/L5. Type validation with deprecated type auto-correction works.

2. **recall() search** (S2 partial): RRF merge formula correct. Graph bonus application correct. Patch switching (75% saturation detection + excluded_project re-search) works. BCM theta_m sliding squared mean correct per theory.

3. **SPRT math** (formulas correct): A=log((1-β)/α)≈2.773, B=log(β/(1-α))≈-1.558, LLR computations correct. The formulas are right — the threshold vs score range is the problem.

4. **3-gate formulas** (all correct): SWR readiness, Bayesian Beta(1,10), MDL cosine similarity matrix — all match specs exactly. The gates work correctly; they just never receive valid input data.

5. **access_control.py** (I-01): 3-layer protection with progressive restriction. Exact spec match. Well-designed — just needs to be called.

6. **Edge case handling** (S3): Empty, single-char, and very-long queries handled gracefully without crashes.

7. **Hub monitor** (S9): compute_ihs, snapshots, health reports, and check_access integration all work correctly.

8. **SQL injection prevention**: All 47 queries use parameterized binding. No direct user data in SQL strings.

---

## Recommended Fix Order

### Phase 0: Infrastructure (unblocks everything)
1. Create `meta` table in `init_db()` (E2E-02)
2. Create `recall_log` table or repurpose `activation_log` VIEW (E2E-03)
3. Add `frequency` column to `nodes` table (E2E-04)
4. Add `get_valid_node_types()` / `get_valid_relation_types()` to validators.py (03-H-01)

### Phase 1: Promotion Pipeline (v2.1 core)
5. Normalize SPRT scores before threshold comparison (E2E-01)
6. Fix BCM to update `edges.strength` (or UCB to read `edges.frequency`) (01-H-02)
7. Load `visit_count` into graph in `_get_graph()` (01-H-01)
8. Add `action_log.record()` to promote_node.py (02-H-01)
9. Build `gates_passed` dynamically (02-M-01)
10. Update `tier` on promotion (02-M-02)

### Phase 2: Security
11. Add `check_access()` to promote_node.py (SEC-01)
12. Add `check_access()` to remember.py (SEC-02)
13. Add `actor` parameter to MCP tool wrappers (SEC-03)
14. Escape `"` in FTS5 query escaping (SEC-04)
15. Clamp `top_k` to max 100 (SEC-10)

### Phase 3: Ontology Consistency
16. Resolve layer conflicts for Question (0 vs 1) and Value (4 vs 5) (05-H-01)
17. Expand PROMOTE_LAYER to all 50 types or add schema.yaml fallback (03-M-01)
18. Remove deprecated types from VALID_PROMOTIONS (05-M-02)
19. Remove deprecated relations from RELATION_TYPES (05-M-03)

### Phase 4: Pruning & Polish
20. Use `edges.strength` as fallback in pruning formula (E2E-06)
21. Implement edge archival or rename to "keep_protected" (04-M-01)
22. Add importance_score 3-factor formula (04-M-02)
23. Move pruning constants to config.py (04-M-03)

### Phase 5: Tests
24. Create test_promote.py (06-H-01)
25. Add hybrid_search integration test (06-M-01)
26. Add real validator tests (not mocked) (06-M-03)

---

## Risk Assessment

| Risk | Level | Rationale |
|------|-------|-----------|
| Data correctness (existing 3,255 nodes) | **LOW** | remember/recall paths work. Existing data is sound. |
| Promotion correctness | **CRITICAL** | Pipeline dead. No organic promotions possible. |
| Security | **HIGH** | L4/L5 protection unenforced. Not critical for single-user, but design intent violated. |
| Search quality | **MEDIUM** | RRF works. BCM/UCB adaptive improvements are inert but don't degrade baseline. |
| Data growth sustainability | **MEDIUM** | Pruning partially works. Edge archive is no-op. |
| Enrichment pipeline | **HIGH** | classifier.py and relation_extractor.py crash on import (03-H-01). |

---

## Conclusion

**v2.1 as a storage + search system: functional.**
The remember→recall loop works correctly. RRF search, F3 firewall, patch switching, and type validation all pass E2E testing.

**v2.1 as an adaptive learning system: non-functional.**
The promotion pipeline (SPRT→3-gate→promote), BCM/UCB adaptive learning, and Bayesian evidence accumulation are all broken by missing infrastructure, data flow disconnects, and threshold mismatches.

**The math is right; the plumbing is broken.**
Every formula (SWR, Bayesian Beta(1,10), MDL cosine, SPRT LLR, BCM dw/dt, UCB exploration) is correctly implemented per spec. The failures are in data flow: tables that don't exist, columns that aren't in the expected place, and values that never propagate between components.

Round 1 (Correctness) is complete. 113 findings identified across 8 categories.
