# 세션 C — PyTorch #5: 최종 로드맵 & 결론

> 2026-03-05 | Q8 + 종합

---

## 핵심 결론

### "PyTorch를 써야 하는가?"

현재 규모(6K edges)에서는 **No**.

| 이유 | 설명 |
|---|---|
| Hebbian | SQLite I/O bound. GPU 전송 오버헤드 > 계산 이득 |
| KG embedding | 6K edges vs 최소 50K 필요. 수렴 불가 |
| 승격 모델 | 베이지안/MDL/SPRT 모두 NumPy/scipy로 충분 |

**PyTorch 전환 임계값**: 60K+ edges (Hebbian: 100K+)

### "우리 데이터로 모델을 만들 수 있나?"

→ **Yes**, but: 대규모 GNN이 아니라 **경량 통계 모델**로.

---

## 우선순위 로드맵

| 순위 | 항목 | 도구 | 공수 | 데이터 |
|---|---|---|---|---|
| 1 | RRF k=30 실험 | config.py 1줄 | 1시간 | ✅ |
| 2 | BCM 정규화 | NumPy | 반나절 | ✅ |
| 3 | 베이지안 승격 | scipy | 반나절 | ⚠️ total_queries 카운터 필요 |
| 4 | SPRT 실시간 감지 | Python | 반나절 | ⚠️ score_history 컬럼 필요 |
| 5 | MDL 승격 검증 | LLM API | 1일 | ✅ |
| 6 | Missing link detector | sklearn | 1일 | ⚠️ 성능 제한 |
| 7 | PyTorch MLP | PyTorch | 2일 | ⚠️ 희소 |
| 8 | TransE/R-GCN | — | — | ❌ 불가 |

---

## DB 스키마 변경 사항 (필요 시)

```sql
-- SPRT용
ALTER TABLE nodes ADD COLUMN score_history TEXT DEFAULT '[]';

-- BCM용
ALTER TABLE nodes ADD COLUMN bcm_threshold REAL DEFAULT 0.5;

-- Bayesian용 (글로벌 카운터)
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
INSERT OR IGNORE INTO meta VALUES ('total_recall_count', '0');
```

---

## 세 모델 통합 흐름

```
recall() 실행
    │
    ├─ SPRT: 즉시 score 누적 → "promote" 신호 감지
    │        (실시간, recall 중)
    │
    └─ analyze_signals() 실행 (daily_enrich)
           │
           ├─ Bayesian: P(real) > 0.5 후보 추출
           │
           └─ MDL: LLM 압축 검증 후 promote_node() 호출
```

---

## 지금 당장 시작할 수 있는 것

```python
# 1. RRF k=30 (즉시)
# config.py line 22
RRF_K = 30

# 2. BCM 정규화 (hybrid.py _hebbian_update 확장)
def _hebbian_update_bcm(result_ids, all_edges):
    # 기존 frequency++ 유지하되 BCM weight 추가 계산
    pass

# 3. Bayesian 승격 체크 (analyze_signals 또는 daily_enrich에 추가)
from scipy.stats import beta as beta_dist
def check_bayesian_promotions(conn, total_queries):
    signals = conn.execute(
        "SELECT * FROM nodes WHERE type='Signal' AND tier=2"
    ).fetchall()
    candidates = []
    for s in signals:
        k = s['frequency'] or 0
        n = max(total_queries, k)
        p = (1 + k) / (1 + k + 10 + (n - k))
        if p > 0.5:
            candidates.append((s['id'], p))
    return sorted(candidates, key=lambda x: -x[1])
```

---

## 파일 인덱스

| 파일 | 내용 |
|---|---|
| `c-pytorch-1-kg-embedding.md` | Q1+Q7: GNN 가능성, Link Prediction |
| `c-pytorch-2-hebbian-bcm.md` | Q2: PyTorch Hebbian, BCM/Oja |
| `c-pytorch-3-promotion-models.md` | Q3+Q4+Q5: MDL, Bayesian, SPRT |
| `c-pytorch-4-rrf-experiment.md` | Q6: RRF k=30, A/B 테스트 |
| `c-pytorch-5-roadmap.md` | Q8: 최종 로드맵 (이 파일) |
