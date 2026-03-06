# D-r3-14: daily_enrich.py Phase 6 Pruning 통합 설계

> 세션 D | Round 3 | 2026-03-05
> B-6 edge pruning + D-6 node pruning + action_log 기록 통합

---

## 개요

| 단계 | 소스 | 대상 | 방법 |
|------|------|------|------|
| Phase 6-A | B-6 | edges | Bäuml ctx_log 기반 strength 평가 → archive/delete |
| Phase 6-B | D-6 Stage 2 | nodes | BSP: pruning_candidate 표시 (30일 유예) |
| Phase 6-C | D-6 Stage 3 | nodes | BSP: 30일 경과 → archived |
| Phase 6-D | A-9 | action_log | pruning 결과 기록 |

**실행 순서:** edge 먼저 → node
이유: node pruning 후 edge 평가 시 고립된 edge가 오판될 수 있음.
edge를 먼저 정리하면 node의 실제 연결도 반영됨.

---

## 1. daily_enrich.py — Phase 6 함수 전체 코드

```python
# scripts/enrich/daily_enrich.py — Phase 6 추가
# (기존 Phase 1-5 이후 맨 끝에 추가)

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def phase6_pruning(
    conn: sqlite3.Connection,
    dry_run: bool = True,
) -> dict:
    """
    Phase 6: Pruning (edge → node 순서)

    Step A: B-6 edge pruning (Bäuml ctx_log 기반 strength 평가)
    Step B: D-6 node BSP Stage 2 (pruning_candidate 표시)
    Step C: D-6 node BSP Stage 3 (30일 경과 → archived)
    Step D: action_log 기록

    Args:
        conn:     DB 연결 (daily_enrich 공유 conn 사용)
        dry_run:  True면 실제 변경 없음 (기본값)

    Returns:
        {
          "edges": {"keep": int, "archive": int, "delete": int},
          "nodes": {
            "candidates": int,
            "protected": int,
            "marked_probation": int,
            "archived": int,
          },
          "dry_run": bool,
        }
    """
    import sys
    from pathlib import Path
    ROOT = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(ROOT))

    results: dict = {"dry_run": dry_run}

    # ── Step A: Edge Pruning (B-6) ──────────────────────────────────────
    print("\n[Phase 6-A] Edge pruning (Bäuml ctx_log)...")
    edge_stats = _run_edge_pruning(conn, dry_run=dry_run)
    results["edges"] = edge_stats
    print(
        f"  edges → keep={edge_stats['keep']} "
        f"archive={edge_stats['archive']} delete={edge_stats['delete']}"
    )

    # ── Step B: Node Pruning Stage 2 (D-6) ─────────────────────────────
    print("\n[Phase 6-B] Node pruning Stage 2 (BSP candidate 표시)...")
    node_stage2 = _run_node_stage2(conn, dry_run=dry_run)
    print(
        f"  nodes → candidates={node_stage2['candidates']} "
        f"protected={node_stage2['protected']} "
        f"marked={node_stage2['marked_probation']}"
    )

    # ── Step C: Node Pruning Stage 3 (D-6) ─────────────────────────────
    print("\n[Phase 6-C] Node pruning Stage 3 (30일 경과 archive)...")
    archived_ids = _run_node_stage3(conn, dry_run=dry_run)
    print(f"  archived={len(archived_ids)}")

    results["nodes"] = {
        "candidates": node_stage2["candidates"],
        "protected": node_stage2["protected"],
        "marked_probation": node_stage2["marked_probation"],
        "archived": len(archived_ids),
    }

    # ── Step D: action_log 기록 ─────────────────────────────────────────
    if not dry_run:
        _log_pruning_action(conn, results)

    return results


# ── Step A 구현 ──────────────────────────────────────────────────────────

def _run_edge_pruning(conn: sqlite3.Connection, dry_run: bool) -> dict:
    """
    B-6 edge pruning: should_prune() 적용 → archive / delete / keep.

    ctx_log: edges.description 컬럼에 JSON 배열로 저장된 쿼리 맥락 로그.
    예: [{"q": "패턴 탐색", "ts": "2026-01-01"}, ...]
    """
    import math

    PRUNE_STRENGTH_THRESHOLD = 0.05   # config.py에서 읽어도 됨
    PRUNE_MIN_CONTEXT_DIVERSITY = 2    # 쿼리 맥락 2개 이상 → 보존

    stats = {"keep": 0, "archive": 0, "delete": 0}

    # archived_at이 없는 활성 edge만 대상 (probation 중인 것은 별도 처리)
    active_edges = conn.execute(
        "SELECT id, source_id, target_id, relation, strength, "
        "       frequency, last_activated, description, archived_at, probation_end "
        "FROM edges "
        "WHERE archived_at IS NULL"
    ).fetchall()

    now_utc = datetime.now(timezone.utc)
    now_str = now_utc.isoformat()

    for edge in active_edges:
        edge_id = edge["id"]
        freq = edge["frequency"] or 0
        last_act = edge["last_activated"]
        days = (
            (now_utc - datetime.fromisoformat(last_act)).days
            if last_act else 9999
        )
        strength = freq * math.exp(-0.005 * days)

        # 강도 기준 통과
        if strength > PRUNE_STRENGTH_THRESHOLD:
            stats["keep"] += 1
            continue

        # Bäuml: 맥락 다양성 체크
        try:
            ctx_log = json.loads(edge["description"] or "[]")
            unique_queries = len(
                {c.get("q", "") for c in ctx_log if isinstance(c, dict)}
            )
        except (json.JSONDecodeError, TypeError):
            unique_queries = 0

        if unique_queries >= PRUNE_MIN_CONTEXT_DIVERSITY:
            stats["keep"] += 1
            continue

        # BSP: source 노드 tier 조회
        src_row = conn.execute(
            "SELECT tier, layer FROM nodes WHERE id = ?", (edge["source_id"],)
        ).fetchone()
        src_tier = src_row["tier"] if src_row else 2
        src_layer = src_row["layer"] if src_row else 0

        # L3+(tier=0) 또는 layer>=2: archive (복구 가능)
        if src_tier == 0 or (src_layer is not None and src_layer >= 2):
            decision = "archive"
        else:
            decision = "delete"

        if not dry_run:
            if decision == "archive":
                probation_end = (
                    now_utc.replace(microsecond=0).isoformat()
                ).replace(
                    now_utc.year, now_utc.month, now_utc.day + 30
                    if now_utc.day + 30 <= 30 else now_utc.day
                )
                # 30일 후 날짜 계산
                from datetime import timedelta
                probation_dt = (now_utc + timedelta(days=30)).isoformat()
                conn.execute(
                    "UPDATE edges SET archived_at=?, probation_end=? WHERE id=?",
                    (now_str, probation_dt, edge_id),
                )
            else:  # delete
                conn.execute("DELETE FROM edges WHERE id=?", (edge_id,))

        stats[decision] += 1

    if not dry_run:
        conn.commit()

    return stats


# ── Step B 구현 ──────────────────────────────────────────────────────────

def _run_node_stage2(conn: sqlite3.Connection, dry_run: bool) -> dict:
    """
    D-6 BSP Stage 2: pruning 후보 식별 → pruning_candidate 표시.
    check_access()로 L4/L5 + Top-10 허브 자동 보호.
    """
    from utils.access_control import check_access

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

    candidates = conn.execute(STAGE1_SQL).fetchall()
    total_candidates = len(candidates)
    protected = 0
    allowed_ids = []

    for c in candidates:
        # check_access: L4/L5 방화벽 + Top-10 허브 보호 자동 처리
        if check_access(c["id"], "write", "system:pruning", conn):
            allowed_ids.append(c["id"])
        else:
            protected += 1

    if not dry_run:
        now_str = datetime.now(timezone.utc).isoformat()
        for nid in allowed_ids:
            conn.execute(
                "UPDATE nodes SET status='pruning_candidate', updated_at=? WHERE id=?",
                (now_str, nid),
            )
            conn.execute(
                "INSERT INTO correction_log "
                "(node_id, field, old_value, new_value, reason, corrected_by, event_type) "
                "VALUES (?, 'status', 'active', 'pruning_candidate', "
                "'BSP Stage 2: q<0.3 + obs<2 + inactive 90d + edge<3', "
                "'system:daily_enrich', 'prune_stage2')",
                (nid,),
            )
        conn.commit()

    return {
        "candidates": total_candidates,
        "protected": protected,
        "marked_probation": len(allowed_ids) if not dry_run else 0,
    }


# ── Step C 구현 ──────────────────────────────────────────────────────────

def _run_node_stage3(conn: sqlite3.Connection, dry_run: bool) -> list[int]:
    """
    D-6 BSP Stage 3: pruning_candidate 중 30일 경과 → archived.
    삭제하지 않음. status='archived'로만 전환.
    """
    expired = conn.execute(
        "SELECT id FROM nodes "
        "WHERE status = 'pruning_candidate' "
        "  AND updated_at < datetime('now', '-30 days')"
    ).fetchall()

    expired_ids = [r["id"] for r in expired]

    if not expired_ids or dry_run:
        if dry_run and expired_ids:
            print(f"  [DRY RUN] {len(expired_ids)}개 archive 예정")
        return expired_ids

    now_str = datetime.now(timezone.utc).isoformat()
    for nid in expired_ids:
        conn.execute(
            "UPDATE nodes SET status='archived', updated_at=? WHERE id=?",
            (now_str, nid),
        )
        conn.execute(
            "INSERT INTO correction_log "
            "(node_id, field, old_value, new_value, reason, corrected_by, event_type) "
            "VALUES (?, 'status', 'pruning_candidate', 'archived', "
            "'BSP Stage 3: 30-day grace period expired', "
            "'system:daily_enrich', 'prune_stage3')",
            (nid,),
        )
    conn.commit()

    return expired_ids


# ── Step D: action_log 기록 ──────────────────────────────────────────────

def _log_pruning_action(conn: sqlite3.Connection, results: dict) -> None:
    """
    A-9 action_log에 pruning 결과 기록.
    action_type="archive" (노드 비활성화)
    """
    try:
        from storage import action_log as al
        al.record(
            action_type="archive",
            actor="system:daily_enrich",
            target_type="graph",
            params=json.dumps({"phase": 6, "description": "BSP pruning + edge cleanup"}),
            result=json.dumps({
                "edges_keep":    results["edges"]["keep"],
                "edges_archive": results["edges"]["archive"],
                "edges_delete":  results["edges"]["delete"],
                "nodes_candidates":  results["nodes"]["candidates"],
                "nodes_protected":   results["nodes"]["protected"],
                "nodes_probation":   results["nodes"]["marked_probation"],
                "nodes_archived":    results["nodes"]["archived"],
            }),
        )
    except Exception:
        pass  # action_log 실패는 무음 처리
```

---

## 2. daily_enrich.py — run_daily() 에 Phase 6 통합

```python
# scripts/enrich/daily_enrich.py — run_daily() 또는 main() 수정

def run_daily(dry_run: bool = True):
    """
    Daily enrichment 전체 파이프라인 실행.
    Phase 1-5: 기존 enrichment
    Phase 6: Pruning (신규)
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    try:
        # ... 기존 Phase 1-5 ...

        # Phase 6: Pruning (dry_run 모드로 먼저 실행 권장)
        print("\n" + "="*50)
        print("Phase 6: Pruning")
        print("="*50)
        pruning_result = phase6_pruning(conn, dry_run=dry_run)

        if dry_run:
            print("\n[DRY-RUN 완료] 실제 변경 없음.")
            print("실제 실행: run_daily(dry_run=False)")
        else:
            print(f"\nPhase 6 완료: {pruning_result}")

    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="dry-run 해제")
    parser.add_argument("--phase", type=int, default=6, help="특정 phase만 실행")
    args = parser.parse_args()

    if args.phase == 6:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        result = phase6_pruning(conn, dry_run=not args.execute)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        conn.close()
    else:
        run_daily(dry_run=not args.execute)
```

---

## 3. 실행 순서 요약

```
Phase 6 실행 흐름:
─────────────────────────────────────────────
[입력] 3,230 nodes (active), 6,020 edges

[6-A] Edge pruning
  ├── 전체 active edge 순회
  ├── strength = freq × exp(-0.005 × days) 계산
  ├── ctx_log 맥락 다양성 체크 (Bäuml)
  └── keep / archive / delete 판정

[6-B] Node Stage 2
  ├── STAGE1_SQL: q<0.3 + obs<2 + inactive 90d + edge<3 + L0/L1
  ├── check_access(): L4/L5 + Top-10 허브 자동 보호
  └── 통과한 노드 → status='pruning_candidate'

[6-C] Node Stage 3
  ├── status='pruning_candidate' + updated_at < -30days
  └── → status='archived' (삭제 아님, 복구 가능)

[6-D] action_log 기록
  └── action_type="archive", result=JSON(전체 통계)

[출력] {
  "edges": {"keep": N, "archive": N, "delete": N},
  "nodes": {"candidates": N, "protected": N,
            "marked_probation": N, "archived": N}
}
─────────────────────────────────────────────
```

---

## 4. 예상 결과 (3,230 nodes, 6,020 edges 기준)

### Edge (B-6 예상)
| 결과 | 예상 % | 설명 |
|------|--------|------|
| keep | 70-75% | 강도 충분 또는 맥락 다양 |
| archive | 15-20% | L3+ tier=0, 30일 재평가 |
| delete | 5-10% | 낮은 tier, 완전 유예 |

### Node (D-6 예상)
| 결과 | 예상 % | 설명 |
|------|--------|------|
| 조건 충족 후보 | 5-15% | q<0.3 + 비활성 90일 + edge<3 |
| 보호 (access denied) | ~1% | L4/L5, Top-10 허브 |
| pruning_candidate | 4-14% | 30일 유예 시작 |
| archived (stage3) | 0% (초기 실행 시) | 30일 후부터 발생 |

---

## 5. 운영 주기 및 명령어

```bash
# dry-run 먼저 (기본)
cd /c/dev/01_projects/06_mcp-memory
python scripts/enrich/daily_enrich.py --phase 6

# 실제 실행 (검토 후)
python scripts/enrich/daily_enrich.py --phase 6 --execute

# 전체 daily_enrich (Phase 1-6)
python scripts/enrich/daily_enrich.py --execute

# 30일 후 Stage 3 결과 확인
python scripts/pruning.py --status

# 아카이브 복구 (필요 시)
# sqlite3 data/memory.db
# UPDATE nodes SET status='active' WHERE id=<ID>;
```

---

## 6. 파일 변경 요약

| 파일 | 변경 | 비고 |
|------|------|------|
| `scripts/enrich/daily_enrich.py` | `phase6_pruning()` + `_run_edge_pruning()` + `_run_node_stage2/3()` + `_log_pruning_action()` 추가 | 기존 Phase 1-5 변경 없음 |
| `utils/access_control.py` | d-r3-13에서 구현 | check_access() 제공 |
| `storage/action_log.py` | a-r1-9 설계 기반 | record() 구현 필요 |
| `config.py` | `PRUNE_STRENGTH_THRESHOLD=0.05`, `PRUNE_MIN_CONTEXT_DIVERSITY=2` 추가 | |

**의존 관계:**
- Phase 6-A: B-6 `should_prune()` 로직 inline (tools/prune.py 미사용)
- Phase 6-B: `utils/access_control.check_access()` 필요 (d-r3-13)
- Phase 6-D: `storage/action_log.record()` 필요 (a-r1-9)
- Phase 6-B hub 보호: `hub_snapshots` 테이블 필요 (hub_monitor.py --snapshot 선행)
