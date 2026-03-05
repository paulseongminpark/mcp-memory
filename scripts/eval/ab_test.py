#!/usr/bin/env python3
"""scripts/eval/ab_test.py — goldset NDCG A/B test (RRF k=30 vs k=60).

Design: c-r3-10
Usage:
  python scripts/eval/ab_test.py              # k=30 vs k=60 comparison
  python scripts/eval/ab_test.py --k 30 60 90 # custom k values
  python scripts/eval/ab_test.py --top-k 10   # top_k for recall (default 10)

Output: markdown table with NDCG@5, NDCG@10 per query and averages.
Target: baseline NDCG > 0.7
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def load_goldset(path: Path | None = None) -> list[dict]:
    """goldset.yaml 로드."""
    if path is None:
        path = ROOT / "scripts" / "eval" / "goldset.yaml"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["queries"]


def ndcg_at_k(result_ids: list[int], relevant: set[int],
              also_relevant: set[int], k: int) -> float:
    """NDCG@k 계산.

    Args:
        result_ids: recall 결과 node_id 목록 (순위순)
        relevant: 정답 ID 집합 (가중치 1.0)
        also_relevant: 부분 정답 ID 집합 (가중치 0.5)
        k: 평가 깊이
    """
    # Relevance score for each result
    def rel_score(nid: int) -> float:
        if nid in relevant:
            return 1.0
        if nid in also_relevant:
            return 0.5
        return 0.0

    # DCG@k
    dcg = 0.0
    for i, nid in enumerate(result_ids[:k]):
        r = rel_score(nid)
        dcg += r / math.log2(i + 2)  # i+2 because log2(1) = 0

    # Ideal DCG@k
    all_scores = sorted(
        [1.0] * len(relevant) + [0.5] * len(also_relevant),
        reverse=True,
    )
    idcg = 0.0
    for i, r in enumerate(all_scores[:k]):
        idcg += r / math.log2(i + 2)

    if idcg == 0:
        return 0.0
    return dcg / idcg


def run_recall_with_rrf_k(query: str, rrf_k: int, top_k: int) -> list[int]:
    """RRF_K를 변경하고 hybrid_search 실행 -> node_id 리스트 반환."""
    import storage.hybrid as hybrid_mod

    original_k = hybrid_mod.RRF_K
    hybrid_mod.RRF_K = rrf_k
    try:
        results = hybrid_mod.hybrid_search(query, top_k=top_k)
        return [r["id"] for r in results]
    finally:
        hybrid_mod.RRF_K = original_k


def run_ab_test(
    k_values: list[int],
    top_k: int = 10,
    goldset_path: Path | None = None,
) -> dict:
    """A/B 테스트 실행.

    Returns:
        {
            "k_values": [30, 60],
            "results": {
                30: [{"id": "q001", "ndcg5": 0.8, "ndcg10": 0.7, ...}, ...],
                60: [...],
            },
            "averages": {
                30: {"ndcg5": 0.75, "ndcg10": 0.72},
                60: {"ndcg5": 0.80, "ndcg10": 0.78},
            },
        }
    """
    queries = load_goldset(goldset_path)
    results: dict[int, list[dict]] = {}
    averages: dict[int, dict] = {}

    for k_val in k_values:
        print(f"\n--- RRF_K={k_val} ---")
        qresults = []

        for q in queries:
            qid = q["id"]
            query_text = q["query"]
            relevant = set(q.get("relevant_ids", []))
            also_relevant = set(q.get("also_relevant", []))

            result_ids = run_recall_with_rrf_k(query_text, k_val, top_k)
            n5 = ndcg_at_k(result_ids, relevant, also_relevant, 5)
            n10 = ndcg_at_k(result_ids, relevant, also_relevant, 10)

            # Check if primary relevant IDs are in results
            hits = relevant & set(result_ids[:top_k])
            hit_rate = len(hits) / len(relevant) if relevant else 0

            qresults.append({
                "id": qid,
                "difficulty": q.get("difficulty", ""),
                "ndcg5": round(n5, 4),
                "ndcg10": round(n10, 4),
                "hit_rate": round(hit_rate, 4),
                "result_count": len(result_ids),
            })

            print(f"  {qid} [{q.get('difficulty', '?'):6s}] "
                  f"NDCG@5={n5:.3f} NDCG@10={n10:.3f} hits={len(hits)}/{len(relevant)}")

        results[k_val] = qresults

        n5_avg = sum(r["ndcg5"] for r in qresults) / len(qresults)
        n10_avg = sum(r["ndcg10"] for r in qresults) / len(qresults)
        hit_avg = sum(r["hit_rate"] for r in qresults) / len(qresults)
        averages[k_val] = {
            "ndcg5": round(n5_avg, 4),
            "ndcg10": round(n10_avg, 4),
            "hit_rate": round(hit_avg, 4),
        }

    return {
        "k_values": k_values,
        "results": results,
        "averages": averages,
    }


def print_markdown(data: dict) -> None:
    """결과를 markdown 테이블로 출력."""
    k_values = data["k_values"]

    # Summary table
    print("\n## Summary")
    header = "| Metric |"
    sep = "|--------|"
    for kv in k_values:
        header += f" k={kv} |"
        sep += "------|"
    print(header)
    print(sep)

    for metric in ["ndcg5", "ndcg10", "hit_rate"]:
        row = f"| {metric} |"
        for kv in k_values:
            val = data["averages"][kv][metric]
            row += f" {val:.4f} |"
        print(row)

    # Target check
    print("\n## Target Check (NDCG > 0.7)")
    for kv in k_values:
        n5 = data["averages"][kv]["ndcg5"]
        n10 = data["averages"][kv]["ndcg10"]
        status5 = "PASS" if n5 > 0.7 else "FAIL"
        status10 = "PASS" if n10 > 0.7 else "FAIL"
        print(f"- k={kv}: NDCG@5={n5:.4f} [{status5}], NDCG@10={n10:.4f} [{status10}]")

    # Detail table (first k value)
    print("\n## Detail (per query)")
    print("| Query | Diff | " + " | ".join(
        f"NDCG@5(k={kv})" for kv in k_values
    ) + " | " + " | ".join(
        f"NDCG@10(k={kv})" for kv in k_values
    ) + " |")
    print("|-------|------|" + "------|" * (len(k_values) * 2))

    # Align by query
    for i, q in enumerate(data["results"][k_values[0]]):
        qid = q["id"]
        diff = q["difficulty"]
        row = f"| {qid} | {diff:6s} |"
        for kv in k_values:
            row += f" {data['results'][kv][i]['ndcg5']:.3f} |"
        for kv in k_values:
            row += f" {data['results'][kv][i]['ndcg10']:.3f} |"
        print(row)

    # Difficulty breakdown
    print("\n## By Difficulty")
    for diff in ["easy", "medium", "hard"]:
        row = f"| {diff:6s} |"
        for kv in k_values:
            subset = [r for r in data["results"][kv] if r["difficulty"] == diff]
            if subset:
                avg5 = sum(r["ndcg5"] for r in subset) / len(subset)
                avg10 = sum(r["ndcg10"] for r in subset) / len(subset)
                row += f" {avg5:.3f}/{avg10:.3f} |"
            else:
                row += " n/a |"
        print(row)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Goldset NDCG A/B test")
    parser.add_argument(
        "--k", type=int, nargs="+", default=[30, 60],
        metavar="RRF_K", help="RRF_K values to compare (default: 30 60)",
    )
    parser.add_argument(
        "--top-k", type=int, default=10,
        help="top_k for recall (default: 10)",
    )
    parser.add_argument(
        "--goldset", type=str, default=None,
        help="goldset.yaml path (default: scripts/eval/goldset.yaml)",
    )
    args = parser.parse_args()

    goldset_path = Path(args.goldset) if args.goldset else None
    data = run_ab_test(args.k, top_k=args.top_k, goldset_path=goldset_path)
    print_markdown(data)
