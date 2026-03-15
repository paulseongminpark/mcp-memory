# Review R1 — E2E 검증 결과

## 검증 요약

| # | 항목 | 결과 | 비고 |
|---|---|---|---|
| 1 | Gate 시뮬레이션 | ✅ PASS | 67개 vc>=10 노드 확인. Obs/Signal은 vc 부족 (자연 축적 필요) |
| 2 | Source 태깅 | ✅ PASS | vector, fts5, graph, typed_vector 정상 태깅 |
| 3 | recall_log 기록 | ✅ PASS | sources JSON 컬럼 자동 생성 + 기록 확인 |
| 4 | RELATION_RULES | ✅ PASS | 6개 새 규칙 테스트, 전부 올바른 관계 반환 |
| 5 | Cross-project | ✅ PASS | mirrors, influenced_by 정상 작동 |
| 6 | promote_node e2e | ✅ PASS | Observation→Signal 승격+롤백 정상 |
| 7 | Full test suite | ✅ PASS | 169/169 |

## 상세 결과

### Source 태깅 (Test 2-3)
```
#4205 [Principle] sources=['fts5', 'typed_vector', 'vector']  ← 3중 소스
#407 [Goal] sources=['fts5']                                    ← FTS5 단독
#173 [Project] sources=['fts5', 'vector']                       ← 2중 소스
```
recall_log에 즉시 기록됨:
```
node_id=4383 sources=["vector"]
node_id=4049 sources=["typed_vector"]
node_id=234 sources=["fts5", "graph"]
```

### RELATION_RULES (Test 4)
새 규칙 전부 작동:
- (Failure→Pattern) = led_to ✅
- (Goal→Experiment) = led_to ✅
- (Principle→Decision) = governs ✅
- (Identity→Goal) = governs ✅
- (Narrative→Failure) = exemplifies ✅
- (Observation→Question) = led_to ✅

### Cross-project (Test 5)
- 같은 타입 다른 프로젝트 → mirrors ✅
- 다른 타입 같은 레이어 → influenced_by ✅
- 다른 레이어 → generalizes_to (layer fallback, 정상) ✅

### Gate 현황 (Test 1)
- Gate 2 통과 (전체): 67개 노드
- Gate 2 통과 (Obs/Signal): 0개 — **예상대로 자연 축적 필요**
- Gate 1 SWR: 기존 recall_log에 sources=NULL → vec_ratio=0 → 새 recall부터 축적 시작

## 판정
**모든 메커니즘 정상 작동.** 승격은 recall 사용 축적 후 자연 발생 예정.
즉시 효과: RELATION_RULES 49개 + cross-project 로직으로 새 edge 품질 향상.
