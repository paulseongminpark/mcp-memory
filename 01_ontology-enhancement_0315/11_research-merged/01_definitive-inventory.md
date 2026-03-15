# Definitive Inventory — 수정 대상

## 파일 목록

| 파일 | 변경 유형 | 문제 |
|---|---|---|
| `storage/hybrid.py` | 수정 | hybrid_search()에 source 태깅 추가 |
| `tools/recall.py` | 수정 | _log_recall_results()에 source 기록 |
| `tools/promote_node.py` | 수정 | swr_readiness() SQL을 새 스키마에 맞게 |
| `config.py` | 정리 | TYPE_CHANNEL_WEIGHTS/TYPE_KEYWORDS deprecated 제거, LAYER_IMPORTANCE 4,5 제거 |
| `ontology/validators.py` | 정리 | suggest_closest_type() deprecated 타입 제거 |
| DB schema | ALTER | recall_log에 sources 컬럼 추가 |

## 작업 범위 외 (이번 파이프라인에서 하지 않음)
- fallback-probable 39.6% 관계 재분류 (LLM 비용 높음, 별도 파이프라인)
- edge 생성 출처 추적 컬럼 추가 (향후)
- relation_extractor.py 실행 (enrichment pipeline 별도)
