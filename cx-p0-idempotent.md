# Phase 0 Idempotency Check (`migrate_v2_ontology.py`)

- Date (UTC): 2026-03-05
- Command run: `python scripts/migrate_v2_ontology.py` (executed twice, back-to-back)

## Run 1

| Step | Status line | Contains `SKIP` |
|---|---|---|
| 1/9 | `action_log 테이블 + 인덱스 6개 생성` | No |
| 2/9 | `type_defs + relation_defs + ontology_snapshots 생성` | No |
| 3/9 | `type_defs 이미 50행 존재 — SKIP` | Yes |
| 4/9 | `relation_defs 이미 49행 존재 — SKIP` | Yes |
| 5/9 | `관계 교정 완료: 0 edges (5개 매핑)` | No |
| 6/9 | `edges.description 마이그레이션: 0 초기화, 0 JSON 교정` | No |
| 7/9 | `activation_log VIEW 생성` | No |
| 8/9 | `v2.1-initial 스냅샷 이미 존재 — SKIP` | Yes |
| 9/9 | `nodes 컬럼 이미 존재 — SKIP` | Yes |

`SKIP` count: **4/9**

## Run 2

| Step | Status line | Contains `SKIP` |
|---|---|---|
| 1/9 | `action_log 테이블 + 인덱스 6개 생성` | No |
| 2/9 | `type_defs + relation_defs + ontology_snapshots 생성` | No |
| 3/9 | `type_defs 이미 50행 존재 — SKIP` | Yes |
| 4/9 | `relation_defs 이미 49행 존재 — SKIP` | Yes |
| 5/9 | `관계 교정 완료: 0 edges (5개 매핑)` | No |
| 6/9 | `edges.description 마이그레이션: 0 초기화, 0 JSON 교정` | No |
| 7/9 | `activation_log VIEW 생성` | No |
| 8/9 | `v2.1-initial 스냅샷 이미 존재 — SKIP` | Yes |
| 9/9 | `nodes 컬럼 이미 존재 — SKIP` | Yes |

`SKIP` count: **4/9**

## Verdict

- Requirement: all 9 steps must show `SKIP` on both runs.
- Actual: **not satisfied** (`4/9` steps show `SKIP` on each run).
