# Cross-Validation

## before → after

| 지표 | before | after | 판정 |
|---|---|---|---|
| RELATION_RULES | 17 (7.6%) | 49 (37.3%) | ✅ 목표 18%+ 달성 |
| Gate 2 통과 가능 | 0 (수학적 불가) | 67개 (vc>=10) | ✅ 해제됨 |
| Gate 1 threshold | 0.55 (불가) | 0.25 (가능) | ✅ 완화됨 |
| Source 인프라 | 없음 | recall_log.sources JSON | ✅ 작동 |
| Cross-project 관계 | parallel_with only | mirrors/influenced_by | ✅ 추가됨 |
| Deprecated 잔류 | 12개 | 0 | ✅ 정리됨 |
| Tests | 169 PASS | 169 PASS | ✅ 회귀 없음 |

## 미달 항목 (예상대로)
- promote 성공 >= 10: 아직 0 (자연 축적 필요)
- Signal >= 15: 아직 4 (자연 축적 필요)
- NDCG: 미측정 (goldset 재실행 필요)

## 미달 사유
승격은 "사용 → 데이터 축적 → Gate 통과"의 자연 프로세스. 
배선이 연결됐으므로 사용이 쌓이면 자동으로 달성됨.
