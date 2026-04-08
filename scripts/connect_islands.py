#!/usr/bin/env python3
"""WS-2.4: 고립 노드(semantic 0-1 edge) 연결 스크립트.

knowledge-bearing 노드 중 semantic edge가 0-1인 것을 vector search로
nearest neighbor와 연결한다.

Usage:
  python scripts/connect_islands.py --batch 100 --dry-run
  python scripts/connect_islands.py --batch 100
"""
import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from storage import sqlite_store, vector_store
from config import infer_relation

KB_TYPES = (
    'Observation', 'Signal', 'Pattern', 'Insight', 'Principle',
    'Framework', 'Decision', 'Experiment', 'Failure', 'Question',
)
SEMANTIC_METHODS = ('rule', 'semantic_auto', 'enrichment', 'manual')
MIN_COSINE = 0.55


def get_island_nodes(limit: int = 0) -> list[dict]:
    """semantic edge 0-1인 knowledge-bearing 노드 추출."""
    ph = ','.join(f"'{t}'" for t in KB_TYPES)
    sql = f"""
    SELECT n.id, n.type, n.content, n.project, n.layer
    FROM nodes n
    WHERE n.status='active' AND n.type IN ({ph})
    AND (SELECT COUNT(*) FROM edges e
         WHERE e.status='active' AND (e.source_id=n.id OR e.target_id=n.id)
         AND e.generation_method IN ('rule','semantic_auto','enrichment','manual')
        ) <= 1
    ORDER BY n.visit_count DESC
    """
    if limit:
        sql += f" LIMIT {limit}"

    with sqlite_store._db() as conn:
        rows = conn.execute(sql).fetchall()
    return [
        {"id": r[0], "type": r[1], "content": r[2], "project": r[3], "layer": r[4]}
        for r in rows
    ]


def find_neighbors(node: dict, top_k: int = 5) -> list[tuple[int, float]]:
    """Chroma vector search로 nearest neighbor 찾기."""
    try:
        results = vector_store.search(
            node["content"][:500], top_k=top_k + 1  # 자기 자신 제외용
        )
    except Exception:
        return []

    neighbors = []
    for nid, distance, _ in results:
        if nid == node["id"]:
            continue
        cosine = 1.0 - distance  # Chroma L2 → cosine 근사
        if cosine >= MIN_COSINE:
            neighbors.append((nid, cosine))
    return neighbors[:top_k]


def connect(node: dict, neighbor_id: int, cosine: float, dry_run: bool = False) -> bool:
    """두 노드를 edge로 연결."""
    # 이미 연결됐는지 확인
    with sqlite_store._db() as conn:
        existing = conn.execute(
            """SELECT id FROM edges WHERE status='active'
               AND ((source_id=? AND target_id=?) OR (source_id=? AND target_id=?))""",
            (node["id"], neighbor_id, neighbor_id, node["id"])
        ).fetchone()
        if existing:
            return False

        neighbor = conn.execute(
            "SELECT type, layer, project FROM nodes WHERE id=? AND status='active'",
            (neighbor_id,)
        ).fetchone()
        if not neighbor:
            return False

    nbr_type, nbr_layer, nbr_project = neighbor
    relation = infer_relation(
        node["type"], node["layer"],
        nbr_type, nbr_layer,
        node["project"], nbr_project
    )

    if dry_run:
        print(f"  DRY: {node['id']}({node['type']}) --{relation}--> {neighbor_id}({nbr_type}) cos={cosine:.3f}")
        return True

    sqlite_store.insert_edge(
        source_id=node["id"],
        target_id=neighbor_id,
        relation=relation,
        strength=cosine,
        generation_method="semantic_auto",
    )
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    islands = get_island_nodes(limit=args.batch)
    print(f"고립 노드: {len(islands)}개 (batch={args.batch})")

    created = 0
    skipped = 0
    for i, node in enumerate(islands, 1):
        neighbors = find_neighbors(node)
        for nbr_id, cosine in neighbors[:2]:  # 최대 2개 연결
            if connect(node, nbr_id, cosine, dry_run=args.dry_run):
                created += 1
            else:
                skipped += 1
        if i % 20 == 0:
            print(f"  진행: {i}/{len(islands)}, 생성: {created}, 스킵: {skipped}")

    print(f"\n완료: 생성 {created}, 스킵 {skipped}")


if __name__ == "__main__":
    main()
