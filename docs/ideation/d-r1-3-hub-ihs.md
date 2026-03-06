# D-3: 허브 보호 대시보드 (IHS)

> 세션 D | 2026-03-05
> Barabási 척도 없는 네트워크 이론 기반 허브 보호 설계

---

## IHS (Integrated Hubness Score) 정의

**IHS = Degree Centrality + Betweenness Centrality + Neighborhood Connectivity**

| 지표 | 의미 | 허브에서의 값 |
|------|------|-------------|
| Degree Centrality | 직접 연결 수 / 전체 | 높음 |
| Betweenness Centrality | 최단 경로 상의 중개 빈도 | 높음 |
| Neighborhood Connectivity | 이웃들의 평균 차수 (정규화) | 중간~높음 |

**단일 지표의 한계:**
- Degree만: 지역 허브 (클러스터 내부)를 놓침
- Betweenness만: 연결다리 노드 (hub가 아닌 브릿지)를 과대평가
- NC만: 주변 허브와 연결된 말단 노드를 과대평가
- IHS 통합: 세 축에서 모두 높은 노드 = 진짜 허브

---

## 구현: `scripts/hub_monitor.py`

```python
#!/usr/bin/env python3
"""
허브 건강성 모니터링 스크립트
실행: python scripts/hub_monitor.py --report
     python scripts/hub_monitor.py --snapshot (주간 저장)
"""

import sqlite3
import numpy as np
import argparse
from datetime import date
from pathlib import Path

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False
    print("WARNING: networkx not installed. Run: pip install networkx")

DB_PATH = Path("data/memory.db")


def load_graph(conn) -> "nx.DiGraph":
    """활성 엣지에서 NetworkX 그래프 생성"""
    edges = conn.execute(
        "SELECT source_id, target_id, strength "
        "FROM edges WHERE source_id IN (SELECT id FROM nodes WHERE status='active')"
        "  AND target_id IN (SELECT id FROM nodes WHERE status='active')"
    ).fetchall()

    G = nx.DiGraph()
    for e in edges:
        G.add_edge(e[0], e[1], weight=e[2])
    return G


def calculate_ihs(G: "nx.DiGraph") -> tuple[list, dict, dict, dict]:
    """
    반환: (top10_list, degree_dict, betweenness_dict, nc_dict)
    """
    if not HAS_NX:
        return [], {}, {}, {}

    # 1. Degree Centrality
    degree = nx.degree_centrality(G)

    # 2. Betweenness Centrality (노드 수에 따라 샘플링)
    n = len(G.nodes)
    if n > 1000:
        betweenness = nx.betweenness_centrality(G, k=min(100, n), normalized=True)
    else:
        betweenness = nx.betweenness_centrality(G, normalized=True)

    # 3. Neighborhood Connectivity (이웃의 평균 차수, 정규화)
    max_deg = max(dict(G.degree()).values()) if G.nodes else 1
    nc = {}
    for node in G.nodes():
        neighbors = list(G.neighbors(node))
        nc[node] = (
            np.mean([G.degree(n) for n in neighbors]) / max_deg
            if neighbors else 0.0
        )

    # IHS 통합
    ihs = {
        node: degree.get(node, 0) + betweenness.get(node, 0) + nc.get(node, 0)
        for node in G.nodes()
    }

    top10 = sorted(ihs.items(), key=lambda x: -x[1])[:10]
    return top10, degree, betweenness, nc


def hub_health_report(conn) -> list[dict]:
    """Top-10 허브 건강성 리포트 생성"""
    G = load_graph(conn)
    top10, degree, betweenness, nc = calculate_ihs(G)

    report = []
    top10_ids = {nid for nid, _ in top10}

    for node_id, ihs_score in top10:
        row = conn.execute(
            "SELECT content, type, layer, tier, quality_score "
            "FROM nodes WHERE id=?", (node_id,)
        ).fetchone()
        if not row:
            continue

        # 서브허브 (차수 5 이상 이웃)
        sub_hubs = [n for n in G.neighbors(node_id) if G.degree(n) >= 5]
        in_degree = G.in_degree(node_id)
        out_degree = G.out_degree(node_id)

        # 위험 평가
        risk = "LOW"
        if not sub_hubs:
            risk = "HIGH"       # 우회 경로 없음
        elif betweenness.get(node_id, 0) > 0.3 and len(sub_hubs) < 2:
            risk = "MEDIUM"     # 높은 중개도 + 서브허브 부족

        report.append({
            "node_id": node_id,
            "preview": row[0][:60] + ("..." if len(row[0]) > 60 else ""),
            "type": row[1],
            "layer": row[2],
            "tier": row[3],
            "quality_score": round(row[4] or 0, 3),
            "ihs": round(ihs_score, 4),
            "degree_centrality": round(degree.get(node_id, 0), 4),
            "betweenness": round(betweenness.get(node_id, 0), 4),
            "nc": round(nc.get(node_id, 0), 4),
            "in_degree": in_degree,
            "out_degree": out_degree,
            "sub_hub_count": len(sub_hubs),
            "risk": risk,
        })

    return report


def save_snapshot(conn, report: list[dict]):
    """주간 스냅샷 저장"""
    today = date.today().isoformat()

    # hub_snapshots 테이블 생성 (없으면)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hub_snapshots (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL,
            node_id       TEXT NOT NULL,
            ihs_score     REAL,
            degree        INTEGER,
            betweenness   REAL,
            risk_level    TEXT
        )
    """)

    for item in report:
        conn.execute(
            "INSERT INTO hub_snapshots "
            "(snapshot_date, node_id, ihs_score, degree, betweenness, risk_level) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (today, item["node_id"], item["ihs"],
             item["in_degree"] + item["out_degree"],
             item["betweenness"], item["risk"])
        )
    conn.commit()
    print(f"스냅샷 저장 완료: {today}, {len(report)}개 허브")


def check_alerts(conn) -> list[str]:
    """전주 대비 이상 감지"""
    alerts = []
    rows = conn.execute("""
        SELECT curr.node_id, curr.ihs_score, prev.ihs_score AS prev_ihs,
               curr.risk_level
        FROM hub_snapshots curr
        JOIN hub_snapshots prev ON curr.node_id = prev.node_id
        WHERE curr.snapshot_date = (SELECT MAX(snapshot_date) FROM hub_snapshots)
          AND prev.snapshot_date = (
            SELECT MAX(snapshot_date) FROM hub_snapshots
            WHERE snapshot_date < (SELECT MAX(snapshot_date) FROM hub_snapshots)
          )
    """).fetchall()

    for row in rows:
        node_id, curr_ihs, prev_ihs, risk = row
        if prev_ihs and curr_ihs < prev_ihs * 0.8:
            alerts.append(f"[ALERT] 허브 {node_id[:8]}... IHS {prev_ihs:.3f}→{curr_ihs:.3f} (20%↓)")
        if risk == "HIGH":
            alerts.append(f"[ALERT] 허브 {node_id[:8]}... sub_hub=0 (단일 허브 위험)")

    return alerts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--alerts", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if args.report or not any([args.snapshot, args.alerts]):
        report = hub_health_report(conn)
        print(f"\n=== Top-{len(report)} Hub Health Report ===")
        for i, h in enumerate(report, 1):
            print(f"\n#{i} [{h['risk']}] {h['preview']}")
            print(f"   Type={h['type']} Layer={h['layer']} Tier={h['tier']}")
            print(f"   IHS={h['ihs']} (D={h['degree_centrality']} B={h['betweenness']} NC={h['nc']})")
            print(f"   in={h['in_degree']} out={h['out_degree']} sub_hubs={h['sub_hub_count']}")

    if args.snapshot:
        report = hub_health_report(conn)
        save_snapshot(conn, report)

    if args.alerts:
        for alert in check_alerts(conn):
            print(alert)

    conn.close()
```

---

## RBAC 설계

### 권한 매트릭스

| 대상 | 쓰기(수정) | 삭제 | 비고 |
|------|-----------|------|------|
| L0-L1 노드 | AI 자동 | AI 자동 | 원시/행위 레이어 |
| L2-L3 노드 | AI 자동 | Human Review | 패턴/원칙 |
| L4-L5 노드 | Human Review | Human Review | 가치/공리 |
| Top-10 IHS 허브 | Human Review | Human Review | 레이어 무관 |

### 구현 설계

```python
# utils/rbac.py (신규)

def check_hub_permission(
    node_id: str,
    action: str,  # "write" | "delete"
    conn,
    top10_ids: set[str] | None = None,
) -> str:
    """
    반환값:
      "ALLOWED"                — AI가 바로 실행 가능
      "HUMAN_REVIEW_REQUIRED"  — correction_log 기록 + 플래그
    """
    # Top-10 허브 보호 (캐시 허용)
    if top10_ids and node_id in top10_ids:
        return "HUMAN_REVIEW_REQUIRED"

    # 레이어 기반 체크
    row = conn.execute("SELECT layer FROM nodes WHERE id=?", (node_id,)).fetchone()
    if not row:
        return "ALLOWED"

    layer = row[0]
    if layer in (4, 5):
        return "HUMAN_REVIEW_REQUIRED"
    if layer in (2, 3) and action == "delete":
        return "HUMAN_REVIEW_REQUIRED"

    return "ALLOWED"


def require_human_review(node_id: str, action: str, reason: str, conn):
    """Human Review 필요 시 correction_log에 플래그 기록"""
    conn.execute(
        "INSERT INTO correction_log "
        "(node_id, field, old_value, new_value, reason, corrected_by, event_type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (node_id, "status", "active", f"pending_{action}",
         reason, "rbac_guard", "human_review_required")
    )
    conn.commit()
```

**사용 예:**
```python
# mcp_server.py delete_node() 에서
from utils.rbac import check_hub_permission, require_human_review

def delete_node(node_id: str):
    perm = check_hub_permission(node_id, "delete", conn)
    if perm == "HUMAN_REVIEW_REQUIRED":
        require_human_review(node_id, "delete", "L4+ or Top-10 hub", conn)
        return {"status": "pending", "message": "Human review required"}
    # 실제 삭제 진행
    ...
```

---

## 모니터링 지표 요약

### 주간 점검 체크리스트

```
□ hub_monitor.py --snapshot 실행
□ hub_monitor.py --alerts 확인
□ Top-10 리스트 변화 검토 (신규 진입/이탈)
□ risk=HIGH 노드 수 추적 (0개 목표)
□ betweenness > 0.3 인데 sub_hub=0 인 노드 확인 → 서브허브 연결 유도
```

### 알림 트리거 규칙

| 조건 | 위험도 | 조치 |
|------|-------|------|
| IHS Top-10 degree 전주 대비 20%↓ | HIGH | 원인 파악 후 엣지 복구 |
| betweenness > 0.3 + sub_hub_count = 0 | HIGH | 서브허브(L2-3 노드) 연결 추가 |
| 신규 노드가 Top-5 허브와 연결 없이 추가 | MEDIUM | Triadic Closure 추천 실행 |
| 전체 허브 IHS 평균 10%↓ (2주 연속) | HIGH | 그래프 재구조화 검토 |
