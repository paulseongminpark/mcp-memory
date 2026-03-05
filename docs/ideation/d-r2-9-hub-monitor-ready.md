# D-9: hub_monitor.py 실행 가능 상태 완성

> 세션 D | 2026-03-05
> DB 스키마 정합성 확인 + 3,230 노드 / 6,020 엣지 기준 예상 결과

---

## DB 스키마 정합성 확인

### node_id 타입: INTEGER (TEXT 아님)

```sql
-- sqlite_store.py L24-25
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- ← INTEGER
    ...

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES nodes(id),  -- ← INTEGER
    target_id INTEGER NOT NULL REFERENCES nodes(id),  -- ← INTEGER
```

**d-3 설계의 수정 필요 포인트:**
- `hub_snapshots.node_id TEXT` → `INTEGER`로 변경
- 쿼리에서 `"WHERE id=?"` 파라미터가 int인지 확인

### hub_snapshots 테이블: 미존재 → 스크립트 내 자동 생성

### action_log / activation_log: 미존재 (D-10에서 설계)

---

## hub_monitor.py — 실행 가능 버전

```python
#!/usr/bin/env python3
"""
허브 건강성 모니터링
실행:
  python scripts/hub_monitor.py           # 리포트 출력
  python scripts/hub_monitor.py --snapshot # 주간 스냅샷 저장
  python scripts/hub_monitor.py --alerts   # 전주 대비 이상 감지
  python scripts/hub_monitor.py --top N    # 상위 N개 (기본 10)
"""

import sqlite3
import argparse
from datetime import date
from pathlib import Path

try:
    import numpy as np
    import networkx as nx
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    print("WARNING: pip install networkx numpy")

# DB 경로 (config.py에서 읽어야 하지만 독립 실행 위해 직접 지정)
DB_PATH = Path(__file__).parent.parent / "data" / "memory.db"


def _get_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_hub_snapshots(conn):
    """hub_snapshots 테이블 없으면 생성"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hub_snapshots (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT    NOT NULL,
            node_id       INTEGER NOT NULL,  -- INTEGER (TEXT 아님)
            ihs_score     REAL,
            degree        INTEGER,
            betweenness   REAL,
            risk_level    TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_hub_snap_date "
        "ON hub_snapshots(snapshot_date, ihs_score DESC)"
    )
    conn.commit()


def load_graph(conn) -> "nx.DiGraph":
    """활성 노드의 엣지로 DiGraph 생성"""
    rows = conn.execute(
        "SELECT e.source_id, e.target_id, e.strength "
        "FROM edges e "
        "WHERE e.source_id IN (SELECT id FROM nodes WHERE status='active') "
        "  AND e.target_id IN (SELECT id FROM nodes WHERE status='active')"
    ).fetchall()

    G = nx.DiGraph()
    for r in rows:
        G.add_edge(r[0], r[1], weight=r[2])
    return G


def calculate_ihs(G: "nx.DiGraph", top_n: int = 10):
    """
    IHS = Degree Centrality + Betweenness Centrality + Neighborhood Connectivity

    3,230 노드 / 6,020 엣지 기준:
      - degree: 즉시 (~1ms)
      - betweenness: 샘플링 없이 실행 (~2-5초, 노드 수 3,230 < threshold 1000 초과)
        → k=100 샘플링 사용
      - NC: ~50ms
    """
    n_nodes = len(G.nodes)
    if n_nodes == 0:
        return [], {}, {}, {}

    # 1. Degree Centrality
    degree = nx.degree_centrality(G)

    # 2. Betweenness Centrality
    # 3,230 노드 > 1000 → 샘플링 필수
    k_sample = min(100, n_nodes)
    betweenness = nx.betweenness_centrality(G, k=k_sample, normalized=True)

    # 3. Neighborhood Connectivity (이웃의 평균 차수, 정규화)
    degree_raw = dict(G.degree())
    max_deg = max(degree_raw.values()) if degree_raw else 1
    nc = {}
    for node in G.nodes():
        neighbors = list(G.neighbors(node))
        nc[node] = (
            np.mean([degree_raw.get(n, 0) for n in neighbors]) / max_deg
            if neighbors else 0.0
        )

    # IHS 통합
    ihs = {
        node: degree.get(node, 0) + betweenness.get(node, 0) + nc.get(node, 0)
        for node in G.nodes()
    }

    top = sorted(ihs.items(), key=lambda x: -x[1])[:top_n]
    return top, degree, betweenness, nc


def hub_health_report(conn, top_n: int = 10) -> list[dict]:
    if not HAS_DEPS:
        return []

    G = load_graph(conn)
    top, degree, betweenness, nc = calculate_ihs(G, top_n)
    top_ids = {nid for nid, _ in top}

    report = []
    for node_id, ihs_score in top:
        row = conn.execute(
            "SELECT content, type, layer, tier, quality_score "
            "FROM nodes WHERE id=?", (node_id,)  # node_id는 INTEGER
        ).fetchone()
        if not row:
            continue

        # 서브허브: 차수 5 이상 이웃
        sub_hubs = [n for n in G.neighbors(node_id) if G.degree(n) >= 5]
        btwn = betweenness.get(node_id, 0)

        # 위험도
        if not sub_hubs:
            risk = "HIGH"
        elif btwn > 0.3 and len(sub_hubs) < 2:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        report.append({
            "node_id": node_id,                      # int
            "preview": row["content"][:60],
            "type": row["type"],
            "layer": row["layer"],
            "tier": row["tier"],
            "quality_score": round(row["quality_score"] or 0, 3),
            "ihs": round(ihs_score, 4),
            "degree_c": round(degree.get(node_id, 0), 4),
            "betweenness": round(btwn, 4),
            "nc": round(nc.get(node_id, 0), 4),
            "in_degree": G.in_degree(node_id),
            "out_degree": G.out_degree(node_id),
            "sub_hub_count": len(sub_hubs),
            "risk": risk,
        })

    return report


def save_snapshot(conn, report: list[dict]):
    _ensure_hub_snapshots(conn)
    today = date.today().isoformat()

    # 오늘 이미 저장했으면 skip
    exists = conn.execute(
        "SELECT COUNT(*) FROM hub_snapshots WHERE snapshot_date=?", (today,)
    ).fetchone()[0]
    if exists:
        print(f"오늘({today}) 스냅샷 이미 존재. --force 옵션으로 덮어쓰기 가능.")
        return

    for h in report:
        conn.execute(
            "INSERT INTO hub_snapshots "
            "(snapshot_date, node_id, ihs_score, degree, betweenness, risk_level) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (today, h["node_id"], h["ihs"],
             h["in_degree"] + h["out_degree"],
             h["betweenness"], h["risk"])
        )
    conn.commit()
    print(f"스냅샷 저장: {today}, {len(report)}개 허브")


def check_alerts(conn) -> list[str]:
    """전주 대비 이상 감지"""
    _ensure_hub_snapshots(conn)
    alerts = []

    rows = conn.execute("""
        SELECT curr.node_id, curr.ihs_score, prev.ihs_score AS prev_ihs,
               curr.risk_level,
               (SELECT content FROM nodes WHERE id=curr.node_id LIMIT 1) AS content
        FROM hub_snapshots curr
        JOIN hub_snapshots prev ON curr.node_id = prev.node_id
        WHERE curr.snapshot_date = (SELECT MAX(snapshot_date) FROM hub_snapshots)
          AND prev.snapshot_date = (
              SELECT MAX(snapshot_date) FROM hub_snapshots
              WHERE snapshot_date < (SELECT MAX(snapshot_date) FROM hub_snapshots)
          )
    """).fetchall()

    for row in rows:
        prev_ihs = row["prev_ihs"]
        curr_ihs = row["ihs_score"]
        content_preview = (row["content"] or "")[:30]

        if prev_ihs and prev_ihs > 0 and curr_ihs < prev_ihs * 0.8:
            alerts.append(
                f"[ALERT] IHS 20%↓ | {content_preview}... "
                f"({prev_ihs:.3f} → {curr_ihs:.3f})"
            )
        if row["risk_level"] == "HIGH":
            alerts.append(f"[ALERT] sub_hub=0 단일허브 위험 | {content_preview}...")

    return alerts


def print_report(report: list[dict]):
    print(f"\n{'='*60}")
    print(f"  Hub Health Report — Top-{len(report)}")
    print(f"{'='*60}")
    for i, h in enumerate(report, 1):
        risk_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(h["risk"], "⚪")
        print(f"\n#{i} {risk_icon} [{h['type']}] L{h['layer']} T{h['tier']}")
        print(f"   {h['preview']}")
        print(f"   IHS={h['ihs']} (D={h['degree_c']} B={h['betweenness']} NC={h['nc']})")
        print(f"   in={h['in_degree']} out={h['out_degree']} sub_hubs={h['sub_hub_count']} q={h['quality_score']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hub health monitor")
    parser.add_argument("--snapshot", action="store_true", help="주간 스냅샷 저장")
    parser.add_argument("--alerts", action="store_true", help="전주 대비 이상 감지")
    parser.add_argument("--top", type=int, default=10, help="상위 N개 (기본 10)")
    parser.add_argument("--force", action="store_true", help="스냅샷 덮어쓰기")
    args = parser.parse_args()

    conn = _get_db()
    _ensure_hub_snapshots(conn)

    report = hub_health_report(conn, top_n=args.top)

    if not args.alerts:
        print_report(report)

    if args.snapshot:
        save_snapshot(conn, report)

    if args.alerts:
        alerts = check_alerts(conn)
        if alerts:
            for a in alerts:
                print(a)
        else:
            print("이상 없음.")

    conn.close()
```

---

## 3,230 노드 / 6,020 엣지 기준 예상 결과

| 단계 | 예상 소요 | 비고 |
|------|---------|------|
| `load_graph()` | ~10ms | SQLite 읽기 |
| `degree_centrality` | ~5ms | O(V+E) |
| `betweenness_centrality` (k=100) | **2-5초** | 샘플링으로 근사 |
| NC 계산 | ~50ms | 이웃 순회 |
| DB 쿼리 (Top-10 노드 정보) | ~5ms | |
| **전체** | **~5-8초** | 허용 범위 |

**Top-10 허브 예상 형태:**
- `orchestration` 프로젝트 관련 노드 (가장 많이 연결됨)
- Layer 2-3 (Pattern, Principle) 노드 → 여러 프로젝트에서 참조
- 자주 recall된 Identity/Value 노드

---

## D-3 RBAC ↔ A-10 방화벽 공존 설계

### 전제
- A 세션 A-10: 방화벽/접근 제어 상위 설계 (상세 미확인)
- D-3 RBAC: L4/L5 + Top-10 허브에 human-in-the-loop

### 충돌 방지 원칙

**단일 체크 포인트 패턴:**
```python
# utils/access_control.py (통합 가드)

def check_node_access(
    node_id: int,
    action: str,   # "write" | "delete" | "read"
    conn,
    top10_hub_ids: set[int] | None = None,
) -> tuple[str, str]:
    """
    반환: ("ALLOWED" | "RESTRICTED" | "HUMAN_REVIEW", reason)

    우선순위:
      1. A-10 방화벽 규칙 (최상위, 미구현 시 pass)
      2. D-3 RBAC (L4/L5, Top-10 허브)
      3. 기본 허용
    """
    # Layer 1: A-10 방화벽 (A 세션 구현 후 연결)
    # if a10_firewall.check(node_id, action) == "BLOCKED":
    #     return "RESTRICTED", "a10_firewall"

    # Layer 2: D-3 RBAC
    if top10_hub_ids and node_id in top10_hub_ids:
        return "HUMAN_REVIEW", "top10_hub_protection"

    row = conn.execute(
        "SELECT layer FROM nodes WHERE id=?", (node_id,)
    ).fetchone()
    if row:
        layer = row[0]
        if layer in (4, 5):
            return "HUMAN_REVIEW", f"layer_{layer}_protection"
        if layer in (2, 3) and action == "delete":
            return "HUMAN_REVIEW", f"layer_{layer}_delete_protection"

    return "ALLOWED", ""
```

**중복 체크 방지:**
- A-10이 먼저 체크 → D-3 RBAC는 통과된 것만 받음
- `check_node_access()` 단일 함수로 통합 → 두 곳에서 각자 체크하지 않음
- A-10 구현 전에는 주석 처리, 구현 후 언코멘트

---

## 첫 실행 명령

```bash
cd /c/dev/01_projects/06_mcp-memory

# 의존성 확인
pip install networkx numpy

# 리포트 (읽기 전용)
python scripts/hub_monitor.py

# 첫 스냅샷 저장
python scripts/hub_monitor.py --snapshot

# 이후 주간 크론
# 0 9 * * 1 cd /path && python scripts/hub_monitor.py --snapshot --alerts
```
