#!/usr/bin/env python3
"""노드 타입 자동 분류 + 관계 추출 배치 스크립트.

Usage:
    python3 scripts/enrich_nodes.py                    # 타입 분류만
    python3 scripts/enrich_nodes.py --relations        # 관계 추출도
    python3 scripts/enrich_nodes.py --model gpt-4.1-nano  # 모델 지정
    python3 scripts/enrich_nodes.py --dry-run          # DB 수정 안 함
"""

import os
import sys
import argparse
import sqlite3
import time

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from config import DB_PATH
from enrichment.classifier import classify_batch
from enrichment.relation_extractor import extract_relations
from storage.sqlite_store import insert_edge


def run_classification(model: str, dry_run: bool, batch_size: int = 10):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Conversation 타입인 Obsidian 노드만 대상
    rows = conn.execute("""
        SELECT id, content, source FROM nodes
        WHERE type = 'Conversation' AND source LIKE 'obsidian:%'
        ORDER BY id
    """).fetchall()

    total = len(rows)
    print(f"분류 대상: {total}개 (Conversation + Obsidian)")

    if total == 0:
        print("분류할 노드 없음")
        conn.close()
        return

    classified = 0
    kept_conversation = 0
    errors = 0
    type_counts = {}

    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        nodes = [{"id": r["id"], "content": r["content"], "source": r["source"]} for r in batch]

        try:
            results = classify_batch(nodes, model=model)
        except Exception as e:
            print(f"  batch {i}-{i+batch_size} error: {e}")
            errors += len(batch)
            continue

        # 결과 적용
        result_map = {r["id"]: r["type"] for r in results}
        for n in nodes:
            new_type = result_map.get(n["id"], "Conversation")
            type_counts[new_type] = type_counts.get(new_type, 0) + 1

            if new_type == "Conversation":
                kept_conversation += 1
                continue

            if not dry_run:
                conn.execute(
                    "UPDATE nodes SET type = ? WHERE id = ?",
                    (new_type, n["id"])
                )
            classified += 1

        if not dry_run:
            conn.commit()

        done = min(i + batch_size, total)
        print(f"  {done}/{total} ({classified} reclassified, {errors} errors)", flush=True)

        # rate limit 방지
        time.sleep(0.5)

    conn.close()

    print(f"\n=== 분류 완료 ===")
    print(f"재분류: {classified}개")
    print(f"Conversation 유지: {kept_conversation}개")
    print(f"에러: {errors}개")
    print(f"\n타입 분포:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")


def run_relations(model: str, dry_run: bool, batch_size: int = 8):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # 비-Conversation 노드 중 edge 없는 것 우선
    rows = conn.execute("""
        SELECT n.id, n.content, n.type, n.project FROM nodes n
        WHERE n.type != 'Conversation'
        AND n.id NOT IN (SELECT source_id FROM edges)
        AND n.id NOT IN (SELECT target_id FROM edges)
        ORDER BY n.created_at DESC
        LIMIT 500
    """).fetchall()

    total = len(rows)
    print(f"\n관계 추출 대상: {total}개 (비-Conversation, edge 없음)")

    if total == 0:
        print("추출할 노드 없음")
        conn.close()
        return

    edges_created = 0

    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        nodes = [
            {"id": r["id"], "content": r["content"], "type": r["type"], "project": r["project"] or ""}
            for r in batch
        ]

        try:
            relations = extract_relations(nodes, model=model)
        except Exception as e:
            print(f"  batch {i} error: {e}")
            continue

        for rel in relations:
            if not dry_run:
                insert_edge(
                    source_id=rel["source"],
                    target_id=rel["target"],
                    relation=rel["relation"],
                    strength=rel["strength"],
                )
            edges_created += 1

        done = min(i + batch_size, total)
        print(f"  {done}/{total} ({edges_created} edges)", flush=True)
        time.sleep(0.5)

    conn.close()
    print(f"\n=== 관계 추출 완료: {edges_created}개 edge 생성 ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--relations", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()

    print(f"Model: {args.model} | Dry-run: {args.dry_run}")
    print(f"DB: {DB_PATH}\n")

    run_classification(args.model, args.dry_run, args.batch_size)

    if args.relations:
        run_relations(args.model, args.dry_run, args.batch_size)
