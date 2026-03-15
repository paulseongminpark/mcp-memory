# Research R1 — 온톨로지 현황 정밀 측정 결과

## 1. 초기 가설 vs 실제 (Fact-Check)

| 항목 | 초기 주장 | 실제 측정 | 판정 |
|---|---|---|---|
| generic 관계 87.2% | connects_with 과다 | connects_with = 0.3% (19/7249) | ❌ 오류 |
| init_db() last_activated 부재 | 컬럼 미존재 | 컬럼 존재 (nodes 테이블) | ❌ 오류 |
| promote_node 3-gate 데이터소스 부재 | 사실상 미작동 | **Gate 1 영구 차단** (recall_log `source` 컬럼 부재) | ✅ 정확 (원인은 다름) |
| E14(관계 정밀화) 0% | 미실행 | relation_extractor.py 존재하나 실행 증거 미확인 | ⚠️ 부분 정확 |
| BCM/UCB silent rollback | last_activated 부재 → 롤백 | last_activated 컬럼 존재, BCM/UCB config 정상 | ❌ 오류 |

## 2. 관계 분포 (7,249 edges)

### Top 10
| 관계 | 수량 | 비율 |
|---|---|---|
| supports | 1,271 | 17.5% |
| part_of | 1,025 | 14.1% |
| contains | 772 | 10.6% |
| expressed_as | 753 | 10.4% |
| generalizes_to | 629 | 8.7% |
| instantiated_as | 494 | 6.8% |
| led_to | 320 | 4.4% |
| enabled_by | 268 | 3.7% |
| parallel_with | 200 | 2.8% |
| exemplifies | 146 | 2.0% |

### Fallback-Probable Relations (infer_relation 자동 추론 가능성)
- `connects_with` (final fallback): 19 (0.3%)
- `generalizes_to` (layer fallback: lower→higher): 629 (8.7%)
- `expressed_as` (layer fallback: higher→lower): 753 (10.4%)
- `supports` (same layer+type fallback): 1,271 (17.5%)
- `parallel_with` (same layer, diff type fallback): 200 (2.8%)
- **합계: 2,872 / 7,249 = 39.6%**

→ "generic 87.2%"는 아니지만, **fallback-probable 39.6%**은 여전히 높음. 이 edges가 실제로 정밀한지 fallback인지 구분 불가 (edge 생성 출처 추적 없음).

### 48 relation types 정의, 50 active in relation_defs (0 deprecated)

## 3. 타입 분포 (3,637 active nodes)

| 타입 | 수량 | 비율 | Layer |
|---|---|---|---|
| Decision | 697 | 19.2% | L1 |
| Tool | 520 | 14.3% | L1 |
| Pattern | 354 | 9.7% | L2 |
| Insight | 353 | 9.7% | L2 |
| Question | 256 | 7.0% | L0 |
| Principle | 240 | 6.6% | L3 |
| Project | 235 | 6.5% | L1 |
| Framework | 232 | 6.4% | L2 |
| Narrative | 185 | 5.1% | L0 |
| Goal | 176 | 4.8% | L1 |
| Observation | 108 | 3.0% | L0 |
| Failure | 106 | 2.9% | L1 |
| Experiment | 97 | 2.7% | L1 |
| Unclassified | 38 | 1.0% | — |
| Identity | 36 | 1.0% | L3 |
| Signal | 4 | 0.1% | L1 |

### 주목할 점
- **Signal: 4개 (0.1%)** — 승격 파이프라인의 시작점이 사실상 비어 있음
- **Observation: 108개 (3.0%)** — Signal로 승격 가능한 후보지만 Gate 1 차단으로 이동 불가
- **type_defs: 16 active + 34 deprecated = 50 total** (v2.0 → v3.0 통합 완료)

## 4. Promote Node 3-Gate 분석

### 문제: Gate 1 영구 차단

```python
# Gate 1: SWR readiness에서:
rows = conn.execute(
    "SELECT source, COUNT(*) FROM recall_log WHERE node_id=? GROUP BY source",
    (node_id,),
).fetchall()
```

- `recall_log` 테이블 스키마: `id, query, node_id, rank, score, mode, timestamp, recall_id`
- **`source` 컬럼 없음** → 항상 예외 발생 → except 블록에서 `vec_ratio = 0.0`
- readiness = 0.6 × 0.0 + 0.4 × cross_ratio = max 0.4
- threshold = 0.55 → **절대 통과 불가**

### Gate 2: 작동 가능하나 비효율
- total_recall_count = 401 (meta 테이블)
- recall_log: 2,899 entries
- 하지만 Gate 1에서 이미 차단되므로 Gate 2에 도달하지 못함

### Gate 3: MDL — 정상 구현
- related_nodes 기반 cosine similarity 검증
- 역시 Gate 1 차단으로 도달 불가

### 결론
**promote_node()는 skip_gates=True 없이는 작동 불가.** recall_log에 `source` 컬럼 (vector vs FTS5 구분)을 추가하고, 실제 recall 시 이를 기록해야 Gate 1 정상 작동.

## 5. Deprecated 타입 잔류 코드

### config.py
- `TYPE_CHANNEL_WEIGHTS`: Connection, Evolution, Agent, Skill, Workflow (5개 deprecated)
- `TYPE_KEYWORDS`: Workflow, Agent, Skill, Evolution, Connection (5개 deprecated)
- `LAYER_IMPORTANCE`: layer 4, 5 참조 (v3에서 최대 layer = 3)

### ontology/validators.py
- `suggest_closest_type()`: AntiPattern, Workflow 키워드 매핑 (deprecated)

### enrichment/classifier.py
- 정상: v3 15 active 타입만 프롬프트에 포함

### enrichment/relation_extractor.py
- `get_valid_relation_types()` 사용 — 정상 (DB 기반)

## 6. Edge 생성 출처 추적 부재

현재 edges 테이블에 생성 출처를 기록하는 컬럼이 없음:
- auto_link (remember() 시 infer_relation으로 자동 생성)
- co_retrieval (enrichment 파이프라인 LLM 추출)
- manual (사용자/Claude 직접 생성)
- promote (promote_node realized_as)

→ fallback-probable 39.6%가 실제로 자동 추론인지, LLM이 정확히 같은 타입을 선택한 것인지 구분 불가.

## 7. Gate 1 Fix 난이도 심층 분석 (R2)

### recall → recall_log 기록 흐름

```
recall() (tools/recall.py)
  → hybrid_search() (storage/hybrid.py)
    → vec_results = vector_store.search()    # ChromaDB
    → fts_results = sqlite_store.search_fts() # SQLite FTS5
    → graph_neighbors = _ucb_traverse()      # Graph
    → typed_vec_by_type = {}                 # Layer A typed search
    → RRF 합산 → source 정보 소실
    → return merged_results (dict list, source 태그 없음)
  → post_search_learn(results, query)        # BCM/SPRT 학습
  → _log_recall_results(query, results, mode) # recall_log INSERT
    → INSERT (query, node_id, rank, score, mode, recall_id)
    → source 컬럼 없음
```

### 핵심 발견
1. `hybrid_search()` 내부에서 `vec_results`, `fts_results`는 **별도 변수로 존재** (line 472, 479)
2. RRF 합산(line 517-529)에서 scores dict에 합산 → **출처 정보 소실**
3. 한 노드가 vector + FTS5 **양쪽에서** 등장 가능 → multi-source 추적 필요
4. `_log_recall_results()` (line 168)는 merged 결과만 받음

### Fix 설계 방향
- **Option A (minimal)**: `hybrid_search()`에서 `node["_sources"] = {"vector", "fts5"}` 태깅 → `_log_recall_results()`에 전달 → recall_log에 `sources TEXT` 컬럼 추가 (JSON array)
- **Option B (robust)**: recall_log를 source별로 분리 기록 (같은 recall_id, node_id지만 source가 다른 2행)
- **권장**: Option A — 기존 코드 변경 최소, recall_log 스키마 변경 1컬럼

### Gate 1 정상화 조건
1. recall_log에 source 컬럼 추가 (ALTER TABLE)
2. `hybrid_search()`에서 각 결과에 source 태깅
3. `_log_recall_results()`에서 source 기록
4. `swr_readiness()`의 SQL을 새 스키마에 맞게 수정
5. 기존 2,899 recall_log 행은 source=NULL → vec_ratio 계산에서 제외 처리

## 8. 실제 문제 우선순위 (Research 결론)

| 순위 | 문제 | 영향도 | 난이도 |
|---|---|---|---|
| 1 | Gate 1 영구 차단 (recall_log source 컬럼 부재) | 🔴 Critical — 승격 완전 불능 | 중 |
| 2 | Signal 4개 — 승격 파이프라인 입구 고갈 | 🔴 High — 구조적 병목 | 중 |
| 3 | Deprecated 타입 잔류 (TYPE_CHANNEL_WEIGHTS 등) | 🟡 Medium — 검색 정확도 저하 | 낮 |
| 4 | Edge 생성 출처 추적 부재 | 🟡 Medium — 품질 측정 불가 | 중 |
| 5 | Fallback-probable 39.6% 관계 정밀화 | 🟡 Medium — 그래프 품질 | 높 |
| 6 | LAYER_IMPORTANCE layer 4,5 참조 | 🟢 Low — dead code | 낮 |
