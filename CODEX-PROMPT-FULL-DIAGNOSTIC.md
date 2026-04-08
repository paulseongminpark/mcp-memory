# Codex 전체 진단 요청: 온톨로지 + Retrieval + DB + Embedding + 모든 것

## 최종 목표

> "Claude가 기억을 가진 채 시작하고, 그 기억이 성장/교정되고, 다시 Claude의 운영에 환류된다."

이 루프가 닫혀야 한다. recall()이 정확한 기억을 꺼내고, 그 기억이 Claude 세션에 반영되고, Claude가 새로운 기억을 저장하면 온톨로지가 성장한다.

**지금 달성한 것:** 온톨로지 자체는 강해졌다. core 123, semantic edge 73%, 인과 체인 1440.
**지금 문제:** recall()이 맞는 걸 못 꺼낸다. vector-only(0.318)보다 hybrid(0.232)가 낮다. 가공할수록 악화.

---

## 현재 DB 상태 (실측 2026-04-08)

### 노드
- **active nodes**: 5,261 (archived: 7)
- **타입 분포**: Decision 1071, Tool 576, Insight 512, Pattern 464, Observation 437, Question 431, Narrative 341, Principle 317, Framework 258, Project 255, Goal 188, Failure 155, Experiment 99, Signal 69, Identity 62, Unclassified 19, Correction 7
- **node_role**: knowledge_candidate 4408, work_item 345, session_anchor 340, knowledge_core 123, external_noise 37, correction 7, blank 1
- **epistemic_status**: provisional 5087, validated 130, outdated 41, flagged 3

### 엣지
- **active edges**: 11,015 (원래 7,009 → 이번 세션에서 +4,006)
- **generation_method**: enrichment 4147, semantic_auto 4106, session_anchor 1687, orphan_repair 732, co_retrieval 168, rule 138, fallback 37
- **relation 상위**: contains 1850, supports 1480, led_to 1105, expressed_as 840, part_of 795, generalizes_to 590, resolved_by 556, resulted_in 516, mirrors 481

### 품질
- **quality_score**: null/0: 54, <0.3: 20, 0.3-0.6: 133, 0.6-0.8: 1763, >=0.8: 3291 → **96%가 0.6 이상 (차별력 없음)**
- **enrichment**: E7 완료 4439 (84.4%), E12 완료 239 (4.5%), 미enriched 75 (1.4%)
- **연결 밀도**: 0 edge: 0, 1 edge: 646, 2 edges: 882, 3 edges: 1148, 4+ edges: 2586

### Chroma (벡터 스토어)
- **memories**: 5,262 (DB 5,261과 1개 차이 — 세션 중 1개 추가됐을 수 있음)
- **memory_nodes**: 5,260 (이원화 상태)
- **embedding model**: text-embedding-3-large (3072 dim)
- **embedding 포맷**: content-only (이전: [Type]+summary+key_concepts+content[:200])

---

## 이번 세션에서 한 작업 (05_ontology-maturation_0408)

### 코드 변경
1. **config.py**: GRAPH_BONUS 0.12→0.005 복원, GRAPH_EXCLUDED_METHODS 추가, maturity gating 함수
2. **hybrid.py**: 
   - scoring 단순화: enrichment_bonus, source_bonus, role_penalty, confidence_bonus 제거 (tier + contradiction만 남김)
   - graph traversal: operational edge 제외 (GRAPH_EXCLUDED_METHODS)
   - graph-only 보호 슬롯 제거
   - maturity gating 분기 추가
   - reranker 호출 전 score 정규화 시도 → 악화 → 되돌림
3. **recall.py**: overfetch(top_k*3) + 후처리 필터 후 top_k 절단, mode=mode→mode=search_mode 버그 수정
4. **reranker.py**: RRF score 정규화 시도 → 악화(0.075) → 되돌림. 현재 원본 blend (CE norm만)
5. **sqlite_store.py**: insert_node()에 중앙 normalize (_normalize_node 개념) 추가
6. **context_selector.py**: knowledge_core 전용 쿼리 추가
7. **session_context.py**: proven_knowledge.md → DB knowledge_core direct 전환
8. **promote_node.py**: 승격 후 render_proven_knowledge.py 자동 호출 추가

### DB 변경
1. **knowledge_core 승격**: 9→123 (114개 승격, precision 0.90)
2. **legacy_unknown 재분류**: 1397→0 (1362 enrichment + 35 fallback)
3. **고립 노드 연결**: semantic 0-1 edge 61.2%→16.5% (~2500 edge 추가)
4. **인과 체인**: +1440 causal edge (Decision→led_to 552, Decision→resulted_in 460, Failure→resolved_by 103, Signal→realized_as 38, Question→resolved_by 287)
5. **blank node_role 수정**: 1→0 (id=6267, hook:PreCompact:relay)
6. **Chroma ghost 제거**: 1건 (id=6268)

---

## NDCG 이력

| 시점 | NDCG@5 | hit_rate | 조건 |
|------|--------|----------|------|
| 원본 baseline (commit 0a77943, 03-27) | **0.364** | — | 단순 scoring, reranker 없음, GRAPH_BONUS=0.005 |
| 작업 시작 전 | 0.283 | 0.780 | reranker ON (weight=0.35), GRAPH_BONUS=0.005 |
| 작업 시작 전 | 0.237 | 0.756 | reranker OFF |
| scoring 단순화 + edge-class 후 | **0.232** | 0.683 | reranker ON (weight=0.35) |

**핵심:** 0.364 → 0.232. 온톨로지는 강화됐지만 retrieval은 악화.

---

## 진단 요청 (전체 스코프)

### 1. Retrieval 파이프라인 전체 분석

관련 파일: `storage/hybrid.py`, `storage/reranker.py`, `tools/recall.py`, `config.py`

질문:
- **hybrid_search()의 현재 scoring 로직이 적절한가?** tier_bonus + contradiction_penalty만 남긴 게 너무 극단적인가?
- **제거한 4개 신호 중 복원해야 할 것은?** 하나씩 복원하며 NDCG 측정해줘:
  - enrichment_bonus (quality*0.2 + temporal*0.1) → NDCG?
  - confidence_bonus ((c-0.5)*0.05) → NDCG?
  - role_penalty (session_anchor -0.08 등) → NDCG?
  - source_bonus (claude +0.05 등) → NDCG?
- **reranker weight 최적값은?** config.py의 RERANKER_WEIGHT를 [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.50]으로 변경하며 각각 subprocess로 `python scripts/eval/ndcg.py` 실행. 현재 값은 0.00 (Paul이 테스트 중 변경).
- **RERANKER_GAP_THRESHOLD 최적값은?** [0.01, 0.03, 0.05, 0.10]
- **reranker 자체가 도움이 되는가?** RERANKER_ENABLED=False일 때 NDCG는?
- **ms-marco-MiniLM이 한국어 짧은 노드(40-200자)에 적합한가?** 다른 모델 제안은?

### 2. Embedding 품질 분석

관련 파일: `embedding/openai_embed.py`, `storage/vector_store.py`, `scripts/reembed_v4.py`

질문:
- **현재 embedding은 content-only인데, 이전에는 [Type]+summary+key_concepts+content[:200] 포맷이었다. 어느 쪽이 NDCG에 유리한가?**
- **memories vs memory_nodes 컬렉션: 둘 다 5260개인데 어떤 차이가 있는가? 어느 쪽이 recall에 쓰이는가?**
- **re-embed가 필요한가?** 현재 embedding이 최신 content와 일치하는지 확인. enrichment 후 content가 바뀌었다면 embedding이 stale일 수 있다.
- **embedding dimension 3072가 이 규모(5260 노드)에 과한가?** 차원 축소가 도움이 될 수 있나?

### 3. Graph / Edge 품질 분석

질문:
- **semantic_auto 4106개 edge의 품질은?** connect_islands.py와 connect_causal.py가 생성한 edge가 실제로 의미 있는지 샘플 검증.
- **contains 1850개가 비정상적으로 많다.** 이 relation이 어디서 생성되는지, 실제 의미가 있는지.
- **orphan_repair 732개를 유지할 이유가 있는가?** traversal에서 제외했지만 DB에 남아있다.
- **edge 11,015개가 5,261 노드에 대해 과한가?** 평균 4.2 edge/node. 노이즈 edge가 recall을 오염시키는지.
- **graph traversal이 현재 도움이 되는가?** semantic-only로 제한했지만, GRAPH_BONUS=0.005가 의미 있는 기여를 하는지. graph channel ON/OFF NDCG 비교.

### 4. Enrichment 파이프라인 분석

질문:
- **quality_score 96%가 0.6 이상. 이 enrichment 로직이 너무 관대한가?** quality_score가 차별력 없으면 enrichment의 의미가 약화.
- **E7 84%, E12 4.5%. E7이 뭐고 E12가 뭐인지.** 어떤 enrichment 단계인지.
- **미enriched 75개(1.4%)는 왜 빠졌는지.**
- **enrichment가 embedding에 반영되는가?** enrichment 후 summary, key_concepts가 바뀌면 embedding도 갱신되어야 하는데.

### 5. 온톨로지 구조 분석

질문:
- **knowledge_core 123개의 프로젝트 분포가 편향되어있는가?** monet-lab/tech-review에 집중되어 있으면 다른 프로젝트 recall이 약화.
- **provisional 5087개 중 knowledge_core 승격 기준에 근접한 것은 몇 개인가?**
- **Unclassified 19개는 왜 분류 안 됐는가?**
- **중복 노드가 있는가?** content_hash로 확인. 승격 샘플에서 중복 1쌍(id=3745, 3679) 발견됨.

### 6. 0.364 baseline과의 정확한 차이

`git show 0a77943:storage/hybrid.py`와 현재 hybrid.py를 비교해서:
- **0.364를 달성한 코드에 있고, 현재 코드에 없는 것은?**
- **현재 코드에 있고, 0.364 코드에 없는 것은?**
- **어떤 변경이 가장 큰 NDCG 하락을 야기했는가?**

### 7. 제안

위 1~6 전체를 종합하여:
- **NDCG 0.4+ 달성을 위한 구체적 코드 변경안**
- **DB 정리가 필요한 항목 (edge 삭제, 노드 재분류 등)**
- **re-embed가 필요한가, 한다면 어떤 포맷으로**
- **reranker 모델 교체가 필요한가**
- **enrichment quality_score 재정의 방안**
- **graph traversal ON/OFF 결정**
- **단기(이번 주) vs 중기(이번 달) 로드맵**

---

## 실행 가이드

### NDCG 측정 방법
```bash
cd /c/dev/01_projects/06_mcp-memory
PYTHONIOENCODING=utf-8 python scripts/eval/ndcg.py
```
82 queries × recall() 실행. reranker ON이면 ~3분, OFF면 ~1분.

### config 변경 후 측정
config.py를 직접 수정 → 별도 python process로 ndcg.py 실행. **import 캐싱 때문에 런타임 패치 불가.**

### goldset
`scripts/eval/goldset_v4.yaml` — FROZEN. 82 queries. 변경 금지.

### 코드 수정 하지 마라. 읽고 진단하고 실험(NDCG 측정)만. 수정안은 제안으로.

---

## 파일 맵

```
storage/hybrid.py       — hybrid_search(): Vector + FTS5 + Graph RRF + scoring + reranker
storage/reranker.py     — cross-encoder rerank: CE norm + RRF blend
storage/vector_store.py — ChromaDB wrapper, collection=memories
storage/sqlite_store.py — SQLite wrapper, insert_node, insert_edge
tools/recall.py         — recall(): overfetch + 후처리 + formatting
tools/context_selector.py — select_context(): 세션 시작 데이터 선택
config.py               — 모든 상수, maturity gating, GRAPH_EXCLUDED_METHODS
scripts/eval/ndcg.py    — NDCG@K 측정 스크립트
scripts/eval/goldset_v4.yaml — FROZEN goldset (82 queries)
embedding/openai_embed.py — text-embedding-3-large
scripts/reembed_v4.py   — re-embed 스크립트
scripts/connect_islands.py — 고립 노드 연결
scripts/connect_causal.py — 인과 체인 보강
data/memory.db          — SQLite DB
data/chroma/            — ChromaDB 벡터 스토어
```
