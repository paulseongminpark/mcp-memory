# Phase 0 Checklist
_Updated: 2026-04-10_

## Goal
- Freeze live truth before bugfix work.
- Prevent stale report numbers from re-entering planning.
- Separate live metrics from manual narrative in `STATE.md`.

## Done
- [x] Canonical planning basis fixed to `MASTERPLAN-FINAL-v3.md`
- [x] `scripts/generate_state.py` supports live snapshot generation
- [x] `scripts/generate_state.py --apply` can write `STATE.md`
- [x] `STATE.md` current block converted to generated region
- [x] `CHANGELOG.md` updated for Phase 0 truth freeze

## Operator Commands
- [x] Snapshot preview: `python scripts/generate_state.py`
- [x] Snapshot apply: `python scripts/generate_state.py --apply`

## Exit Criteria
- [x] Live metrics can be refreshed with one command
- [x] `STATE.md` clearly distinguishes generated facts from manual sections
- [x] Phase 0 checklist exists and is followable

## Next Queue
- [ ] P0-1 pruning hotfix: add `WHERE status='active'` to active edge scan in `scripts/daily_enrich.py`
- [ ] P0-2 FTS rebuild migration: align live `nodes_fts` with 7-column schema
- [ ] P0-3 enum drift fix: register `gemini-enrichment`, `vector-similarity` in `config_ontology.py`
- [ ] P1-1 Hebbian integrity fix: remove lost-update path in `storage/hybrid.py`
- [ ] P1-2 search diagnostics: channel attribution + reranker contribution measurement
