"""GPT 기반 노드 타입 자동 분류."""

import json
import time
from openai import OpenAI

from config import OPENAI_API_KEY
from ontology.validators import get_valid_node_types

_client = OpenAI(api_key=OPENAI_API_KEY)
MAX_RETRIES = 3

VALID_TYPES = get_valid_node_types()

SYSTEM_PROMPT = f"""You are a memory node classifier. Given a text chunk, classify it into exactly ONE of these types:

{chr(10).join(f'- {t}' for t in VALID_TYPES)}

Type definitions:
- Decision: 명시적 결정, 선택, "~하기로 했다"
- Failure: 실패, 에러, 버그, 실수
- Pattern: 반복 확인된 규칙, 패턴
- Identity: 사용자의 가치관, 철학, 자기 서술
- Preference: 도구/방식 선호
- Goal: 목표, 방향, 비전
- Insight: 깨달음, 발견
- Question: 미해결 질문
- Metaphor: 비유, "~는 마치 ~"
- Connection: 새로운 연결 발견
- Evolution: 시스템/사고 변화 과정
- Breakthrough: 돌파구, 큰 전환점
- SystemVersion: 버전 변경 기록, CHANGELOG
- Experiment: 실험, 테스트
- Tool: 도구 설정, 설치, 사용법
- Framework: 아키텍처, 프레임워크 설계
- Principle: 원칙, 규칙 수립
- Workflow: 워크플로우, 프로세스 정의
- AntiPattern: 안티패턴, 하지 말아야 할 것
- Project: 프로젝트 정의, 개요
- Tension: 갈등, 모순, 트레이드오프
- Narrative: 서사, 이야기, 맥락 설명
- Skill: 스킬, 명령어 정의
- Agent: 에이전트 정의, 역할
- Conversation: 일반 대화, 분류 불가한 대화 로그
- Unclassified: 어디에도 맞지 않는 것

Rules:
- Return ONLY a JSON array of objects: [{{"id": <id>, "type": "<type>"}}]
- Conversation is the LAST resort — only use when nothing else fits
- Be aggressive in classifying: most content has a meaningful type
- Consider the source file path as context"""


def classify_batch(nodes: list[dict], model: str = "gpt-4.1-mini") -> list[dict]:
    """Classify a batch of nodes.

    Args:
        nodes: [{"id": int, "content": str, "source": str}]
        model: OpenAI model to use

    Returns:
        [{"id": int, "type": str}]
    """
    items = []
    for n in nodes:
        src = n.get("source", "")
        preview = n["content"][:300]
        items.append(f'ID={n["id"]} | source={src}\n{preview}')

    user_msg = "Classify each node:\n\n" + "\n---\n".join(items)

    for attempt in range(MAX_RETRIES):
        try:
            resp = _client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0,
                max_tokens=len(nodes) * 30,
            )
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
            else:
                raise

    text = resp.choices[0].message.content.strip()
    # JSON 파싱
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        results = json.loads(text)
    except json.JSONDecodeError:
        return []

    # 유효성 검증
    valid = []
    for r in results:
        if isinstance(r, dict) and "id" in r and "type" in r:
            if r["type"] in VALID_TYPES:
                valid.append({"id": r["id"], "type": r["type"]})
    return valid
