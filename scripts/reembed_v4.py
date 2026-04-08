#!/usr/bin/env python3
"""전체 re-embed — v4 포맷 ([Type|Project] summary + claims + queries + keywords).

PowerShell에서 실행:
  python scripts/reembed_v4.py
"""
import sys, os, sqlite3, json, time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from config import OPENAI_API_KEY
from openai import OpenAI
import chromadb

DB = os.path.join(ROOT, "data", "memory.db")
CHROMA_PATH = os.path.join(ROOT, "data", "chroma")
BATCH_SIZE = 50  # OpenAI embedding batch limit
MAX_RETRIES = 3


def build_embed_text(node):
    """v4 임베딩 텍스트 — content only (대조 실험)."""
    return node['content'] or ''


def main():
    oai = OpenAI(api_key=OPENAI_API_KEY)
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Delete and recreate collection for clean state
    try:
        chroma_client.delete_collection('memories')
        print("Deleted old ChromaDB collection")
    except:
        pass
    collection = chroma_client.create_collection(
        name='memories',
        metadata={"hnsw:space": "cosine"},
    )
    print("Created new ChromaDB collection")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT id, type, content, summary, key_concepts, project, tags,
               retrieval_queries, atomic_claims
        FROM nodes WHERE status='active'
        ORDER BY id
    """).fetchall()
    conn.close()

    total = len(rows)
    print(f"Nodes to embed: {total}")
    print(f"Batch size: {BATCH_SIZE}")
    print()

    embedded = 0
    errors = 0
    start_time = time.time()

    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]

        ids = [str(r['id']) for r in batch]
        texts = [build_embed_text(r) for r in batch]
        metadatas = [
            {
                "type": r['type'] or 'Unclassified',
                "project": r['project'] or '',
                "tags": r['tags'] or '',
            }
            for r in batch
        ]

        for attempt in range(MAX_RETRIES):
            try:
                resp = oai.embeddings.create(
                    model="text-embedding-3-large",
                    input=texts,
                )
                embeddings = [d.embedding for d in resp.data]

                collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=texts,
                )
                embedded += len(batch)
                break

            except Exception as e:
                err = str(e)
                if '429' in err or 'rate' in err.lower():
                    wait = 20 * (attempt + 1)
                    print(f"\r  rate limit — waiting {wait}s...", end="", flush=True)
                    time.sleep(wait)
                else:
                    errors += len(batch)
                    if errors <= 5:
                        print(f"\n  Error: {err[:60]}")
                    break

        elapsed = time.time() - start_time
        rate = embedded / elapsed if elapsed > 0 else 0
        eta = (total - embedded) / rate / 60 if rate > 0 else 0
        print(
            f"\r  [{embedded}/{total}] {embedded*100/total:.1f}% | "
            f"{rate:.1f}/s | ETA {eta:.0f}min | err={errors}",
            end="", flush=True
        )

    print(f"\n\nDone: {embedded} embedded, {errors} errors")
    print(f"ChromaDB count: {collection.count()}")

    # Update metadata in DB to clear provisional flag
    conn = sqlite3.connect(DB)
    conn.execute("""
        UPDATE nodes SET metadata = REPLACE(metadata, '"embedding_provisional": "true"', '"embedding_provisional": "false"')
        WHERE status='active' AND metadata LIKE '%embedding_provisional%true%'
    """)
    conn.commit()
    prov = conn.execute("SELECT COUNT(*) FROM nodes WHERE metadata LIKE '%embedding_provisional%true%'").fetchone()[0]
    conn.close()
    print(f"Remaining provisional: {prov}")


if __name__ == "__main__":
    main()
