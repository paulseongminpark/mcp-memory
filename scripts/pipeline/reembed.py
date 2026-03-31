"""벡터 재임베딩 — summary+key_concepts+content[:200] 기반."""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from openai import OpenAI
from config import OPENAI_API_KEY, EMBEDDING_MODEL, EMBEDDING_DIM, CHROMA_PATH
from storage.sqlite_store import _db
import chromadb

BATCH_SIZE = 100  # OpenAI embedding batch limit


def build_embed_text(node: dict) -> str:
    """노드에서 임베딩용 텍스트 생성. 타입 태그 + hints 포함."""
    import json as _json
    parts = []
    # 타입 태그를 첫 줄에 추가
    node_type = node.get("type", "")
    if node_type:
        parts.append(f"[{node_type}]")
    if node.get("summary"):
        parts.append(node["summary"])
    if node.get("key_concepts"):
        # JSON array or comma-separated
        kc = node["key_concepts"]
        if kc.startswith("["):
            try:
                kc = ", ".join(_json.loads(kc))
            except Exception:
                pass
        parts.append(kc)
    content = node.get("content", "")
    if content:
        parts.append(content[:200])
    # retrieval_hints: related_queries + context_keys 추가
    hints = node.get("retrieval_hints")
    if hints:
        try:
            h = _json.loads(hints) if isinstance(hints, str) else hints
            if isinstance(h, dict):
                rq = h.get("related_queries", [])
                ck = h.get("context_keys", [])
                if rq:
                    parts.append(", ".join(str(q) for q in rq[:5]))
                if ck:
                    parts.append(", ".join(str(k) for k in ck[:5]))
        except Exception:
            pass
    return "\n".join(parts)


def main():
    client = OpenAI(api_key=OPENAI_API_KEY)
    chroma = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma.get_or_create_collection(
        name="memory_nodes",
        metadata={"hnsw:space": "cosine"},
    )

    # 1. 모든 active 노드 로드
    with _db() as conn:
        rows = conn.execute("""
            SELECT id, type, layer, content, summary, key_concepts, tags, project, retrieval_hints
            FROM nodes WHERE status='active'
            ORDER BY id
        """).fetchall()

    nodes = [dict(r) for r in rows]
    total = len(nodes)
    print(f"Total nodes to re-embed: {total}")

    # 2. 배치별 임베딩 + upsert
    embedded = 0
    errors = 0
    for i in range(0, total, BATCH_SIZE):
        batch = nodes[i : i + BATCH_SIZE]
        texts = [build_embed_text(n) for n in batch]
        ids = [str(n["id"]) for n in batch]

        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts,
                dimensions=EMBEDDING_DIM,
            )
            embeddings = [d.embedding for d in response.data]

            # ChromaDB upsert
            metadatas = [
                {
                    "type": n.get("type", ""),
                    "layer": n.get("layer", 0),
                    "tags": n.get("tags", "") or "",
                    "project": n.get("project", "") or "",
                }
                for n in batch
            ]
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            embedded += len(batch)
            print(f"  Batch {i // BATCH_SIZE + 1}: {embedded}/{total}")

        except Exception as e:
            errors += len(batch)
            print(f"  Batch {i // BATCH_SIZE + 1} ERROR: {e}")
            time.sleep(2)

    print(f"\nDONE: {embedded} embedded, {errors} errors")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
