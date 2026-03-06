# D-2: 5개 합의 지점 해결 방안

> 세션 D | 2026-03-05
> 9개 AI 진단 (섹션 6.1) 에서 전원 합의한 5개 문제의 구체적 해결 설계

---

## A. Hebbian 불안정 → 정규화 (세션 B 연계)

### 현재 상태 (코드 확인)

```python
# storage/hybrid.py _hebbian_update()
# 현재: frequency +1 무한 증가, strength 상한 없음
conn.execute(
    "UPDATE edges SET frequency=frequency+1, last_activated=? WHERE id=?",
    (now, edge_id)
)
# base_strength, decay_rate 컬럼 있으나 강도 정규화 로직 없음
```

### 해결안 1: tanh 정규화

```python
def _update_edge_hebbian(edge_id: str, conn):
    """
    tanh(frequency / τ) 으로 strength를 [0, base_strength] 범위에 수렴시킴.
    발산 방지 + 점진적 포화 (biological synapse 유사).
    """
    row = conn.execute(
        "SELECT base_strength, frequency FROM edges WHERE id=?", (edge_id,)
    ).fetchone()

    tau = 10  # 실험 파라미터 (10 세션 → 포화의 76%)
    new_strength = row["base_strength"] * math.tanh(row["frequency"] / tau)

    conn.execute(
        "UPDATE edges SET strength=?, frequency=frequency+1, last_activated=? WHERE id=?",
        (new_strength, datetime.utcnow().isoformat(), edge_id)
    )
```

**τ 선택 기준:**
- τ=5: 5 세션에서 76% 포화 (빠른 학습)
- τ=10: 10 세션에서 76% 포화 (권장 시작점)
- τ=20: 20 세션에서 76% 포화 (느린 학습, 노이즈 내성↑)

### 해결안 2: BCM Sliding Threshold (세션 B 설계)

```python
def _bcm_update(edge_id: str, conn, session_window: int = 20):
    """
    BCM (Bienenstock-Cooper-Munro) 규칙:
    θ = E[y²] = 최근 N 세션의 활성화 강도 제곱 평균
    strength - θ > 0 → LTP (강화)
    strength - θ < 0 → LTD (억제)
    """
    recent_strengths = conn.execute(
        "SELECT strength FROM edges WHERE source_id IN ("
        "  SELECT source_id FROM edges WHERE id=?"
        ") ORDER BY last_activated DESC LIMIT ?",
        (edge_id, session_window)
    ).fetchall()

    if not recent_strengths:
        return  # fallback to tanh

    theta = sum(r["strength"]**2 for r in recent_strengths) / len(recent_strengths)
    row = conn.execute("SELECT strength FROM edges WHERE id=?", (edge_id,)).fetchone()
    current = row["strength"]

    lr = 0.01  # 학습률
    delta = lr * current * (current - theta)
    new_strength = max(0.0, min(1.0, current + delta))

    conn.execute(
        "UPDATE edges SET strength=?, frequency=frequency+1, last_activated=? WHERE id=?",
        (new_strength, datetime.utcnow().isoformat(), edge_id)
    )
```

**BCM 장점:** 자동 임계값 조정. 노드 활성화가 많으면 θ↑ → 추가 강화 어려움 (homeostatic plasticity).

### 권장: 1단계 tanh, 2단계 BCM

```
즉시: tanh (단순, 안전, 효과 즉각)
1달 후: BCM으로 전환 (A/B 테스트 후)
```

---

## B. 시간 감쇠 — 현재 미구현

### 현재 상태

```python
# storage/sqlite_store.py nodes 테이블
# decay_rate 컬럼 존재 (L35 근방)
# storage/hybrid.py
# last_activated 업데이트만 있고, 실제 decay 적용 없음
```

### 해결 설계: 검색 시 동적 적용

```python
# storage/hybrid.py hybrid_search() 내 재정렬 단계에 추가

import math
from datetime import datetime, timezone

DECAY_RATE_BY_LAYER = {
    0: 0.010,  # L0 원시: 90일이면 40% 감쇠
    1: 0.007,
    2: 0.005,  # L2 패턴: 중간 감쇠
    3: 0.003,
    4: 0.001,  # L4-5 가치/공리: 1000일 후 37%
    5: 0.001,
}

def _effective_strength(edge: dict, current_time: datetime) -> float:
    """
    검색 시점에 decay를 적용한 유효 강도.
    DB에는 쓰지 않음 (읽기 전용 계산).
    """
    if not edge.get("last_activated"):
        return edge["strength"]

    try:
        last = datetime.fromisoformat(edge["last_activated"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        delta_days = (current_time - last).total_seconds() / 86400
    except (ValueError, TypeError):
        return edge["strength"]

    layer = edge.get("layer", 0)
    rate = DECAY_RATE_BY_LAYER.get(layer, 0.005)
    return edge["strength"] * math.exp(-rate * delta_days)
```

**적용 위치:** `hybrid_search()`의 Enrichment 가중치 적용 직전.

```python
# hybrid.py L101-108 수정안
now = datetime.now(timezone.utc)
for node_id, score in rrf_scores.items():
    node = node_cache[node_id]
    quality_boost = node.get("quality_score", 0) * ENRICHMENT_QUALITY_WEIGHT
    temporal_boost = node.get("temporal_relevance", 0.5) * ENRICHMENT_TEMPORAL_WEIGHT
    tier_boost = {0: 0.15, 1: 0.05, 2: 0.0}.get(node.get("tier", 2), 0.0)

    # 연결된 엣지의 decay 반영 (평균)
    edge_decay = 1.0
    node_edges = [e for e in all_edges if e["source_id"] == node_id or e["target_id"] == node_id]
    if node_edges:
        edge_decay = sum(_effective_strength(e, now) / max(e["strength"], 1e-6)
                         for e in node_edges) / len(node_edges)

    final_score = score * (1 + quality_boost + temporal_boost + tier_boost) * edge_decay
    rrf_scores[node_id] = final_score
```

---

## C. 검증 체계 구축 순서

### 현재 상태

```
검증 체계 = 없음.
- 골드셋 없음
- NDCG/MRR 측정 없음
- A/B 테스트 없음
- validators.py는 있으나 미호출 (d-1 참조)
```

### 4단계 구축 로드맵

**Phase 1 — 즉시: validators.py 연결**
```python
# mcp_server.py에 추가 (d-1-fatal-weaknesses.md 참조)
# 소요: 30분
```

**Phase 2 — 1주: 골드셋 구축**
```
형식: data/eval/goldset.jsonl
각 라인:
{
  "query": "맥락 관리 전략",
  "expected_node_ids": ["node_abc", "node_xyz"],
  "expected_types": ["Pattern", "Principle"],
  "session": "recall_test_2026-03-05"
}

목표: 100개 (수동 구축)
출처: 실제 세션에서 Paul이 검색한 쿼리 + 만족한 결과
```

**Phase 3 — 2주: NDCG@10 오프라인 평가**
```python
# scripts/eval/ndcg_eval.py (신규)
import numpy as np

def ndcg_at_k(retrieved_ids: list, gold_ids: list, k: int = 10) -> float:
    """Normalized Discounted Cumulative Gain@K"""
    relevance = [1 if nid in gold_ids else 0 for nid in retrieved_ids[:k]]
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(relevance))
    ideal = sorted(relevance, reverse=True)
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0

def evaluate_goldset(goldset_path: str = "data/eval/goldset.jsonl") -> dict:
    """전체 골드셋 평균 NDCG@10 측정"""
    scores = []
    with open(goldset_path) as f:
        for line in f:
            item = json.loads(line)
            results = hybrid_search(item["query"], top_k=10)
            retrieved_ids = [r["id"] for r in results]
            score = ndcg_at_k(retrieved_ids, item["expected_node_ids"])
            scores.append(score)
    return {
        "ndcg_at_10_mean": np.mean(scores),
        "ndcg_at_10_std": np.std(scores),
        "n_queries": len(scores),
    }
```

**Phase 4 — 1달: A/B 테스트**
```python
# config.py에 실험 플래그
AB_TEST_GROUP = os.getenv("AB_TEST_GROUP", "control")  # "control" | "treatment"
AB_RRF_K = {"control": 60, "treatment": 30}[AB_TEST_GROUP]
AB_QUALITY_WEIGHT = {"control": 0.2, "treatment": 0.4}[AB_TEST_GROUP]
```

---

## D. Palantir 참조 — 무엇을 먼저 차용하나

### Palantir Foundry OMS 패턴 (섹션 8.1)

| 우선순위 | 패턴 | 현재 상태 | 적용 설계 |
|---------|------|----------|---------|
| **1** | **리니지(Lineage) 추적** | correction_log 있음 (최근 추가) | correction_log 확장 → 전체 이력 |
| **2** | 메타/인스턴스 분리 | L4-L5 vs L0-L1로 이미 근사 | 별도 구현 불필요 |
| **3** | 버전 스냅샷 | 없음 | schema.yaml 버전 + DB 주간 스냅샷 |
| **4** | Deprecation 처리 | status 필드만 | replaced_by 필드 추가 |

### 리니지 확장 설계 (우선순위 1)

```sql
-- correction_log 확장 (현재 필드 + 추가)
CREATE TABLE correction_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id      TEXT NOT NULL,
    field        TEXT NOT NULL,
    old_value    TEXT,
    new_value    TEXT,
    reason       TEXT,
    corrected_by TEXT,   -- 'enricher_e12' | 'user' | 'auto_drift_detector'
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- 추가 필드
    event_type       TEXT,   -- 'enrich' | 'promote' | 'prune' | 'semantic_drift'
    similarity_score REAL,
    auto_rollback    INTEGER DEFAULT 0,
    session_id       TEXT
);
```

### Deprecation 설계

```sql
-- nodes 테이블에 추가
ALTER TABLE nodes ADD COLUMN replaced_by TEXT REFERENCES nodes(id);
ALTER TABLE nodes ADD COLUMN deprecated_at DATETIME;
ALTER TABLE nodes ADD COLUMN deprecation_reason TEXT;

-- 사용:
UPDATE nodes SET
    status='deprecated',
    replaced_by='new_node_id',
    deprecated_at=CURRENT_TIMESTAMP,
    deprecation_reason='merged into more general Pattern node'
WHERE id='old_node_id';
```

---

## E. 하드코딩 파라미터 — 실험 우선순위

### 현재 하드코딩 목록 (config.py / hybrid.py)

```python
RRF_K = 60                      # Reciprocal Rank Fusion k
ENRICHMENT_QUALITY_WEIGHT = 0.2  # quality_score 가중치
ENRICHMENT_TEMPORAL_WEIGHT = ?   # (확인 필요)
GRAPH_BONUS = ?                  # 그래프 채널 보너스
tier_bonus = {0: 0.15, 1: 0.05, 2: 0.0}  # 하드코딩
exploration_weight = 0.1         # UCB 탐색 가중치 (섹션 7.3)
```

### 실험 순서 (ROI 기준)

| 순위 | 파라미터 | 현재값 | 실험 범위 | 측정 지표 | 예상 영향 |
|-----|---------|-------|----------|---------|---------|
| 1 | RRF_K | 60 | 30, 60, 100 | NDCG@10 | 검색 정밀도 직접 영향 |
| 2 | ENRICHMENT_QUALITY_WEIGHT | 0.2 | 0.1, 0.2, 0.4 | 사용자 만족도 | 품질 노드 부각 |
| 3 | decay_rate (신규) | 미구현 | 0.001~0.01 | edge 분포 변화 | 오래된 노드 억제 |
| 4 | DRIFT_THRESHOLD (신규) | 없음 | 0.3, 0.5, 0.7 | 환각 탐지율 | 안전성 |
| 5 | tau (Hebbian) | 미구현 | 5, 10, 20 | edge strength 분포 | 학습 안정성 |
| 6 | tier_bonus | {0:0.15,...} | 다양 | NDCG@10 | tier 활용도 |

### 실험 방법

```python
# scripts/param_sweep.py (설계)
SWEEP_CONFIGS = [
    {"RRF_K": 30, "ENRICHMENT_QUALITY_WEIGHT": 0.2},
    {"RRF_K": 60, "ENRICHMENT_QUALITY_WEIGHT": 0.2},  # baseline
    {"RRF_K": 100, "ENRICHMENT_QUALITY_WEIGHT": 0.2},
    {"RRF_K": 60, "ENRICHMENT_QUALITY_WEIGHT": 0.4},
]

for cfg in SWEEP_CONFIGS:
    override_config(cfg)
    result = evaluate_goldset()
    print(f"{cfg} → NDCG@10={result['ndcg_at_10_mean']:.4f}")
```
