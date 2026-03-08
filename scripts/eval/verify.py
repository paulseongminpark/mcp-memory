"""scripts/eval/verify.py — 모듈형 검증 시스템 러너."""
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from checks import CheckResult
from checks import (
    search_quality, schema_consistency, data_integrity,
    promotion_pipeline, recall_scenarios,
    enrichment_coverage, graph_health, type_distribution,
)
from storage.sqlite_store import _db

MODULES = [
    search_quality, schema_consistency, data_integrity,
    promotion_pipeline, recall_scenarios,
    enrichment_coverage, graph_health, type_distribution,
]


def run_all(quick=False) -> list[CheckResult]:
    """전체 검증 실행. quick=True면 search_quality 스킵 (서버 시작용)."""
    run_id = str(uuid.uuid4())[:8]
    all_results: list[CheckResult] = []
    modules = [m for m in MODULES if not (quick and m == search_quality)]
    for mod in modules:
        try:
            results = mod.run()
            all_results.extend(results)
        except Exception as e:
            all_results.append(CheckResult(
                name=mod.__name__.split(".")[-1],
                category="error",
                status="FAIL",
                details={"error": str(e)},
            ))
    # DB 저장
    _save_results(run_id, all_results)
    # 요약 출력
    _print_summary(run_id, all_results)
    return all_results


def _save_results(run_id: str, results: list[CheckResult]) -> None:
    with _db() as conn:
        for r in results:
            conn.execute(
                """INSERT INTO verification_log
                   (run_id, check_name, category, score, threshold, status, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (run_id, r.name, r.category, r.score, r.threshold,
                 r.status, json.dumps(r.details, ensure_ascii=False)),
            )
        conn.commit()


def _print_summary(run_id: str, results: list[CheckResult]) -> None:
    pass_count = sum(1 for r in results if r.status == "PASS")
    warn_count = sum(1 for r in results if r.status == "WARN")
    fail_count = sum(1 for r in results if r.status == "FAIL")
    print(f"\n{'='*60}")
    print(f"VERIFICATION {run_id}: {pass_count} PASS / {warn_count} WARN / {fail_count} FAIL")
    print(f"{'='*60}")
    for r in results:
        icon = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}.get(r.status, "??")
        score_str = f" ({r.score:.3f}/{r.threshold:.3f})" if (r.score is not None and r.threshold is not None) else ""
        print(f"  [{icon}] {r.category:12s} | {r.name}{score_str}")
    if fail_count:
        print(f"\nFAILED CHECKS:")
        for r in results:
            if r.status == "FAIL":
                print(f"  - {r.name}: {r.details}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="search_quality 스킵")
    args = parser.parse_args()
    results = run_all(quick=args.quick)
    fail_count = sum(1 for r in results if r.status == "FAIL")
    sys.exit(1 if fail_count else 0)
