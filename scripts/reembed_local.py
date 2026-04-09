#!/usr/bin/env python3
"""reembed_local.py — ChromaDB를 로컬 임베딩(1024 dim)으로 재구축.

OpenAI 3072 dim → local multilingual-e5-large 1024 dim.
기존 ChromaDB 컬렉션을 삭제하고 active 노드만 새로 임베딩.

Usage:
  python scripts/reembed_local.py              # dry-run
  python scripts/reembed_local.py --execute    # 실행
"""

import os
import sys
import time

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

# 강제 로컬 임베딩
os.environ["EMBEDDING_PROVIDER"] = "local"

import importlib
import config
importlib.reload(config)

import sqlite3
import chromadb
from embedding.local_embed import embed_batch
from embedding.embed_text_builder import build_embed_text


def get_active_nodes(conn) -> list[dict]:
    rows = conn.execute(
        """SELECT id, content, summary, key_concepts, tags,
                  domains, facets, retrieval_queries
           FROM nodes WHERE status = 'active'
           ORDER BY id"""
    ).fetchall()
    return [dict(r) for r in rows]


def build_text_for_embedding(node: dict) -> str:
    """enrichment 필드가 있으면 활용, 없으면 content만."""
    try:
        return build_embed_text(node)
    except Exception:
        return (node.get("content") or "")[:500]


def main(execute: bool = False):
    db_path = os.path.join(PROJECT_ROOT, "data", "memory.db")
    chroma_path = os.path.join(PROJECT_ROOT, "data", "chroma")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    nodes = get_active_nodes(conn)
    print(f"Active nodes to embed: {len(nodes)}")

    if not execute:
        print("[DRY-RUN] Would re-embed all nodes with local model (1024 dim)")
        print(f"  ChromaDB path: {chroma_path}")
        print(f"  Estimated time: ~{len(nodes) * 0.15:.0f}s")
        conn.close()
        return

    # ChromaDB 클라이언트 생성
    client = chromadb.PersistentClient(path=chroma_path)

    # 기존 컬렉션 삭제 + 재생성
    collection_names = [c.name for c in client.list_collections()]
    for name in collection_names:
        print(f"  Deleting collection: {name}")
        client.delete_collection(name)

    collection = client.create_collection(
        name="memories",
        metadata={"hnsw:space": "cosine"},
    )
    print(f"  Created new collection: memories (cosine)")

    # 배치 임베딩
    batch_size = 32
    total = len(nodes)
    t0 = time.time()

    for i in range(0, total, batch_size):
        batch = nodes[i:i + batch_size]
        texts = [build_text_for_embedding(n) for n in batch]
        ids = [str(n["id"]) for n in batch]

        vectors = embed_batch(texts)

        collection.add(
            ids=ids,
            embeddings=vectors,
            documents=texts,
        )

        elapsed = time.time() - t0
        progress = min(i + batch_size, total)
        rate = progress / elapsed if elapsed > 0 else 0
        eta = (total - progress) / rate if rate > 0 else 0
        print(f"  [{progress:>5}/{total}] {elapsed:.1f}s elapsed, ~{eta:.0f}s remaining")

    elapsed = time.time() - t0
    print(f"\nDone: {total} nodes re-embedded in {elapsed:.1f}s")
    print(f"  Collection count: {collection.count()}")

    conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    main(execute=args.execute)
