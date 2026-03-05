"""A/B 테스트: RRF_K=60 vs RRF_K=30 검색 품질 비교.

실행: python scripts/eval/ab_test.py --goldset scripts/eval/goldset.yaml
결과: NDCG@5, MRR, P@5 출력
"""
import sys
import json
import math
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

import config as cfg
from storage.hybrid import hybrid_search


def load_goldset(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["queries"]


def dcg(rel_list: list[float], k: int) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rel_list[:k]))


def ndcg_at_k(retrieved_ids: list[int], relevant_ids: list[int],
               also_relevant: list[int], k: int) -> float:
    rel_map = {rid: 1.0 for rid in relevant_ids}
    rel_map.update({rid: 0.5 for rid in also_relevant})

    gains = [rel_map.get(nid, 0.0) for nid in retrieved_ids[:k]]
    ideal = sorted([rel_map.get(nid, 0.0) for nid in rel_map], reverse=True)

    dcg_val = dcg(gains, k)
    idcg_val = dcg(ideal, k)
    return dcg_val / idcg_val if idcg_val > 0 else 0.0


def mrr(retrieved_ids: list[int], relevant_ids: set[int]) -> float:
    for i, nid in enumerate(retrieved_ids):
        if nid in relevant_ids:
            return 1.0 / (i + 1)
    return 0.0


def precision_at_k(retrieved_ids: list[int], relevant_ids: set[int], k: int) -> float:
    hits = sum(1 for nid in retrieved_ids[:k] if nid in relevant_ids)
    return hits / k


def run_eval(queries: list[dict], rrf_k: int, top_k: int = 5) -> dict:
    original_k = cfg.RRF_K
    cfg.RRF_K = rrf_k

    ndcg_scores, mrr_scores, p5_scores = [], [], []

    for q in queries:
        results = hybrid_search(q["query"], top_k=top_k)
        retrieved = [r["id"] for r in results]
        relevant = set(q.get("relevant_ids", []))
        also_relevant = q.get("also_relevant", [])

        ndcg_scores.append(ndcg_at_k(retrieved, list(relevant), also_relevant, top_k))
        mrr_scores.append(mrr(retrieved, relevant))
        p5_scores.append(precision_at_k(retrieved, relevant, top_k))

    cfg.RRF_K = original_k

    n = len(queries)
    return {
        "rrf_k": rrf_k,
        "n_queries": n,
        f"NDCG@{top_k}": round(sum(ndcg_scores) / n, 4),
        "MRR": round(sum(mrr_scores) / n, 4),
        f"P@{top_k}": round(sum(p5_scores) / n, 4),
    }


def main() -> None:
    goldset_path = "scripts/eval/goldset.yaml"
    for arg in sys.argv[1:]:
        if arg.startswith("--goldset="):
            goldset_path = arg.split("=", 1)[1]
        elif not arg.startswith("--") and Path(arg).exists():
            goldset_path = arg

    if not Path(goldset_path).exists():
        print(f"ERROR: goldset not found: {goldset_path}")
        print("먼저 scripts/eval/goldset.yaml 을 Paul이 직접 라벨링해야 합니다.")
        sys.exit(1)

    queries = load_goldset(goldset_path)
    print(f"골드셋 로드: {len(queries)}개 쿼리\n")

    result_60 = run_eval(queries, rrf_k=60)
    result_30 = run_eval(queries, rrf_k=30)

    print("=== A/B 테스트 결과 ===")
    print(f"{'지표':<12} {'k=60':>8} {'k=30':>8} {'개선':>8}")
    print("-" * 42)
    for key in [f"NDCG@5", "MRR", "P@5"]:
        a = result_60.get(key, 0)
        b = result_30.get(key, 0)
        delta = b - a
        sign = "+" if delta > 0 else ""
        print(f"{key:<12} {a:>8.4f} {b:>8.4f} {sign}{delta:>7.4f}")

    winner = "k=30" if result_30["NDCG@5"] >= result_60["NDCG@5"] else "k=60"
    print(f"\n판정: {winner} 승리")

    out_path = BASE_DIR / "data" / "reports" / "ab_test_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"k60": result_60, "k30": result_30}, f, ensure_ascii=False, indent=2)
    print(f"결과 저장: {out_path}")


if __name__ == "__main__":
    main()
