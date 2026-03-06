# B-10: B-5 재공고화 — 실제 구현 코드

> 세션 B | 2026-03-05 | 오케스트레이터 확정: 전체 Phase 1 첫 번째 구현
> 참조: `tools/recall.py` (44줄), `storage/hybrid.py` (119줄)

## 결론 요약

| 항목 | 결정 |
|---|---|
| 삽입 위치 | `hybrid.py` 116번 줄 이후 (`_hebbian_update` 와 같은 conn) |
| DB 필드 | `edges.description TEXT DEFAULT ''` 재사용 (스키마 변경 없음) |
| 트랜잭션 | `_hebbian_update` + `_record_context` 를 하나의 conn으로 통합 |
| 마이그레이션 | `'' → '[]'`, 비-JSON 텍스트 → `'[]'` |

---

## 현재 코드 분석

### tools/recall.py (전체 44줄)
```
L1-5   : import
L8-13  : recall() 시그니처
L14    : results = hybrid_search(...)         ← 검색
L16-17 : 빈 결과 체크
L19-37 : 포매팅 루프 (edges 조회 포함)
L39-43 : return
```

### storage/hybrid.py 핵심 흐름
```
L14-44 : _hebbian_update() — frequency+1, last_activated
L47-118: hybrid_search()
  L74  : all_edges = sqlite_store.get_all_edges()
  L75  : graph = build_graph(all_edges)
  L76  : graph_neighbors = traverse(...)
  L116 : _hebbian_update([n["id"] for n in result], all_edges)
  L118 : return result                        ← 여기 위에 삽입
```

---

## 구현: _hebbian_update() 확장

`_hebbian_update()` 내부에서 같은 conn으로 context 기록.
별도 함수 `_record_reconsolidation_context()` 없이 통합.

```python
# storage/hybrid.py — _hebbian_update() 전체 교체 (L14-44)

from config import (
    DEFAULT_TOP_K, RRF_K, GRAPH_BONUS,
    ENRICHMENT_QUALITY_WEIGHT, ENRICHMENT_TEMPORAL_WEIGHT,
    CONTEXT_HISTORY_LIMIT,          # 추가: 5
)
import json

def _hebbian_update(result_ids: list[int], all_edges: list[dict],
                    query: str = ""):
    """헤비안 학습 + 재공고화 맥락 기록 (단일 트랜잭션).

    - frequency +1, last_activated 갱신 (기존)
    - edges.description에 사용 맥락 JSON 추가 (B-5 신규)

    query: 빈 문자열이면 맥락 기록 생략 (하위 호환성 유지).
    """
    if not result_ids:
        return
    id_set = set(result_ids)
    now = datetime.now(timezone.utc).isoformat()

    activated_edges = [
        e for e in all_edges
        if e.get("source_id") in id_set and e.get("target_id") in id_set
    ]
    if not activated_edges:
        return

    conn = None
    try:
        conn = sqlite_store._connect()
        for edge in activated_edges:
            eid = edge.get("id")

            # 1. 헤비안: frequency +1, last_activated
            conn.execute(
                "UPDATE edges SET frequency = COALESCE(frequency, 0) + 1, "
                "last_activated = ? WHERE id = ?",
                (now, eid),
            )

            # 2. 재공고화: description에 맥락 추가 (query 있을 때만)
            if query:
                raw = edge.get("description") or ""
                try:
                    ctx_log = json.loads(raw) if raw else []
                    if not isinstance(ctx_log, list):
                        ctx_log = []
                except (json.JSONDecodeError, ValueError):
                    ctx_log = []

                ctx_log.append({"q": query[:80], "t": now})
                ctx_log = ctx_log[-CONTEXT_HISTORY_LIMIT:]  # 최근 5개만

                conn.execute(
                    "UPDATE edges SET description = ? WHERE id = ?",
                    (json.dumps(ctx_log, ensure_ascii=False), eid),
                )

        conn.commit()
    except Exception:
        pass  # 학습 실패가 검색을 중단시키지 않음
    finally:
        if conn:
            conn.close()
```

---

## hybrid_search() 호출 수정 (L116)

```python
# storage/hybrid.py L116 — 기존:
_hebbian_update([n["id"] for n in result], all_edges)

# 변경 후:
_hebbian_update([n["id"] for n in result], all_edges, query=query)
```

**변경 범위**: 1줄만 수정. 시그니처에 `query=""` 기본값 추가이므로 하위 호환.

---

## config.py 추가

```python
# config.py에 추가 (Enrichment Pipeline 섹션 근처)
CONTEXT_HISTORY_LIMIT = 5  # edge당 재공고화 맥락 최대 보존 수
```

---

## DB 마이그레이션 SQL

`edges.description DEFAULT ''` — 기존 값이 빈 문자열 또는 비-JSON 텍스트일 수 있음.

```sql
-- 1단계: 빈 문자열과 비-JSON 텍스트 → '[]'로 초기화
-- (json_valid()는 SQLite 3.38+에서 지원)
UPDATE edges
SET description = '[]'
WHERE description IS NULL
   OR description = ''
   OR (length(trim(description)) > 0 AND json_valid(description) = 0);

-- 2단계: 확인
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN json_valid(description) THEN 1 ELSE 0 END) AS valid_json,
    SUM(CASE WHEN description = '[]' THEN 1 ELSE 0 END) AS empty_array
FROM edges;
```

**sqlite3.38 미만 환경 대응** (SQLite 버전 확인: `SELECT sqlite_version();`):
```sql
-- json_valid() 없을 때:
UPDATE edges
SET description = '[]'
WHERE description IS NULL OR description = '';
-- 비-JSON 텍스트는 Python에서 try/except로 처리 (위 구현 코드에 이미 포함)
```

---

## 트랜잭션 처리 분석

| 항목 | 기존 | 변경 후 |
|---|---|---|
| DB 연결 수 | 1 (frequency 갱신) | 1 (동일 conn) |
| 트랜잭션 수 | 1 commit | 1 commit |
| edge당 SQL 수 | 1 UPDATE | 2 UPDATE |
| 성능 영향 | 기준 | 활성 edge N개 × UPDATE 1개 추가 (미미) |

활성 edge 수: recall() 결과 5개 × 연결 edge ≈ 5~15개 정도. 성능 영향 무시 가능.

---

## 검증

```python
# 검증 코드 (Python):
from storage import sqlite_store

recall("포트폴리오 설계")  # 한 번 호출 후

conn = sqlite_store._connect()
rows = conn.execute(
    "SELECT id, description FROM edges "
    "WHERE description != '' AND description != '[]' "
    "LIMIT 5"
).fetchall()
conn.close()

for row in rows:
    import json
    ctx = json.loads(row[1])
    print(f"edge #{row[0]}: {ctx}")
# 기대 출력:
# edge #42: [{"q": "포트폴리오 설계", "t": "2026-03-05T..."}]
```
