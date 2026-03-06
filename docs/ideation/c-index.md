# 세션 C 인덱스 — PyTorch/ML 실험 가능성

> compact 후 이 파일만 읽고 이어서 진행한다.
> 다음 파일 번호: **c-r3-13-...**
> R3 완료: c-r3-10(골드셋), c-r3-11(promote 3-gate), c-r3-12(SPRT 검증)

## 완료된 주제

| 파일 | 라운드 | 한줄 요약 |
|---|---|---|
| `c-r0-pytorch-ml.md` | R0 | 세션 C 전체 인덱스 (요약본) |
| `c-r1-1-kg-embedding.md` | R1 | 6K edges로 TransE/R-GCN 불가, sklearn MLP + OpenAI embeddings로 missing link 탐지 가능 |
| `c-r1-2-hebbian-bcm.md` | R1 | PyTorch Hebbian 불필요(I/O bound), BCM은 NumPy — B-1 LAYER_ETA 정본으로 교체 확정 |
| `c-r1-3-promotion-models.md` | R1 | MDL+Bayesian+SPRT 3중 승격 모델 구현 가능, score_history/total_queries 컬럼 필요 |
| `c-r1-4-rrf-experiment.md` | R1 | RRF_K=60→30 1줄 변경, tier=0 노드 골드셋 20-50개 + NDCG@5/MRR 측정 설계 |
| `c-r1-5-roadmap.md` | R1 | PyTorch 전환 임계값 60K+ edges, 지금은 경량 통계 모델 순으로 구현 |
| `c-r2-6-goldset-design.md` | R2 | tier=0 실제 노드 30개 조회, YAML 라벨링 포맷+예시 3개, scripts/eval/ab_test.py 완성 |
| `c-r2-7-promotion-integration.md` | R2 | SPRT→hybrid.py, Bayesian→analyze_signals.py, MDL→promote_node.py 삽입점 확정. DB migration SQL 5개 |
| `c-r2-8-link-detector.md` | R2 | ChromaDB coll.get() 전체 추출, sklearn LR AUC 0.72-0.82 예측, top-20 enriched 출력 |
| `c-r2-9-cross-session-alignment.md` | R2 | C-2 단일 η → B-1 LAYER_ETA 교체. SWR→Bayesian→MDL 직렬 게이트. k=30 시 RWR_SURPRISE_WEIGHT=0.05 |
| `c-r3-10-config-changes.md` | R3 | [revert됨] config.py 변경 초안 |
| `c-r3-11-migration.md` | R3 | [revert됨] migrate_phase2.py 초안 |
| `c-r3-12-scripts-structure.md` | R3 | [revert됨] scripts 구조 초안 |
| `c-r3-10-goldset-draft.md` | R3 | **[신규]** 골드셋 25개 쿼리 초안 (YAML, Paul 검토 대상) |
| `c-r3-11-promotion-final.md` | R3 | **[신규]** promote_node.py 전체 교체 코드 (SWR+Bayesian+MDL 3-gate) |
| `c-r3-12-sprt-validation.md` | R3 | **[신규]** SPRT 파라미터 수학 검증 + 3,230 노드 규모 추정 + 조정 가이드 |

## 핵심 확정 사항

- **RRF k=30**: Phase 1 즉시. `config.py` 1줄 + `RWR_SURPRISE_WEIGHT=0.05` 동반
- **BCM η**: B-1 정본 `LAYER_ETA = {0:0.02, 1:0.015, 2:0.01, 3:0.005, 4:0.001, 5:0.0001}`
- **컬럼명**: `θ_m`, `activity_history` (B-1 기준 통일)
- **승격 게이트 순서**: SWR readiness → Bayesian P>0.5 → MDL similarity>0.75
- **scripts/**: `eval/` (A/B 테스트), `link_detector/` (missing edge) 신규 생성 필요

## DB 마이그레이션 (Phase 2 선행 필요)

```sql
ALTER TABLE nodes ADD COLUMN score_history TEXT DEFAULT '[]';
ALTER TABLE nodes ADD COLUMN promotion_candidate INTEGER DEFAULT 0;
ALTER TABLE nodes ADD COLUMN θ_m REAL DEFAULT 0.5;
ALTER TABLE nodes ADD COLUMN activity_history TEXT DEFAULT '[]';
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT DEFAULT '0');
INSERT OR IGNORE INTO meta VALUES ('total_recall_count', '0');
CREATE TABLE IF NOT EXISTS recall_log (id INTEGER PRIMARY KEY AUTOINCREMENT, node_id INTEGER, source TEXT, query_hash TEXT, recalled_at TEXT);
```

## 미완료 (R3 이후)

- [ ] `scripts/eval/goldset.yaml` Paul 라벨링 (현재 3개, 목표 20-50개)
- [ ] DB migration 실행: `python scripts/migrate_phase2.py`
- [ ] `scripts/eval/ab_test.py` 실제 실행 및 결과 기록
- [ ] `scripts/link_detector/train_predict.py` 실행 → top-20 출력 Paul 검토
- [ ] `storage/hybrid.py` BCM 구현 (B-1 LAYER_ETA + θ_m 적용)
- [ ] `tools/analyze_signals.py` Bayesian 승격 판단 추가
- [ ] `tools/promote_node.py` MDL gate 추가
- [ ] `storage/hybrid.py` SPRT 검사 + recall_log INSERT 추가
