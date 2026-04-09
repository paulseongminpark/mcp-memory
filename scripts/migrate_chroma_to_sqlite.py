#!/usr/bin/env python3
"""Migrate embeddings from ChromaDB to SQLite nodes.embedding BLOB.

One-time migration for 1-Store architecture.

Usage:
  python scripts/migrate_chroma_to_sqlite.py              # dry-run
  python scripts/migrate_chroma_to_sqlite.py --execute     # run migration
"""

import os
import sys
import sqlite3
import time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import numpy as np

CHROMA_PATH = os.path.join(ROOT, "data", "chroma")
DB_PATH = os.path.join(ROOT, "data", "memory.db")


def vector_to_blob(vec: list[float]) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def main(execute: bool = False):
    import chromadb

    # Connect to ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(
        name="memories",
        metadata={"hnsw:space": "cosine"},
    )

    total_in_chroma = collection.count()
    print(f"ChromaDB collection 'memories': {total_in_chroma} vectors")

    # Get all embeddings from ChromaDB
    # ChromaDB returns in batches, get all at once
    result = collection.get(
        include=["embeddings"],
        limit=total_in_chroma,
    )

    chroma_ids = result["ids"]
    chroma_embeddings = result["embeddings"]
    print(f"Retrieved {len(chroma_ids)} embeddings from ChromaDB")

    # Connect to SQLite
    conn = sqlite3.connect(DB_PATH)

    # Ensure embedding column exists
    try:
        conn.execute("ALTER TABLE nodes ADD COLUMN embedding BLOB")
        conn.commit()
        print("Added embedding column to nodes table")
    except Exception:
        pass  # already exists

    # Check how many active nodes exist
    active_count = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE status='active'"
    ).fetchone()[0]
    print(f"Active nodes in SQLite: {active_count}")

    # Check how many already have embeddings
    existing_count = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE embedding IS NOT NULL"
    ).fetchone()[0]
    print(f"Nodes already with embeddings: {existing_count}")

    if not execute:
        # Check dimension of first embedding
        if chroma_embeddings is not None and len(chroma_embeddings) > 0:
            dim = len(chroma_embeddings[0])
            blob_size = dim * 4
            total_size = len(chroma_embeddings) * blob_size
            print(f"\n[DRY-RUN]")
            print(f"  Embedding dimension: {dim}")
            print(f"  Blob size per vector: {blob_size} bytes")
            print(f"  Total estimated size: {total_size / 1024 / 1024:.1f} MB")
            print(f"  Vectors to migrate: {len(chroma_ids)}")
        print("\nRun with --execute to perform migration.")
        conn.close()
        return

    # Migrate
    t0 = time.time()
    migrated = 0
    skipped = 0
    missing = 0
    batch_size = 500

    for i in range(0, len(chroma_ids), batch_size):
        batch_ids = chroma_ids[i:i + batch_size]
        batch_embs = chroma_embeddings[i:i + batch_size]

        updates = []
        for str_id, emb in zip(batch_ids, batch_embs):
            try:
                node_id = int(str_id)
            except (ValueError, TypeError):
                skipped += 1
                continue

            if emb is None:
                skipped += 1
                continue

            # Check node exists
            row = conn.execute(
                "SELECT id FROM nodes WHERE id = ?", (node_id,)
            ).fetchone()
            if not row:
                missing += 1
                continue

            blob = vector_to_blob(emb)
            updates.append((blob, node_id))

        if updates:
            conn.executemany(
                "UPDATE nodes SET embedding = ? WHERE id = ?",
                updates,
            )
            conn.commit()
            migrated += len(updates)

        elapsed = time.time() - t0
        progress = min(i + batch_size, len(chroma_ids))
        print(f"  [{progress:>5}/{len(chroma_ids)}] migrated={migrated} skipped={skipped} missing={missing} ({elapsed:.1f}s)")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Migrated: {migrated}")
    print(f"  Skipped: {skipped}")
    print(f"  Missing (node not in SQLite): {missing}")

    # Verify
    final_count = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE embedding IS NOT NULL"
    ).fetchone()[0]
    print(f"  Nodes with embeddings after migration: {final_count}")

    conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate ChromaDB -> SQLite embeddings")
    parser.add_argument("--execute", action="store_true", help="Run migration (default: dry-run)")
    args = parser.parse_args()
    main(execute=args.execute)
