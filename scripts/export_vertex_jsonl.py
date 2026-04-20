#!/usr/bin/env python3
"""
mcp-memory nodes → Vertex AI Search JSONL export

Output format: Vertex AI Search structured data store document format
  {"id": "node_<id>", "structData": {...}}

Usage:
  python scripts/export_vertex_jsonl.py
  python scripts/export_vertex_jsonl.py --output /path/to/output.jsonl
  python scripts/export_vertex_jsonl.py --status active --min-quality 0.5
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "memory.db"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "09_vertex-genai-ideation_0420" / "output" / "nodes_export.jsonl"

SKIP_FIELDS = {"embedding"}  # binary blob — skip


def parse_json_field(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def export_nodes(db_path: Path, output_path: Path, status_filter=None, min_quality=None):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    conditions = ["status != 'deleted'"]
    params = []

    if status_filter:
        conditions.append("status = ?")
        params.append(status_filter)

    if min_quality is not None:
        conditions.append("quality_score >= ?")
        params.append(min_quality)

    where = " AND ".join(conditions)
    query = f"SELECT * FROM nodes WHERE {where} ORDER BY id"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    exported = 0
    skipped = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows:
            node_id = f"node_{row['id']}"
            struct = {}

            for key in row.keys():
                if key in SKIP_FIELDS:
                    continue
                val = row[key]
                if val is None:
                    continue

                # JSON 필드 파싱
                if key in ("metadata", "tags", "key_concepts", "facets", "domains",
                           "secondary_types", "activity_history", "score_history",
                           "retrieval_hints", "retrieval_queries", "atomic_claims"):
                    parsed = parse_json_field(val)
                    if parsed is not None:
                        # Vertex AI structData는 nested object/array 허용
                        struct[key] = parsed
                elif key == "id":
                    struct["node_id"] = int(val)
                else:
                    struct[key] = val

            # Vertex AI Search 필수: content 필드 (전문 검색용 텍스트)
            text_parts = []
            if row["content"]:
                text_parts.append(row["content"])
            if row["summary"]:
                text_parts.append(f"[summary] {row['summary']}")
            if row["key_concepts"]:
                kc = parse_json_field(row["key_concepts"])
                if isinstance(kc, list):
                    text_parts.append(f"[concepts] {', '.join(str(k) for k in kc)}")

            struct["search_text"] = " | ".join(text_parts) if text_parts else ""

            doc = {"id": node_id, "structData": struct}

            try:
                line = json.dumps(doc, ensure_ascii=False)
                f.write(line + "\n")
                exported += 1
            except (TypeError, ValueError) as e:
                print(f"  SKIP node_{row['id']}: {e}", file=sys.stderr)
                skipped += 1

    return exported, skipped


def main():
    parser = argparse.ArgumentParser(description="Export mcp-memory nodes to Vertex AI Search JSONL")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--status", help="Filter by status (e.g. active, backlog)")
    parser.add_argument("--min-quality", type=float, help="Minimum quality_score (0.0-1.0)")
    args = parser.parse_args()

    print(f"DB: {args.db}")
    print(f"Output: {args.output}")
    if args.status:
        print(f"Filter: status={args.status}")
    if args.min_quality is not None:
        print(f"Filter: quality>={args.min_quality}")

    exported, skipped = export_nodes(args.db, args.output, args.status, args.min_quality)

    size_mb = args.output.stat().st_size / 1024 / 1024
    print(f"\nDone: {exported} nodes exported, {skipped} skipped")
    print(f"File: {args.output} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
