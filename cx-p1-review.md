# P1 Review: `storage/` and `tools/` vs `docs/ideation/`

- Date: 2026-03-05
- Scope: All Python files under `storage/` and `tools/` excluding tests (16 files total, including `__init__.py`)
- Constraint followed: No existing files modified; report file only

## Method

- Enumerated target files with `rg --files storage tools -g "*.py" -g "!**/tests/**"`
- Mapped each file to ideation specs via `rg/Select-String` in `docs/ideation/`
- Compared function signatures and expected behavior against final spec docs (`a-r3-*`, `b-r3-*`, `c-r3-*`, `d-r3-*`, orchestrator final)
- Import/syntax checks:
  - `python -m compileall -q storage tools` -> OK
  - Runtime import smoke test for all target modules -> all imports OK
  - `pyflakes` not installed (`No module named pyflakes`), so lint-level undefined-name analysis was not available

## Findings (Severity Ordered)

### High

1. `tools/promote_node.py` does not match C-11 final promotion spec.
- Current code: [tools/promote_node.py](tools/promote_node.py):10 defines `promote_node(node_id, target_type, reason="", related_ids=None)` only.
- Missing from spec: `skip_gates: bool = False`, SWR/Bayesian/MDL gate pipeline helpers.
- Spec refs: [docs/ideation/c-r3-11-promotion-final.md](docs/ideation/c-r3-11-promotion-final.md):54, :113, :147, :191.
- Impact: Promotion proceeds without the 3-gate readiness/evidence checks required by final spec.

2. `tools/analyze_signals.py` missing C-11 Bayesian/SPRT integration.
- Current code still uses `_recommend()` only: [tools/analyze_signals.py](tools/analyze_signals.py):100, :126.
- Missing from spec: `_recommend_v2()`, `_bayesian_cluster_score()`, `bayesian_p`/`sprt_flagged` fields, meta-based total query usage.
- Spec refs: [docs/ideation/c-r3-11-promotion-final.md](docs/ideation/c-r3-11-promotion-final.md):321-396.
- Impact: Cluster recommendations are based only on maturity, not final multi-signal promotion criteria.

3. `storage/hybrid.py` missing SPRT candidate updates from C-11.
- Current code has no `_sprt_check()` and returns after BCM/logging: [storage/hybrid.py](storage/hybrid.py):424-427.
- Spec requires `_sprt_check()` plus `promotion_candidate` updates before return.
- Spec refs: [docs/ideation/c-r3-11-promotion-final.md](docs/ideation/c-r3-11-promotion-final.md):423-479.
- Impact: Signal candidate marking for promotion pipeline never occurs.

4. `tools/recall.py` updates `stats` instead of `meta` for `total_recall_count`.
- Current SQL writes `stats(key,value,updated_at)`: [tools/recall.py](tools/recall.py):113-117.
- Final orchestration decision replaced `stats` with `meta` table.
- Spec refs: [docs/ideation/0-orchestrator-round3-final.md](docs/ideation/0-orchestrator-round3-final.md):92-100, :131, :455; [docs/ideation/c-r3-11-promotion-final.md](docs/ideation/c-r3-11-promotion-final.md):494-497.
- Impact: Bayesian promotion logic depending on `meta.total_recall_count` can be stale/zero.

### Medium

5. `storage/sqlite_store.py::insert_edge()` lacks `action_log.edge_corrected` logging path specified in A-17.
- Current code writes to `correction_log` only: [storage/sqlite_store.py](storage/sqlite_store.py):175-180.
- Spec adds in-transaction `action_log.record(action_type="edge_corrected", conn=conn)`.
- Spec refs: [docs/ideation/a-r3-17-actionlog-record.md](docs/ideation/a-r3-17-actionlog-record.md):450-464.
- Impact: Correction telemetry is incomplete vs action taxonomy design.

6. `storage/sqlite_store.py::log_correction()` is behind D-12 helper signature.
- Current signature lacks `event_type` and insert statement omits `event_type` column: [storage/sqlite_store.py](storage/sqlite_store.py):277-295.
- `correction_log` schema in `init_db()` also omits `event_type`: [storage/sqlite_store.py](storage/sqlite_store.py):83-93.
- Spec ref: [docs/ideation/d-r3-12-drift-final.md](docs/ideation/d-r3-12-drift-final.md):425-445.
- Impact: Cannot represent correction event class expected by drift-final design.

### Low

7. `storage/__init__.py` missing A-17 export line.
- File is empty; spec requested `from storage import action_log` addition.
- Spec ref: [docs/ideation/a-r3-17-actionlog-record.md](docs/ideation/a-r3-17-actionlog-record.md):671-674.
- Impact: Low at runtime (submodule imports still work), but diverges from spec packaging intent.

8. Error-handling coverage is inconsistent in several write paths.
- No outer `try/finally` around DB write lifecycle in [tools/save_session.py](tools/save_session.py):20-42 and [tools/promote_node.py](tools/promote_node.py):53-77.
- `storage/sqlite_store.py` write helpers (`insert_node`, `insert_edge`) also assume happy path.
- Impact: DB exceptions can leak connections or partially skip cleanup in failure scenarios.

## Per-File Compliance Matrix

| File | Primary Spec Reference(s) | Signature Match | Backward Compatibility | Missing Imports | Error Handling | Status |
|---|---|---|---|---|---|---|
| `storage/action_log.py` | `a-r3-17-actionlog-record.md` | Yes (`record(...)`) | Yes | None found | Present (silent-fail) | PASS |
| `storage/hybrid.py` | `b-r3-14-hybrid-final.md`, `c-r3-11-promotion-final.md` | B-14: Yes, C-11: No (`_sprt_check` missing) | Existing API preserved (`hybrid_search` optional args) | None found | Present in core paths | PARTIAL |
| `storage/sqlite_store.py` | `a-r3-17-actionlog-record.md`, `d-r3-12-drift-final.md` | Core signatures mostly match | Existing callers likely unaffected | None found | Partial | PARTIAL |
| `storage/vector_store.py` | `d-r3-12-drift-final.md` | Yes (`get_node_embedding`) | Yes | None found | Partial (helper guarded) | PASS |
| `storage/__init__.py` | `a-r3-17-actionlog-record.md` | N/A | N/A | N/A | N/A | FAIL (spec divergence) |
| `tools/remember.py` | `a-r3-18-remember-final.md` | Yes (`classify/store/link/remember`) | Yes (spec states 100% compatibility) | None found | Present in vector/auto-link paths | PASS |
| `tools/recall.py` | `b-r3-15-recall-final.md`, orchestrator R3 decision | B-15: Yes | Yes for old calls (`mode` optional) | None found | Present in recall counter path | PARTIAL (meta/stats divergence) |
| `tools/promote_node.py` | `c-r3-11-promotion-final.md` | No (missing `skip_gates` + gate helpers) | Older API preserved, final API missing | None found | Partial | FAIL |
| `tools/analyze_signals.py` | `c-r3-11-promotion-final.md` | Public signature unchanged | Existing API preserved, final behavior missing | None found | Partial | FAIL |
| `tools/get_becoming.py` | No direct ideation spec found | N/A | N/A | None found | Partial | NO-SPEC |
| `tools/get_context.py` | No direct ideation spec found | N/A | N/A | None found | Minimal | NO-SPEC |
| `tools/inspect_node.py` | No direct ideation spec found | N/A | N/A | None found | JSON parse guards present | NO-SPEC |
| `tools/save_session.py` | No direct ideation spec found | N/A | N/A | None found | Minimal | NO-SPEC |
| `tools/suggest_type.py` | No direct ideation spec found | N/A | N/A | None found | Minimal | NO-SPEC |
| `tools/visualize.py` | `b-r2-11-cte-impl.md` (build_graph kept) | Yes for known requirement | Yes | None found | Partial (`ImportError` handled) | PASS |
| `tools/__init__.py` | No direct ideation spec found | N/A | N/A | N/A | N/A | NO-SPEC |

## Summary

- Files reviewed: 16
- PASS: 4
- PARTIAL: 3
- FAIL: 3
- NO-SPEC (in `docs/ideation/`): 6
- Missing imports check: No runtime import failures found.

Most impactful gaps are the unimplemented C-11 promotion path (`promote_node`, `analyze_signals`, `hybrid`, and `recall` meta counter alignment).
