"""Missing Link Detector — OpenAI embeddings + sklearn으로 잠재 edge 탐지.

실행: python scripts/link_detector/train_predict.py [--top-k 20]
결과: 연결되어야 하지만 없는 노드 쌍 top-K 출력
"""
import sys
import sqlite3
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

import config as cfg


def get_all_embeddings() -> tuple[list[int], np.ndarray, dict]:
    """ChromaDB에서 전체 노드 임베딩 추출."""
    import chromadb

    client = chromadb.PersistentClient(path=cfg.CHROMA_PATH)
    coll = client.get_or_create_collection("memory")
    total = coll.count()
    if total == 0:
        raise RuntimeError("ChromaDB 비어있음. 먼저 임베딩 생성 필요.")

    result = coll.get(include=["embeddings", "metadatas"], limit=total)

    ids = [int(m["node_id"]) for m in result["metadatas"] if "node_id" in m]
    embs = np.array([
        result["embeddings"][i]
        for i, m in enumerate(result["metadatas"])
        if "node_id" in m
    ], dtype=np.float32)

    id_to_idx = {nid: i for i, nid in enumerate(ids)}
    return ids, embs, id_to_idx


def get_existing_edges(conn: sqlite3.Connection) -> set[tuple[int, int]]:
    cur = conn.cursor()
    cur.execute("SELECT source_id, target_id FROM edges")
    edges = set()
    for src, tgt in cur.fetchall():
        edges.add((src, tgt))
        edges.add((tgt, src))  # 무방향으로 취급
    return edges


def build_features(h_emb: np.ndarray, t_emb: np.ndarray) -> np.ndarray:
    """[h; t; h⊙t] — 9216-dim feature vector."""
    return np.concatenate([h_emb, t_emb, h_emb * t_emb])


def train_link_predictor(ids: list[int], embs: np.ndarray,
                          existing: set[tuple[int, int]], id_to_idx: dict):
    """sklearn LogisticRegression으로 link predictor 학습."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score

    # positive samples
    pos_pairs = [
        (src, tgt) for src, tgt in existing
        if src in id_to_idx and tgt in id_to_idx and src < tgt
    ]

    if len(pos_pairs) < 10:
        raise RuntimeError(f"학습 데이터 부족: {len(pos_pairs)}개 edges")

    rng = np.random.default_rng(42)
    id_arr = np.array(ids)

    # negative sampling (기존 edge 없는 랜덤 쌍)
    neg_pairs = []
    attempts = 0
    while len(neg_pairs) < len(pos_pairs) and attempts < len(pos_pairs) * 10:
        attempts += 1
        i, j = rng.choice(len(ids), 2, replace=False)
        a, b = id_arr[i], id_arr[j]
        if (a, b) not in existing and (b, a) not in existing:
            neg_pairs.append((int(a), int(b)))

    print(f"학습 데이터: positive={len(pos_pairs)}, negative={len(neg_pairs)}")

    X, y = [], []
    for src, tgt in pos_pairs:
        X.append(build_features(embs[id_to_idx[src]], embs[id_to_idx[tgt]]))
        y.append(1)
    for src, tgt in neg_pairs:
        X.append(build_features(embs[id_to_idx[src]], embs[id_to_idx[tgt]]))
        y.append(0)

    X = np.array(X, dtype=np.float32)
    y = np.array(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = LogisticRegression(max_iter=1000, C=1.0, solver="lbfgs")
    clf.fit(X_train, y_train)

    y_prob = clf.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)
    print(f"Validation AUC: {auc:.4f}")

    return clf


def predict_missing_links(clf, ids: list[int], embs: np.ndarray,
                           existing: set[tuple[int, int]], id_to_idx: dict,
                           top_k: int = 20) -> list[dict]:
    """미연결 쌍 중 score 높은 top-K 반환."""
    rng = np.random.default_rng(0)
    # 랜덤 샘플 1000쌍 평가
    candidates = []
    id_arr = np.array(ids)
    sampled = set()

    for _ in range(5000):
        i, j = rng.choice(len(ids), 2, replace=False)
        a, b = int(id_arr[i]), int(id_arr[j])
        if a > b:
            a, b = b, a
        if (a, b) in sampled:
            continue
        sampled.add((a, b))
        if (a, b) not in existing and (b, a) not in existing:
            feat = build_features(embs[id_to_idx[a]], embs[id_to_idx[b]])
            candidates.append((a, b, feat))
        if len(candidates) >= 1000:
            break

    if not candidates:
        return []

    X_cand = np.array([c[2] for c in candidates], dtype=np.float32)
    scores = clf.predict_proba(X_cand)[:, 1]

    results = sorted(
        [(candidates[i][0], candidates[i][1], float(scores[i]))
         for i in range(len(candidates))],
        key=lambda x: -x[2]
    )

    conn = sqlite3.connect(cfg.DB_PATH)
    cur = conn.cursor()

    out = []
    for src, tgt, score in results[:top_k]:
        cur.execute("SELECT type, content FROM nodes WHERE id=?", (src,))
        sr = cur.fetchone()
        cur.execute("SELECT type, content FROM nodes WHERE id=?", (tgt,))
        tr = cur.fetchone()
        if sr and tr:
            out.append({
                "src_id": src, "src_type": sr[0], "src": sr[1][:60],
                "tgt_id": tgt, "tgt_type": tr[0], "tgt": tr[1][:60],
                "score": round(score, 4),
            })
    conn.close()
    return out


def main() -> None:
    top_k = 20
    for arg in sys.argv[1:]:
        if arg.startswith("--top-k="):
            top_k = int(arg.split("=")[1])

    print("임베딩 로드 중...")
    ids, embs, id_to_idx = get_all_embeddings()
    print(f"  {len(ids)}개 노드 임베딩 로드 완료 (dim={embs.shape[1]})")

    conn = sqlite3.connect(cfg.DB_PATH)
    existing = get_existing_edges(conn)
    conn.close()
    print(f"  기존 edges: {len(existing) // 2}개 (양방향 포함 {len(existing)})")

    print("\n모델 학습 중...")
    clf = train_link_predictor(ids, embs, existing, id_to_idx)

    print(f"\nTop-{top_k} Missing Links 예측 중...")
    results = predict_missing_links(clf, ids, embs, existing, id_to_idx, top_k)

    print(f"\n{'#':<3} {'Score':>6}  {'Src(id,type)':<30} {'Tgt(id,type)':<30}")
    print("-" * 80)
    for i, r in enumerate(results, 1):
        src_info = f"[{r['src_id']}]{r['src_type']}"
        tgt_info = f"[{r['tgt_id']}]{r['tgt_type']}"
        print(f"{i:<3} {r['score']:>6.4f}  {src_info:<30} {tgt_info:<30}")
        print(f"     src: {r['src']}")
        print(f"     tgt: {r['tgt']}")

    import json
    out_path = BASE_DIR / "data" / "reports" / "missing_links.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
