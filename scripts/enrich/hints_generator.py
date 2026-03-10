"""Ontology v3 Step 2 — retrieval_hints 배치 생성.

실행: python -m scripts.enrich.hints_generator [--batch-size 20] [--dry-run]
모델: gpt-5-mini (무료 2.5M tokens/일)

배치 방식: 20개 노드를 한 API 호출로 처리 → ~150 호출로 전체 완료
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from openai import OpenAI
from config import OPENAI_API_KEY
from storage.sqlite_store import _db

_client = OpenAI(api_key=OPENAI_API_KEY)

BATCH_HINTS_PROMPT = """아래 기억 노드들 각각의 인출 맥락을 설계하라.

각 노드에 대해 다음 JSON 객체를 생성:
{
    "id": <노드ID>,
    "when_needed": "이 기억이 필요한 구체적 상황 1문장 (한국어)",
    "related_queries": ["예상 검색어 3-5개"],
    "context_keys": ["맥락 키워드 3-5개"]
}

전체를 JSON 배열로 응답: [{...}, {...}, ...]

규칙:
- when_needed: "~할 때", "~를 논의할 때" 형태
- related_queries: 실제 사용자가 검색할 법한 자연어 쿼리 (한국어+영어 혼합)
- context_keys: 이 노드가 관련된 도메인/개념 키워드
"""


def generate_hints_batch(nodes: list[dict], model: str = "gpt-5-mini") -> list[dict]:
    """배치 노드의 retrieval_hints 생성."""
    items = []
    for n in nodes:
        items.append(f'ID={n["id"]} | type={n["type"]} | tags={n.get("tags","")}\n{n["content"][:300]}')

    user_msg = "다음 노드들의 인출 맥락을 설계하라:\n\n" + "\n---\n".join(items)

    for attempt in range(3):
        try:
            resp = _client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": BATCH_HINTS_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_completion_tokens=max(3000, len(nodes) * 300),
            )
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
            else:
                print(f"  API 에러 (3회 실패): {e}")
                return []

    text = (resp.choices[0].message.content or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    try:
        results = json.loads(text)
    except json.JSONDecodeError:
        print(f"  JSON 파싱 실패 (batch {len(nodes)}개)")
        return []

    if not isinstance(results, list):
        return []

    # validation
    valid = []
    for r in results:
        if not isinstance(r, dict) or "id" not in r:
            continue
        validated = {"id": r["id"]}
        if isinstance(r.get("when_needed"), str):
            validated["when_needed"] = r["when_needed"][:500]
        if isinstance(r.get("related_queries"), list):
            validated["related_queries"] = [str(q)[:200] for q in r["related_queries"][:10]]
        if isinstance(r.get("context_keys"), list):
            validated["context_keys"] = [str(k)[:100] for k in r["context_keys"][:10]]
        if len(validated) > 1:  # id 외에 최소 1개 필드
            valid.append(validated)

    return valid


def batch_generate_hints(batch_size: int = 20, model: str = "gpt-5-mini",
                         dry_run: bool = False) -> dict:
    """retrieval_hints가 NULL인 노드에 배치 생성."""
    stats = {"total": 0, "generated": 0, "errors": 0, "api_calls": 0}

    with _db() as conn:
        nodes = conn.execute("""
            SELECT id, type, content, tags FROM nodes
            WHERE status='active' AND retrieval_hints IS NULL
            ORDER BY id
        """).fetchall()

        stats["total"] = len(nodes)
        batches = (len(nodes) + batch_size - 1) // batch_size
        print(f"retrieval_hints 생성: {len(nodes)}개, {batches} batches (size={batch_size})\n")

        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i+batch_size]
            batch_nodes = [{"id": r[0], "type": r[1], "content": r[2], "tags": r[3]} for r in batch]

            results = generate_hints_batch(batch_nodes, model=model)
            stats["api_calls"] += 1

            # id → hints 매핑
            hints_map = {}
            for r in results:
                node_id = r.pop("id")
                hints_map[node_id] = r

            for node_id, _, _, _ in batch:
                if node_id in hints_map:
                    if not dry_run:
                        conn.execute(
                            "UPDATE nodes SET retrieval_hints=? WHERE id=?",
                            (json.dumps(hints_map[node_id], ensure_ascii=False), node_id)
                        )
                    stats["generated"] += 1
                else:
                    stats["errors"] += 1

            if not dry_run:
                conn.commit()

            processed = min(i + batch_size, len(nodes))
            batch_num = i // batch_size + 1
            print(f"  [{processed}/{len(nodes)}] batch {batch_num}/{batches} | gen={stats['generated']} err={stats['errors']}")

            if i + batch_size < len(nodes):
                time.sleep(0.5)

    return stats


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    batch_size = 20
    if "--batch-size" in sys.argv:
        idx = sys.argv.index("--batch-size")
        batch_size = int(sys.argv[idx + 1])

    stats = batch_generate_hints(batch_size=batch_size, dry_run=dry_run)
    print(f"\n결과: {json.dumps(stats, indent=2)}")
