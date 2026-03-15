# Ideation Final — 온톨로지 강화 설계

## 방향
"개별 버그 수리"가 아닌 **자기 성장 루프 전체 관통 + 관계 품질 강화**

## 핵심 발견 (Research → Ideation)

### 승격 파이프라인: 설계만 있고 배선 없음
- Gate 1: recall_log.source 컬럼 부재 → vec_ratio = 항상 0 → 영구 차단
- Gate 2: nodes.frequency 갱신 로직 없음 + Beta(1,10) prior가 현재 규모에서 수학적 불가
- Gate 3: MDL 정상이나 Gate 1,2 차단으로 도달 불가
- 결과: 전체 역사에서 승격 1건, Signal 4개

### 관계 품질: 커버리지 부족
- RELATION_RULES: 17/225 타입 쌍 (7.6%)
- fallback-probable edges: 2,872/7,249 (39.6%)
- cross-project edges: 445/5,229 (8.5%) — 지식 사일로

### 코드 위생
- deprecated 타입 잔류: TYPE_CHANNEL_WEIGHTS 5개, TYPE_KEYWORDS 5개, suggest_closest_type 2개
- LAYER_IMPORTANCE layer 4,5 dead code

## 구현 6항목

| # | 항목 | 파일 | 변경 유형 |
|---|---|---|---|
| 1 | Deprecated 정리 | config.py, validators.py | 제거+추가 |
| 2 | Gate 2 → visit_count threshold | promote_node.py | 함수 교체 |
| 3 | Gate 1 threshold 0.55→0.25 | promote_node.py | 상수 변경 |
| 4 | recall_log source 인프라 | hybrid.py, recall.py, DB migration | 3파일 수정 |
| 5 | RELATION_RULES 확장 17→40+ | config.py | 규칙 추가 |
| 6 | Cross-project 관계 로직 | config.py (infer_relation) | 로직 추가 |

## Success Criteria

| 지표 | before | target |
|---|---|---|
| promote 성공 건수 | 1 | >= 10 |
| Signal 노드 수 | 4 | >= 15 |
| RELATION_RULES 커버리지 | 7.6% | 18%+ |
| NDCG@5 | 현재치 | >= 현재치 |
| tests | 169 PASS | 전부 PASS |

## 범위 외 (향후)
- 유령 노드 782개 (enrichment 재실행)
- Edge strength 재캘리브 (BCM 튜닝)
- Tiny 노드 408개 정리
- 기존 fallback edge 2,872개 LLM 재분류
