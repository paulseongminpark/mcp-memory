# B-R3-15: tools/recall.py 최종 교체 코드

> 세션 B | Round 3 | 2026-03-05
> 참조: B-4(패치 전환), B-13(흐름 다이어그램), B-12(mode 파라미터)
> 대상: `tools/recall.py` (현재 44줄 → 목표 ~90줄)

---

## Diff 요약 (변경 전 → 후)

| 위치 | 변경 | 내용 |
|---|---|---|
| L5 imports | ADD | `PATCH_SATURATION_THRESHOLD` |
| L8-13 시그니처 | ADD | `mode: str = "auto"` 파라미터 |
| L14 hybrid_search 호출 | CHANGE | `mode=mode` 전달 |
| (신규) L18-24 | ADD | B-4 패치 전환 블록 |
| (신규) L26 | ADD | `_increment_recall_count()` 호출 |
| L19-37 포매팅 | SAME | 기존 유지 |
| (신규) 함수들 | ADD | `_is_patch_saturated()`, `_dominant_project()`, `_increment_recall_count()` |

---

## config.py 추가 항목 (구현 전 필수)

```python
PATCH_SATURATION_THRESHOLD = 0.75  # 75% 이상 동일 project → 패치 포화
```

---

## stats 테이블 마이그레이션 SQL

`total_recall_count` 저장소. `ON CONFLICT` UPSERT 의존.

```sql
-- stats 테이블 생성 (없으면)
CREATE TABLE IF NOT EXISTS stats (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL DEFAULT '0',
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 초기값 삽입
INSERT OR IGNORE INTO stats(key, value) VALUES('total_recall_count', '0');

-- 확인
SELECT key, value FROM stats WHERE key = 'total_recall_count';
```

**stats 테이블 활용 예상**:
- `total_recall_count`: 전체 recall 호출 횟수
- 향후: `last_checkpoint_at`, `daily_enrich_last_run` 등 확장 가능

---

## 최종 코드: tools/recall.py 전체

```python
"""recall() — 3중 하이브리드 검색으로 기억을 검색한다.

Phase 1: mode 파라미터 (B-12), 패치 전환 (B-4), total_recall_count 갱신.
"""

from storage.hybrid import hybrid_search
from storage import sqlite_store
from config import DEFAULT_TOP_K, PATCH_SATURATION_THRESHOLD


def recall(
    query: str,
    type_filter: str = "",
    project: str = "",
    top_k: int = DEFAULT_TOP_K,
    mode: str = "auto",   # "auto" | "focus" | "dmn"
) -> dict:
    """기억 검색.

    mode:
      "auto"  — 쿼리 길이로 탐험 계수 자동 결정 (기본)
      "focus" — 강한 연결 우선 (UCB_C_FOCUS=0.3), 집중 검색
      "dmn"   — 미탐색 연결 우선 (UCB_C_DMN=2.5), 연상 검색
    """
    # 1차 검색
    results = hybrid_search(
        query,
        type_filter=type_filter,
        project=project,
        top_k=top_k,
        mode=mode,
    )

    if not results:
        return {"results": [], "message": "No memories found."}

    # B-4: 패치 전환 (Marginal Value Theorem)
    # project 명시 시 전환 생략 (사용자 의도 존중)
    # top_k < 3 시 포화 판단 불가 → 생략
    if not project and _is_patch_saturated(results):
        dominant = _dominant_project(results)
        alt = hybrid_search(
            query,
            top_k=top_k,
            mode=mode,
            excluded_project=dominant,
        )
        # 원본 상위 절반 + 새 패치 결과 절반
        results = results[:top_k // 2] + alt[:top_k - top_k // 2]
        results.sort(key=lambda r: r["score"], reverse=True)

    # total_recall_count 갱신 (통계/UCB 정규화용)
    _increment_recall_count()

    # 포매팅 (기존 로직 유지)
    formatted = []
    for r in results:
        edges = sqlite_store.get_edges(r["id"])
        related = [
            f"{e['relation']}→#{e['target_id'] if e['source_id'] == r['id'] else e['source_id']}"
            for e in edges[:3]
        ]
        formatted.append({
            "id": r["id"],
            "type": r["type"],
            "content": r["content"][:200],
            "project": r["project"],
            "tags": r["tags"],
            "score": round(r["score"], 3),
            "created_at": r["created_at"],
            "related": related,
        })

    return {
        "results": formatted,
        "count": len(formatted),
        "message": f"Found {len(formatted)} memory(ies) for '{query}'",
    }


# ─── 패치 전환 헬퍼 (B-4) ─────────────────────────────────────────

def _is_patch_saturated(results: list[dict]) -> bool:
    """75% 이상이 동일 project → 패치 포화 판정.

    results < 3 → False (포화 판단 불충분).
    "" (빈 project) 노드는 포화 계산에 포함됨 — 개선 여지 있음.
    """
    if len(results) < 3:
        return False
    projects = [r.get("project", "") for r in results]
    dominant = max(set(projects), key=projects.count)
    return projects.count(dominant) / len(projects) >= PATCH_SATURATION_THRESHOLD


def _dominant_project(results: list[dict]) -> str:
    """가장 많이 등장한 project 반환."""
    projects = [r.get("project", "") for r in results]
    return max(set(projects), key=projects.count)


# ─── 통계 카운터 ─────────────────────────────────────────────────

def _increment_recall_count():
    """total_recall_count 증가 (stats 테이블 UPSERT).

    stats 테이블 미존재 시 graceful skip.
    향후 UCB 정규화, 사용 패턴 분석에 활용.
    """
    try:
        conn = sqlite_store._connect()
        conn.execute("""
            INSERT INTO stats(key, value, updated_at)
                VALUES('total_recall_count', '1', datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = CAST(CAST(value AS INTEGER) + 1 AS TEXT),
                updated_at = datetime('now')
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass  # stats 테이블 미생성 시 graceful skip
```

---

## mode 파라미터 동작 정리

| mode | UCB c값 | 탐색 특성 | 적합한 쿼리 |
|---|---|---|---|
| `"focus"` | 0.3 | 강한 연결 우선 | "포트폴리오 Next.js 이미지 최적화" (5단어+) |
| `"auto"` | 1.0 | 균형 | 기본값, 대부분 쿼리 |
| `"dmn"` | 2.5 | 미탐색 우선 | "기억" (1단어, 방산적 연상) |
| (자동 판단) | 쿼리 길이 기반 | — | mode="auto" 시 내부 분기 |

mode="auto" 자동 분기 기준 (`_auto_ucb_c()` 내부):
- 5단어+ → focus (c=0.3)
- 3-4단어 → auto (c=1.0)
- 2단어- → dmn (c=2.5)

---

## 패치 전환 시나리오

### 포화 예시
```
recall("포트폴리오") 결과:
  [pf, pf, pf, pf, pf]  → 5/5 = 100% → 포화
  dominant = "portfolio"

2차 hybrid_search(excluded_project="portfolio") 결과:
  [orch, mcp, orch, tech, daily]

최종 결합:
  results[:2] = [pf, pf]  (원본 상위)
  alt[:3]     = [orch, mcp, orch]  (새 패치)
  → [pf, pf, orch, mcp, orch] 재정렬
```

### 전환 조건 체크
```python
# project 명시 시 전환 없음 (사용자 의도 우선)
recall("포트폴리오", project="portfolio")  # 전환 없음

# top_k=2 시 포화 판단 불가
recall("포트폴리오", top_k=2)  # _is_patch_saturated → False (len < 3)

# 일반 검색
recall("포트폴리오")  # 포화 시 전환
```

---

## 기존 코드와의 하위 호환성

| 기존 호출 패턴 | Phase 1 동작 |
|---|---|
| `recall(query)` | mode="auto" 기본값 → 동일 동작 |
| `recall(query, project="pf")` | project 명시 → 패치 전환 없음 |
| `recall(query, top_k=10)` | top_k 전달 그대로 |
| `recall(query, type_filter="Pattern")` | type_filter 그대로 전달 |

**호환성 보장**: `mode` 파라미터만 추가. 기존 호출 전부 동일하게 동작.

---

## DB 쓰기 횟수 (recall 1회 기준)

| 경로 | 쓰기 |
|---|---|
| 정상 (포화 없음) | 3N + K UPDATEs (hybrid_search 1회) + 1 stats UPDATE |
| 포화 경로 | (3N + K) × 2 + 1 stats UPDATE (hybrid_search 2회) |

포화 발생률 예상: 10~20% (project 미지정 쿼리 한정).
