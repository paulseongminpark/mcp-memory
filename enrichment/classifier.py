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

Type definitions (v3 — 15 active types):
- Decision: 명시적 결정, 선택, 트레이드오프, 경계 설정, 제약 조건
- Pattern: 반복 확인된 규칙, 패턴, 경험 법칙, 루틴/의식
- Principle: 원칙, 규칙, 가치관, 철학, 믿음, 전제/가정
- Failure: 실패, 에러, 버그, 실수, 안티패턴, 교정
- Insight: 깨달음, 발견, 돌파구, 새로운 연결, 개념 정리
- Goal: 목표, 방향, 비전, 계획, 약속/헌신
- Experiment: 실험, 테스트, 검증 시도
- Project: 프로젝트 정의, 시스템 버전, 개요
- Tool: 도구, 스킬, 에이전트, 명령어, 설정, 사용법
- Framework: 아키텍처, 프레임워크, 멘탈 모델, 관점/렌즈
- Narrative: 서사, 이야기, 맥락 설명, 비유
- Identity: 가치관, 스타일, 철학, 습관, 선호
- Signal: 약한 신호, 관찰 횟수 낮은 패턴 후보, 트리거
- Observation: 직접 관찰, 맥락 기록, 증거/데이터, 대화 로그
- Question: 열린 질문, 미해결 긴장, 역설, 궁금증
- Unclassified: 어디에도 맞지 않는 것

Deprecated type mapping (이전 타입이 보이면 새 타입으로 분류):
Skill/Agent → Tool, SystemVersion → Project, Breakthrough/Connection → Insight,
Conversation/Context/Evidence → Observation, Tension/Paradox/Wonder/Aporia → Question,
AntiPattern/Correction → Failure, Preference → Identity,
Philosophy/Value/Belief/Axiom/Assumption → Principle,
Evolution/Heuristic/Ritual → Pattern, Metaphor → Narrative,
Lens/Mental Model → Framework, Boundary/Constraint/Trade-off → Decision,
Plan/Vision/Commitment → Goal, Trigger → Signal

Rules:
- Return ONLY a JSON array of objects: [{{"id": <id>, "type": "<type>"}}]
- Observation is the LAST resort — only use when nothing else fits
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
