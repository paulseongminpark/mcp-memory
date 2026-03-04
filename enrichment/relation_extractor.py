"""GPT 기반 노드 간 관계 추출."""

import json
import time
from openai import OpenAI

from config import OPENAI_API_KEY
from ontology.validators import get_valid_relation_types

_client = OpenAI(api_key=OPENAI_API_KEY)
MAX_RETRIES = 3

VALID_RELATIONS = get_valid_relation_types()

SYSTEM_PROMPT = f"""You are a knowledge graph relation extractor. Given a set of memory nodes, identify meaningful relationships between them.

Valid relation types:
{chr(10).join(f'- {r}' for r in VALID_RELATIONS)}

Rules:
- Return ONLY a JSON array: [{{"source": <id>, "target": <id>, "relation": "<type>", "strength": <0.1-1.0>}}]
- Only extract relationships you are confident about (strength >= 0.5)
- Max 5 relations per batch
- Do NOT create self-referencing edges
- Consider temporal, causal, structural, and semantic relationships"""


def extract_relations(nodes: list[dict], model: str = "gpt-4.1-mini") -> list[dict]:
    """Extract relations between nodes.

    Args:
        nodes: [{"id": int, "content": str, "type": str, "project": str}]

    Returns:
        [{"source": int, "target": int, "relation": str, "strength": float}]
    """
    items = []
    for n in nodes:
        preview = n["content"][:200]
        items.append(f'ID={n["id"]} [{n["type"]}] project={n.get("project","")}\n{preview}')

    user_msg = "Find relationships between these nodes:\n\n" + "\n---\n".join(items)

    for attempt in range(MAX_RETRIES):
        try:
            resp = _client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0,
                max_tokens=300,
            )
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
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
        return []

    valid = []
    node_ids = {n["id"] for n in nodes}
    for r in results:
        if (isinstance(r, dict)
            and r.get("relation") in VALID_RELATIONS
            and r.get("source") in node_ids
            and r.get("target") in node_ids
            and r.get("source") != r.get("target")):
            valid.append({
                "source": r["source"],
                "target": r["target"],
                "relation": r["relation"],
                "strength": max(0.1, min(1.0, r.get("strength", 0.7))),
            })
    return valid
