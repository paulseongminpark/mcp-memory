# T2-C-06: Tests — Architecture Review

**Reviewer**: rv-c2 (Claude Opus)
**Round**: 2 (Architecture)
**Category**: Tests
**Date**: 2026-03-06
**Criteria**: Test architecture, fixtures, mocking patterns, test isolation, assertion quality, test naming

---

## Executive Summary

7개 테스트 파일(117 tests)의 아키텍처를 분석한 결과, **conftest.py 부재**로 인한 fixture 중복(38%), **DB 격리 전략 불일치**(tempfile vs :memory: vs mock-only), **assertion 강도 편차**가 주요 문제로 확인됨. test_access_control.py는 모범 사례(in-memory DB, TC ID 매핑, 구체적 assertion)를 보여주지만, 나머지 파일들은 이 수준에 미달.

| Severity | Count |
|----------|-------|
| HIGH     | 2     |
| MEDIUM   | 4     |
| LOW      | 3     |
| INFO     | 3     |

---

## HIGH Findings

### H-01: conftest.py 부재 — fixture 중복 38%

**위치**: `tests/` 디렉토리 (conftest.py 없음)

**현상**: 7개 파일이 각자 DB 생성 로직을 정의하며, 동일한 `nodes` 테이블을 3곳에서 **미묘하게 다른 schema**로 생성.

```python
# test_hybrid.py:17-83 — score_history, promotion_candidate 포함
conn.executescript("""CREATE TABLE nodes (id, content, type, layer,
    visit_count, frequency, score_history, promotion_candidate, ...)""")

# test_action_log.py:17-42 — 위 필드 없음
conn.executescript("""CREATE TABLE sessions (...) CREATE TABLE action_log (...)""")

# test_drift.py:70-115 — quality_score, abstraction_level, enrichment_status 추가
conn.executescript("""CREATE TABLE nodes (id, content, type, layer,
    quality_score, abstraction_level, enrichment_status, ...)""")
```

**영향**:
- Schema 변경 시 3곳을 동시에 수정해야 함 (동기화 누락 리스크)
- migration 테스트에서 실제 schema와 불일치 가능
- T2-C-03 H-01(Triple Source of Truth)의 테스트 계층 확장 — **4th source** 추가

**개선안**: conftest.py에 `SHARED_SCHEMA` 정의, 각 테스트가 import하여 사용

---

### H-02: test_hybrid.py의 전역 tempfile 경쟁 조건

**위치**: `tests/test_hybrid.py:13-14, 86-96`

**현상**: 모듈 레벨 전역 변수로 단일 DB 경로 공유, autouse fixture에서 매 테스트마다 unlink+recreate.

```python
_tmp = tempfile.mkdtemp()           # 세션당 1회만 호출
_test_db = Path(_tmp) / "test_hybrid.db"  # 모든 테스트가 동일 경로

@pytest.fixture(autouse=True)
def setup_db():
    if _test_db.exists():
        _test_db.unlink()    # 경쟁 조건 지점
    _create_test_db()
    with patch("config.DB_PATH", _test_db), \
         patch("storage.sqlite_store.DB_PATH", _test_db), \
         patch("storage.action_log.sqlite_store.DB_PATH", _test_db):
        yield
    if _test_db.exists():
        _test_db.unlink()
```

**영향**:
- `pytest -n auto` (병렬 실행) 시 FileNotFoundError 발생 가능
- 3중 patch vs test_action_log.py의 2중 patch — **patch 대상 불일치**

**개선안**: `tmp_path` fixture (pytest 내장) + UUID 기반 고유 경로
```python
@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / f"test_{uuid.uuid4()}.db"
    # ...
```

---

## MEDIUM Findings

### M-01: test_drift.py connection close() 누락

**위치**: `tests/test_drift.py:70-115` (`_make_enricher_conn()`)

**현상**: 각 테스트가 `_make_enricher_conn()`으로 in-memory DB connection 생성하지만 명시적 close() 없음.

```python
def _make_enricher_conn(...) -> tuple:
    conn = sqlite3.connect(":memory:")
    # ... setup ...
    return enricher, conn  # close() 안 함

def test_td13_e1_normal_summary_applied():
    enricher, conn = _make_enricher_conn(nodes=[...])
    # ... assertions ...
    # conn.close() 없이 종료 → GC에 의존
```

**영향**: 15개 테스트 × connection 누적 → 병렬 실행 시 connection pool 고갈 가능

---

### M-02: Mock 과잉/부족 불균형

**위치**: 여러 파일

**과잉 mock** — `test_hybrid.py:228-248` (캐시 테스트):
```python
def test_get_graph_cache():
    with patch.object(sqlite3, "connect"):  # 실제 사용 안 됨
        with patch("storage.hybrid.sqlite_store") as mock_store, \
             patch("storage.hybrid.build_graph", return_value=mock_graph):
            result1 = hybrid._get_graph()
            result2 = hybrid._get_graph()
            assert mock_store.get_all_edges.call_count == 1  # mock 호출 수만 확인
```
- `sqlite3.connect` patch는 불필요
- 실제 캐시 TTL 로직 미검증, mock 호출 수만 확인

**부족 mock** — `test_drift.py:172-193` (E7 drift):
```python
with patch("utils.similarity.cosine_similarity", return_value=0.1) as mock_cos:
    enricher._apply("E7", "embedding text", node, updates)
    mock_add.assert_not_called()  # 호출 여부만 확인, 인자는?
```
- cosine_similarity를 0.1로 고정 → 실제 유사도 계산 우회
- drift 판정 알고리즘 자체 미검증

---

### M-03: Assertion 메시지 전면 부재

**위치**: test_hybrid.py, test_recall_v2.py, test_remember_v2.py, test_drift.py, test_action_log.py

**현상**: test_access_control.py만 `pytest.raises(match=...)` 사용. 나머지 5개 파일은 assertion 메시지 없음.

```python
# test_hybrid.py:149 — 실패 시 원인 파악 불가
assert new_freq != old_freq

# test_hybrid.py:179 — magic number, 의도 불분명
assert vc1 == 6  # "6"은 setup_db()의 초기값 5에 종속

# test_remember_v2.py:232 — 타입만 확인
assert isinstance(edges, list)  # 내용은?
```

**영향**: 테스트 실패 시 디버깅 비용 증가, CI 로그에서 원인 파악 어려움

---

### M-04: Patch 대상 불일치

**위치**: test_hybrid.py vs test_action_log.py

**현상**: 동일한 DB 접근을 가로채는 patch 대상이 파일마다 다름.

```python
# test_hybrid.py: 3중 patch
patch("config.DB_PATH", _test_db)
patch("storage.sqlite_store.DB_PATH", _test_db)
patch("storage.action_log.sqlite_store.DB_PATH", _test_db)  # 3번째

# test_action_log.py: 2중 patch
patch("config.DB_PATH", _test_db)
patch("storage.sqlite_store.DB_PATH", _test_db)
# action_log.sqlite_store.DB_PATH 미패치
```

**영향**: action_log 관련 테스트가 의도치 않게 실제 DB에 접근할 수 있음

---

## LOW Findings

### L-01: 네이밍 컨벤션 3가지 혼재

| 파일 | 패턴 | 추적성 |
|------|------|--------|
| test_access_control.py | `test_tc[ID]_[시나리오]_[결과]` | spec 매핑 (d-r3-13) |
| test_validators_integration.py | `test_tc[ID]_[시나리오]` | spec 매핑 |
| test_drift.py | `test_td[ID]_[시나리오]` | spec 매핑 |
| test_recall_v2.py | `class Test[Module]: def test_[scenario]` | 클래스 기반 |
| test_remember_v2.py | `class Test[Module]: def test_[scenario]` | 클래스 기반 |
| test_hybrid.py | `test_[function]_[change]` | 함수 기반 (약함) |
| test_action_log.py | `test_[feature]` | 함수 기반 (약함) |

---

### L-02: Weak assertion 패턴

```python
# test_hybrid.py:247-248 — mock 호출 수만 확인
assert mock_store.get_all_edges.call_count == 1

# test_drift.py:197-213 — 호출 여부만 확인, 인자 미검증
mock_add.assert_called_once()

# test_recall_v2.py:217 — 길이만 확인
assert len(result["results"][0]["content"]) == 200
```

---

### L-03: DB 격리 전략 3가지 혼재

| 전략 | 파일 | 격리 등급 |
|------|------|---------|
| `:memory:` (매번 새로) | test_access_control.py | A (완벽) |
| mock only | test_recall_v2.py, test_remember_v2.py, test_validators_integration.py | A (완벽) |
| tempfile (autouse) | test_hybrid.py, test_action_log.py | B (경쟁 조건) |
| `:memory:` (수동, close 없음) | test_drift.py | B (leak) |

---

## INFO Findings

### I-01: test_access_control.py — 모범 사례 (Positive)

in-memory DB, TC ID 체계, spec 매핑(d-r3-13), pytest.raises(match=...), 역할별 전수 검증(15 TC). 다른 파일이 이 수준을 따르면 전체 테스트 품질 대폭 향상.

### I-02: test_recall_v2.py/test_remember_v2.py — 클래스 기반 조직 (Positive)

`TestIsPatchSaturated`, `TestDominantProject`, `TestRecall` 등 기능별 클래스 그룹화로 pytest collection 시 명확한 계층 구조.

### I-03: test_validators_integration.py — 순수 mock 테스트 (Positive)

DB 불필요, 순수 함수 테스트로 격리 완벽. `validate_node_type()`, `validate_relation()` 검증이 type_defs 테이블 fallback까지 커버.

---

## Scorecard

| 평가항목 | 등급 | 점수 |
|---------|------|------|
| Test Architecture | B+ | 3.5/5 |
| Fixtures | B- | 2.8/5 |
| Mocking Patterns | B- | 2.8/5 |
| Test Isolation | B | 3.0/5 |
| Assertion Quality | B | 3.2/5 |
| Test Naming | C+ | 2.5/5 |
| **Overall** | **B-** | **17.8/30** |

---

## Cross-References

- H-01 fixture schema 중복 → T2-C-03 H-01 (Triple Source of Truth)의 4번째 소스
- H-02 patch 대상 불일치 → T2-C-02 H-01 (private API `_connect()` 직접 사용)
- M-02 mock 과잉 → T2-C-01 (storage abstraction quality)
