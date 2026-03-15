# Workflow — 구현 흐름

## 순서
1. Deprecated 정리 → tests 확인
2. Gate 2 visit_count → tests 확인
3. Gate 1 threshold → tests 확인
4. Source 인프라 (hybrid.py + recall.py + DB) → tests 확인
5. RELATION_RULES 확장 → tests 확인
6. Cross-project 로직 → tests 확인
7. 승격 실행 (promote_node 수동 테스트)
8. 기준선 재측정 (Signal 수, promote 건수, NDCG)

## 각 단계 후 체크
- pytest 169 PASS 유지
- 기존 데이터 무결성 확인
