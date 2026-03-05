# 세션 C — PyTorch #1: KG Embedding & Link Prediction 가능성

> 2026-03-05 | Q1 + Q7

---

## 데이터 현황

| 항목 | 수치 | ML 관점 |
|---|---|---|
| Nodes | 3,230 | 타입당 평균 65개 → 희소 |
| Edges | 6,020 | 관계당 평균 125개 → 희소 |
| Relation types | 48 | KG embedding 난이도 상 |
| Embedding dim | 3072 | OpenAI text-embedding-3-large (기존 보유) |

KG embedding 벤치마크:
- FB15k-237: 310K triples
- WN18RR: 93K triples
- **우리: 6K → 최소 벤치마크의 1/15**

---

## Q1. PyTorch로 어떤 모델을 학습시킬 수 있나

**판정: 표준 KG embedding 불가. MLP는 가능.**

| 모델 | 판정 | 이유 |
|---|---|---|
| TransE / TransR / RotatE | ❌ 불가 | 최소 50K triples 필요 |
| R-GCN full training | ❌ 불가 | 48 relations × 평균 125 edges → 수렴 불가 |
| t-SNE / UMAP visualization | ✅ 즉시 가능 | 기존 embeddings 활용 |
| MLP link predictor (sklearn) | ✅ 가능 | OpenAI embeddings feature로 |
| PyTorch MLP | ⚠️ 가능, 제한적 | sklearn보다 이득 없음 |

**PyTorch가 의미 있으려면: 60K+ edges (현재의 10x)**

---

## Q7. Link Prediction — 어떤 모델이 적합한가

**판정: TransE/R-GCN 불가. sklearn MLP with OpenAI embeddings 가능.**

```python
from sklearn.linear_model import LogisticRegression
import numpy as np

def get_link_features(h_id, t_id, embeddings):
    h_emb = embeddings[h_id]  # 3072-dim
    t_emb = embeddings[t_id]  # 3072-dim
    return np.concatenate([h_emb, t_emb, h_emb * t_emb])  # 9216-dim

# 학습: 기존 edges = positive, random pairs = negative
# train 4,816 / val 601 / test 603
```

**실제 가치**: missing edge 탐지 — "연결되어야 하는데 안 된 개념 쌍" top-20 제안.

---

## 결론

PyTorch 대규모 KG 학습은 데이터 부족으로 불가.
가장 빠른 실험: `sklearn.LogisticRegression` + 기존 ChromaDB embeddings.
