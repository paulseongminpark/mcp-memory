#!/usr/bin/env python3
"""
codex_review.py -- Codex CLI 기반 코드/프롬프트/온톨로지 검증

4개 리뷰 대상:
  1. 프롬프트 품질 (scripts/enrich/prompts/)
  2. 파이프라인 코드 (scripts/daily_enrich.py)
  3. 온톨로지 일관성 (ontology/schema.yaml)
  4. enrichment 모듈 의존성 (scripts/enrich/)

Usage:
  python scripts/codex_review.py
  python scripts/codex_review.py --dry-run
  python scripts/codex_review.py --target pipeline
  python scripts/codex_review.py --model o3
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config

REPORT_DIR = config.REPORT_DIR

REVIEWS = [
    {
        "name": "prompts",
        "label": "프롬프트 품질",
        "target": "scripts/enrich/prompts/",
        "prompt": (
            "Analyze every prompt template YAML file in scripts/enrich/prompts/. "
            "For each file evaluate: "
            "1) Clarity of instructions for the LLM "
            "2) Edge cases not covered "
            "3) Ambiguous directives that could produce inconsistent outputs "
            "4) Token efficiency - are prompts unnecessarily verbose? "
            "5) Concrete improvements with before/after examples. "
            "Output a structured markdown report."
        ),
    },
    {
        "name": "pipeline",
        "label": "파이프라인 코드",
        "target": "scripts/daily_enrich.py",
        "prompt": (
            "Review scripts/daily_enrich.py for: "
            "1) Token waste - unnecessary API calls or redundant processing "
            "2) Error handling gaps - unhandled exceptions, missing rollback "
            "3) Batch optimization - could batches be larger/smaller? "
            "4) Phase ordering - are dependencies between phases correct? "
            "5) Budget management - is the 80% phase limit optimal? "
            "Also review scripts/enrich/token_counter.py for budget tracking correctness. "
            "Output a structured markdown report with severity ratings."
        ),
    },
    {
        "name": "ontology",
        "label": "온톨로지 일관성",
        "target": "ontology/schema.yaml",
        "prompt": (
            "Review ontology/schema.yaml and cross-reference with config.py RELATION_TYPES. "
            "Check: "
            "1) Type boundary ambiguity - are any node types too similar? "
            "2) Missing relation types - common relationships not covered? "
            "3) Logical contradictions in inverse definitions "
            "4) Schema completeness - are required_fields actually useful? "
            "5) Consistency between schema.yaml relation_types and config.py RELATION_TYPES list. "
            "Also check scripts/migrate_v2.py TYPE_TO_LAYER mapping for completeness. "
            "Output a structured markdown report."
        ),
    },
    {
        "name": "modules",
        "label": "enrichment 모듈 의존성",
        "target": "scripts/enrich/",
        "prompt": (
            "Analyze all Python files in scripts/enrich/ for: "
            "1) Module dependency issues - circular imports, tight coupling "
            "2) Error propagation - does a failure in one module corrupt shared state? "
            "3) Data integrity - are SQL transactions used correctly? "
            "4) Shared state - are there race conditions or stale data issues? "
            "5) API contract consistency - do modules assume compatible schemas? "
            "Cross-reference with scripts/daily_enrich.py to verify orchestration is correct. "
            "Output a structured markdown report with file:line references."
        ),
    },
]


def check_target_exists(review: dict) -> tuple[bool, str]:
    """리뷰 대상이 존재하고 내용이 있는지 확인."""
    target = ROOT / review["target"]
    if not target.exists():
        return False, f"Target not found: {review['target']}"
    if target.is_dir():
        files = list(target.glob("*.py")) + list(target.glob("*.yaml")) + list(target.glob("*.yml"))
        if not files:
            return False, f"Target directory empty: {review['target']}"
    return True, "ok"


def run_codex_review(review: dict, model: str, timeout: int) -> dict:
    """단일 리뷰 실행."""
    result = {
        "name": review["name"],
        "label": review["label"],
        "target": review["target"],
        "status": "pending",
        "output": "",
        "duration": 0,
        "error": None,
    }

    exists, msg = check_target_exists(review)
    if not exists:
        result["status"] = "skipped"
        result["error"] = msg
        return result

    output_file = REPORT_DIR / f"codex-{review['name']}-{datetime.now().strftime('%Y%m%d')}.md"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        "codex", "exec",
        "--full-auto",
        "--ephemeral",
        "-C", str(ROOT),
        "-m", model,
        "-o", str(output_file),
        review["prompt"],
    ]

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(ROOT),
            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
        )
        duration = time.monotonic() - start
        result["duration"] = round(duration, 1)

        if proc.returncode == 0:
            result["status"] = "completed"
            if output_file.exists():
                result["output"] = output_file.read_text(encoding="utf-8")
            else:
                result["output"] = proc.stdout or "(no output captured)"
        else:
            result["status"] = "error"
            result["error"] = proc.stderr[:500] if proc.stderr else f"exit code {proc.returncode}"
            result["output"] = proc.stdout or ""

    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
        result["error"] = f"Exceeded {timeout}s timeout"
        result["duration"] = timeout
    except FileNotFoundError:
        result["status"] = "error"
        result["error"] = "codex CLI not found in PATH"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:500]

    return result


def generate_report(results: list[dict]) -> Path:
    """종합 리뷰 리포트 생성."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = REPORT_DIR / f"codex-review-{today}.md"

    lines = [
        f"# Codex Review Report {today}",
        "",
        "## Summary",
        "",
        "| Review | Status | Duration |",
        "|--------|--------|----------|",
    ]

    for r in results:
        status_icon = {
            "completed": "OK", "skipped": "SKIP",
            "error": "ERR", "timeout": "TIMEOUT",
        }.get(r["status"], r["status"])
        lines.append(f"| {r['label']} | {status_icon} | {r['duration']}s |")

    lines.append("")

    for r in results:
        lines.append(f"## {r['label']}")
        lines.append(f"Target: `{r['target']}`")
        lines.append(f"Status: {r['status']}")
        lines.append("")

        if r["error"]:
            lines.append(f"**Error:** {r['error']}")
            lines.append("")

        if r["output"]:
            lines.append(r["output"])
            lines.append("")

        lines.append("---")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser(description="Codex CLI code review")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would be reviewed without calling Codex")
    ap.add_argument("--target", choices=["prompts", "pipeline", "ontology", "modules"],
                    help="Run specific review only")
    ap.add_argument("--model", default="o3-mini",
                    help="Codex model (default: o3-mini)")
    ap.add_argument("--timeout", type=int, default=300,
                    help="Per-review timeout in seconds (default: 300)")
    args = ap.parse_args()

    reviews = REVIEWS
    if args.target:
        reviews = [r for r in REVIEWS if r["name"] == args.target]

    print("=" * 50)
    print("Codex Review Pipeline")
    print(f"model={args.model}  targets={len(reviews)}  dry_run={args.dry_run}")
    print("=" * 50)

    results = []
    for review in reviews:
        exists, msg = check_target_exists(review)
        status = "ready" if exists else f"skip ({msg})"
        print(f"\n--- {review['label']} ---")
        print(f"  target: {review['target']}")
        print(f"  status: {status}")

        if args.dry_run:
            results.append({
                "name": review["name"],
                "label": review["label"],
                "target": review["target"],
                "status": "dry_run",
                "output": "",
                "duration": 0,
                "error": None,
            })
            continue

        if not exists:
            results.append({
                "name": review["name"],
                "label": review["label"],
                "target": review["target"],
                "status": "skipped",
                "output": "",
                "duration": 0,
                "error": msg,
            })
            continue

        print("  running codex...")
        result = run_codex_review(review, args.model, args.timeout)
        results.append(result)
        print(f"  result: {result['status']} ({result['duration']}s)")

    report_path = generate_report(results)
    print(f"\nReport: {report_path}")
    print("Done.")


if __name__ == "__main__":
    main()
