# B-5: 맥락 의존적 재공고화

> 세션 B | 2026-03-05 | 참조: `tools/recall.py` `recall()`, `storage/hybrid.py` `_hebbian_update()`
> **구현 우선순위 1위 — 코드 변경 최소, B-6 Pruning의 데이터 소스**

## 설계 목표

Nader(2000): 기억은 인출 시마다 불안정해지고 맥락에 따라 재구성된다.
Bäuml: 재공고화 효과는 원래 학습 맥락의 접근 가능성에 달려 있다.

현재: `_hebbian_update()`는 edge frequency만 +1. 맥락 정보 없음.
목표: "이 연결이 포트폴리오 설계에서 활용됨" 같은 맥락을 edge에 기록.

---

## 구현 방식

edges 테이블 `description` 필드를 JSON 맥락 로그로 재사용 (스키마 변경 최소).

```python
# tools/recall.py — recall() 반환 직전에 호출

CONTEXT_HISTORY_LIMIT = 5  # config.py 추가: edge당 최근 5개 맥락만 유지

def _record_reconsolidation_context(result_ids: list[int], query: str,
                                     all_edges: list[dict]):
    """활성화된 edge에 사용 맥락 기록.
    저장 형식: [{"q": "포트폴리오 설계", "t": "2026-03-05T09:00:00Z"}, ...]
    이 데이터가 B-6 Pruning 맥락 다양성 판단에 사용됨.
    """
    id_set = set(result_ids)
    now = datetime.now(timezone.utc).isoformat()

    for edge in all_edges:
        src, tgt = edge['source_id'], edge['target_id']
        if src not in id_set or tgt not in id_set:
            continue

        # 기존 맥락 로드 (description이 이미 다른 포맷일 경우 초기화)
        try:
            ctx_log = json.loads(edge.get('description') or '[]')
            if not isinstance(ctx_log, list):
                ctx_log = []
        except (json.JSONDecodeError, TypeError):
            ctx_log = []

        ctx_log.append({"q": query[:80], "t": now})
        ctx_log = ctx_log[-CONTEXT_HISTORY_LIMIT:]  # 최근 5개만

        conn.execute(
            "UPDATE edges SET description=? WHERE id=?",
            (json.dumps(ctx_log, ensure_ascii=False), edge['id'])
        )
```

### recall() 수정

```python
def recall(query, type_filter="", project="", top_k=5, mode="auto"):
    results = hybrid_search(...)

    # 패치 전환 로직 (B-4)
    # ...

    # 재공고화 맥락 기록 (B-5)
    _record_reconsolidation_context(
        [n['id'] for n in results], query, all_edges
    )

    return _format(results)
```

---

## 성능 고려

활성화된 edge만 업데이트 (전체 6,020개 중 소수).
`_hebbian_update()`와 같은 DB 커넥션 재사용 가능 → 오버헤드 미미.

---

## 맥락 조회 예시

```python
# edge의 재공고화 맥락 확인:
edge = sqlite_store.get_edge(edge_id)
ctx = json.loads(edge.get('description') or '[]')
# [{"q": "포트폴리오 설계", "t": "2026-03-05T09:00:00Z"},
#  {"q": "mcp-memory v2.0", "t": "2026-03-05T11:30:00Z"}]
```

---

## DB 변경

| 테이블 | 컬럼 | 변경 사항 |
|---|---|---|
| edges | `description` | 기존 필드 재활용. 기존 텍스트 값은 마이그레이션 필요. |

마이그레이션:
```sql
-- 기존 description이 텍스트(비JSON)인 행 초기화
UPDATE edges SET description = '[]'
WHERE description IS NOT NULL
  AND json_valid(description) = 0;
```

## 검증
`inspect(edge_id)` → description JSON 확인.
며칠 사용 후 맥락 로그 누적 여부 + 쿼리 다양성 확인.
