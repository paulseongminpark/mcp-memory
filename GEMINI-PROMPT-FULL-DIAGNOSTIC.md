# Gemini 전체 진단 요청: mcp-memory 온톨로지 + Retrieval + DB + Embedding

## ⛔ 코드 수정 절대 금지. git commit 금지. 읽고 진단하고 실험(NDCG 측정)만. 수정안은 제안으로만.

---

## 최종 목표

> "Claude가 기억을 가진 채 시작하고, 그 기억이 성장/교정되고, 다시 Claude의 운영에 환류된다."

recall()이 정확한 기억을 꺼내야 한다. 현재 못 꺼내고 있다.

## 현재 상황 요약

- **NDCG@5 = 0.218** (목표: 0.4+, 원본 baseline: 0.364)
- 온톨로지 자체는 크게 강화됨 (core 123, semantic edge 73%, 인과 체인 1440)
- 하지만 retrieval(hybrid_search → recall)이 오히려 악화
- **vector-only가 hybrid보다 낫다** — 가공할수록 악화

---

## DB 현재 상태 (2026-04-08 실측)

### 노드 (5,261 active)
| 지표 | 값 |
|------|-----|
| Decision | 1071 |
| Tool | 576 |
| Insight | 512 |
| Pattern | 464 |
| Observation | 437 |
| Question | 431 |
| Narrative | 341 |
| Principle | 317 |
| Framework | 258 |
| Project | 255 |
| Goal | 188 |
| Failure | 155 |
| Experiment | 99 |
| Signal | 69 |
| Identity | 62 |
| Unclassified | 19 |
| Correction | 7 |

### node_role
- knowledge_candidate: 4408
- work_item: 345
- session_anchor: 340
- **knowledge_core: 123** (9에서 승격)
- external_noise: 37
- correction: 7
- blank: 1

### epistemic_status
- provisional: 5087
- validated: 130
- outdated: 41
- flagged: 3

### 엣지 (11,015 active)
| generation_method | 수 | 비율 |
|---|---|---|
| enrichment | 4147 | 37.6% |
| **semantic_auto** | **4106** | **37.3%** (이번 세션 신규) |
| session_anchor | 1687 | 15.3% |
| orphan_repair | 732 | 6.6% |
| co_retrieval | 168 | 1.5% |
| rule | 138 | 1.3% |
| fallback | 37 | 0.3% |

### relation 상위
contains 1850, supports 1480, led_to 1105, expressed_as 840, part_of 795, generalizes_to 590, resolved_by 556, resulted_in 516, mirrors 481

### 품질 지표
- quality_score >= 0.6: **96%** (차별력 없음)
- confidence >= 0.8: 70%
- enrichment E7 완료: 84.4%, E12: 4.5%, 미enriched: 1.4%
- 연결 밀도: 0 edge: 0, 1 edge: 646, 2: 882, 3: 1148, 4+: 2586

### Chroma
- memories: 5,262 (runtime recall이 사용)
- memory_nodes: 5,260 (이원화 상태)
- embedding: text-embedding-3-large, 3072 dim, **content-only**

---

## 이번 세션 변경 사항

### 코드 변경
1. `config.py`: GRAPH_BONUS 0.12→0.005, GRAPH_EXCLUDED_METHODS, maturity gating, **RERANKER_WEIGHT 현재 0.35**
2. `hybrid.py`: scoring 단순화 (enrichment_bonus/source_bonus/role_penalty/confidence_bonus 제거, tier+contradiction만), graph semantic-only traversal, graph-only slot 제거, maturity gating
3. `recall.py`: overfetch(top_k*3), **score>=0.3 필터 제거** (scoring 단순화로 모든 score가 0.3 미만이 됨), mode 버그 수정
4. `reranker.py`: RRF 정규화 시도→악화→되돌림
5. `sqlite_store.py`: 중앙 normalize (node_role/epistemic_status default)
6. `context_selector.py`: knowledge_core 쿼리 추가
7. `session_context.py`: DB direct (proven_knowledge.md → DB knowledge_core)
8. `promote_node.py`: render_proven_knowledge.py 자동 호출

### DB 변경
- knowledge_core: 9→123 (114 승격)
- legacy_unknown: 1397→0 (enrichment으로 재분류)
- 고립 노드 연결: +~2500 semantic_auto edge
- 인과 체인: +1440 causal edge
- Chroma ghost 1건 제거

---

## NDCG 이력

| 시점 | NDCG@5 | hit_rate | 조건 |
|------|--------|----------|------|
| **원본 baseline** (0a77943, 03-27) | **0.364** | — | 단순 scoring, reranker 없음 |
| 작업 시작 전 reranker ON | 0.283 | 0.780 | weight=0.35 |
| 작업 시작 전 reranker OFF | 0.237 | 0.756 | |
| scoring 단순화 후 reranker ON | 0.240 | 0.695 | weight=0.35 |
| score 필터 제거 후 weight=0.00 | 0.218 | 0.646 | weight가 0.00으로 변경됨 |
| **현재** | **측정 필요** | — | weight=0.35 복원, score 필터 제거 |

---

## 내가 발견한 원인들

### 1. score >= 0.3 필터가 거의 모든 결과를 잘라냄
scoring 단순화 후 RRF score 범위가 0.05~0.17. 0.3 threshold에서 100% 필터됨. **이미 제거함.**

### 2. RERANKER_WEIGHT가 0.00으로 남아있었음
테스트 중 변경된 채로. reranker 사실상 비활성. **0.35로 복원함.**

### 3. reranker CE(ms-marco-MiniLM)와 RRF score의 스케일 불일치
RRF score 0.05~0.17, CE norm 0~1. weight 0.35에서: `final = 0.65*0.12 + 0.35*0.7 = 0.323`. CE가 scoring의 ~75% 지배. ms-marco는 영어 문서 검색용이라 한국어 짧은 노드(40~200자)에 부적합할 수 있음.

### 4. 원본 baseline(0.364)에 있던 enrichment_bonus가 제거됨
baseline: RRF + enrichment_bonus(quality*0.2 + temporal*0.1) + tier_bonus. 현재: RRF + tier_bonus + contradiction. enrichment_bonus가 uniform이라 차별력 없다고 판단했지만, 절대값 올리는 역할은 했을 수 있음.

### 5. semantic_auto edge 4106개의 품질이 미검증
connect_islands.py + connect_causal.py로 대량 생성. infer_relation() 의존. 이 edge가 graph traversal에서 노이즈를 주입할 수 있음.

---

## 진단 요청

### A. 먼저 현재 NDCG 측정
```bash
cd /c/dev/01_projects/06_mcp-memory
PYTHONIOENCODING=utf-8 python scripts/eval/ndcg.py
```
config.py: RERANKER_WEIGHT=0.35, RERANKER_ENABLED=True. score>=0.3 필터 제거됨.

### B. Retrieval 파이프라인 분석
1. **0.364 baseline 코드와 현재 코드의 정확한 차이**: `git diff 0a77943 HEAD -- storage/hybrid.py tools/recall.py config.py`
2. **reranker weight grid search** — config.py 직접 수정 → subprocess로 ndcg.py 실행:
   ```bash
   for w in 0.00 0.05 0.10 0.15 0.20 0.25 0.30 0.35 0.50; do
     sed -i "s/RERANKER_WEIGHT = [0-9.]*/RERANKER_WEIGHT = $w/" config.py
     echo -n "w=$w: "
     PYTHONIOENCODING=utf-8 python scripts/eval/ndcg.py 2>/dev/null | grep "ndcg@5"
   done
   sed -i "s/RERANKER_WEIGHT = [0-9.]*/RERANKER_WEIGHT = 0.35/" config.py
   ```
3. **RERANKER_ENABLED=False** 상태 NDCG (순수 RRF 성능)
4. **scoring 신호 복원 실험**: 제거한 4개를 하나씩 복원하며 NDCG 측정
5. **graph channel ON/OFF**: maturity gating에서 graph_channel=False 강제 시 NDCG

### C. Embedding 분석
1. memories vs memory_nodes: 어떤 차이? 어느 쪽이 recall에 쓰이는지 (`storage/vector_store.py` 확인)
2. embedding이 최신 content와 일치하는지: enrichment 후 content 변경 시 embedding stale 가능성
3. content-only vs structured embedding: 이전 포맷 `[Type]+summary+key_concepts+content[:200]`과 비교

### D. DB/Edge 품질
1. **semantic_auto 4106개 샘플 검증**: 랜덤 20개 edge의 양 endpoint content 비교 → 실제 의미 있는 연결인지
2. **contains 1850개가 과다**: 어디서 생성? 의미 있나?
3. **중복 노드**: content_hash 기반 확인

### E. 종합 제안
위 A~D 결과로:
- NDCG 0.4+ 달성 코드 변경안
- re-embed 필요 여부
- reranker 모델 교체 필요 여부
- 삭제/정리할 edge
- 단기/중기 로드맵

---

## 파일 맵

```
storage/hybrid.py         — hybrid_search(): Vector+FTS5+Graph RRF + scoring + reranker
storage/reranker.py       — cross-encoder rerank
storage/vector_store.py   — ChromaDB, collection=memories
storage/sqlite_store.py   — SQLite wrapper
tools/recall.py           — recall(): overfetch + 후처리
tools/context_selector.py — 세션 컨텍스트 데이터
config.py                 — 모든 상수
scripts/eval/ndcg.py      — NDCG 측정
scripts/eval/goldset_v4.yaml — FROZEN goldset (82 queries)
embedding/openai_embed.py — text-embedding-3-large
data/memory.db            — SQLite
data/chroma/              — ChromaDB
```

## ⛔ 다시 한번: 코드 수정 금지. git commit 금지. 진단과 실험만. 수정안은 제안으로.
