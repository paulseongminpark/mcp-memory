# T2-C-07: E2E Scenarios — Architecture Review

**Reviewer**: rv-c2 (Claude Opus)
**Round**: 2 (Architecture)
**Category**: E2E Scenarios
**Date**: 2026-03-06
**Criteria**: Flow architecture optimality, unnecessary indirection, missing short circuits

---

## Executive Summary

10개 E2E 경로를 추적한 결과, server.py→tools 라우팅은 **깔끔한 직접 호출** 구조이나, **recall() 내부의 폭발적 복잡도**(9단계 처리), **N+1 쿼리 패턴 4곳**, **부수효과 무시(pass)** 3곳이 핵심 아키텍처 문제로 확인됨. suggest_type()은 remember()의 불필요한 wrapper.

| Severity | Count |
|----------|-------|
| HIGH     | 3     |
| MEDIUM   | 4     |
| LOW      | 2     |
| INFO     | 3     |

---

## Flow Architecture Overview

```
server.py (FastMCP @mcp.tool)
  |-- S1: remember()   → classify → store → link (3단계, 최적)
  |-- S2: recall()     → hybrid_search (9단계, 과복잡)
  |-- S3: promote()    → 3-gate SWR→Bayesian→MDL (3단계, 최적)
  |-- S4: analyze()    → clustering + recommend (2단계, 간결)
  |-- S5: becoming()   → query + sort (2단계, 간결)
  |-- S6: context()    → 4x get_recent_nodes (4쿼리, 병합 가능)
  |-- S7: inspect()    → node + edges (2단계, N+1)
  |-- S8: save()       → UPSERT (1단계, 최소)
  |-- S9: suggest()    → remember() 위임 (불필요한 wrapper)
  |-- S10: visualize() → search + traverse + pyvis (3단계)
```

---

## HIGH Findings

### H-01: hybrid_search() 내 N+1 노드 조회

**위치**: `storage/hybrid.py:440-450`

**현상**: RRF 점수 계산 후, 상위 `top_k*2`개 노드를 **개별 조회**하여 타입/프로젝트 필터링 수행.

```python
sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
candidates = []
for node_id in sorted_ids[:top_k * 2]:
    node = sqlite_store.get_node(node_id)  # N번 호출
    if type_filter and node["type"] != type_filter:
        continue  # RRF 계산은 이미 완료 (낭비)
    if project and node["project"] != project:
        continue
```

**영향**:
- `top_k=5` → 최대 10개 개별 SELECT 쿼리
- 필터링이 RRF **이후** 사후 처리 → 불필요한 노드까지 RRF 점수 계산
- T2-C-01에서 식별된 connection 관리 문제와 결합 시 성능 저하 가속

**개선안**: 배치 쿼리 `SELECT * FROM nodes WHERE id IN (...)` + 필터링을 벡터/FTS 단계에서 선행

---

### H-02: recall() N+1 엣지 조회 (포매팅)

**위치**: `tools/recall.py:58-62`

**현상**: 검색 결과 포매팅 시 각 노드의 엣지를 개별 조회.

```python
formatted = []
for r in results:  # top_k번 반복
    edges = sqlite_store.get_edges(r["id"])  # 개별 쿼리
    related = [...]
    formatted.append({...})
```

**영향**: `top_k=5` → 5번 추가 SELECT. inspect()의 같은 패턴(H-03)과 합치면 **시스템 전체 N+1 패턴 3곳**.

**개선안**: 배치 `SELECT * FROM edges WHERE source_id IN (...) OR target_id IN (...)`

---

### H-03: promote_node() 게이트 간 데이터 재로드

**위치**: `tools/promote_node.py:167-240`

**현상**: 3개 게이트가 순차 실행되면서 같은 데이터를 반복 로드.

```python
# 메인
node = sqlite_store.get_node(node_id)           # 1번째 조회

# Gate 1: SWR
conn = sqlite_store._connect()
edge_rows = conn.execute("SELECT ... FROM edges WHERE ...")  # 엣지 조회
for nbr_id in neighbor_ids:
    row = conn.execute("SELECT project FROM nodes WHERE id=?", (nbr_id,))  # N번

# Gate 2: Bayesian
total_queries = _get_total_recall_count()        # 2번째 연결

# Gate 3: MDL
related_nodes = [sqlite_store.get_node(rid) for rid in related_ids]  # M번
```

**영향**: 단일 promote_node() 호출에 **4개 이상 DB 연결**, 이웃 노드 중복 조회

**개선안**: 게이트 함수에 `(node_data, edges, related_nodes)` 사전 로드 데이터 전달

---

## MEDIUM Findings

### M-01: suggest_type() — 불필요한 wrapper (S9)

**위치**: `tools/suggest_type.py:6-32`

**현상**: 고유 로직 0줄. remember()에 metadata 추가 + 태그 수정만 수행.

```python
def suggest_type(content, reason, attempted_type, tags, project):
    metadata = {"attempted_type": attempted_type, "reason_failed": reason}
    result = remember(  # 단순 위임
        content=content, type="Unclassified",
        tags=f"unclassified,needs-review,{tags}".strip(","),
        project=project, metadata=metadata,
    )
    result["suggestion"] = {...}
    return result
```

**영향**: 불필요한 함수 계층, 테스트/유지보수 오버헤드

---

### M-02: get_context() 4개 쿼리 순차 실행 (S6)

**위치**: `tools/get_context.py:6-16`

**현상**: 4개 타입의 최근 노드를 개별 쿼리로 조회.

```python
decisions = sqlite_store.get_recent_nodes(project, limit=3, type_filter="Decision")
questions = sqlite_store.get_recent_nodes(project, limit=3, type_filter="Question")
insights  = sqlite_store.get_recent_nodes(project, limit=2, type_filter="Insight")
failures  = sqlite_store.get_recent_nodes(project, limit=2, type_filter="Failure")
```

**개선안**: 1개 쿼리 `WHERE type IN ('Decision','Question','Insight','Failure') ORDER BY created_at DESC` + 후처리

---

### M-03: 부수효과 실패 무시 (pass) 3곳

**위치**: `storage/hybrid.py:467, 485, 494`

**현상**: BCM 학습, SPRT 판정, action_log 기록이 모두 `except: pass`로 실패 무시.

```python
# BCM 학습
try:
    _bcm_update(ids, scores, all_edges, query)
except Exception:
    pass  # 학습 실패 무시

# SPRT 판정
try:
    _sprt_check(node, score, sprt_conn)
except Exception:
    pass  # 승격 판정 실패 무시

# 활성화 로그
try:
    _log_recall_activations(result, query)
except Exception:
    pass  # 감사 추적 손실
```

**영향**:
- BCM 학습 실패 → 엣지 가중치 갱신 안 됨 (검색 품질 점진 저하)
- SPRT 실패 → Signal 승격 판정 누락
- action_log 실패 → 감사 추적 보장 불가 (T2-C-05 M-03과 연결)

---

### M-04: recall() 패치 전환 시 중복 hybrid_search 호출

**위치**: `tools/recall.py:40-50`

**현상**: 패치 포화(B-4) 감지 시 hybrid_search를 **2번** 호출하고 사후 병합.

```python
results = hybrid_search(query, ...)               # 1번째 호출

if _is_patch_saturated(results) and not project:
    dominant = _dominant_project(results)
    alt = hybrid_search(query, ..., excluded_project=dominant)  # 2번째 호출
    results = results[:top_k // 2] + alt[:top_k - top_k // 2]
    results.sort(key=lambda r: r["score"], reverse=True)
```

**영향**: 패치 전환 시 검색 비용 2배. 두 결과의 정규화/중복 제거 로직 부재.

---

## LOW Findings

### L-01: inspect() N+1 이웃 노드 조회

**위치**: `tools/inspect_node.py:38-52`

```python
for e in edges:
    other = sqlite_store.get_node(e["target_id"])  # 엣지당 1번 조회
```

엣지 수가 많은 허브 노드(top-10 IHS)의 경우 수백 번 조회 가능.

---

### L-02: type_filter 검증 비대칭

**위치**: `server.py` — remember()에만 타입 검증, recall()의 type_filter는 미검증

```python
# remember(): 검증 있음
valid, correction = validate_node_type(type)

# recall(): 검증 없음
return _recall(query, type_filter=type_filter, ...)  # 오타 시 조용히 빈 결과
```

---

## INFO Findings

### I-01: server.py→tools 직접 라우팅 (Positive)

10개 도구 모두 server.py에서 tool 함수를 직접 호출. 불필요한 중간 계층(router, dispatcher) 없음. 깔끔한 구조.

### I-02: promote_node() 3-gate 조기 반환 (Positive)

각 게이트 실패 시 즉시 status 반환. 불필요한 후속 게이트 실행 방지.

```python
if not swr_pass:
    return {"status": "not_ready", "gate": "SWR", ...}
if not bayes_pass:
    return {"status": "not_ready", "gate": "Bayesian", ...}
if not mdl_pass:
    return {"status": "not_ready", "gate": "MDL", ...}
```

### I-03: remember() classify→store→link 파이프라인 (Positive)

3단계 파이프라인이 명확한 단일 책임 분리. classify는 순수 함수, store는 DB, link는 그래프. F3 방화벽이 link 단계에서 L4/L5 자동 연결을 차단.

---

## N+1 Query Map (시스템 전체)

| 위치 | 패턴 | 영향 |
|------|------|------|
| hybrid.py:440 | 노드 개별 조회 (RRF 후) | top_k*2 쿼리 |
| recall.py:58 | 엣지 개별 조회 (포매팅) | top_k 쿼리 |
| inspect_node.py:38 | 이웃 노드 개별 조회 | edges_count 쿼리 |
| promote_node.py:200 | 이웃 project 개별 조회 | neighbors_count 쿼리 |

---

## Scorecard

| 평가항목 | 등급 | 점수 |
|---------|------|------|
| Flow optimality | B | 6.5/10 |
| Unnecessary indirection | B+ | 7.0/10 |
| Missing short circuits | B | 6.5/10 |
| **Overall** | **B** | **6.7/10** |

---

## Cross-References

- H-01/H-02 N+1 쿼리 → T2-C-01 (DB abstraction quality)
- H-03 게이트 데이터 재로드 → T2-C-02 H-01 (`_connect()` 직접 사용)
- M-03 부수효과 무시 → T2-C-05 M-03 (correction_log vs action_log)
- M-01 suggest_type wrapper → T2-C-02 (tool composition)
