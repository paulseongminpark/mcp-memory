#!/usr/bin/env python3
"""NDCG@K 측정 — goldset_corrected.yaml 기반.

Usage:
  python ndcg.py                # 기본 K=5,10
  python ndcg.py --k 5          # K=5만
  python ndcg.py --verbose      # 쿼리별 상세
"""
import math
import os
import sys
import yaml

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

# .env 로드 (OPENAI_API_KEY 필요)
env_file = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

from tools.recall import recall

GOLDSET_V4 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goldset_v4.yaml")
GOLDSET_LEGACY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goldset_corrected.yaml")
GOLDSET = GOLDSET_V4 if os.path.exists(GOLDSET_V4) else GOLDSET_LEGACY


def load_goldset() -> list[dict]:
    with open(GOLDSET, "r", encoding="utf-8") as f:
        return yaml.safe_load(f).get("queries", [])


def dcg(relevances: list[float], k: int) -> float:
    """Discounted Cumulative Gain."""
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances[:k]))


def ndcg_at_k(relevant_ids: list[int], also_relevant: list[int],
              retrieved_ids: list[int], k: int) -> float:
    """NDCG@K 계산. relevant=1.0, also_relevant=0.5."""
    rel_set = set(relevant_ids)
    also_set = set(also_relevant or [])

    # 실제 relevance 점수
    actual = []
    for rid in retrieved_ids[:k]:
        if rid in rel_set:
            actual.append(1.0)
        elif rid in also_set:
            actual.append(0.5)
        else:
            actual.append(0.0)

    # 이상적 relevance (내림차순)
    ideal = sorted(
        [1.0] * len(relevant_ids) + [0.5] * len(also_relevant or []),
        reverse=True,
    )

    actual_dcg = dcg(actual, k)
    ideal_dcg = dcg(ideal, k)

    return actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0


def run_eval(k_values: list[int] = None, verbose: bool = False) -> dict:
    """전체 goldset에 대해 NDCG 측정."""
    if k_values is None:
        k_values = [5, 10]

    queries = load_goldset()
    results = {f"ndcg@{k}": [] for k in k_values}
    hit_count = 0

    for q in queries:
        qid = q["id"]
        query_text = q["query"]
        relevant = q.get("relevant_ids", [])
        also = q.get("also_relevant", [])

        # recall 실행 (v4: mode-aware)
        query_mode = q.get("mode", "generic")
        try:
            recall_result = recall(query=query_text, top_k=max(k_values), mode=query_mode)
            retrieved_ids = [n["id"] for n in recall_result.get("results", [])]
        except Exception as e:
            if verbose:
                print(f"  {qid}: ERROR — {e}")
            retrieved_ids = []

        # hit rate
        all_relevant = set(relevant) | set(also or [])
        if any(rid in all_relevant for rid in retrieved_ids[:max(k_values)]):
            hit_count += 1

        for k in k_values:
            score = ndcg_at_k(relevant, also, retrieved_ids, k)
            results[f"ndcg@{k}"].append(score)

            if verbose:
                print(f"  {qid}: ndcg@{k}={score:.3f} | retrieved={retrieved_ids[:k]}")

    # 평균
    summary = {}
    for key, scores in results.items():
        summary[key] = round(sum(scores) / len(scores), 3) if scores else 0
    summary["hit_rate"] = round(hit_count / len(queries), 3) if queries else 0
    summary["queries"] = len(queries)

    return summary


def main():
    verbose = "--verbose" in sys.argv
    k_values = [5, 10]
    if "--k" in sys.argv:
        idx = sys.argv.index("--k")
        k_values = [int(sys.argv[idx + 1])]

    print(f"NDCG 측정 (goldset: {GOLDSET})")
    print(f"K values: {k_values}\n")

    summary = run_eval(k_values=k_values, verbose=verbose)

    print(f"\n=== Results ===")
    for key, val in summary.items():
        print(f"  {key}: {val}")


if __name__ == "__main__":
    main()
