"""Ontology v3 Step 2 — Workflow 532개 LLM 재분류.

실행: python scripts/migrate_workflow.py [--dry-run] [--batch-size 20]
모델: gpt-5-mini (무료 2.5M tokens/일)
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from config import OPENAI_API_KEY
from storage.sqlite_store import _db

_client = OpenAI(api_key=OPENAI_API_KEY)

RECLASSIFY_PROMPT = """이 Workflow 노드들을 가장 적절한 v3 타입으로 재분류하라.

선택지:
- Pattern: 반복 사용되는 절차/패턴/규칙
- Framework: 설계 구조, 아키텍처
- Tool: 도구, 스크립트, 명령어, 템플릿
- Goal: 구현 계획, 로드맵, 목표
- Experiment: 실험 계획, 검증
- ARCHIVED: 일회성 구현 태스크 (이미 실행 완료, 검색 가치 없음)

기준:
- "매번 이렇게 한다" → Pattern
- "이런 구조를 사용한다" → Framework
- "이 도구/스크립트를 쓴다" → Tool
- "이것을 달성해야 한다" → Goal
- "이것을 실험/검증한다" → Experiment
- "한 번 하고 끝난 구현 태스크" → ARCHIVED

JSON 배열로 응답: [{"id": <id>, "type": "<type>", "reason": "한줄"}]
"""


def reclassify_batch(nodes: list[dict], model: str = "gpt-5-mini") -> list[dict]:
    """Workflow 노드 배치를 LLM으로 재분류."""
    items = []
    for n in nodes:
        preview = n["content"][:400]
        tags = n.get("tags", "")
        items.append(f'ID={n["id"]} | tags={tags}\n{preview}')

    user_msg = "다음 Workflow 노드들을 재분류하라:\n\n" + "\n---\n".join(items)

    for attempt in range(3):
        try:
            resp = _client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": RECLASSIFY_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_completion_tokens=max(2000, len(nodes) * 200),
            )
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
            else:
                raise

    text = resp.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    try:
        results = json.loads(text)
    except json.JSONDecodeError:
        print(f"  JSON 파싱 실패: {text[:200]}")
        return []

    valid_types = {"Pattern", "Framework", "Tool", "Goal", "Experiment", "ARCHIVED"}
    valid = []
    for r in results:
        if isinstance(r, dict) and "id" in r and "type" in r and r["type"] in valid_types:
            valid.append(r)
    return valid


def migrate_workflows(dry_run: bool = False, batch_size: int = 20,
                      model: str = "gpt-5-mini") -> dict:
    """Workflow 전체 재분류."""
    stats = {"total": 0, "Pattern": 0, "Framework": 0, "Tool": 0,
             "Goal": 0, "Experiment": 0, "ARCHIVED": 0, "errors": 0}

    # PROMOTE_LAYER for layer assignment
    from config import PROMOTE_LAYER

    with _db() as conn:
        workflows = conn.execute("""
            SELECT id, content, tags FROM nodes
            WHERE type='Workflow' AND status='active'
            ORDER BY id
        """).fetchall()

        stats["total"] = len(workflows)
        print(f"Workflow {len(workflows)}개 재분류 시작 (batch={batch_size}, model={model})\n")

        for i in range(0, len(workflows), batch_size):
            batch = workflows[i:i+batch_size]
            nodes = [{"id": r[0], "content": r[1], "tags": r[2]} for r in batch]

            results = reclassify_batch(nodes, model=model)

            for r in results:
                node_id = r["id"]
                new_type = r["type"]
                reason = r.get("reason", "")

                if new_type == "ARCHIVED":
                    if not dry_run:
                        conn.execute(
                            "UPDATE nodes SET status='archived' WHERE id=?",
                            (node_id,)
                        )
                    stats["ARCHIVED"] += 1
                else:
                    layer = PROMOTE_LAYER.get(new_type, 1)
                    tier_map = {"Pattern": 1, "Framework": 2, "Tool": 2,
                                "Goal": 1, "Experiment": 1}
                    tier = tier_map.get(new_type, 2)
                    if not dry_run:
                        conn.execute("""
                            UPDATE nodes SET type=?, layer=?, tier=?
                            WHERE id=?
                        """, (new_type, layer, tier, node_id))
                    stats[new_type] = stats.get(new_type, 0) + 1

            processed = min(i + batch_size, len(workflows))
            print(f"  [{processed}/{len(workflows)}] batch done")

            # API rate limit 고려
            if i + batch_size < len(workflows):
                time.sleep(0.5)

        if not dry_run:
            # type_defs deprecated
            conn.execute("""
                UPDATE type_defs SET
                    status='deprecated',
                    deprecated_reason='v3 타입 축소: Workflow → LLM 재분류',
                    replaced_by='Pattern',
                    deprecated_at=datetime('now'),
                    version=COALESCE(version,0)+1
                WHERE name='Workflow' AND status='active'
            """)
            conn.commit()
            print("\nWorkflow type_defs deprecated.")

    return stats


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    batch_size = 20
    if "--batch-size" in sys.argv:
        idx = sys.argv.index("--batch-size")
        batch_size = int(sys.argv[idx + 1])

    stats = migrate_workflows(dry_run=dry_run, batch_size=batch_size)
    print(f"\n결과: {json.dumps(stats, indent=2)}")

    if not dry_run:
        # 검증
        with _db() as conn:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE type='Workflow' AND status='active'"
            ).fetchone()[0]
            print(f"\n남은 Workflow: {remaining}")
