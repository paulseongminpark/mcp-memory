# 세션 C — PyTorch #4: RRF k=30 실험 설계

> 2026-03-05 | Q6

---

## Q6. RRF k=30 실험 — A/B 테스트 프레임워크

**판정: 1-line config 변경. 핵심은 골드셋 구축.**

---

## 수학적 배경

현재: `config.py` `RRF_K = 60`
RRF 공식: `score += 1.0 / (k + rank)`

k 변경의 효과:

| rank | k=60 | k=30 | 차이 |
|---|---|---|---|
| 1 | 1/61 = 0.016 | 1/31 = 0.032 | +100% |
| 5 | 1/65 = 0.015 | 1/35 = 0.029 | +85% |
| 10 | 1/70 = 0.014 | 1/40 = 0.025 | +75% |
| 20 | 1/80 = 0.013 | 1/50 = 0.020 | +60% |

k=30 → 상위 랭크를 더 강하게 가중. 정밀도 vs 재현율 트레이드오프 없이 상위 결과 집중.

원 논문(Cormack, Clarke, Butt): k=60은 "파일럿 고정값". 수학적 최적값은 데이터 의존적.

---

## 구현: 1줄 변경

```python
# config.py
RRF_K = 30  # 기존: 60
```

---

## 골드셋 구축

### 방법

```sql
-- 현재 tier=0 (L3+) 고품질 노드를 기준으로
SELECT id, content, type, layer
FROM nodes
WHERE tier = 0
ORDER BY quality_score DESC
LIMIT 50;
```

→ 이 50개 노드에 대해:
1. 각 노드 content에서 핵심 키워드 추출
2. 자연어 쿼리 1-2개 작성 (Paul이 실제 쓸 법한 표현)
3. 정답: 해당 노드가 top-5에 포함되어야 함

### 예시

```python
GOLD_SET = [
    {
        "query": "컨텍스트를 화폐처럼 관리하는 방법",
        "expected_node_id": 1234,  # [Principle] LLM 컨텍스트 토큰 비용 최적화
        "expected_rank": "top-3",
    },
    {
        "query": "오케스트레이션 시스템 파일 구조",
        "expected_node_id": 5678,  # [Pattern] Flat Root + 계층적 메타데이터
        "expected_rank": "top-1",
    },
    # ... 20-50개
]
```

---

## 측정 지표

```python
import numpy as np

def ndcg_at_k(results: list[dict], relevant_id: int, k=5) -> float:
    """NDCG@k — 순위 가중 정밀도"""
    dcg = 0.0
    for i, r in enumerate(results[:k]):
        if r["id"] == relevant_id:
            dcg = 1.0 / np.log2(i + 2)  # rank i+1
            break
    idcg = 1.0  # 완벽한 경우: rank 1에 정답
    return dcg / idcg

def mrr(results: list[dict], relevant_id: int) -> float:
    """Mean Reciprocal Rank"""
    for i, r in enumerate(results):
        if r["id"] == relevant_id:
            return 1.0 / (i + 1)
    return 0.0

def precision_at_k(results: list[dict], relevant_id: int, k=5) -> float:
    """P@k"""
    hits = sum(1 for r in results[:k] if r["id"] == relevant_id)
    return hits / k
```

---

## A/B 실험 프레임워크

```python
def run_ab_test(gold_set, k_values=[30, 60]):
    results = {}
    for k in k_values:
        # config 임시 변경
        import config
        original_k = config.RRF_K
        config.RRF_K = k

        ndcg_scores, mrr_scores = [], []
        for item in gold_set:
            search_results = hybrid_search(item["query"], top_k=10)
            ndcg_scores.append(ndcg_at_k(search_results, item["expected_node_id"]))
            mrr_scores.append(mrr(search_results, item["expected_node_id"]))

        results[k] = {
            "NDCG@5": np.mean(ndcg_scores),
            "MRR": np.mean(mrr_scores),
        }
        config.RRF_K = original_k  # 복원

    return results
```

---

## 예상 결과

k=30이 유리한 경우: Principle/Value 같은 고품질 노드가 상위에 집중되어 있을 때.
k=60이 유리한 경우: 관련 노드가 여러 랭킹에 분산되어 있을 때.

**현재 tier/enrichment 보너스 시스템과 함께 작동하므로 k=30 유리 가능성 높음.**
