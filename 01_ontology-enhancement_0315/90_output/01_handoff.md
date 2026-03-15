# Handoff

## 즉시 효과 (이번 커밋 후)
- 새 recall마다 sources 기록 시작 → Gate 1 데이터 축적
- 새 remember마다 49개 규칙 기반 관계 생성 → 그래프 품질 향상
- cross-project edge: mirrors/influenced_by/transfers_to

## 모니터링 (향후 1-2주)
- `SELECT COUNT(*) FROM recall_log WHERE sources IS NOT NULL` → 축적 추이
- `SELECT type, COUNT(*) FROM nodes WHERE type='Signal'` → Signal 증가 추이
- promote_node() 자연 호출 시 Gate 통과 여부

## 후속 파이프라인 후보
1. enrichment 배치 재실행 (734개 unenriched + 20 hints err)
2. 기존 fallback edge 2,872개 LLM 재분류
3. Edge strength BCM 재캘리브레이션
4. Tiny 노드 408개 정리 정책
