# T2-C-08: Security — Architecture Review

**Reviewer**: rv-c2 (Claude Opus)
**Round**: 2 (Architecture)
**Category**: Security
**Date**: 2026-03-06
**Criteria**: Defense-in-depth, trust boundaries, principle of least privilege

---

## Executive Summary

mcp-memory v2.1의 보안 아키텍처는 **enterprise-grade 수준**으로 평가. SQL injection 방어 100% parametrized, LAYER_PERMISSIONS 계층별 ACL, A-10 방화벽(F1/F3), D-3 허브 보호까지 4중 방어 구현. 주요 약점은 **외부 API 응답 검증 부재**(embedding 벡터 shape/range 미검증)와 **FTS5 이스케이핑 불완전** 2건.

| Severity | Count |
|----------|-------|
| HIGH     | 1     |
| MEDIUM   | 3     |
| LOW      | 2     |
| INFO     | 3     |

---

## Defense-in-Depth Analysis

### 입력 검증 3계층 구조

```
L1: MCP Server (server.py)
    └─ validate_node_type() → deprecated 자동 처리 / 없는 타입 차단
    └─ suggest_closest_type() → 유사 타입 제안

L2: Tool Layer (tools/remember.py)
    └─ classify() → 온톨로지 재검증 + type_defs 테이블 조회
    └─ F3 방화벽 → L4/L5 자동 edge 차단

L3: Storage Layer (storage/sqlite_store.py)
    └─ Prepared statements (? placeholder) 100%
    └─ JSON serialization 강제 (metadata)
    └─ 타입 기본값 (Unclassified)
```

### SQL Injection 방어 — 100% Parametrized

50+ SQL 실행 포인트 전수 검증:
- `SELECT * FROM nodes WHERE id = ?` — parametrized
- `INSERT INTO nodes (...)` — parametrized
- 동적 쿼리 (get_recent_nodes) — `sql += " AND type = ?"`, `params.append(value)`
- FTS5 (search_fts) — `_escape_fts_query()` 구현

**위험한 동적 SQL 패턴**: 미발견 (eval/exec/__import__ 안전 사용)

---

## HIGH Findings

### H-01: 외부 API 응답 검증 부재

**위치**: `storage/vector_store.py`, `embedding/openai_embed.py`

**현상**: OpenAI/Anthropic embedding API 응답을 shape/range 검증 없이 ChromaDB에 직접 저장.

```python
# vector_store.py
vector = embed_text(content)  # embedding API 호출
coll.upsert(
    embeddings=[vector],  # shape 검증 없음, range 검증 없음
)
```

**영향**:
- 잘못된 차원의 벡터 → ChromaDB 쿼리 실패 (런타임 에러)
- 비정규화 벡터 → cosine similarity 계산 왜곡 → drift 감지 오탐
- API 응답 조작 시나리오 (중간자 공격) → 검색 결과 오염

**개선안**:
```python
def _validate_embedding(vector, expected_dim=3072):
    assert len(vector) == expected_dim, f"Expected {expected_dim}, got {len(vector)}"
    assert all(-1.0 <= v <= 1.0 for v in vector), "Embedding out of range"
    return vector
```

---

## MEDIUM Findings

### M-01: FTS5 이스케이핑 불완전

**위치**: `storage/sqlite_store.py:283-289`

**현상**: 쿼리 문자열 내 큰따옴표 미처리.

```python
def _escape_fts_query(query: str) -> str:
    terms = query.split()
    return " ".join(f'"{t}"' for t in terms if t)
```

**공격 벡터**: `query = 'test "inner" quote'` → `"test" "inner" "quote"` (FTS5 구문 오류 가능)

**영향**: SQL injection은 아니지만 FTS5 파서 에러 → 검색 실패

**개선안**:
```python
def _escape_fts_query(query: str) -> str:
    terms = query.split()
    return " ".join(f'"{t.replace(chr(34), chr(34)+chr(34))}"' for t in terms if t)
```

---

### M-02: access_control 우회 경로 — _connect() 직접 사용

**위치**: 5/10 tools (`recall.py`, `promote_node.py`, `analyze_signals.py`, `get_becoming.py`, `save_session.py`)

**현상**: `sqlite_store._connect()`로 raw connection 획득 후 직접 SQL 실행 → access_control.check_access() 우회.

```python
# tools/promote_node.py
conn = sqlite_store._connect()
conn.execute("UPDATE nodes SET layer=?, type=? WHERE id=?", (...))  # 권한 검증 없음
conn.commit()
```

**영향**:
- promote_node가 L4/L5 노드를 검증 없이 수정 가능 (A-10 F1 우회)
- save_session이 sessions 테이블에 무제한 쓰기 가능
- T2-C-02 H-01과 동일 근본 원인

**현재 완화책**: promote_node 내에 자체 VALID_PROMOTIONS 검증 존재 (부분 방어)

---

### M-03: 에러 정보 노출 수준 불일치

**위치**: 여러 tools

**현상**: 일부 도구는 내부 에러를 그대로 반환, 일부는 generic 메시지.

```python
# remember.py — 내부 에러 노출
except Exception as e:
    return {"node_id": node_id, "warning": f"Vector store failed: {e}"}

# recall.py — 에러 처리 없음 (exception 전파)
results = hybrid_search(query, ...)  # 실패 시 unhandled exception

# get_context.py — 에러 처리 없음 (39줄, try/except 0개)
```

**영향**: 내부 DB 경로, 스택 트레이스가 MCP 클라이언트에 노출 가능

---

## LOW Findings

### L-01: enrichment actor 세분화 미활용

**위치**: `utils/access_control.py`

**현상**: `enrichment:E1`~`enrichment:E25` 형태의 세분화된 actor를 지원하지만, 실제로는 `actor.split(":")[0]`으로 `enrichment`만 추출하여 동일 권한 적용.

```python
actor_base = actor.split(":")[0]  # enrichment:E7 → enrichment
return actor_base in allowed or actor in allowed
```

**영향**: E1(요약)과 E7(embedding)이 동일 권한 — 최소 권한 원칙 약화. 현재는 문제 없지만 향후 enrichment 단계별 차등 권한 필요 시 재설계 필요.

---

### L-02: DB 파일 권한 미설정

**위치**: `config.py` — DB_PATH 정의

**현상**: SQLite DB 파일의 OS 레벨 권한(chmod) 설정 없음. DB 파일이 기본 umask로 생성.

**영향**: 다중 사용자 환경에서 DB 파일에 대한 무단 접근 가능 (현재 단일 사용자 → 실질 영향 낮음)

---

## INFO Findings

### I-01: LAYER_PERMISSIONS — 5단계 계층적 ACL (Positive)

```
L5 (Axiom):  write/delete = paul only
L4 (Value):  write/content = paul only, metadata = paul+claude
L3 (Framework): write = paul+claude, delete = paul
L2 (Pattern):   write = paul+claude, delete = paul
L0-L1 (Obs):    write = paul+claude+system+enrichment
```

엄격한 계층 분리. L4/L5는 F1 방화벽으로 이중 보호.

### I-02: A-10 F3 자동edge 차단 — 기대 이상의 세밀함 (Positive)

```python
# remember.py:165 — 저장 노드가 L4/L5면 edge 생성 안 함
if layer is not None and layer in {4, 5}:
    return []

# remember.py:175 — 이웃 노드가 L4/L5면 해당 edge만 스킵
if sim_layer is not None and sim_layer in {4, 5}:
    continue
```

양방향 보호: (1) L4/L5 노드 → 자동 연결 전면 차단, (2) 일반 노드 → L4/L5 이웃과의 연결만 차단.

### I-03: D-3 허브 보호 — Human-in-the-loop (Positive)

Top-10 IHS 허브 노드에 대한 write/delete 작업은 paul 포함 모든 actor 차단. human review 강제.

```python
if operation in ("delete", "write") and node_id in hub_ids:
    return False  # paul도 차단 → 별도 승인 프로세스 필요
```

15개 TC로 전수 검증 완료 (test_access_control.py).

---

## Trust Boundary Map

```
[External]                    [Internal]

MCP Client
  │ (untrusted input)
  ▼
server.py ─── L1 검증 ───┐
  │                       │
  ▼                       ▼
tools/*.py ── L2 검증 ── access_control.py
  │                       │
  ▼                       ▼
sqlite_store ─ L3 검증 ── LAYER_PERMISSIONS
  │
  ▼
SQLite DB (parametrized)

[Trusted External]
  │
  ▼
OpenAI/Anthropic API
  │ (응답 검증 부재 ← H-01)
  ▼
ChromaDB (vector store)
```

---

## Scorecard

| 평가항목 | 등급 | 점수 |
|---------|------|------|
| Defense-in-depth | A | 9/10 |
| Trust boundaries | A- | 8/10 |
| Least privilege | A | 9/10 |
| **Overall** | **A-** | **8.7/10** |

---

## Cross-References

- M-02 _connect() 우회 → T2-C-02 H-01 (private API leakage)
- M-03 에러 노출 → T2-C-02 M-01 (inconsistent error format)
- H-01 embedding 검증 → T2-C-03 (validator extensibility)
- I-02 F3 방화벽 → T2-C-05 M-02 (A-10 F2-F6 미구현)
