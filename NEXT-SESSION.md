# 다음 세션: Ontology Maturation NDCG 복구

## 즉시 할 것

1. **NDCG 측정** — config.py RERANKER_WEIGHT=0.35 확인 후 `python scripts/eval/ndcg.py`
2. **Codex 결과 반영** — `CODEX-PROMPT-FULL-DIAGNOSTIC.md` 기반 Codex 진단 결과 적용
3. **Gemini 결과 반영** — `GEMINI-PROMPT-FULL-DIAGNOSTIC.md` 기반 진단 결과 적용

## 현재 상태

- **NDCG@5 = 미측정** (score>=0.3 필터 제거 + RERANKER_WEIGHT=0.35 복원 후 아직 안 재봄)
- 이전 측정: 0.232 (weight=0.00 잔류 + score 필터 있었음)
- 목표: 0.4+
- baseline: 0.364 (commit 0a77943)

## 이번 세션에서 한 것 (05_ontology-maturation_0408)

**온톨로지 강화 (완료):**
- knowledge_core: 9→123 (precision 0.90)
- semantic edge: 43%→73% (legacy_unknown 1397→0)
- KB 고립 노드: 61%→16.5% (+2500 semantic_auto edge)
- 인과 체인: +1440 (led_to/resolved_by/realized_as)
- writer contract: 중앙 normalize, blank 0
- Chroma ghost 제거, 5260 일치
- maturity gating 구현 (level 3)
- SoT: session_context.py → DB knowledge_core direct
- promote_node → render 자동 호출

**retrieval 변경 (미해결):**
- scoring 단순화 (enrichment/source/role/confidence 제거)
- graph edge-class 필터 (operational 제외)
- score>=0.3 필터 제거 (scoring 단순화로 전부 0.3 미만이 됨)
- RERANKER_WEIGHT 0.35 복원 (0.00 잔류 수정)
- reranker RRF 정규화 시도 → 악화 → 되돌림

## NDCG 문제 원인 (발견됨)

1. **score>=0.3 필터**: scoring 단순화 후 모든 score가 0.05~0.17. 필터가 100% 절단. → **제거함**
2. **RERANKER_WEIGHT=0.00 잔류**: 테스트 중 변경된 채 남음. reranker 사실상 비활성. → **0.35 복원함**
3. **CE 스케일 불일치**: RRF 0.05~0.17 vs CE norm 0~1. weight 0.35에서 CE가 ~75% 지배
4. **ms-marco 한국어 부적합 가능성**: 영어 문서 검색용 모델, 한국어 짧은 노드에 미검증

## 다음 세션 작업

1. NDCG 측정 (두 문제 수정 후 상태)
2. Codex/Gemini 진단 결과 종합
3. reranker weight grid search (subprocess 방식)
4. 필요 시 scoring 신호 일부 복원
5. 필요 시 re-embed 검토

## 파일 위치
- 계획: `05_ontology-maturation_0408/01_plan.md`
- baseline: `05_ontology-maturation_0408/baseline_snapshot.json`
- Codex 프롬프트: `CODEX-PROMPT-FULL-DIAGNOSTIC.md`
- Gemini 프롬프트: `GEMINI-PROMPT-FULL-DIAGNOSTIC.md`
- goldset: `scripts/eval/goldset_v4.yaml` (FROZEN)
