"""checks/search_quality.py — NDCG@5, NDCG@10, hit_rate 검증."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from checks import CheckResult
from config import VERIFY_THRESHOLDS


def run() -> list[CheckResult]:
    """goldset.yaml 로드 → hybrid_search 실행 → NDCG 계산."""
    from scripts.eval.ab_test import load_goldset, ndcg_at_k
    from storage.hybrid import hybrid_search

    goldset = load_goldset()
    k_vals = [5, 10]
    ndcg_sums = {k: 0.0 for k in k_vals}
    hit_total = 0
    zero_queries = []

    for q in goldset:
        query = q["query"]
        relevant = set(q.get("relevant_ids", []))
        also_relevant = set(q.get("also_relevant_ids", []))

        results = hybrid_search(query, top_k=10)
        result_ids = [r["id"] for r in results]

        for k in k_vals:
            ndcg = ndcg_at_k(result_ids, relevant, also_relevant, k)
            ndcg_sums[k] += ndcg

        # hit_rate: top-10 안에 relevant 1개+
        hits = set(result_ids[:10]) & relevant
        if hits:
            hit_total += 1

        if not (set(result_ids[:5]) & (relevant | also_relevant)):
            zero_queries.append(query)

    n = len(goldset) or 1
    ndcg5 = ndcg_sums[5] / n
    ndcg10 = ndcg_sums[10] / n
    hit_rate = hit_total / n

    results_out = [
        CheckResult(
            name="ndcg@5",
            category="search",
            score=ndcg5,
            threshold=VERIFY_THRESHOLDS["ndcg@5"],
            details={"zero_queries": zero_queries},
        ),
        CheckResult(
            name="ndcg@10",
            category="search",
            score=ndcg10,
            threshold=VERIFY_THRESHOLDS["ndcg@10"],
        ),
        CheckResult(
            name="hit_rate",
            category="search",
            score=hit_rate,
            threshold=VERIFY_THRESHOLDS["hit_rate"],
        ),
    ]
    return results_out
