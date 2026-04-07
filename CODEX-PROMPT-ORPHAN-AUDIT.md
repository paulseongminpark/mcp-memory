# Codex Prompt: Orphan Repair Edge Audit

## 목적

`generation_method='orphan_repair'`인 732개 edge의 품질을 감사한다.
이 edge들은 nearest-neighbor 임베딩 매칭으로 기계적 생성됨 — semantic 의미가 없는 약한 연결이 섞여있다.

약한 edge를 식별하고, 삭제 후보를 리포트한다.

## 환경

- DB: `data/memory.db` (SQLite)
- 프로젝트 루트: 현재 디렉토리
- `sys.path.insert(0, '.')`
- 테스트: `python -m pytest tests/ -x -q` (193 tests)

## 제약

- **기존 코드 수정 금지**
- **git 금지**
- **DELETE 금지** — soft-delete만 (`UPDATE edges SET status='deleted'`)
- dry-run 먼저, apply는 `--apply` 플래그

---

## Task 1: 품질 분류 스크립트

파일: `scripts/audit_orphan_edges.py`

### 분류 기준

각 orphan_repair edge에 대해 아래 3가지를 측정한다:

**A. strength 기반**
- strength < 0.3 → `weak` (cosine distance > 0.7 = 거의 무관)
- strength 0.3-0.5 → `marginal`
- strength >= 0.5 → `ok`

**B. 타입 호환성**
- source/target 노드의 type 조합이 RELATION_RULES(config.py)에 정의되어 있으면 → `typed`
- 정의되어 있지 않으면 → `untyped`

**C. 프로젝트 일치**
- 같은 project → `same_project`
- 다른 project → `cross_project`

### 삭제 후보 기준

아래 **모두** 해당하면 삭제 후보:
- strength < 0.3
- untyped (RELATION_RULES에 매칭 없음)

아래 **하나라도** 해당하면 삭제 후보:
- strength < 0.15 (극히 약한 연결)

### 출력

```
사용법:
  python scripts/audit_orphan_edges.py              # 분석만
  python scripts/audit_orphan_edges.py --apply      # 삭제 후보 soft-delete
```

dry-run 출력:
```
=== Orphan Repair Edge Audit ===
Total orphan_repair edges: 732

Strength distribution:
  weak (< 0.3): NNN
  marginal (0.3-0.5): NNN
  ok (>= 0.5): NNN

Type compatibility:
  typed: NNN
  untyped: NNN

Delete candidates:
  weak + untyped: NNN
  ultra-weak (< 0.15): NNN
  Total unique delete candidates: NNN

Sample delete candidates (10개):
  edge#NNNN src=#NNNN(Type) → tgt=#NNNN(Type) strength=0.NN relation=XXX
  ...

After deletion:
  Remaining orphan_repair: NNN
  New orphans created: NNN (이 edge 삭제 시 고아 되는 노드)
```

### 중요: 고아 방지

edge 삭제 후 해당 노드가 다시 orphan이 되는지 확인해야 한다.
삭제 후보 edge가 해당 노드의 **유일한 edge**이면 삭제하지 않는다.

```sql
-- 이 edge가 노드의 유일한 연결인지 확인
SELECT COUNT(*) FROM edges 
WHERE (source_id = ? OR target_id = ?) 
AND status = 'active' AND id != ?
```

결과가 0이면 해당 edge는 삭제 후보에서 제외한다.

---

## Task 2: 리포트 생성

파일: `data/orphan_audit_report.json`

```json
{
  "timestamp": "ISO",
  "total_audited": 732,
  "strength_distribution": {"weak": N, "marginal": N, "ok": N},
  "type_compatibility": {"typed": N, "untyped": N},
  "delete_candidates": N,
  "protected_by_orphan_guard": N,
  "deleted": N,
  "remaining_orphan_repair": N,
  "new_orphans_after_delete": N
}
```

---

## Task 3: Regression Test

파일: `tests/test_orphan_audit.py`

테스트 항목 (최소 3개):

1. `test_no_new_orphans_after_audit` — audit apply 후 새 orphan 0
2. `test_deleted_edges_are_soft_deleted` — status='deleted'이지 물리 삭제 아님
3. `test_remaining_orphan_repair_edges_above_threshold` — 남은 orphan_repair edge의 strength 전부 >= 0.15

---

## 실행 순서

```
1. python scripts/audit_orphan_edges.py          (분석)
2. python scripts/audit_orphan_edges.py --apply  (soft-delete)
3. python scripts/r2_saturation_report.py        (fill rate 재확인)
4. python -m pytest tests/ -x -q                 (전체 테스트)
```

## 성공 기준

- [ ] 삭제 후보 식별 + 리포트
- [ ] soft-delete 적용 후 새 orphan = 0
- [ ] 남은 orphan_repair edge 전부 strength >= 0.15
- [ ] 193+ tests passed
