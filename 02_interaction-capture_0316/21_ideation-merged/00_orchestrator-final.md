# PDR — Pipeline DONE Retrospective 설계 확정

## 개요
세션 전체 대화를 8차원으로 스캔하여 mcp-memory에 Observation(L0) 노드로 저장하는 rigid 스킬.

## 트리거
| 시점 | 방식 | 범위 |
|---|---|---|
| compact 직전 | 수동 /pdr 또는 자동 | 현재 세션 전체 |
| Pipeline DONE | G6 하드 블록 | 마지막 세션 + 이전 PDR recall |

## 8차원 스캔
| # | 차원 | tag | 최소 |
|---|---|---|---|
| 1 | 사고 방식 | thinking-style | 2 |
| 2 | 선호/반응 | preference | 2 |
| 3 | 감정 신호 | emotional | 1 |
| 4 | 결정 스타일 | decision-style | 2 |
| 5 | 언어 패턴 | language | 1 |
| 6 | 작업 리듬 | work-rhythm | 1 |
| 7 | 메타인지 | metacognition | 2 |
| 8 | 관계/연결 | connection | 2 |

목표: 20~25개 / 최소: 13개

## 저장 형식
```python
remember(
    content="[PDR] {관찰}",
    type="Observation",
    tags="pdr, {dimension-tag}, {키워드}",
    project="{프로젝트}",
    source="pdr",
    confidence=0.70
)
```

## 중복 방지
- 저장 전 recall(content, top_k=3)
- 동일 → 스킵 / 유사+새 관점 → 저장+edge / 반복 확인 → Signal 승격 제안

## 비용
~14,000 tokens/회 (recall 5K + remember 6K + 스캔 3K)

## 기존 경로와의 관계
- auto_remember: 도구 이벤트 (공존)
- /checkpoint: 중간 세이브 (공존, PDR이 recall해서 중복 스킵)
- /session-end: 세션 아카이브 (공존)
- /pdr: 전체 회고 (새로운 4번째 경로)

## 산출물
Pipeline DONE 시 90_output/02_pdr-report.md 생성 필수
