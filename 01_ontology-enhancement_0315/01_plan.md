# Ontology Enhancement — Plan

## 작업 목표
1. generic 관계(connects_with) 87.2% → 50% 이하로 축소
2. E14(관계 정밀화) 실제 구현 + 실행
3. promote_node 3-gate 데이터소스 문제 해결
4. init_db() last_activated 컬럼 추가 (BCM/UCB silent rollback 방지)
5. deprecated 타입 잔류 코드 정리 (TYPE_CHANNEL_WEIGHTS, TYPE_KEYWORDS, suggest_closest_type)

## 손실불가 기준
- 기존 169 tests 전부 PASS 유지
- NDCG@5 현재 수준 이상 유지
- 기존 2,947 노드 데이터 무손실

## 대상 파일/범위
- `config.py` — RELATION_RULES, RELATION_TYPES, TYPE_CHANNEL_WEIGHTS, TYPE_KEYWORDS
- `enrichment/classifier.py` — 타입 분류 프롬프트
- `enrichment/relation_extractor.py` — 관계 추출
- `ontology/validators.py` — 타입/관계 검증
- `storage/sqlite_store.py` — init_db(), promote_node, BCM/UCB
- `server.py` — MCP 도구 인터페이스
- `scripts/enrich/` — enrichment 파이프라인 스크립트

## Phase 분할
| Phase | 라운드 수 | 내용 |
|---|---|---|
| Research (10-19) | 1~2 | 현황 측정: 관계 분포, generic 비율, E14/promote/BCM 코드 분석 |
| Ideation (20-29) | 1~2 | 강화 전략: 어떤 관계를 어떻게 정밀화할지, promote 수정 방향 |
| Implementation (30-39) | 1~2 | 코드 구현 + 마이그레이션 스크립트 |
| Review (40-49) | 1 | measure 재측정, 회귀 검증 |

## Pane 분할
- 단일 Pane (Pane F). 모델: Opus.
