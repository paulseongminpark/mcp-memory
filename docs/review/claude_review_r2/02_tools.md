# T2-C-02 — Tools Layer Architecture Review

> **Round**: 2 (Architecture)
> **Reviewer**: rv-c2 (Claude Opus)
> **Scope**: tools/*.py (10 files) + server.py (tool routing)
> **Key Question**: "이것이 잘 설계되었는가?"
> **Focus**: Tool-storage coupling, shared code patterns, error propagation, response format consistency, tool composition

---

## Executive Summary

Tools 레이어는 10개 MCP 도구를 구현하며 storage 레이어와 server.py 사이에 위치한다. 핵심 도구(remember, recall, promote_node)는 잘 분리된 파이프라인 구조를 갖추고 있으나, **storage 레이어의 private API(`_connect()`) 직접 호출**이 5/10 도구에서 반복되어 레이어 경계가 무너져 있다. 코드 중복 2건, 응답 형식 비일관성, 에러 처리 편차가 아키텍처 수준의 개선이 필요한 영역이다.

**발견 사항**: HIGH 3 / MEDIUM 5 / LOW 3 / INFO 3

---

## Findings

### H-01: Private API Leakage — `_connect()` Direct Access (Coupling)

**Severity**: HIGH
**Files**: recall.py, promote_node.py, analyze_signals.py, get_becoming.py, save_session.py

5/10 도구가 `sqlite_store._connect()`를 직접 호출하여 raw SQL을 실행한다. Python의 `_` prefix 관례(private)를 무시하고 storage 레이어의 추상화를 우회한다.

| Tool | Private API Usage | Purpose |
|------|-------------------|---------|
| recall.py L111 | `sqlite_store._connect()` | meta 테이블 UPSERT |
| promote_node.py L39, L258 | `sqlite_store._connect()` | recall_log SELECT, nodes UPDATE, edges INSERT |
| analyze_signals.py L21 | `sqlite_store._connect()` | `SELECT * FROM nodes WHERE type='Signal'` |
| get_becoming.py L20 | `sqlite_store._connect()` | `SELECT FROM nodes WHERE type IN (...)` |
| save_session.py L3 | `from storage.sqlite_store import _connect` | sessions 테이블 UPSERT |

**대조**: remember.py는 public API만 사용한다 — `insert_node()`, `insert_edge()`, `get_node()`.

**문제점**:
1. sqlite_store의 내부 구현(연결 생성 방식, WAL 설정 등) 변경 시 5개 파일이 동시에 깨짐
2. 트랜잭션/에러 정책을 storage 레이어에서 통합 관리할 수 없음
3. save_session.py는 `from storage.sqlite_store import _connect`로 직접 import — 가장 강한 결합

**권장**: sqlite_store에 누락된 public methods 추가:
- `upsert_meta(key, value)` — recall.py, promote_node.py 용
- `get_nodes_by_type(types, filters)` — analyze_signals.py, get_becoming.py 용
- `update_node(node_id, **fields)` — promote_node.py 용
- `upsert_session(session_id, data)` — save_session.py 용

---

### H-02: Duplicated `_get_total_recall_count()` (Shared Code)

**Severity**: HIGH
**Files**: promote_node.py, analyze_signals.py

두 파일에 **동일한 함수**가 복사-붙여넣기 되어 있다:

```python
# promote_node.py (Lines 90-98)
def _get_total_recall_count():
    try:
        conn = sqlite_store._connect()
        row = conn.execute("SELECT value FROM meta WHERE key='total_recall_count'").fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0

# analyze_signals.py (Lines 183-191) — 동일 구현
def _get_total_recall_count():
    try:
        conn = sqlite_store._connect()
        row = conn.execute(...).fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0
    finally:
        conn.close()
```

**차이점**: analyze_signals.py만 `finally: conn.close()` 포함 — promote_node.py는 연결 누수 가능.

**권장**: sqlite_store에 `get_meta(key)` public method 추가. 두 도구 모두 이를 사용.

---

### H-03: Validation Logic Split — server.py vs tools (Composition)

**Severity**: HIGH
**File**: server.py (Lines 63-96)

타입 검증 로직이 tool 함수 내부가 아닌 **server.py의 remember() wrapper**에 위치한다:

```
server.py::remember()  →  validate_node_type()  →  _remember()
                         suggest_closest_type()
```

**문제점**:
1. **테스트 우회**: tools/remember.py를 직접 import하면 타입 검증 없이 저장 가능
2. **불일치**: 13개 도구 중 remember만 server.py에서 검증, 나머지 12개는 통과형(pass-through)
3. **promote_node**: 타입 전환 시 `VALID_PROMOTIONS` dict로 자체 검증 — server.py 검증과 별도 경로

**권장**: 검증 로직을 tools/remember.py 내부로 이동. server.py는 순수 routing만 담당.

---

### M-01: Inconsistent Error Response Format (Response Format)

**Severity**: MEDIUM

도구별 에러 응답 구조가 통일되지 않았다:

| Tool | Error Response Keys | Example |
|------|-------------------|---------|
| remember.py | `{"error": str, "suggestion": str, "message": str}` | Unknown type |
| promote_node.py | `{"error": str, "message": str}` | Node not found |
| promote_node.py | `{"status": "not_ready", "swr_score": float, ...}` | Gate failure |
| promote_node.py | `{"status": "insufficient_evidence", "p_real": float, ...}` | Gate 2 failure |
| inspect_node.py | `{"error": str, "message": str}` | Node not found |
| visualize.py | `{"error": str}` | pyvis missing |

**문제점**:
- `error` 키 유무가 불일치 — 에러인지 정상인지 프로그래밍적 판별 불가
- promote_node는 `status` 키로 실패를 표현 — `error` 대신
- visualize는 `message` 키 없이 `error`만 반환

**권장**: 공통 에러 envelope 도입:
```python
{"success": False, "error": {"code": str, "message": str, "details": dict}}
```

---

### M-02: Inconsistent Maturity Calculation (Shared Code)

**Severity**: MEDIUM
**Files**: analyze_signals.py, get_becoming.py

두 도구가 "성숙도(maturity)"를 **다른 공식**으로 계산한다:

```python
# analyze_signals.py — 3-factor
maturity = size_norm * 0.5 + quality_avg * 0.3 + domain_div * 0.2

# get_becoming.py — 2-factor
maturity = quality_score * 0.6 + min(1.0, edge_count / 10) * 0.4
```

analyze_signals는 클러스터 단위(size, quality, domain diversity), get_becoming은 개별 노드 단위(quality, edge density). 개념적으로 다른 계산이지만 같은 `maturity` 이름을 사용하여 혼동을 유발한다.

**권장**: 이름 분화 — `cluster_maturity` vs `node_readiness` 또는 공통 maturity 모델 통합.

---

### M-03: action_log Recording Inconsistency (Error Propagation)

**Severity**: MEDIUM

| Tool | Mutates Data? | Records to action_log? |
|------|:---:|:---:|
| remember.py | Yes (insert node, edge) | **Yes** (node_created, edge_auto) |
| promote_node.py | Yes (update node, insert edge) | **No** |
| save_session.py | Yes (upsert session) | **No** |

**문제점**: promote_node는 노드 타입/레이어를 변경하고 realized_as 엣지를 생성하는 **중요한 mutation** 이지만 action_log에 기록하지 않는다. 감사 추적(audit trail) 누락.

**권장**: 모든 mutation 도구에 action_log.record() 추가. 최소 promote_node에는 필수.

---

### M-04: Connection Lifecycle Management (Error Propagation)

**Severity**: MEDIUM
**Files**: promote_node.py, recall.py, get_becoming.py

Private `_connect()`를 사용하는 도구들의 연결 관리가 불안전하다:

```python
# promote_node.py — conn.close()가 성공 경로에만 존재
conn = sqlite_store._connect()
# ... 200줄의 로직 ...
conn.commit()
conn.close()  # Line ~285 — 예외 발생 시 도달 못 함
```

```python
# recall.py — conn.close()가 try 블록 안
try:
    conn = sqlite_store._connect()
    conn.execute(...)
    conn.commit()
    conn.close()
except Exception:
    pass  # conn이 열려 있을 수 있음
```

**대조**: analyze_signals.py는 `finally: conn.close()`를 사용 — 올바른 패턴.

**권장**: context manager 패턴 적용 (T2-C-01 H-01과 동일 권장 사항):
```python
with sqlite_store.connection() as conn:
    ...  # 자동 close 보장
```

---

### M-05: No Error Handling in get_context.py, save_session.py (Error Propagation)

**Severity**: MEDIUM
**Files**: get_context.py, save_session.py

| Tool | Lines | try/except | Risk |
|------|-------|-----------|------|
| get_context.py | 39 | 0 | sqlite_store 장애 시 unhandled exception → MCP 서버 에러 전파 |
| save_session.py | 51 | 0 | DB 연결/SQL 실패 시 unhandled exception |

MCP 서버 컨텍스트에서 unhandled exception은 도구 호출 실패로 클라이언트에 전파된다. 최소한의 try/except + 사용자 친화적 에러 메시지가 필요하다.

---

### L-01: N+1 Query in inspect_node.py (Performance)

**Severity**: LOW
**File**: inspect_node.py

```python
edges = sqlite_store.get_edges(node_id)  # 1 query
for e in edges:
    if e["source_id"] == node_id:
        other = sqlite_store.get_node(e["target_id"])  # N queries
    else:
        other = sqlite_store.get_node(e["source_id"])  # N queries
```

엣지 수만큼 개별 노드 조회 발생. 현재 규모(~3,000 노드)에서는 문제 없으나, 허브 노드(100+ 엣지)에서 성능 저하 가능.

**권장**: `get_nodes_batch(ids)` 일괄 조회 API 도입.

---

### L-02: Unused Import in promote_node.py

**Severity**: LOW
**File**: promote_node.py

```python
import math  # Line 2 — 파일 내 미사용
```

---

### L-03: Hardcoded Content Truncation (Response Format)

**Severity**: LOW

| Tool | Truncation | Location |
|------|-----------|----------|
| get_context.py | `[:100]` | Line 35 |
| recall.py | `[:200]` | Line 63 |
| inspect_node.py | 없음 (전체 반환) | - |

콘텐츠 자르기 기준이 통일되지 않았다. config 상수로 관리하면 일관성 확보 가능.

---

### I-01: Tool Complexity Spectrum

**Severity**: INFO

도구 복잡도가 극단적으로 분산되어 있다:

| Tier | Tools | LOC Range | Storage Calls |
|------|-------|-----------|--------------|
| **Complex** | remember, promote_node | 290+ | 5-8 calls, multiple layers |
| **Medium** | recall, analyze_signals, visualize | 80-130 | 2-4 calls |
| **Simple** | get_context, inspect_node, get_becoming, save_session | 39-91 | 1-3 calls |
| **Wrapper** | suggest_type | 33 | 0 (delegates to remember) |

이 자체는 문제가 아니나, Complex tier 도구에 에러 처리/로깅이 집중되어야 함을 시사한다.

---

### I-02: Clean Composition Patterns (Positive)

**Severity**: INFO (Positive Finding)

몇 가지 잘 설계된 패턴:

1. **suggest_type → remember**: 깔끔한 delegation (얇은 래퍼 + 메타데이터 보강)
2. **remember의 3단계 파이프라인**: classify → store → link (단일 책임 분리)
3. **promote_node의 3-gate 직렬 검증**: SWR → Bayesian → MDL (명확한 파이프라인)
4. **visualize의 lazy import**: pyvis, hybrid_search를 필요 시에만 로드
5. **FastMCP 데코레이터 라우팅**: server.py의 `@mcp.tool()` 패턴 — 깔끔한 dispatch

---

### I-03: server.py as Thin Wrapper (Positive)

**Severity**: INFO (Positive Finding)

server.py의 대부분 도구는 순수 통과형이다 — 파라미터를 그대로 내부 함수에 전달하고 결과를 반환한다. 이는 올바른 관심사 분리로, routing과 비즈니스 로직이 명확히 분리되어 있다.

**예외**: remember()만 타입 검증 래퍼 로직 보유 (→ H-03에서 지적).

---

## Architecture Coupling Matrix

```
            sqlite_store  vector_store  hybrid  action_log  config  validators  graph
remember       ■ public     ■ public      ■        ■          ■        ■
recall         ■ _connect   □            ■        □          ■        □
promote_node   ■ _connect   ■ _get_coll  □        □          ■        □
analyze_signals ■ _connect   □            □        □          ■        □
get_becoming   ■ _connect   □            □        □          ■        □
get_context    ■ public     □            □        □          □        □
inspect_node   ■ public     □            □        □          □        □
save_session   ■ _connect   □            □        □          □        □
suggest_type   □ (via rem)  □            □        □          □        □
visualize      ■ public     □            ■        □          ■        □          ■

■ = direct usage  □ = not used  _connect = private API access
```

**관찰**: sqlite_store 의존도 100%, 그 중 50%가 private API 경유.

---

## Summary Table

| ID | Severity | Category | Finding | Files |
|----|----------|----------|---------|-------|
| H-01 | HIGH | Coupling | Private API `_connect()` 직접 호출 5/10 도구 | recall, promote, analyze, becoming, session |
| H-02 | HIGH | Shared Code | `_get_total_recall_count()` 중복 (연결 누수 차이) | promote_node, analyze_signals |
| H-03 | HIGH | Composition | 타입 검증이 server.py에 위치 (우회 가능) | server.py |
| M-01 | MEDIUM | Response | 에러 응답 형식 비일관 (error vs status) | 전체 |
| M-02 | MEDIUM | Shared Code | maturity 계산 공식 이름 충돌 | analyze_signals, get_becoming |
| M-03 | MEDIUM | Error | action_log 기록 누락 (promote_node mutation) | promote_node |
| M-04 | MEDIUM | Error | Connection lifecycle — finally 없는 _connect() 사용 | promote, recall, becoming |
| M-05 | MEDIUM | Error | 에러 처리 부재 (get_context, save_session) | get_context, save_session |
| L-01 | LOW | Performance | N+1 쿼리 (inspect_node 엣지 순회) | inspect_node |
| L-02 | LOW | Code Quality | 미사용 import (math) | promote_node |
| L-03 | LOW | Response | 콘텐츠 truncation 기준 비일관 | get_context, recall, inspect_node |
| I-01 | INFO | Structure | 도구 복잡도 스펙트럼 (33~293 LOC) | 전체 |
| I-02 | INFO | Positive | 깔끔한 composition 패턴 (suggest_type, remember 파이프라인) | suggest_type, remember |
| I-03 | INFO | Positive | server.py thin wrapper 패턴 | server.py |

---

## Cross-Reference with T2-C-01

| T2-C-01 Finding | T2-C-02 Overlap |
|-----------------|-----------------|
| H-01 Connection Management | M-04 동일 문제가 tools 레이어에서 확대 재생산 |
| H-03 God Function (hybrid_search) | recall.py의 hybrid_search 호출은 clean — 문제는 hybrid 내부 |
| M-02 Error Handling 불일치 | M-01, M-05에서 tools 레이어 에러 불일치 확인 |

---

## Top 3 Architecture Recommendations

1. **sqlite_store Public API 확장** — `_connect()` 직접 호출을 제거하고 필요한 public methods(upsert_meta, get_nodes_by_type, update_node, upsert_session)를 추가한다. 이것 하나로 H-01, H-02, M-04가 동시 해결된다.

2. **공통 에러 응답 envelope** — 모든 도구가 `{"success": bool, "data": dict, "error": dict|None}` 형식을 사용하도록 표준화. M-01 해결 + 클라이언트 측 에러 핸들링 단순화.

3. **검증 로직 위치 통일** — server.py에서 tools 내부로 검증 이동. server.py는 순수 routing만 담당. H-03 해결 + 테스트 커버리지 보장.
