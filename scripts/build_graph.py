#!/usr/bin/env python3
"""전체 노드 대상 배치 graph building.

두 단계:
1. Vector similarity edges: ChromaDB에서 각 노드의 유사 노드 찾아 edge 생성
2. GPT semantic edges: 비-Conversation 노드 클러스터에서 의미 관계 추출

Usage:
    python3 scripts/build_graph.py              # 두 단계 모두
    python3 scripts/build_graph.py --vector-only
    python3 scripts/build_graph.py --gpt-only
    python3 scripts/build_graph.py --threshold 0.35
"""

import os
import sys
import time
import argparse
import sqlite3

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from config import DB_PATH
from storage.sqlite_store import insert_edge, get_all_edges
from storage.vector_store import _get_collection
from enrichment.relation_extractor import extract_relations


def existing_edge_pairs() -> set:
    """이미 존재하는 edge (source, target) 쌍."""
    edges = get_all_edges()
    pairs = set()
    for e in edges:
        pairs.add((e["source_id"], e["target_id"]))
        pairs.add((e["target_id"], e["source_id"]))  # 양방향 중복 방지
    return pairs


def build_vector_edges(threshold: float = 0.35, top_k: int = 3, batch: int = 100):
    """ChromaDB 유사도 기반 edge 생성."""
    print(f"\n=== Step 1: Vector Similarity Edges (threshold={threshold}) ===")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # 전체 노드 ID 목록
    all_nodes = conn.execute("SELECT id, type FROM nodes ORDER BY id").fetchall()
    total = len(all_nodes)
    print(f"대상: {total}개 노드")

    coll = _get_collection()
    existing = existing_edge_pairs()
    created = 0
    skipped = 0

    for i, node in enumerate(all_nodes):
        nid = node["id"]

        try:
            item = coll.get(ids=[str(nid)], include=["embeddings"])
            emb = item["embeddings"]
            if emb is None or len(emb) == 0:
                continue
            vec = emb[0].tolist() if hasattr(emb[0], "tolist") else emb[0]
            results = coll.query(
                query_embeddings=[vec],
                n_results=min(top_k + 1, coll.count()),
                include=["distances"],
            )
        except Exception as e:
            print(f"  skip #{nid}: {e}")
            continue

        ids = results["ids"][0]
        dists = results["distances"][0]

        for j, (cid, dist) in enumerate(zip(ids, dists)):
            target_id = int(cid)
            if target_id == nid:
                continue
            if dist > threshold:
                continue
            if (nid, target_id) in existing:
                skipped += 1
                continue

            # 타입 기반 관계 결정
            src_type = node["type"]
            tgt_row = conn.execute("SELECT type FROM nodes WHERE id=?", (target_id,)).fetchone()
            tgt_type = tgt_row["type"] if tgt_row else "Conversation"

            if src_type == tgt_type:
                relation = "supports"
            elif src_type in ("Failure", "AntiPattern") or tgt_type in ("Failure", "AntiPattern"):
                relation = "connects_with"
            elif src_type == "Decision" and tgt_type == "Insight":
                relation = "led_to"
            elif src_type == "Insight" and tgt_type == "Decision":
                relation = "inspired_by"
            elif src_type == "Pattern" and tgt_type in ("Principle", "Workflow"):
                relation = "governed_by"
            else:
                relation = "connects_with"

            strength = max(0.0, 1.0 - dist)
            insert_edge(nid, target_id, relation, strength=strength)
            existing.add((nid, target_id))
            existing.add((target_id, nid))
            created += 1

        if (i + 1) % batch == 0:
            print(f"  {i+1}/{total} ({created} edges created)", flush=True)

    conn.close()
    print(f"\nVector edges 완료: {created}개 생성 ({skipped} skipped)")
    return created


def build_gpt_edges(model: str = "gpt-4.1-mini", cluster_size: int = 8, max_nodes: int = 500):
    """비-Conversation 노드 클러스터에서 GPT로 의미 관계 추출."""
    print(f"\n=== Step 2: GPT Semantic Edges (model={model}) ===")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # 비-Conversation + edge 적은 노드 우선
    rows = conn.execute(f"""
        SELECT n.id, n.content, n.type, n.project,
               (SELECT COUNT(*) FROM edges e WHERE e.source_id=n.id OR e.target_id=n.id) as edge_cnt
        FROM nodes n
        WHERE n.type != 'Conversation'
        ORDER BY edge_cnt ASC, n.created_at DESC
        LIMIT {max_nodes}
    """).fetchall()

    total = len(rows)
    print(f"대상: {total}개 비-Conversation 노드")

    existing = existing_edge_pairs()
    created = 0

    for i in range(0, total, cluster_size):
        cluster = rows[i:i + cluster_size]
        nodes = [
            {"id": r["id"], "content": r["content"],
             "type": r["type"], "project": r["project"] or ""}
            for r in cluster
        ]

        try:
            relations = extract_relations(nodes, model=model)
        except Exception as e:
            print(f"  cluster {i} error: {e}")
            time.sleep(3)
            continue

        for rel in relations:
            src, tgt = rel["source"], rel["target"]
            if (src, tgt) in existing:
                continue
            insert_edge(src, tgt, rel["relation"], strength=rel["strength"])
            existing.add((src, tgt))
            existing.add((tgt, src))
            created += 1

        if (i + cluster_size) % 80 == 0:
            print(f"  {min(i+cluster_size, total)}/{total} ({created} edges)", flush=True)

        time.sleep(0.3)

    conn.close()
    print(f"\nGPT edges 완료: {created}개 생성")
    return created


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vector-only", action="store_true")
    parser.add_argument("--gpt-only", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.35,
                        help="Vector similarity threshold (default 0.35)")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--max-gpt-nodes", type=int, default=500)
    args = parser.parse_args()

    if not args.gpt_only:
        v = build_vector_edges(threshold=args.threshold)

    if not args.vector_only:
        g = build_gpt_edges(model=args.model, max_nodes=args.max_gpt_nodes)

    # 최종 통계
    conn = sqlite3.connect(str(DB_PATH))
    total_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    total_edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    orphans = conn.execute("""
        SELECT COUNT(*) FROM nodes
        WHERE id NOT IN (SELECT source_id FROM edges)
        AND id NOT IN (SELECT target_id FROM edges)
    """).fetchone()[0]
    conn.close()

    print(f"\n=== 최종 ===")
    print(f"노드: {total_nodes} | 에지: {total_edges} | 고립: {orphans}")
