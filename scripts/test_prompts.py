#!/usr/bin/env python3
"""
test_prompts.py -- 50개 표본 프롬프트 dry-run 테스트

타입별 균등 + 고난이도 표본을 선정하고
YAML 프롬프트의 변수 치환 결과를 출력.

Usage:
  python scripts/test_prompts.py                # dry-run 출력
  python scripts/test_prompts.py --live         # 실제 API 호출
  python scripts/test_prompts.py --task E1      # 특정 task만
  python scripts/test_prompts.py --count 10     # 표본 수 조절
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from scripts.enrich.prompt_loader import PromptLoader
from scripts.enrich.token_counter import TokenBudget

REPORT_DIR = config.REPORT_DIR


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def select_samples(conn: sqlite3.Connection, count: int = 50) -> list[dict]:
    """타입별 균등 + 고난이도 표본 선정."""
    # 타입별 분포 조회
    type_rows = conn.execute(
        "SELECT type, COUNT(*) as cnt FROM nodes WHERE status='active' "
        "GROUP BY type ORDER BY cnt DESC"
    ).fetchall()

    types = [(r["type"], r["cnt"]) for r in type_rows]
    total_types = len(types)
    per_type = max(1, count // total_types)
    remaining = count - (per_type * total_types)

    samples = []
    seen_ids = set()

    for node_type, _ in types:
        # 각 타입에서 per_type개 + 고난이도 우선
        rows = conn.execute(
            """SELECT * FROM nodes
               WHERE type = ? AND status = 'active'
               ORDER BY
                 CASE WHEN content IS NULL OR content = '' THEN 1 ELSE 0 END,
                 LENGTH(content) DESC
               LIMIT ?""",
            (node_type, per_type + 2),
        ).fetchall()

        for r in rows:
            if len(samples) >= count:
                break
            node = dict(r)
            if node["id"] not in seen_ids:
                samples.append(node)
                seen_ids.add(node["id"])

    # 부족하면 랜덤으로 채움
    if len(samples) < count:
        extra = conn.execute(
            f"SELECT * FROM nodes WHERE status='active' AND id NOT IN "
            f"({','.join('?' * len(seen_ids))}) ORDER BY RANDOM() LIMIT ?",
            list(seen_ids) + [count - len(samples)],
        ).fetchall()
        for r in extra:
            samples.append(dict(r))

    return samples[:count]


def trunc(text: str, max_chars: int = 3000) -> str:
    if not text or len(text) <= max_chars:
        return text or ""
    return text[:max_chars] + "...[truncated]"


def render_node_prompts(pl: PromptLoader, node: dict, tasks: list[str]) -> list[dict]:
    """노드용 프롬프트 렌더링 (E1-E12)."""
    results = []
    content = trunc(node.get("content", ""))

    task_kwargs = {
        "E1": {"content": content},
        "E2": {"content": content},
        "E3": {"existing_tags": node.get("tags", ""), "content": content},
        "E4": {"facets_allowlist": config.FACETS_ALLOWLIST, "content": content},
        "E5": {
            "domains_allowlist": config.DOMAINS_ALLOWLIST,
            "project": node.get("project", ""),
            "source": node.get("source", ""),
            "content": content,
        },
        "E6": {"primary_type": node.get("type", "Unclassified"), "content": content},
        "E7": {
            "summary": node.get("summary", ""),
            "key_concepts": node.get("key_concepts", ""),
            "tags": node.get("tags", ""),
            "facets": node.get("facets", ""),
            "domains": node.get("domains", ""),
        },
        "E8": {"node_type": node.get("type"), "content": content},
        "E9": {"layer": node.get("layer"), "content": content},
        "E10": {
            "today": datetime.now().strftime("%Y-%m-%d"),
            "created_at": node.get("created_at", "?"),
            "content": content,
        },
        "E11": {"node_type": node.get("type"), "content": content},
        "E12": {
            "layer": node.get("layer"),
            "node_type": node.get("type"),
            "content": content,
        },
    }

    for tid in tasks:
        if tid not in task_kwargs:
            continue
        try:
            system, user = pl.render(tid, **task_kwargs[tid])
            results.append({
                "task": tid,
                "node_id": node["id"],
                "node_type": node.get("type"),
                "system": system,
                "user": user,
                "est_tokens": (len(system) + len(user)) // 3 + 500,
            })
        except Exception as e:
            results.append({
                "task": tid,
                "node_id": node["id"],
                "error": str(e),
            })

    return results


def main():
    ap = argparse.ArgumentParser(description="Prompt dry-run test")
    ap.add_argument("--live", action="store_true", help="Call OpenAI API")
    ap.add_argument("--task", help="Specific task (e.g. E1, E13)")
    ap.add_argument("--count", type=int, default=50, help="Sample count")
    ap.add_argument("--output", help="Save to file instead of stdout")
    args = ap.parse_args()

    pl = PromptLoader()
    conn = connect_db()

    node_tasks = [f"E{i}" for i in range(1, 13)]
    if args.task:
        node_tasks = [t for t in node_tasks if t == args.task]

    # 1. 표본 선정
    samples = select_samples(conn, count=args.count)
    type_dist = defaultdict(int)
    for s in samples:
        type_dist[s.get("type", "?")] += 1

    print(f"Selected {len(samples)} samples from {len(type_dist)} types")
    print(f"Distribution: {dict(type_dist)}")
    print()

    # 2. 프롬프트 렌더링
    all_results = []
    total_tokens = 0

    for node in samples:
        prompts = render_node_prompts(pl, node, node_tasks)
        for p in prompts:
            est = p.get("est_tokens", 0)
            total_tokens += est

            if not args.output:
                print(f"--- {p['task']} | node #{p.get('node_id')} "
                      f"({p.get('node_type')}) | ~{est} tokens ---")
                print(f"SYSTEM: {p.get('system', '')[:200]}")
                print(f"USER: {p.get('user', '')[:200]}")
                if p.get("error"):
                    print(f"ERROR: {p['error']}")
                print()

        all_results.extend(prompts)

    # 3. 요약
    errors = [r for r in all_results if "error" in r]
    print("=" * 50)
    print(f"Total prompts rendered: {len(all_results)}")
    print(f"Errors: {len(errors)}")
    print(f"Estimated total tokens: {total_tokens:,}")
    print(f"Tasks tested: {sorted(set(r['task'] for r in all_results))}")

    if args.live:
        print("\n--live mode: API calls not yet implemented")
        print("Run daily_enrich.py --dry-run for full pipeline test")

    # 4. 파일 출력
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            json.dumps(all_results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Saved to {args.output}")

    conn.close()


if __name__ == "__main__":
    main()
