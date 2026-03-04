#!/usr/bin/env python3
"""메모리 검색 CLI — 에이전트가 Bash로 호출.

Usage:
    python3 scripts/query_memory.py "검색어"
    python3 scripts/query_memory.py "검색어" --type Decision
    python3 scripts/query_memory.py "검색어" --project orchestration --top_k 3
"""

import os
import sys
import argparse

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from config import DB_PATH


def query_cli(query: str, type_filter: str = "", project: str = "", top_k: int = 5) -> str:
    if not DB_PATH.exists():
        return "DB not found"

    # FTS5 검색 (벡터 검색은 API 필요하므로 CLI에서는 FTS만)
    from storage.sqlite_store import search_fts, get_node

    results = search_fts(query, top_k=top_k * 2)

    lines = []
    count = 0
    for node_id, content, score in results:
        if count >= top_k:
            break
        node = get_node(node_id)
        if not node:
            continue
        if type_filter and node["type"] != type_filter:
            continue
        if project and node.get("project", "") != project:
            continue

        lines.append(
            f"#{node['id']} [{node['type']}] {node['content'][:80]} "
            f"(project={node.get('project', '-')}, {node['created_at'][:10]})"
        )
        count += 1

    if not lines:
        return f"'{query}' 검색 결과 없음"
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Memory search CLI")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--type", default="", help="Filter by node type")
    parser.add_argument("--project", default="", help="Filter by project")
    parser.add_argument("--top_k", type=int, default=5, help="Number of results")
    args = parser.parse_args()

    result = query_cli(args.query, type_filter=args.type, project=args.project, top_k=args.top_k)
    print(result)
