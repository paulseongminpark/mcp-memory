# Ontology v3 관련 인사이트 필터

- 검토 범위: `docs/ideation/*.md` 전체 73개 파일
- 포함 기준: `type`, `retrieval`, `autonomy`, `co-retrieval`, `dispatch`에 직접 연결되는 설계 문장만 채택
- 제외 기준: validation/pruning/drift/hub/metrics/energy/action_log 일반론처럼 v3 축과 직접 연결이 약한 항목은 제외
- 메모: `dispatch` 태그는 문서에 단어가 직접 없더라도, 분기/라우팅/상황별 경로 선택 설계가 명시된 경우에만 부여

## Type

### 1. 메타 스키마 분리 + remember 분해
출처: `a-r1-1-palantir.md`

원문 핵심:
> `remember()`가 세 가지 역할을 동시에 수행한다: 1. **분류** — `validate_node_type()` + `suggest_closest_type()`으로 타입 결정 2. **저장** — SQLite `insert_node()` + ChromaDB `add()` 3. **연결** — `vector_store.search()` → `infer_relation()` → `insert_edge()`
>
> Palantir의 핵심 교훈: **파서(분류)와 트랜스폼(저장)을 분리하면 온톨로지 진화가 파서 정의 업데이트만으로 가능해진다.**

v3 태그: `type`, `dispatch`, `autonomy`

### 2. deprecated를 전제로 한 버전 관리
출처: `a-r1-4-ontology-versioning.md`

원문 핵심:
> **Wikidata 3-rank**: normal -> preferred -> deprecated (+ reason)
>
> **Gene Ontology**: replaced_by 태그 + 대량 Obsolete 전략

v3 태그: `type`

### 3. 타입 축소는 삭제가 아니라 대체 매핑 기반 deprecate
출처: `a-r1-11-subtraction-data.md`

원문 핵심:
> 19개 미사용 타입 -> 즉시 deprecated
>
> `interpreted_as`, `viewed_through` -> deprecated

v3 태그: `type`

### 4. validator도 schema.yaml이 아니라 type_defs를 읽어야 함
출처: `a-r2-13-migration-sql.md`

원문 핵심:
> `type_defs` 테이블에서 활성 타입 조회. `schema.yaml` 대체.
>
> `type_defs` 기반 검증. deprecated 타입이면 `replaced_by` 반환.

v3 태그: `type`

### 5. live DB를 타입 정본으로 쓰고 deprecated는 자동 교정
출처: `d-r3-11-validators-final.md`

원문 핵심:
> `validators.py` 타입 소스 | `schema.yaml` 기반 set | `type_defs` 테이블 (live DB)
>
> deprecated 타입 처리 | 없음 | `replaced_by` 자동 교정 + 경고

v3 태그: `type`, `autonomy`

### 6. 새 타입 추가 시 수정 지점을 classify 하나로 축소
출처: `a-r2-14-remember-refactor.md`

원문 핵심:
> 변경 전: `remember.py` + `schema.yaml` + `validators.py` + `config.py` 전부 수정
>
> 변경 후: `type_defs`에 INSERT + `classify()` 규칙 추가 (1곳)

v3 태그: `type`, `dispatch`, `autonomy`

### 7. remember 파이프라인은 분리하되 외부 API는 유지
출처: `a-r3-18-remember-final.md`

원문 핵심:
> 기존 MCP API 100% 호환. 내부적으로 `classify → store → link` 파이프라인.
>
> 방화벽 F3: L4/L5 노드에 대한 자동 edge 생성을 차단한다.

v3 태그: `type`, `dispatch`, `autonomy`

## Retrieval / Co-Retrieval

### 8. retrieval 소스 자체를 로그로 남겨야 co-retrieval 판단이 가능함
출처: `b-r1-2-swr-transfer.md`

원문 핵심:
> `source TEXT, -- 'vector' | 'fts5' | 'graph'`
>
> `vec_ratio > 0.6` → 의미적 연결 우세 → "신피질 전이 준비"

v3 태그: `retrieval`, `co-retrieval`

### 9. 기본 검색은 3-way hybrid여야 함
출처: `b-r3-14-hybrid-final.md`

원문 핵심:
> `3-way hybrid search: Vector + FTS5 + UCB Graph.`
>
> `Reciprocal Rank Fusion`으로 vector/FTS 랭크를 합치고, `graph_neighbors`에는 `GRAPH_BONUS`를 더한다.

v3 태그: `retrieval`, `co-retrieval`

### 10. RRF는 k=30으로 상위 집중도를 높이는 방향
출처: `c-r1-4-rrf-experiment.md`

원문 핵심:
> `k=30` → 상위 랭크를 더 강하게 가중. 정밀도 vs 재현율 트레이드오프 없이 상위 결과 집중.
>
> 현재 `tier/enrichment` 보너스 시스템과 함께 작동하므로 `k=30` 유리 가능성 높음.

v3 태그: `retrieval`, `co-retrieval`

### 11. k=30으로 가면 RWR surprise는 같이 낮춰야 함
출처: `c-r2-9-cross-session-alignment.md`

원문 핵심:
> **위험**: `k=30` + 높은 `RWR_SURPRISE_WEIGHT` → 저차수 노드의 "의외성"이 관련성을 압도.
>
> **결론**: `k=30 + RWR_SURPRISE_WEIGHT=0.05` 조합이 안전.

v3 태그: `retrieval`, `co-retrieval`

### 12. retrieval은 호출 맥락을 edge에 재기록해야 함
출처: `b-r1-5-reconsolidation.md`

원문 핵심:
> 활성화된 edge에 사용 맥락 기록. 저장 형식: `[{"q": "포트폴리오 설계", "t": "..."}]`
>
> `ctx_log = ctx_log[-CONTEXT_HISTORY_LIMIT:]`  # 최근 5개만

v3 태그: `retrieval`

### 13. 그래프 탐색은 NetworkX BFS보다 SQL CTE로 내려갈 수 있음
출처: `b-r2-11-cte-impl.md`

원문 핵심:
> `SQL Recursive CTE` 기반 그래프 탐색. Chen (2014) DB-optimized SA.
>
> `build_graph() + NetworkX BFS`를 SQL로 대체. `idx_edges_source`, `idx_edges_target` 인덱스 활용.

v3 태그: `retrieval`

### 14. 그래프 비용은 TTL 캐시 후 SQL-only UCB로 단계 전환
출처: `b-r3-16-graph-optimization.md`

원문 핵심:
> `all_edges + NetworkX graph` 캐시 반환 (`TTL=5분`). 캐시 히트 시 빌드 비용 완전 생략.
>
> 효과: 연속 recall 시 `~90%` graph 비용 절감

v3 태그: `retrieval`

## Autonomy / Dispatch

### 15. recall은 패치 포화 시 새 패치로 재검색해야 함
출처: `b-r1-4-patch-foraging.md`

원문 핵심:
> `Marginal Value Theorem`: 수확 체감 → 새 패치로 이동. `project`가 명시된 경우 전환하지 않음 (사용자 의도 존중).
>
> `alt = hybrid_search(query, top_k=top_k, excluded_project=dominant, mode=mode)`

v3 태그: `retrieval`, `dispatch`, `autonomy`

### 16. recall mode는 쿼리 문맥에 따라 탐색 성격을 바꿔야 함
출처: `b-r3-15-recall-final.md`

원문 핵심:
> `mode`: `"auto"` — 쿼리 길이로 탐험 계수 자동 결정, `"focus"` — 강한 연결 우선, `"dmn"` — 미탐색 연결 우선.
>
> **호환성 보장**: `mode` 파라미터만 추가. 기존 호출 전부 동일하게 동작.

v3 태그: `retrieval`, `dispatch`, `autonomy`
