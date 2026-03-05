# c-r3-11: DB Migration Phase 2

> scripts/migrate_phase2.py 생성 완료

## 실행 방법

```bash
# 드라이런 (변경 없이 확인만)
python scripts/migrate_phase2.py --dry-run

# 실제 실행
python scripts/migrate_phase2.py
```

## 추가 컬럼/테이블

| 대상 | 변경 | 용도 |
|---|---|---|
| nodes.score_history | TEXT DEFAULT '[]' | SPRT score 누적 (JSON array) |
| nodes.promotion_candidate | INTEGER DEFAULT 0 | 승격 후보 플래그 |
| nodes.θ_m | REAL DEFAULT 0.5 | BCM 적응형 임계값 |
| nodes.activity_history | TEXT DEFAULT '[]' | Hebbian activity 이력 |
| meta | 신규 테이블 | total_recall_count 등 전역 카운터 |
| recall_log | 신규 테이블 | recall 이력 (SWR readiness용) |

## recall_log 스키마

```sql
CREATE TABLE IF NOT EXISTS recall_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER,
    source TEXT,         -- 'vector'|'graph'|'fts'
    query_hash TEXT,     -- SHA256[:8]
    recalled_at TEXT     -- ISO8601
);
```

## 의존성 체크

- `storage/hybrid.py` SPRT 구현 전 migration 필수
- `tools/analyze_signals.py` Bayesian 구현 전 migration 필수
- `tools/promote_node.py` MDL gate 구현 전 migration 필수
- `storage/hybrid.py` recall_log INSERT는 B-2 swr_readiness() 구현 시 추가

## 기존 migrate_v2.py와 관계

migrate_v2.py: v2.0 온톨로지 스키마 마이그레이션
migrate_phase2.py: v2.0 위에 ML 피처 컬럼 추가 (독립 실행 가능)
