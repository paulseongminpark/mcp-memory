# Storage Layer Review - Round 2 (Architecture)

> Reviewer: Claude (Opus)
> Date: 2026-03-06
> Perspective: Architecture & Design Quality
> Files Reviewed: storage/sqlite_store.py, storage/hybrid.py, storage/vector_store.py, storage/action_log.py

---

## Findings

### [Severity: HIGH]

**H-01** Connection Management Anti-Pattern: No Pooling, No Context Manager
- File: `storage/sqlite_store.py:11-18`
- Description: `_connect()` 는 매 호출마다 새 `sqlite3.Connection`을 생성하고, 각 public 메서드가 `conn = _connect()` ... `conn.close()` 패턴을 수동 반복한다. Context manager도 없고, connection pool도 없다.
- Impact:
  - **성능**: 매 호출마다 connect/close 오버헤드. WAL pragma, foreign_keys pragma 매번 재설정.
  - **안전성**: 예외 발생 시 `conn.close()`에 도달하지 못할 수 있음 (try/finally 미사용).
  - **코드 중복**: 8개 메서드 모두 동일 3줄 패턴 반복.
- Recommendation:
  ```python
  @contextmanager
  def _db():
      conn = _connect()
      try:
          yield conn
      finally:
          conn.close()
  ```
  모든 메서드를 `with _db() as conn:` 으로 전환. 장기적으로 connection reuse (module-level singleton + thread-local) 도입.

**H-02** Transaction Boundary Inconsistency in insert_edge()
- File: `storage/sqlite_store.py:266-279`
- Description: `insert_edge()` 는 edge INSERT 후 relation 교정 시 `correction_log` INSERT도 같은 트랜잭션에 포함하지만, `conn.commit()` 이 한 번만 호출된다. 만약 correction_log INSERT에서 예외가 발생하면, 메인 edge INSERT도 롤백된다. 의도된 동작인지 불분명.
- Impact: Edge 삽입과 교정 로그가 원자적으로 묶여있어, 로그 실패가 edge 생성을 실패시킬 수 있음.
- Recommendation: `SAVEPOINT` 를 사용하여 correction_log를 optional sub-transaction으로 격리하거나, correction_log 실패를 catch하여 edge는 보존.

**H-03** hybrid.py의 God-Function: hybrid_search() 110+ Lines, 9 Responsibilities
- File: `storage/hybrid.py:385-496`
- Description: `hybrid_search()` 가 단일 함수에 9개 파이프라인 단계를 모두 포함:
  1. Vector 검색, 2. FTS 검색, 3. Seed 수집, 4. UCB 그래프 탐색, 5. RRF 병합, 6. 필터+enrichment 가중치, 7. BCM 학습, 8. SPRT 승격 판정, 9. 활성화 로깅.
- Impact:
  - **테스트 어려움**: 개별 단계를 독립 테스트하기 어려움.
  - **수정 위험**: 한 단계 변경이 다른 단계에 부수 효과.
  - **가독성**: 함수 하나에 검색 + 학습 + 판정 + 로깅이 혼재.
- Recommendation: Pipeline pattern 도입. 각 단계를 독립 함수로 추출하되, `hybrid_search()` 는 파이프라인 오케스트레이터 역할만.
  ```python
  def hybrid_search(query, ...):
      vec, fts = _search_channels(query, top_k, where)
      seeds = _collect_seeds(vec, fts)
      neighbors = _ucb_graph_traverse(seeds, query, mode)
      scores = _rrf_merge(vec, fts, neighbors)
      candidates = _filter_and_enrich(scores, ...)
      _bcm_learn(candidates, ...)
      _sprt_evaluate(candidates, ...)
      _log_activations(candidates, query, session_id)
      return candidates
  ```

**H-04** Module-Level Mutable State: Graph Cache Thread-Safety
- File: `storage/hybrid.py:26-28`
- Description: `_GRAPH_CACHE`, `_GRAPH_CACHE_TS` 가 모듈 레벨 전역 변수로 관리됨. TTL 5분 캐시. 스레드 안전 장치(lock) 없음.
- Impact: 현재 단일 프로세스 MCP 서버에서는 안전하나, 향후 멀티스레드/async 환경 전환 시 race condition 발생. 캐시 무효화와 재구성이 동시에 일어날 수 있음.
- Recommendation: `threading.Lock` 추가 또는 `functools.lru_cache` + TTL wrapper 사용. 최소한 주석으로 "single-process assumption" 명시 (현재 라인 35에 있으나 강화 필요).

---

### [Severity: MEDIUM]

**M-01** vector_store.py Singleton vs sqlite_store.py Per-Call: 연결 전략 불일치
- File: `storage/vector_store.py:9-23` vs `storage/sqlite_store.py:11-18`
- Description: vector_store는 `_client`/`_collection` 을 모듈 레벨 singleton으로 재사용하는 반면, sqlite_store는 매 호출마다 새 connection을 생성한다. 같은 storage 레이어 내에서 연결 관리 패턴이 불일치.
- Impact: 설계 일관성 저하. 새 기여자가 "어떤 패턴을 따라야 하는지" 혼란.
- Recommendation: storage 레이어 전체에 일관된 연결 전략 수립. SQLite도 module-level connection reuse가 가능 (WAL 모드에서 안전).

**M-02** Error Handling Philosophy 불일치
- File: 전체 storage 레이어
- Description:
  - `sqlite_store.search_fts()`: `except Exception: return []` (silent fail)
  - `sqlite_store.log_correction()`: `except Exception: pass` (silent fail)
  - `sqlite_store.insert_node()`: 에러 처리 없음 (예외 전파)
  - `hybrid.py._bcm_update()`: `except Exception: pass` (silent fail, 검색 계속)
  - `hybrid.py.hybrid_search()` vec: `except Exception: vec_results = []` (graceful degrade)
  - `action_log.record()`: `except Exception: return None` (silent fail)
  - `vector_store.add()`: 에러 처리 없음 (예외 전파)
- Impact: "어떤 에러가 치명적이고 어떤 에러가 무시 가능한지" 일관된 정책 없음. 디버깅 시 실패 원인 추적 어려움 (bare except + no logging).
- Recommendation: 3-tier 에러 정책 수립:
  1. **Critical** (데이터 무결성): 예외 전파 + 트랜잭션 롤백 (insert_node, insert_edge)
  2. **Degradable** (검색 품질): graceful degrade + warning 로그 (vec_search, fts_search, graph_traverse)
  3. **Optional** (부수 기능): silent fail + debug 로그 (action_log, correction_log, BCM, SPRT)

**M-03** action_log: Write-Only Module, No Query API
- File: `storage/action_log.py`
- Description: `record()` 단 1개 함수만 구현. 조회 메서드가 전혀 없음. `activation_log` VIEW는 sqlite_store.py의 init_db()에서 정의되지만, 이를 쿼리하는 API가 action_log 모듈에 없음.
- Impact:
  - 로깅 데이터 활용을 위해 외부에서 raw SQL 직접 실행 필요.
  - action_log의 "감사 추적" 역할이 반쪽 — 쓰기만 있고 읽기 없음.
  - SPRT score_history, BCM theta_m 등이 action_log 데이터에 의존하는데, 조회 경로가 분산.
- Recommendation: 최소한 `query_by_node(node_id)`, `query_by_session(session_id)`, `count_by_type(action_type)` 추가.

**M-04** BCM _bcm_update()의 3N+K DB Write 패턴
- File: `storage/hybrid.py:165-278`
- Description: BCM 학습이 recall() 호출마다 실행되며, 활성 edge 수(N)에 비례하는 UPDATE 쿼리 발생:
  - N × edge frequency UPDATE
  - N × node theta_m/activity_history UPDATE
  - K × node visit_count UPDATE
  - 1 × conn.commit()
- Impact: recall()이 검색만이 아니라 대량 쓰기도 유발. 결과 개수와 엣지 밀도에 따라 수십~수백 UPDATE. 단일 commit이므로 원자성은 보장되나, latency 증가.
- Recommendation:
  - `executemany()` 로 배치화하여 SQLite 왕복 감소.
  - BCM 업데이트를 비동기/deferred로 분리 (검색 결과 반환 후 백그라운드 학습).

**M-05** sqlite_store.py 스키마: nodes 테이블 55 컬럼 과잉
- File: `storage/sqlite_store.py:24-56`
- Description: `nodes` 테이블이 55개 컬럼을 가짐. Core(id, type, content), Quality(confidence, quality_score 등), Enrichment(enrichment_status 등), Maturity(theta_m, visit_count 등), Promotion 등 여러 관심사가 한 테이블에 혼재.
- Impact:
  - `SELECT *` 쿼리가 불필요한 데이터까지 로드 (대부분의 쿼리에서 10개 미만 컬럼만 필요).
  - 스키마 진화 시 ALTER TABLE 복잡도 증가.
  - 관심사 분리(SoC) 위반.
- Recommendation: 현 단계에서 테이블 분리는 과도한 리팩토링. 대신:
  1. 조회 메서드에서 `SELECT *` 대신 필요 컬럼만 명시.
  2. 향후 성장 시 EAV 또는 vertical partitioning 고려 (maturity/enrichment를 별도 테이블로).

**M-06** FTS5와 Trigger 동기화 취약점
- File: `storage/sqlite_store.py:100-122`
- Description: FTS5 인덱스(`nodes_fts`)는 INSERT/DELETE/UPDATE trigger로 동기화되는데, UPDATE trigger의 대상 컬럼이 `content, type, tags, metadata, summary, key_concepts`로 한정. 만약 이외 경로로 content가 변경되면(예: raw SQL) FTS5와 비동기화 발생.
- Impact: FTS 검색 결과가 실제 데이터와 불일치할 수 있음. enrichment 과정에서 summary/key_concepts가 변경될 때 trigger가 작동하므로 현재는 안전하나, 직접 SQL 사용 시 위험.
- Recommendation: 문서화 — "모든 content/metadata 변경은 반드시 ORM 메서드를 통해야 함." init_db()에 주석 추가.

---

### [Severity: LOW]

**L-01** hybrid.py의 sqlite_store._connect() 직접 호출
- File: `storage/hybrid.py:200, 295, 340`
- Description: hybrid.py가 sqlite_store의 private 함수 `_connect()` 를 직접 호출하여 DB 연결을 얻음. Public API를 우회하는 레이어 경계 위반.
- Impact: sqlite_store의 연결 관리 전략 변경 시 hybrid.py도 수정 필요. 캡슐화 위반.
- Recommendation: sqlite_store에 `get_connection()` public 메서드 추가하거나, hybrid.py가 필요한 쿼리를 sqlite_store의 public API로 위임.

**L-02** vector_store.py 메타데이터 타입 필터링
- File: `storage/vector_store.py:30`
- Description: ChromaDB 메타데이터에 `str, int, float, bool` 만 저장 가능. list/dict는 조용히 제외됨.
- Impact: 메타데이터에 tags(list)나 복합 데이터를 저장하려는 향후 시도가 실패.
- Recommendation: list → JSON string 변환 또는 명시적 경고 로그 추가.

**L-03** action_log의 Retention Policy 부재
- File: `storage/action_log.py` (전체)
- Description: action_log 테이블에 삭제/아카이브 메커니즘 없음. 모든 액션이 영구 보존됨.
- Impact: 장기 운영 시 테이블 크기 무한 증가. 현재 규모(~3,255 노드)에서는 문제 아니나, recall 당 2+ rows 추가로 선형 성장.
- Recommendation: 90일 이상 로그 아카이브 또는 집계 후 삭제 정책. `daily_enrich`에 Phase 7로 추가 가능.

**L-04** init_db() 내 action_log FK 제약의 실용성
- File: `storage/sqlite_store.py:149-151`
- Description: `action_log.session_id` 가 `sessions.session_id` FK 참조. 하지만 많은 action_log 기록이 session 외부에서 발생 (enrichment, migration 등). FK 제약이 `NULL` 허용이므로 현재는 작동하나, 의미적으로 모호.
- Impact: session_id가 NULL인 레코드가 대다수일 수 있음. FK의 실질적 가치 감소.
- Recommendation: FK 유지하되, 문서에 "session_id=NULL은 비대화형 액션을 의미" 명시.

---

### [Severity: INFO]

**I-01** 인덱스 전략 평가: 적절
- File: `storage/sqlite_store.py:124-160, 205-208`
- Description: 총 13+ 인덱스. nodes(5), edges(4), action_log(6), type_defs(2), relation_defs(2). `idx_action_node_activated`은 partial index(WHERE 절)로 activation_log VIEW 최적화. 복합 인덱스 `(target_type, target_id)` 도 적절.
- Assessment: 현재 데이터 규모(~3,255 nodes, ~6,324 edges)에서 충분. 과도한 인덱싱도 아님.

**I-02** hybrid.py의 Graceful Degradation 설계: 우수
- File: `storage/hybrid.py` (전체)
- Description: 검색 파이프라인의 각 단계(vec, fts, graph, BCM, SPRT, action_log)가 독립적으로 실패 가능하며, 실패해도 다음 단계로 진행. 부분 결과라도 반환.
- Assessment: "검색은 반드시 결과를 반환한다"는 설계 원칙이 일관되게 적용됨. 학습/로깅 실패가 사용자 경험에 영향 없음.

**I-03** action_log의 Optional Connection 패턴: 잘 설계됨
- File: `storage/action_log.py:82-110`
- Description: `record(conn=external_conn)` 으로 외부 트랜잭션 참여 가능, `record()` 으로 독립 실행 가능. "쓰기 전용 감사 로그"라는 단일 책임 명확.
- Assessment: 트랜잭션 참여 모드는 향후 "remember + action_log를 하나의 트랜잭션으로" 패턴에 활용 가능. 확장성 좋음.

**I-04** RRF k=60 선택: 업계 표준
- File: `storage/hybrid.py:431-438`
- Description: Reciprocal Rank Fusion의 k=60은 원 논문(Cormack et al. 2009) 권장값. 이상치 저항적이며 순위 기반이므로 점수 스케일 차이 무관.
- Assessment: 적절한 설계 선택.

---

## Architecture Assessment

### Layer Boundary Clarity: 6/10

| Aspect | Score | Note |
|--------|-------|------|
| sqlite_store ↔ tools | 8/10 | Public API 경유, 깔끔 |
| hybrid ↔ sqlite_store | 5/10 | `_connect()` 직접 호출 (L-01) |
| vector_store ↔ embedding | 7/10 | openai_embed 분리, 인터페이스 명확 |
| action_log ↔ hybrid | 6/10 | 동적 import + ImportError catch (느슨하나 비표준) |
| config 의존 | 7/10 | 모든 모듈이 config import — 중앙 집중식, 적절 |

### DB Abstraction Quality: 5/10

- sqlite_store가 "thin wrapper" 수준. ORM도 아니고, Repository 패턴도 아닌 중간 지대.
- `get_node()`, `get_edges()` 는 적절한 추상화이나, hybrid.py가 raw SQL을 직접 실행하는 부분이 추상화를 무너뜨림.
- vector_store는 ChromaDB API를 잘 감싸고 있음.

### Transaction Handling: 5/10

- 각 메서드가 독립 트랜잭션 — 단순하나 cross-operation 원자성 없음.
- `remember()` 가 `insert_node()` + `insert_edge()` × N + `action_log.record()` × N을 호출할 때, 각각 별도 트랜잭션. 중간 실패 시 partial state.
- action_log의 `conn` 파라미터는 이를 해결할 수 있으나 실제 사용되지 않음.

### Connection Management: 4/10

- sqlite_store: per-call (비효율)
- vector_store: singleton (효율)
- hybrid.py: sqlite_store._connect() 직접 사용 (경계 위반)
- 일관성 없음.

### Index Strategy: 8/10

- 적절한 수와 종류의 인덱스. Partial index 활용. 과도하지 않음.
- FTS5 trigger 동기화도 구현됨.

---

## Coupling Matrix

```
              sqlite_store  hybrid  vector_store  action_log  config
sqlite_store       -          ←H        -            ←L         ←M
hybrid             H→         -         M→           L→(dyn)    ←H
vector_store       -          -         -            -          ←L
action_log         M→         -         -            -          ←L
config             -          -         -            -          -

H=High, M=Medium, L=Low, ←=imported by, →=imports
```

- **hybrid → sqlite_store**: 가장 강한 커플링. `_connect()` 직접, `search_fts()`, `get_node()`, `get_all_edges()` 사용.
- **hybrid → config**: 15+ 상수 import. 불가피하나 가장 많은 의존.
- **action_log → sqlite_store**: `_connect()` 1회. 느슨.

---

## Coverage

- Files reviewed: 4/4
- Public methods verified: 14/14
- Architecture aspects checked: 9/9 (boundary, abstraction, transaction, connection, index, error handling, state management, coupling, code duplication)

## Summary

- CRITICAL: 0
- HIGH: 4
- MEDIUM: 6
- LOW: 4
- INFO: 4

**Top 3 Most Impactful Findings:**
1. **H-03** hybrid_search() God Function — 110+ lines, 9 responsibilities. 테스트·유지보수·확장 모두에 영향. Pipeline 분해가 아키텍처 품질을 가장 크게 개선할 수 있는 포인트.
2. **H-01** Connection Management Anti-Pattern — context manager 없는 수동 connect/close가 storage 레이어 전체의 안전성·성능·코드 품질을 저하. 가장 적은 노력으로 가장 넓은 영향.
3. **M-02** Error Handling 불일치 — 3-tier 에러 정책 부재로 디버깅 어려움, 장애 추적 불가. 일관된 정책 수립이 운영 안정성의 기반.
