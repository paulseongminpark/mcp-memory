# Implementation Final — 변경 요약

## 변경 파일 (6개 소스 + 3개 테스트)

### 소스
| 파일 | 변경 |
|---|---|
| config.py | TYPE_CHANNEL_WEIGHTS v3 정리, TYPE_KEYWORDS v3 정리, LAYER_IMPORTANCE L4/5 제거, RELATION_RULES 17→49, infer_relation cross-project 로직, SWR threshold 0.55→0.25 |
| ontology/validators.py | suggest_closest_type v3 타입 기준 |
| tools/promote_node.py | Gate 2: Bayesian→visit_count>=10, swr_readiness sources JSON 파싱 |
| storage/hybrid.py | source_map 추적 + _sources 태깅 |
| tools/recall.py | _log_recall_results sources 컬럼 auto-migration + JSON 기록 |

### 테스트
| 파일 | 변경 |
|---|---|
| tests/test_type_boost.py | Workflow→Pattern, Agent→Tool, deprecated assert 제거 |
| tests/test_promote_v2.py | promotion_probability→promotion_frequency_check mock 교체 |
| tests/test_promote_e2e.py | bayesian→frequency mock, _seed_gate_readiness visit_count 기반 |
| tests/test_integration.py | bayesian→frequency mock 교체 |

## 검증
- 169/169 tests PASS
- 기존 데이터 무변경 (ALTER TABLE은 recall 시 자동)
