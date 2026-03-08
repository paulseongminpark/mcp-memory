"""Codex CLI로 벌크 enrichment — API 비용 없이."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from storage.sqlite_store import _db

BATCH_SIZE = 30
OUTPUT_DIR = ROOT / "data" / "enrichment_batches"


def export_unenriched() -> int:
    """enrichment 필요한 노드 export."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with _db() as conn:
        rows = conn.execute("""
            SELECT id, type, content, tags, project
            FROM nodes
            WHERE status='active'
              AND (enrichment_status IS NULL OR enrichment_status='pending'
                   OR enrichment_status='{}')
            ORDER BY id
        """).fetchall()
    nodes = [dict(r) for r in rows]
    batches = [nodes[i:i + BATCH_SIZE] for i in range(0, len(nodes), BATCH_SIZE)]
    for i, batch in enumerate(batches):
        path = OUTPUT_DIR / f"batch_{i:03d}.json"
        path.write_text(json.dumps(batch, ensure_ascii=False, indent=2))
    print(f"Exported {len(nodes)} nodes in {len(batches)} batches")
    return len(batches)


def run_codex_batch(batch_idx: int) -> None:
    """단일 배치를 Codex CLI로 enrichment."""
    input_path = OUTPUT_DIR / f"batch_{batch_idx:03d}.json"
    output_path = OUTPUT_DIR / f"result_{batch_idx:03d}.json"
    if not input_path.exists():
        return
    nodes = json.loads(input_path.read_text())
    prompt = (
        "아래 노드들에 대해 enrichment를 수행하라. 각 노드에 대해:\n"
        "- summary: 1-2문장 요약 (한국어)\n"
        "- key_concepts: 핵심 개념 3-7개 (한국어, 쉼표 구분)\n"
        "- domains: 관련 도메인 2-4개 (영어, 쉼표 구분)\n"
        "- facets: 세부 특성 2-4개 (영어, 쉼표 구분)\n\n"
        f"입력 노드:\n{json.dumps(nodes, ensure_ascii=False, indent=2)}\n\n"
        '출력: JSON 배열. 각 원소는 {"id": int, "summary": str, "key_concepts": str, "domains": str, "facets": str}\n'
        "JSON만 출력하라. 다른 텍스트 금지."
    )
    result = subprocess.run(
        ["codex", "exec", prompt, "-o", str(output_path)],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        print(f"Batch {batch_idx} FAILED: {result.stderr[:200]}")


def import_results() -> None:
    """Codex 결과를 DB에 반영."""
    imported = 0
    for path in sorted(OUTPUT_DIR.glob("result_*.json")):
        try:
            results = json.loads(path.read_text())
            with _db() as conn:
                for r in results:
                    conn.execute("""
                        UPDATE nodes SET
                            summary=?, key_concepts=?, domains=?, facets=?,
                            enrichment_status='enriched'
                        WHERE id=?
                    """, (r["summary"], r["key_concepts"],
                          r.get("domains", ""), r.get("facets", ""),
                          r["id"]))
                conn.commit()
            imported += len(results)
        except Exception as e:
            print(f"Import {path.name} failed: {e}")
    print(f"Imported {imported} enrichments")


if __name__ == "__main__":
    total = export_unenriched()
    for i in range(total):
        print(f"\nBatch {i + 1}/{total}")
        run_codex_batch(i)
    import_results()
