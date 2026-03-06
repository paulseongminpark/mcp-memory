# 세션 C — PyTorch #8: Missing Link Detector

> 2026-03-05 | Q7 심화 — ChromaDB 추출 + sklearn 구현 + top-20 출력

---

## 성능 예측 (6K edges)

| 항목 | 수치 | 분석 |
|---|---|---|
| Train edges | 4,816 | positive samples |
| Negative ratio | 1:5 | train 24,080 negatives |
| Feature dim | 9,216 | `[h; t; h⊙t]` |
| 예상 AUC-ROC | 0.72–0.82 | OpenAI embeddings 품질 덕분 |
| Precision@20 (missing) | 0.30–0.50 | ground truth 없어 낮음 |
| 훈련 시간 | < 30초 | sklearn LogisticRegression |

**핵심 제약**: ground truth missing edge가 없음 → Precision@20은 추정치.
대신 "연결 확률 상위 20쌍"을 Paul이 수동 검토하는 방식으로 운영.

---

## ChromaDB 임베딩 추출

```python
# scripts/link_detector/extract_embeddings.py

import numpy as np
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from storage.vector_store import _get_collection


def extract_all_embeddings() -> tuple[dict[int, np.ndarray], list[int]]:
    """ChromaDB에서 전체 노드 임베딩 추출.

    Returns:
        embeddings: {node_id: 3072-dim np.array}
        all_ids: node_id 목록
    """
    coll = _get_collection()
    total = coll.count()
    if total == 0:
        return {}, []

    # ChromaDB는 batch get 지원 — 전체 한 번에 추출
    result = coll.get(
        include=["embeddings", "metadatas"],
        limit=total,   # 전체
    )

    embeddings = {}
    for id_str, emb in zip(result["ids"], result["embeddings"]):
        node_id = int(id_str)
        embeddings[node_id] = np.array(emb, dtype=np.float32)

    return embeddings, list(embeddings.keys())


def get_existing_edges(db_path: str = "data/memory.db") -> set[tuple[int, int]]:
    """기존 edges를 (source_id, target_id) set으로 반환."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT source_id, target_id FROM edges").fetchall()
    conn.close()
    edge_set = set()
    for s, t in rows:
        edge_set.add((s, t))
        edge_set.add((t, s))  # 무방향 처리
    return edge_set
```

---

## 학습 + 예측 스크립트

```python
# scripts/link_detector/train_predict.py

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
import sqlite3, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.link_detector.extract_embeddings import extract_all_embeddings, get_existing_edges


def make_features(h_id: int, t_id: int, embs: dict) -> np.ndarray | None:
    """[h; t; h⊙t] 9216-dim feature vector."""
    if h_id not in embs or t_id not in embs:
        return None
    h, t = embs[h_id], embs[t_id]
    return np.concatenate([h, t, h * t])


def build_dataset(embs: dict, existing_edges: set, neg_ratio: int = 5):
    """Positive = 기존 edges, Negative = 무작위 쌍."""
    all_ids = list(embs.keys())
    X, y = [], []

    # Positive samples
    for (s, t) in existing_edges:
        if s > t:  # 중복 제거 (무방향)
            continue
        feat = make_features(s, t, embs)
        if feat is not None:
            X.append(feat)
            y.append(1)

    n_pos = len(X)
    n_neg = n_pos * neg_ratio

    # Negative samples (무작위 쌍 중 기존 edge 아닌 것)
    attempts = 0
    while len(y) - n_pos < n_neg and attempts < n_neg * 10:
        h, t = random.sample(all_ids, 2)
        if (h, t) not in existing_edges and (t, h) not in existing_edges:
            feat = make_features(h, t, embs)
            if feat is not None:
                X.append(feat)
                y.append(0)
        attempts += 1

    return np.array(X), np.array(y)


def find_missing_links(model, embs: dict, existing_edges: set,
                        top_k: int = 20) -> list[dict]:
    """연결 없는 노드 쌍 중 예측 확률 상위 top_k 반환."""
    all_ids = list(embs.keys())
    candidates = []

    # 샘플링: 전체 N*(N-1)/2 쌍 불가 → 무작위 100K 쌍 샘플링
    sample_size = min(100_000, len(all_ids) * (len(all_ids) - 1) // 2)
    sampled = set()
    while len(sampled) < sample_size:
        h, t = random.sample(all_ids, 2)
        pair = (min(h, t), max(h, t))
        if pair not in sampled and pair not in existing_edges:
            sampled.add(pair)

    for h, t in sampled:
        feat = make_features(h, t, embs)
        if feat is None:
            continue
        prob = model.predict_proba([feat])[0][1]
        candidates.append({"h": h, "t": t, "prob": round(float(prob), 4)})

    candidates.sort(key=lambda x: -x["prob"])
    return candidates[:top_k]


def run():
    print("Extracting embeddings...")
    embs, all_ids = extract_all_embeddings()
    existing_edges = get_existing_edges()
    print(f"Nodes with embeddings: {len(embs)}, Existing edges: {len(existing_edges)//2}")

    print("Building dataset...")
    X, y = build_dataset(embs, existing_edges, neg_ratio=5)
    print(f"Dataset: {sum(y==1)} pos, {sum(y==0)} neg")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, stratify=y)

    print("Training LogisticRegression...")
    model = LogisticRegression(C=0.1, max_iter=1000, random_state=42)
    model.fit(X_train, y_train)

    y_prob = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)
    print(f"AUC-ROC: {auc:.4f}")

    print(f"\nFinding top-20 missing links...")
    missing = find_missing_links(model, embs, existing_edges, top_k=20)
    return missing, auc


if __name__ == "__main__":
    missing, auc = run()
    print(f"\n{'='*60}")
    print(f"Top-20 Missing Link Candidates (AUC={auc:.3f})")
    print(f"{'='*60}")
    for r in missing:
        print(f"[{r['h']:4d}] ←→ [{r['t']:4d}]  prob={r['prob']:.3f}")
```

---

## top-20 출력 형식 (enrich하여 사람이 읽을 수 있게)

```python
# scripts/link_detector/enrich_output.py
import sqlite3, sys
from pathlib import Path

def enrich_missing_links(missing: list[dict], db_path="data/memory.db") -> list[dict]:
    """node_id → content/type 로 변환."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    enriched = []
    for item in missing:
        h = conn.execute("SELECT id, type, content FROM nodes WHERE id=?",
                         (item["h"],)).fetchone()
        t = conn.execute("SELECT id, type, content FROM nodes WHERE id=?",
                         (item["t"],)).fetchone()
        if h and t:
            enriched.append({
                "prob": item["prob"],
                "h": {"id": h["id"], "type": h["type"],
                       "preview": (h["content"] or "")[:60]},
                "t": {"id": t["id"], "type": t["type"],
                       "preview": (t["content"] or "")[:60]},
                "suggested_relation": "connects_with",  # 기본값, 수동 검토 필요
            })
    conn.close()
    return enriched
```

예상 출력:
```
============================================================
Top-20 Missing Link Candidates (AUC=0.76)
============================================================
prob=0.91 | [4163] Value    "뇌의 다차원적 연결을 외부화..."
          ←→ [4166] Value   "이색적 접합 — 서로 다른 도메인..."
          → 제안: reinforces_mutually (같은 Value 레이어)

prob=0.88 | [181]  Principle "Context = Currency..."
          ←→ [377]  Principle "토큰은 화폐다..."
          → 제안: supports (이미 연결됐을 수 있음 → 확인 필요)

prob=0.85 | [4165] Philosophy "의지에 의존하지 않고 환경 설계..."
          ←→ [406]  Principle "7일이면 충분하다..."
          → 제안: exemplifies (철학이 원칙으로 구현됨)
```

---

## 파일 구조

```
scripts/
└── link_detector/
    ├── extract_embeddings.py   ← ChromaDB 추출
    ├── train_predict.py        ← 학습 + top-20 탐지
    └── enrich_output.py        ← 결과 사람이 읽게 변환
```

## 실행

```bash
cd /c/dev/01_projects/06_mcp-memory
python scripts/link_detector/train_predict.py
```
