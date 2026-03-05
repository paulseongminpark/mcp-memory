# D-6: Pruning 구현 설계

> 세션 D | 2026-03-05
> BSP (Biological Synaptic Pruning) 3단계 + 맥락 의존적 보호

---

## 이론적 기반

### 시냅스 가지치기 (섹션 2.3)
- 인간 뇌: 청소년기 시냅스의 약 50% 제거 → 효율 증가
- "덜어냄이 성장이다" — 핵심 연결 강화, 노이즈 제거

### Bäuml (1998) 맥락 의존적 망각
- 같은 맥락(프로젝트/도메인) 내에서는 기억을 더 잘 보존
- 고립된 기억은 더 빠르게 소실

### BSP 3단계 설계 원칙
1. **평가** (Stage 1): 중요도 점수화
2. **유예** (Stage 2): 30일 관찰 기간
3. **아카이브** (Stage 3): 삭제 아님 (영구 보존, 비활성화)

---

## Stage 1: 후보 식별

### 기본 조건 SQL

```sql
-- scripts/pruning.py 내 사용
SELECT
    n.id,
    n.content,
    n.type,
    n.layer,
    n.quality_score,
    n.observation_count,
    n.last_activated,
    n.created_at,
    n.tier,
    COUNT(e.id) AS edge_count,
    -- 가중 중요도 점수 (낮을수록 pruning 대상)
    (
        COALESCE(n.quality_score, 0) * 0.4 +
        COALESCE(CAST(n.observation_count AS REAL) / 10.0, 0) * 0.3 +
        CASE
            WHEN n.last_activated IS NULL THEN 0
            ELSE MAX(0, 1.0 - (julianday('now') - julianday(n.last_activated)) / 90.0)
        END * 0.3
    ) AS importance_score
FROM nodes n
LEFT JOIN edges e ON (e.source_id = n.id OR e.target_id = n.id)
    AND e.source_id IN (SELECT id FROM nodes WHERE status='active')
    AND e.target_id IN (SELECT id FROM nodes WHERE status='active')
WHERE n.status = 'active'
  -- 조건 1: 낮은 품질
  AND COALESCE(n.quality_score, 0) < 0.3
  -- 조건 2: 낮은 관찰 수
  AND COALESCE(n.observation_count, 0) < 2
  -- 조건 3: 장기 비활성
  AND (
      n.last_activated IS NULL
      OR n.last_activated < datetime('now', '-90 days')
  )
  -- 조건 4: 레이어 제한 (L2 이상은 보호)
  AND n.layer IN (0, 1)
GROUP BY n.id
-- 조건 5: 허브 연결 없음 (엣지 3개 미만)
HAVING edge_count < 3
ORDER BY importance_score ASC, n.last_activated ASC
LIMIT 100;
```

### 보호 우선순위 (제외 조건)

```sql
-- 위 쿼리에 추가 NOT IN:

-- 보호 1: L2 이상 (패턴/원칙/가치)
-- → WHERE n.layer IN (0, 1) 로 이미 처리

-- 보호 2: Top-10 허브에 직접 연결된 노드
AND n.id NOT IN (
    SELECT DISTINCT e.source_id FROM edges e
    WHERE e.target_id IN (SELECT node_id FROM hub_snapshots
                          WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM hub_snapshots)
                          AND risk_level = 'LOW'
                          ORDER BY ihs_score DESC LIMIT 10)
    UNION
    SELECT DISTINCT e.target_id FROM edges e
    WHERE e.source_id IN (SELECT node_id FROM hub_snapshots
                          WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM hub_snapshots)
                          ORDER BY ihs_score DESC LIMIT 10)
)
```

---

## Stage 2: 유예 (30일)

```python
# scripts/pruning.py

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("data/memory.db")

STAGE1_SQL = """
SELECT
    n.id, n.content, n.type, n.layer, n.quality_score,
    n.observation_count, n.last_activated, n.tier,
    COUNT(e.id) AS edge_count,
    (
        COALESCE(n.quality_score, 0) * 0.4 +
        COALESCE(CAST(n.observation_count AS REAL) / 10.0, 0) * 0.3 +
        CASE
            WHEN n.last_activated IS NULL THEN 0
            ELSE MAX(0, 1.0 - (julianday('now') - julianday(n.last_activated)) / 90.0)
        END * 0.3
    ) AS importance_score
FROM nodes n
LEFT JOIN edges e ON (e.source_id = n.id OR e.target_id = n.id)
WHERE n.status = 'active'
  AND COALESCE(n.quality_score, 0) < 0.3
  AND COALESCE(n.observation_count, 0) < 2
  AND (n.last_activated IS NULL OR n.last_activated < datetime('now', '-90 days'))
  AND n.layer IN (0, 1)
GROUP BY n.id
HAVING edge_count < 3
ORDER BY importance_score ASC
LIMIT 100
"""


def stage1_identify(conn) -> list[dict]:
    """Stage 1: pruning 후보 식별"""
    rows = conn.execute(STAGE1_SQL).fetchall()
    return [
        {
            "id": r[0],
            "content_preview": r[1][:60],
            "type": r[2],
            "layer": r[3],
            "quality_score": r[4],
            "observation_count": r[5],
            "last_activated": r[6],
            "tier": r[7],
            "edge_count": r[8],
            "importance_score": round(r[9], 4),
        }
        for r in rows
    ]


def stage2_mark_candidates(conn, candidate_ids: list[str], dry_run: bool = True) -> int:
    """Stage 2: 후보 노드를 pruning_candidate 상태로 전환"""
    if not candidate_ids:
        return 0

    if dry_run:
        print(f"[DRY RUN] {len(candidate_ids)}개 노드를 pruning_candidate로 표시 예정")
        return len(candidate_ids)

    now = datetime.now(timezone.utc).isoformat()

    for nid in candidate_ids:
        # 상태 변경
        conn.execute(
            "UPDATE nodes SET status='pruning_candidate', updated_at=? WHERE id=?",
            (now, nid)
        )
        # correction_log 기록
        conn.execute(
            "INSERT INTO correction_log "
            "(node_id, field, old_value, new_value, reason, corrected_by, event_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nid, "status", "active", "pruning_candidate",
             "BSP Stage 2: low quality + low activation + few edges",
             "pruning_script", "prune_stage2")
        )

    conn.commit()
    print(f"Stage 2 완료: {len(candidate_ids)}개 노드 → pruning_candidate")
    return len(candidate_ids)
```

---

## Stage 3: 아카이브

```python
def stage3_archive(conn, dry_run: bool = True) -> list[str]:
    """
    Stage 3: 유예 30일 경과한 pruning_candidate → archived
    삭제하지 않음. 영구 보존 + 비활성화.
    """
    expired = conn.execute(
        "SELECT id, content FROM nodes "
        "WHERE status='pruning_candidate' "
        "  AND updated_at < datetime('now', '-30 days')"
    ).fetchall()

    if not expired:
        print("아카이브 대상 없음 (유예 기간 미경과)")
        return []

    expired_ids = [r[0] for r in expired]

    if dry_run:
        print(f"[DRY RUN] {len(expired_ids)}개 노드 아카이브 예정:")
        for r in expired[:5]:
            print(f"  - {r[0][:8]}... {r[1][:40]}")
        return expired_ids

    now = datetime.now(timezone.utc).isoformat()

    for nid, content in expired:
        conn.execute(
            "UPDATE nodes SET status='archived', updated_at=? WHERE id=?",
            (now, nid)
        )
        conn.execute(
            "INSERT INTO correction_log "
            "(node_id, field, old_value, new_value, reason, corrected_by, event_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nid, "status", "pruning_candidate", "archived",
             "BSP Stage 3: 30-day grace period expired",
             "pruning_script", "prune_stage3")
        )

    conn.commit()
    print(f"Stage 3 완료: {len(expired_ids)}개 노드 → archived")
    return expired_ids
```

---

## 맥락 의존적 Pruning (Bäuml)

```python
def contextual_pruning_weight(
    node: dict,
    conn,
    top10_hub_ids: set[str],
) -> float:
    """
    맥락 보호 가중치. 0.0 = 보호 (pruning 제외), 1.0 = 정상 대상.

    보호 조건:
    1. 같은 프로젝트 내 강한 연결 (edge 3개 이상)
    2. Top-10 허브와 직접 연결
    3. 최근 14일 내 같은 세션에서 함께 활성화된 노드와 연결

    근거 (Bäuml): 같은 맥락의 기억은 서로를 강화함.
    """
    node_id = node["id"]
    project = node.get("project", "")

    # 보호 1: 허브 직접 연결
    if node_id in top10_hub_ids:
        return 0.0

    hub_connections = conn.execute(
        "SELECT COUNT(*) FROM edges "
        "WHERE (source_id=? AND target_id IN ({})) "
        "   OR (target_id=? AND source_id IN ({}))".format(
            ",".join("?" * len(top10_hub_ids)),
            ",".join("?" * len(top10_hub_ids))
        ),
        [node_id] + list(top10_hub_ids) + [node_id] + list(top10_hub_ids)
    ).fetchone()[0] if top10_hub_ids else 0

    if hub_connections > 0:
        return 0.0

    # 보호 2: 프로젝트 내 연결 밀도
    if project:
        same_proj_edges = conn.execute(
            "SELECT COUNT(*) FROM edges e "
            "JOIN nodes n2 ON (e.target_id = n2.id OR e.source_id = n2.id) "
            "WHERE (e.source_id = ? OR e.target_id = ?) "
            "  AND n2.project = ? AND n2.id != ?",
            (node_id, node_id, project, node_id)
        ).fetchone()[0]

        if same_proj_edges >= 3:
            return 0.0  # 프로젝트 내 허브 역할

    # 보호 3: 최근 공동 활성화 (14일)
    recent_co_activated = conn.execute(
        "SELECT COUNT(DISTINCT al2.node_id) "
        "FROM activation_log al1 "
        "JOIN activation_log al2 ON al1.session_id = al2.session_id "
        "WHERE al1.node_id = ? "
        "  AND al2.node_id != ? "
        "  AND al1.activated_at >= datetime('now', '-14 days')",
        (node_id, node_id)
    ).fetchone()[0]

    if recent_co_activated >= 2:
        return 0.5  # 절반 보호 (가중치 감소)

    return 1.0  # 정상 pruning 대상


def apply_contextual_weights(
    candidates: list[dict],
    conn,
    top10_hub_ids: set[str],
) -> list[dict]:
    """후보 목록에 contextual 가중치 적용 → 보호 대상 제거"""
    filtered = []
    for cand in candidates:
        weight = contextual_pruning_weight(cand, conn, top10_hub_ids)
        if weight > 0:
            cand["pruning_weight"] = weight
            filtered.append(cand)
        else:
            print(f"  보호: {cand['content_preview'][:40]} (weight=0)")
    return filtered
```

---

## 전체 실행 스크립트

```python
#!/usr/bin/env python3
"""
scripts/pruning.py — BSP 3단계 실행
실행:
  python scripts/pruning.py --stage=1           # 후보 탐색
  python scripts/pruning.py --stage=2           # 유예 표시 (dry-run)
  python scripts/pruning.py --stage=2 --execute # 실제 실행
  python scripts/pruning.py --stage=3           # 아카이브 (dry-run)
  python scripts/pruning.py --stage=3 --execute # 실제 실행
  python scripts/pruning.py --status            # 현재 pruning 상태 요약
"""
import argparse
import sqlite3
from pathlib import Path

DB_PATH = Path("data/memory.db")

def get_top10_hub_ids(conn) -> set:
    """최근 hub_snapshots에서 Top-10 허브 ID 로드"""
    rows = conn.execute(
        "SELECT node_id FROM hub_snapshots "
        "WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM hub_snapshots) "
        "ORDER BY ihs_score DESC LIMIT 10"
    ).fetchall()
    return {r[0] for r in rows}


def print_status(conn):
    """현재 pruning 상태 요약"""
    counts = conn.execute(
        "SELECT status, COUNT(*) FROM nodes GROUP BY status"
    ).fetchall()
    print("\n=== 노드 상태 요약 ===")
    for status, count in counts:
        print(f"  {status}: {count}개")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, choices=[1, 2, 3])
    parser.add_argument("--execute", action="store_true",
                        help="dry-run 해제하여 실제 실행")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if args.status:
        print_status(conn)

    elif args.stage == 1:
        candidates = stage1_identify(conn)
        top10_ids = get_top10_hub_ids(conn)
        filtered = apply_contextual_weights(candidates, conn, top10_ids)
        print(f"\n=== Stage 1 결과: {len(filtered)}개 후보 ===")
        for c in filtered[:10]:
            print(f"  [{c['type']}] L{c['layer']} q={c['quality_score']:.2f} "
                  f"e={c['edge_count']} | {c['content_preview']}")

    elif args.stage == 2:
        candidates = stage1_identify(conn)
        top10_ids = get_top10_hub_ids(conn)
        filtered = apply_contextual_weights(candidates, conn, top10_ids)
        ids = [c["id"] for c in filtered]
        stage2_mark_candidates(conn, ids, dry_run=not args.execute)

    elif args.stage == 3:
        stage3_archive(conn, dry_run=not args.execute)

    conn.close()
```

---

## 운영 주기

| 단계 | 실행 주기 | 명령 |
|------|---------|------|
| Stage 1 (탐색) | 월 1회 | `python scripts/pruning.py --stage=1` |
| Stage 2 (유예 표시) | 검토 후 수동 | `python scripts/pruning.py --stage=2 --execute` |
| Stage 3 (아카이브) | 자동 (30일 후) | `python scripts/pruning.py --stage=3 --execute` |
| 상태 확인 | 수시 | `python scripts/pruning.py --status` |
| 허브 스냅샷 (보호용) | 주 1회 | `python scripts/hub_monitor.py --snapshot` |

**주의:** Stage 3는 `archived` 상태로 변경할 뿐 실제 삭제 없음. 복구 가능:
```sql
UPDATE nodes SET status='active', updated_at=CURRENT_TIMESTAMP WHERE id='NODE_ID';
```
