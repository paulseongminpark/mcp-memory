# Claim Extraction Prompt — v8 Phase 0

> SoT: 07_ontology-redesign_0410/30_build-r1/03_impl-plan.md Day 2 Stream B
> 모델: Qwen2.5-7B-Instruct-Q4_K_M (Ollama, local)
> 검증: 2026-04-12 Day 1 샘플 테스트 통과 (eval_duration 1358ms)

---

## System Prompt

```
Paul의 발화에서 claim들을 추출하세요.

규칙:
1. claim은 "Paul은 ~한다/생각한다/느낀다/선호한다/싫어한다" 형태의 명제입니다
2. 1개 발화에서 여러 claim을 추출할 수 있습니다 (보통 2-5개)
3. 반드시 JSON **array**로 출력합니다 — 단일 object 금지
4. 명확하지 않으면 추출하지 마세요 (빈 array OK)

dimension 후보 (하나 선택):
- thinking_style: 사고 방식, 처리 속도
- preference: 선호/반응
- emotion: 감정 신호
- decision_style: 결정 방식
- language: 언어/표현 패턴
- rhythm: 작업 리듬
- metacognition: 자기 인지/한계 인식
- connection: 관계/연결 방식

출력 스키마:
{"claims": [{"text": "Paul은 ...", "dimension": "...", "confidence": 0.0-1.0}]}
```

## User Prompt (파라미터)

```
발화: "{capture_content}"

JSON:
```

## Ollama API 호출

```python
import requests
import json

def extract_claims(capture_content: str) -> list[dict]:
    system = """Paul의 발화에서 claim들을 추출하세요.

규칙:
1. claim은 "Paul은 ~한다/생각한다/느낀다/선호한다/싫어한다" 형태의 명제입니다
2. 1개 발화에서 여러 claim을 추출할 수 있습니다 (보통 2-5개)
3. 반드시 JSON **array**로 출력합니다 — 단일 object 금지
4. 명확하지 않으면 추출하지 마세요 (빈 array OK)

dimension 후보 (하나 선택):
- thinking_style: 사고 방식, 처리 속도
- preference: 선호/반응
- emotion: 감정 신호
- decision_style: 결정 방식
- language: 언어/표현 패턴
- rhythm: 작업 리듬
- metacognition: 자기 인지/한계 인식
- connection: 관계/연결 방식

출력 스키마:
{"claims": [{"text": "Paul은 ...", "dimension": "...", "confidence": 0.0-1.0}]}"""

    prompt = f"{system}\n\n발화: \"{capture_content}\"\n\nJSON:"

    r = requests.post('http://localhost:11434/api/generate', json={
        'model': 'qwen2.5:7b-instruct-q4_K_M',
        'prompt': prompt,
        'stream': False,
        'format': 'json',
        'options': {'temperature': 0.2}
    }, timeout=60)
    data = r.json()
    result = json.loads(data['response'])
    return result.get('claims', [])
```

## 테스트 케이스

### 입력 1
```
나는 느리다. 모든 데이터를 하나씩 봐야하고 이해해야하니까.
```

### 출력 1 (검증됨, Day 1)
```json
{
  "claims": [
    {"text": "Paul은 느리다.", "dimension": "thinking_style", "confidence": 0.9},
    {"text": "Paul은 모든 데이터를 하나씩 봐야하고 이해해야 한다.", "dimension": "thinking_style", "confidence": 1.0}
  ]
}
```

### 품질 체크 항목
- [x] Array 형태 출력
- [x] 복수 claim 추출 (단일 발화에서 2개)
- [x] "Paul은 X" 형태 정규화
- [x] dimension 정확 매핑
- [x] confidence 0.0-1.0 범위
- [x] 응답 시간 < 2초 (1358ms)

## 개선 대기 항목 (Day 2 이후)

- [ ] 더 복잡한 multi-sentence 입력 테스트
- [ ] negative case ("불명확 → 빈 array") 검증
- [ ] few-shot 예시 2-3개 시스템 프롬프트에 포함하여 일관성 향상
- [ ] dimension 분류 정확도 측정 (Paul 검증 샘플 10개)
