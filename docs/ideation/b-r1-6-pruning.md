# B-6: Pruning 맥락 의존성 (Bäuml + BSP)

> 세션 B | 2026-03-05 | 참조: `daily_enrich.py`, B-5 재공고화 (데이터 소스)
> **전제: B-5 완료 후 ctx_log 데이터 쌓이면 즉시 사용 가능**

## 설계 목표

현재 pruning: 없음 (3,230 노드, 6,020 엣지 전부 유지. tier=2(auto) 78%).
단순 `frequency < threshold` 삭제 → 맥락 다양성 포함.

뇌과학 근거:
- **Bäuml (2012, 2015)**: 망각의 효과는 원래 학습 맥락의 접근 가능성에 달려 있다.
  다양한 맥락에서 활성화된 기억은 강도 낮아도 보존.
- **BSP (PMC8220807)**: 3단계 — 중요도 평가 → Probation → 아카이빙 vs 삭제
- **Maastricht (2024)**: KG에서 불필요한 트리플 삭제가 오히려 추천 성능 개선

---

## 구현 스케치

```python
# tools/prune.py (신규) 또는 daily_enrich.py Phase 6으로 통합

import math
import json
from datetime import datetime, timezone, timedelta

PRUNE_STRENGTH_THRESHOLD = 0.05    # config.py 추가
PRUNE_MIN_CONTEXT_DIVERSITY = 2    # 맥락 2개 이상 → 보존
PROBATION_DAYS = 30                # 아카이브 후 재평가 기간

def should_prune(edge: dict) -> str:
    """
    Returns: 'keep' | 'archive' | 'delete'

    판단 순서:
    1. 강도(strength) — 충분히 강하면 무조건 keep
    2. 맥락 다양성 — B-5 ctx_log 활용
       다양한 맥락에서 활성화된 edge는 강도 낮아도 keep
    3. 티어별 처분 — L3+(tier=0): archive / 낮은 티어: delete
    """
    freq = edge.get('frequency') or 0
    last_act = edge.get('last_activated')
    if last_act:
        days = (datetime.now(timezone.utc) - datetime.fromisoformat(last_act)).days
    else:
        days = 9999
    strength = freq * math.exp(-0.005 * days)

    if strength > PRUNE_STRENGTH_THRESHOLD:
        return 'keep'

    # Bäuml: 맥락 다양성 체크
    try:
        ctx_log = json.loads(edge.get('description') or '[]')
        unique_queries = len({c.get('q', '') for c in ctx_log if isinstance(c, dict)})
    except (json.JSONDecodeError, TypeError):
        unique_queries = 0

    if unique_queries >= PRUNE_MIN_CONTEXT_DIVERSITY:
        return 'keep'

    # BSP Probation: 티어별 처분
    src_tier = get_node_tier(edge['source_id'])
    if src_tier == 0:    # L3+ → 아카이브 (복구 가능)
        return 'archive'
    return 'delete'


def archive_edge(conn, edge_id: int):
    """BSP Probation: 30일 후 재평가."""
    now = datetime.now(timezone.utc)
    probation_end = (now + timedelta(days=PROBATION_DAYS)).isoformat()
    conn.execute(
        "UPDATE edges SET archived_at=?, probation_end=? WHERE id=?",
        (now.isoformat(), probation_end, edge_id)
    )


def run_pruning(conn) -> dict:
    """전체 edge 순회 → should_prune() 적용."""
    all_edges = sqlite_store.get_all_edges()
    stats = {'keep': 0, 'archive': 0, 'delete': 0}

    for edge in all_edges:
        # 이미 아카이브된 edge는 재평가
        if edge.get('archived_at'):
            probation_end = edge.get('probation_end')
            if probation_end and datetime.fromisoformat(probation_end) > datetime.now(timezone.utc):
                continue  # 아직 Probation 기간
            decision = should_prune(edge)
            if decision == 'delete':
                conn.execute("DELETE FROM edges WHERE id=?", (edge['id'],))
            else:
                conn.execute(  # 복구
                    "UPDATE edges SET archived_at=NULL, probation_end=NULL WHERE id=?",
                    (edge['id'],)
                )
            continue

        decision = should_prune(edge)
        stats[decision] += 1
        if decision == 'archive':
            archive_edge(conn, edge['id'])
        elif decision == 'delete':
            conn.execute("DELETE FROM edges WHERE id=?", (edge['id'],))

    conn.commit()
    return stats
```

---

## DB 변경

| 테이블 | 컬럼 | 타입 | 용도 |
|---|---|---|---|
| edges | `archived_at` | TEXT | BSP Probation 시작 시각 |
| edges | `probation_end` | TEXT | 재평가 시각 (30일 후) |

---

## 실행 시점
`daily_enrich.py` Phase 6 (마지막 단계, swing_toward 이후).
또는 독립 스크립트: `python -m tools.prune --dry-run` 먼저 확인.

## 검증
`--dry-run` 모드로 실행 → `stats` 출력 확인.
예상: delete < 10%, archive 15~20%, keep 70%+.
archive 비율이 너무 높으면 `PRUNE_STRENGTH_THRESHOLD` 낮추기.
