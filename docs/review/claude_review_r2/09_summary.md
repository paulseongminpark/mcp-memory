# T2-C-09: Round 2 Architecture Review — Summary

**Reviewer**: rv-c2 (Claude Opus)
**Round**: 2 (Architecture)
**Date**: 2026-03-06
**Scope**: mcp-memory v2.1 전체 — 8개 카테고리 종합

---

## Executive Summary

mcp-memory v2.1의 아키텍처 리뷰 Round 2를 8개 카테고리에서 수행한 결과, **총 102건의 발견사항**(HIGH 19, MEDIUM 36, LOW 22, INFO 25)을 식별했다. 가장 지배적인 아키텍처 문제는 **private API `_connect()` 직접 사용이 시스템 전반에 침투**한 것으로, storage-tools-scripts 3개 레이어에 걸쳐 반복된다. 보안 아키텍처(A-)는 enterprise-grade 수준으로 강점이며, 테스트 아키텍처(B-)와 E2E 흐름 최적성(B)이 상대적 약점이다.

---

## 1. Aggregate Findings

| Category | HIGH | MEDIUM | LOW | INFO | Score |
|----------|------|--------|-----|------|-------|
| C-01 Storage | 4 | 6 | 4 | 4 | 5.6/10 |
| C-02 Tools | 3 | 5 | 3 | 3 | 6.0/10 |
| C-03 Utils/Ontology | 2 | 4 | 3 | 3 | 6.5/10 |
| C-04 Scripts | 2 | 5 | 3 | 3 | 6.0/10 |
| C-05 Spec Alignment | 2 | 5 | 2 | 3 | 6.8/10 |
| C-06 Tests | 2 | 4 | 3 | 3 | 5.9/10 |
| C-07 E2E Scenarios | 3 | 4 | 2 | 3 | 6.7/10 |
| C-08 Security | 1 | 3 | 2 | 3 | 8.7/10 |
| **Total** | **19** | **36** | **22** | **25** | **6.5/10** |

---

## 2. Architecture Scorecard

| Dimension | Score | Key Evidence |
|-----------|-------|-------------|
| **Layer Boundary Clarity** | 5/10 | _connect() 직접 호출이 tools(5/10), scripts(3+), hybrid.py에 침투 |
| **DB Abstraction Quality** | 5/10 | sqlite_store가 thin wrapper — hybrid/tools가 raw SQL 직접 실행 |
| **Transaction Handling** | 5/10 | 각 메서드 독립 트랜잭션, cross-operation 원자성 없음 |
| **Connection Management** | 4/10 | Per-call(sqlite) vs singleton(vector) 불일치, context manager 부재 |
| **Error Handling Consistency** | 4/10 | 3가지 철학 혼재: silent fail / graceful degrade / exception propagation |
| **Code Duplication** | 4/10 | _call_json() 3중, pruning 2중, _get_total_recall_count() 2중 |
| **Config Organization** | 5/10 | 7개 관심사 flat 혼재, infer_relation() 비즈니스 로직, DB_PATH 4곳 하드코딩 |
| **Type System Design** | 7/10 | 50+48 타입, dual-source fallback, deprecation 지원, 3중 진실 원천 감점 |
| **Security Architecture** | 9/10 | 4중 방어(A10+Hub+RBAC+F3), SQL 100% parametrized, LAYER_PERMISSIONS 엄격 |
| **Test Architecture** | 6/10 | conftest.py 부재, fixture 중복 38%, DB 격리 전략 불일치 |
| **Spec Quality** | 7/10 | 수학적 엄밀성 우수(SPRT), 공유 개념 소유권 부재, 코드-스펙 경계 혼재 |
| **E2E Flow Design** | 7/10 | server→tools 직접 라우팅 깔끔, N+1 쿼리 4곳, hybrid_search 9단계 과복잡 |

**Overall Architecture Grade: B- (6.5/10)**

---

## 3. Coupling Matrix (System-Wide)

```
                sqlite_store  vector_store  hybrid  action_log  config  validators  access_ctl  graph
Storage:
  sqlite_store       -            -           ←H        ←L        ←M       -           -         -
  hybrid            H→(pvt)       M→          -         L→(dyn)   ←H       -           -         M→
  vector_store       -            -           -          -         ←L       -           -         -
  action_log        M→(pvt)       -           -          -         ←L       -           -         -

Tools:
  remember          ■ pub        ■ pub       ■          ■          ■        ■           -         -
  recall            ■ _connect   -           ■          -          ■        -           -
  promote_node      ■ _connect   ■ _get_coll -          -          ■        -           -
  analyze_signals   ■ _connect   -           -          -          ■        -           -
  get_becoming      ■ _connect   -           -          -          ■        -           -
  save_session      ■ _connect   -           -          -          -        -           -
  get_context       ■ pub        -           -          -          -        -           -
  inspect_node      ■ pub        -           -          -          -        -           -
  suggest_type      - (via rem)  -           -          -          -        -           -
  visualize         ■ pub        -           ■          -          ■        -           ■

Scripts:
  daily_enrich      ■ _connect   -           -          ■          ■        -           ■
  pruning           ■ direct     -           -          -          ■        -           ■
  hub_monitor       ■ direct     -           -          -          ■        -           -
  calibrate_drift   ■ direct     -           -          -          -        -           -
  safety_net        ■ direct     -           -          -          -        -           -
  export_obsidian   ■ direct     -           -          -          -        -           -

■ pub = public API    ■ _connect = private API    ■ direct = sqlite3.connect() 직접
```

**핵심 관찰**:
1. **sqlite_store 의존도 100%** — 모든 레이어가 의존. 그 중 **50% 이상이 private API 경유**
2. **config 의존도 80%** — 15+ 상수 import. 불가피하지만 가장 넓은 fan-out
3. **hybrid.py가 가장 강한 커플링 허브** — sqlite_store, vector_store, graph, config, action_log 동시 의존

---

## 4. Recurring Patterns (Cross-Category Themes)

### Theme 1: Private API Leakage (`_connect()`)
- **등장**: C-01 L-01, C-02 H-01, C-04 implicit, C-07 H-03, C-08 M-02
- **범위**: 5/10 tools, 3+ scripts, hybrid.py 3곳, action_log 1곳
- **근본 원인**: sqlite_store의 public API가 필요한 쿼리를 모두 커버하지 못함
- **해결**: public method 7개 추가 (upsert_meta, get_nodes_by_type, update_node, upsert_session, get_nodes_batch, get_meta, get_connection)

### Theme 2: Code Duplication Culture
- **등장**: C-02 H-02, C-04 H-01, C-04 H-02, C-04 M-04
- **규모**: _call_json() ~180 LOC × 3, pruning ~100 LOC × 2, _get_total_recall_count() 10 LOC × 2, dashboard ~150 LOC × 2
- **총 중복**: ~620 LOC (전체 ~15,000 LOC의 4%)
- **해결**: 공통 모듈 추출 3건 (api_client.py, sqlite_store.get_meta(), pruning import)

### Theme 3: N+1 Query Pattern
- **등장**: C-01 implicit, C-02 L-01, C-07 H-01, C-07 H-02
- **위치**: hybrid.py (노드 조회), recall.py (엣지 조회), inspect_node.py (이웃 조회), promote_node.py (이웃 project 조회)
- **영향**: top_k=5 기준 최소 20개 추가 쿼리 (recall 1회당)
- **해결**: 배치 쿼리 API 2개 추가 (get_nodes_batch, get_edges_batch)

### Theme 4: Error Handling Inconsistency
- **등장**: C-01 M-02, C-02 M-01/M-05, C-07 M-03, C-08 M-03
- **3가지 철학 혼재**:
  1. Silent fail (`except: pass`) — BCM, SPRT, action_log, correction_log
  2. Graceful degrade (`except: return []`) — vec_search, fts_search
  3. Exception propagation (no try/except) — insert_node, get_context, save_session
- **해결**: 3-tier 에러 정책 수립 + 공통 에러 envelope 도입

### Theme 5: Source of Truth Fragmentation
- **등장**: C-03 H-01, C-04 M-05, C-06 H-01
- **4곳**: schema.yaml, config.py, DB type_defs/relation_defs, migrate_v2_ontology.py 하드코딩
- **테스트에서 5번째 소스**: fixture 내 schema 정의 (3곳에서 미묘하게 다름)
- **해결**: schema.yaml을 canonical source로 지정, 시작 시 자동 동기화

### Theme 6: Connection Management Anti-Pattern
- **등장**: C-01 H-01, C-02 M-04, C-04 L-01, C-06 H-02, C-06 M-01
- **패턴**: context manager 없는 수동 connect/close, finally 블록 부재
- **영향**: 예외 시 connection leak, 테스트 병렬 실행 시 경쟁 조건
- **해결**: `@contextmanager _db()` 도입, 모든 메서드를 `with _db() as conn:` 전환

---

## 5. Strengths (Positive Findings)

| # | Strength | Evidence | Categories |
|---|----------|----------|------------|
| 1 | **4중 보안 방어** | A10 F1 + Hub D-3 + RBAC + F3 자동edge 차단 | C-08 I-01~03 |
| 2 | **SQL injection 제로** | 50+ 쿼리 100% parametrized | C-08 |
| 3 | **Graceful degradation** | 검색 파이프라인 각 단계 독립 실패 가능 | C-01 I-02 |
| 4 | **Validator dual-source fallback** | type_defs DB → schema.yaml → Unclassified | C-03 I-01 |
| 5 | **Relation taxonomy** | 48개 관계, 8개 의미 카테고리 체계적 분류 | C-03 I-03 |
| 6 | **promote_node 3-gate 조기 반환** | 각 게이트 실패 시 즉시 반환 | C-07 I-02 |
| 7 | **remember 3단계 파이프라인** | classify → store → link 단일 책임 | C-07 I-03 |
| 8 | **server.py thin wrapper** | 순수 routing, 비즈니스 로직 분리 | C-02 I-03 |
| 9 | **Script idempotency** | state-based filter, file overwrite 패턴 | C-04 I-01 |
| 10 | **migrate_v2.py CLI** | 3-mode + backup + rollback 모범 사례 | C-04 I-02 |
| 11 | **SPRT 수학적 엄밀성** | Wald(1945) 이론, 민감도 분석 완비 | C-05 I-01 |
| 12 | **Access control TC 전수 검증** | 15 TC, in-memory DB, spec 매핑 | C-06 I-01 |

---

## 6. Top 10 Design Recommendations (Priority Order)

### P0 — Critical (즉시)

**R-01: sqlite_store Public API 확장**
- 해결: C-01 H-01, C-02 H-01/H-02, C-07 H-01/H-02/H-03
- 추가 메서드: `get_connection()`, `upsert_meta()`, `get_nodes_by_type()`, `update_node()`, `upsert_session()`, `get_nodes_batch()`, `get_edges_batch()`
- 영향: **19건** 의 _connect() 직접 호출 제거, N+1 쿼리 4곳 해결
- 예상 변경: sqlite_store.py +150 LOC, tools/ -100 LOC (net +50)

**R-02: Connection Management Context Manager**
- 해결: C-01 H-01, C-02 M-04, C-04 L-01, C-06 H-02
- 변경: `@contextmanager _db()` 도입, 모든 connect/close를 `with _db() as conn:` 전환
- 영향: connection leak 방지, finally 블록 불필요, 테스트 격리 개선
- 예상 변경: sqlite_store.py +10 LOC, 전체 -30 LOC (중복 제거)

### P1 — High (1주 내)

**R-03: 3-Tier Error Policy 수립**
- 해결: C-01 M-02, C-02 M-01/M-05, C-07 M-03, C-08 M-03
- Critical (데이터 무결성): exception propagation + rollback
- Degradable (검색 품질): graceful degrade + warning log
- Optional (부수 기능): silent fail + debug log
- 공통 에러 envelope: `{"success": bool, "data": dict, "error": {"code": str, "message": str}}`

**R-04: enrich/api_client.py 공통 모듈 추출**
- 해결: C-04 H-01
- 변경: `_call_json()`, 재시도 로직, 429 처리를 `EnrichmentAPIClient` 클래스로
- 영향: ~180 LOC 중복 제거, API provider 변경 시 1곳만 수정
- 예상 변경: api_client.py +80 LOC, 3개 enricher -180 LOC (net -100)

**R-05: conftest.py 생성 + 테스트 DB 통합**
- 해결: C-06 H-01, C-06 H-02, C-06 M-01
- 변경: 공유 SHARED_SCHEMA, test_db fixture (tmp_path + UUID), mock_vector_store stub
- 영향: fixture 중복 38% 제거, 병렬 테스트 안전, connection leak 방지

### P2 — Medium (2주 내)

**R-06: schema.yaml Single Source of Truth**
- 해결: C-03 H-01, C-04 M-05
- 변경: 시작 시 schema.yaml → DB type_defs/relation_defs 자동 동기화, config.py 타입 상수는 schema.yaml 파싱
- 영향: 5개 소스 → 1개 canonical source

**R-07: config.py 관심사 분리**
- 해결: C-03 H-02, C-03 M-03
- 변경: `infer_relation()` → `ontology/inference.py` 이동, config.py = 순수 상수만
- 영향: config.py 259줄 → ~200줄, 테스트 용이성 향상

**R-08: hybrid_search Pipeline 분해**
- 해결: C-01 H-03
- 변경: 9단계를 독립 함수로 추출, hybrid_search = 파이프라인 오케스트레이터
- 영향: 테스트 가능성 대폭 향상, 각 단계 독립 최적화 가능

### P3 — Low (선택)

**R-09: pruning.py → daily_enrich import 통합**
- 해결: C-04 H-02
- 변경: daily_enrich phase6가 `from scripts.pruning import stage2, stage3` import
- 영향: ~100 LOC 중복 제거

**R-10: A-10 F2-F6 중앙화**
- 해결: C-05 M-02, C-08
- 변경: F3 로직을 remember.py에서 access_control.py로 이동
- 영향: 분산 방화벽 → 중앙 방화벽, 다른 도구의 F3 우회 방지

---

## 7. Risk Heat Map

```
              Storage  Tools  Utils  Scripts  Specs  Tests  E2E  Security
Coupling        ■■■     ■■■    ■■      ■■      -      -     ■■     ■■
Duplication      ■      ■■     -       ■■■     -      ■■     -      -
Error Handling  ■■■     ■■■    -        ■      -      -     ■■      ■
Connection      ■■■     ■■     -        ■      -      ■■    ■■      -
Consistency      ■      ■■    ■■■      ■■     ■■      ■     ■       -
Testability     ■■       ■     -        -      -     ■■■    -       -

■ = low risk  ■■ = medium risk  ■■■ = high risk  - = N/A
```

**최고 위험 영역**: Storage connection management + Tools coupling + Error handling consistency

---

## 8. Architecture Maturity Assessment

| Level | Description | Status |
|-------|-------------|--------|
| L1: Initial | 코드가 작동함 | **완료** — 117 tests 통과, 13 MCP 도구 정상 |
| L2: Managed | 일관된 패턴 적용 | **부분** — 보안/검증은 일관적, 에러/연결은 불일치 |
| L3: Defined | 아키텍처 경계 명확 | **부분** — server/tools 깔끔, storage/tools 경계 위반 |
| L4: Measured | 품질 메트릭 추적 | **초기** — NDCG 0.057 baseline, goldset 25개 |
| L5: Optimizing | 지속 개선 프로세스 | **미달** — 리뷰 프로세스 구축 중 |

**현재 성숙도: L2.5** — R-01~R-05 적용 시 L3 달성 가능

---

## 9. Comparison: Design Intent vs Reality

| Design Intent | Reality | Gap |
|---------------|---------|-----|
| sqlite_store = DB abstraction | Thin wrapper, private API 노출 | 높음 |
| tools = 비즈니스 로직 캡슐화 | 5/10 도구가 raw SQL 직접 실행 | 높음 |
| config.py = 상수 정의 | 비즈니스 로직 포함 (infer_relation) | 중간 |
| schema.yaml = 타입 정의 SoT | 5개 소스 중 하나에 불과 | 높음 |
| access_control = 중앙 보안 | F1만 중앙, F3은 remember.py 분산 | 낮음 |
| action_log = 감사 추적 | Write-only, 조회 API 없음 | 중간 |
| tests = 품질 보증 | conftest.py 없음, 격리 불일치 | 중간 |
| specs = 설계 문서 | 코드:스펙 비율 13:1, 구현 가이드 | 중간 |

---

## 10. Conclusion

mcp-memory v2.1은 **보안과 온톨로지 설계에서 enterprise-grade 수준**을 달성했으나, **storage 추상화와 에러 처리의 일관성**이 아키텍처의 가장 큰 약점이다. R-01(public API 확장)과 R-02(context manager)를 적용하면 HIGH findings의 **60% (12/19)** 가 해결되며, 이는 가장 높은 ROI를 제공하는 개선 포인트이다.

**Round 2 Architecture Review 완료.**

---

## Appendix: Finding Index

| ID | Cat | Sev | Finding |
|----|-----|-----|---------|
| C01-H01 | Storage | HIGH | Connection management anti-pattern — no pooling, no context manager |
| C01-H02 | Storage | HIGH | Transaction boundary inconsistency in insert_edge() |
| C01-H03 | Storage | HIGH | hybrid_search() God Function — 110+ lines, 9 responsibilities |
| C01-H04 | Storage | HIGH | Module-level mutable state — graph cache thread-safety |
| C02-H01 | Tools | HIGH | Private API `_connect()` direct access (5/10 tools) |
| C02-H02 | Tools | HIGH | Duplicated `_get_total_recall_count()` (connection leak difference) |
| C02-H03 | Tools | HIGH | Validation logic split — server.py vs tools |
| C03-H01 | Utils | HIGH | Triple Source of Truth — schema drift risk |
| C03-H02 | Utils | HIGH | Business logic `infer_relation()` in config.py |
| C04-H01 | Scripts | HIGH | `_call_json()` triplicated (~180 LOC duplicated) |
| C04-H02 | Scripts | HIGH | Pruning logic duplicated (daily_enrich vs pruning) |
| C05-H01 | Specs | HIGH | Shared concept ownership undefined |
| C05-H02 | Specs | HIGH | Spec-implementation boundary blur (code:spec 13:1) |
| C06-H01 | Tests | HIGH | conftest.py absent — fixture duplication 38% |
| C06-H02 | Tests | HIGH | test_hybrid.py global tempfile race condition |
| C07-H01 | E2E | HIGH | hybrid_search() N+1 node queries |
| C07-H02 | E2E | HIGH | recall() N+1 edge queries (formatting) |
| C07-H03 | E2E | HIGH | promote_node() gate data reload |
| C08-H01 | Security | HIGH | External API response validation absent (embedding shape) |
