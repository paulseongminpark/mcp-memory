# Confirmed Decisions

## D1: 방향 — 시스템 완성
자기 성장 루프 전체 관통 + 관계 품질 강화. 개별 버그가 아닌 시스템 레벨.

## D2: Gate 2 — Bayesian 제거, visit_count threshold
Beta(1,10) prior는 현재 규모(401 queries, 3637 nodes)에서 수학적 불가.
visit_count >= 10으로 교체. 60개 노드가 즉시 후보.

## D3: Gate 1 — threshold 완화 + source 인프라
threshold 0.55→0.25. cross_ratio만으로 통과 가능하게.
source 태깅은 인프라로 같이 넣되, Gate 1이 즉시 의존하지 않음.

## D4: nodes.frequency → deprecated
visit_count와 동일 의미. Gate 2에서 visit_count 직접 사용.

## D5: RELATION_RULES 확장
17→40+ 타입 쌍. cross-project 전용 로직 추가.
LLM 비용 0, config 변경만.

## D6: 구현 순서
1. Deprecated 정리 (안전)
2. Gate 2 visit_count (1줄)
3. Gate 1 threshold (1줄)
4. Source 인프라 (3파일 + ALTER TABLE)
5. RELATION_RULES 확장 (config)
6. Cross-project 로직 (infer_relation)
