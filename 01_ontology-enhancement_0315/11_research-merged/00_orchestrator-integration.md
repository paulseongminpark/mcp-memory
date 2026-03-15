# Research Merged — 통합 결론

## 핵심 발견 (3개)

### 1. promote_node Gate 1 영구 차단 (Critical)
- recall_log에 `source` 컬럼 부재 → vec_ratio = 항상 0.0 → readiness max 0.4 < threshold 0.55
- fix: hybrid_search() source 태깅 → recall() 전달 → recall_log 기록 (3함수 + ALTER TABLE)
- 기존 2,899 recall_log 행은 source=NULL 처리 필요

### 2. Signal 타입 고갈 (High)
- Signal = 4개 (0.1%), Observation = 108개 (3.0%)
- Gate 1 차단으로 Observation → Signal 승격 불가 → 파이프라인 입구 고갈

### 3. Deprecated 타입 잔류 코드 (Medium)
- config.py: TYPE_CHANNEL_WEIGHTS/TYPE_KEYWORDS에 5개 deprecated 타입
- validators.py: suggest_closest_type()에 2개 deprecated 타입
- config.py: LAYER_IMPORTANCE에 layer 4,5 (v3에서 최대 3)

## 초기 가설 교정

| 가설 | 실제 |
|---|---|
| generic 관계 87.2% | connects_with 0.3%. fallback-probable 39.6% |
| last_activated 부재 | 컬럼 존재 |
| BCM/UCB rollback | 정상 작동 |
| Gate 부재 | Gate 존재하나 데이터 미연결로 영구 차단 |

## 측정 기준선 (before)
- connects_with: 19/7,249 (0.3%)
- fallback-probable: 2,872/7,249 (39.6%)
- Signal nodes: 4/3,637 (0.1%)
- promote_node 성공률: 0% (Gate 1 차단)
- Tests: 169 PASS
