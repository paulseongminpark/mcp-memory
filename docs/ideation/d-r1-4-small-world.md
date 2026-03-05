# D-4: 스몰 월드 특성 측정 + 유지

> 세션 D | 2026-03-05
> Watts-Strogatz (1998) 이론 + Kleinberg 내비게이션 기반 설계

---

## 스몰 월드 이론 요약

**조건:** 높은 클러스터링 계수(C) + 짧은 평균 경로 길이(L)

**지표 — Small World Index σ:**
```
σ = (C / C_r) / (L / L_r)
C_r, L_r = 동일 크기 Erdős–Rényi 랜덤 그래프의 기준값
σ > 1 → Small World
σ >> 1 → Strong Small World
```

**mcp-memory에서 스몰 월드가 중요한 이유:**
- 임의의 두 기억이 짧은 경로로 연결 (recall 효율)
- 클러스터 내 기억은 서로 강하게 연결 (프로젝트/주제 응집)
- 허브를 통한 글로벌 접근성 유지

---

## 측정 스크립트: `scripts/small_world_audit.py`

```python
#!/usr/bin/env python3
"""
스몰 월드 특성 측정 + 주간 리포트
실행: python scripts/small_world_audit.py
"""

import sqlite3
import numpy as np
import json
from datetime import date
from pathlib import Path

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

DB_PATH = Path("data/memory.db")
REPORT_PATH = Path("data/reports")


def load_active_edges(conn) -> list:
    return conn.execute(
        "SELECT source_id, target_id, strength "
        "FROM edges "
        "WHERE source_id IN (SELECT id FROM nodes WHERE status='active') "
        "  AND target_id IN (SELECT id FROM nodes WHERE status='active')"
    ).fetchall()


def measure_small_world(conn) -> dict:
    if not HAS_NX:
        return {"error": "networkx not installed"}

    edges = load_active_edges(conn)
    if len(edges) < 3:
        return {"error": "not enough edges"}

    G = nx.DiGraph()
    G.add_edges_from([(e[0], e[1]) for e in edges])
    G_u = G.to_undirected()

    # 최대 연결 컴포넌트만 (고립 노드 제외)
    components = list(nx.connected_components(G_u))
    if not components:
        return {"error": "no connected components"}

    largest_cc = max(components, key=len)
    G_sub = G_u.subgraph(largest_cc).copy()

    n = len(G_sub.nodes)
    m = len(G_sub.edges)

    # 클러스터링 계수
    C = nx.average_clustering(G_sub)

    # 평균 경로 길이 (대규모 시 샘플링)
    if n > 500:
        # 500개 샘플로 근사
        sample_nodes = list(G_sub.nodes)[:500]
        G_sample = G_sub.subgraph(sample_nodes)
        # 샘플이 연결되어 있는지 확인
        if nx.is_connected(G_sample):
            L = nx.average_shortest_path_length(G_sample)
        else:
            # 최대 CC만
            sample_cc = max(nx.connected_components(G_sample), key=len)
            L = nx.average_shortest_path_length(G_sample.subgraph(sample_cc))
    else:
        if nx.is_connected(G_sub):
            L = nx.average_shortest_path_length(G_sub)
        else:
            return {"error": "graph not connected (unexpected)"}

    # Erdős–Rényi 기준값
    p = 2 * m / (n * (n - 1)) if n > 1 else 0.001
    C_r = p
    L_r = np.log(n) / np.log(n * p) if (n * p) > 1 else float('inf')

    # Small World Index σ
    sigma = (C / max(C_r, 1e-9)) / (L / max(L_r, 1e-9)) if L_r != float('inf') else 0.0

    return {
        "date": date.today().isoformat(),
        "node_count": n,
        "edge_count": m,
        "clustering_coeff": round(C, 4),
        "avg_path_length": round(L, 4),
        "random_clustering": round(C_r, 6),
        "random_path_length": round(L_r, 4) if L_r != float('inf') else None,
        "small_world_sigma": round(sigma, 4),
        "is_small_world": sigma > 1.0,
        "density": round(2 * m / (n * (n - 1)), 6) if n > 1 else 0,
        "largest_cc_fraction": round(len(largest_cc) / len(G_u.nodes), 3),
    }


def save_report(metrics: dict):
    REPORT_PATH.mkdir(parents=True, exist_ok=True)
    report_file = REPORT_PATH / f"small_world_{metrics['date']}.json"
    with open(report_file, "w") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"리포트 저장: {report_file}")


def print_report(metrics: dict):
    if "error" in metrics:
        print(f"오류: {metrics['error']}")
        return

    status = "✅ Small World" if metrics["is_small_world"] else "❌ Not Small World"
    print(f"\n=== 스몰 월드 분석 ({metrics['date']}) ===")
    print(f"상태: {status} (σ={metrics['small_world_sigma']})")
    print(f"노드: {metrics['node_count']} | 엣지: {metrics['edge_count']}")
    print(f"클러스터링 계수: {metrics['clustering_coeff']} (랜덤: {metrics['random_clustering']})")
    print(f"평균 경로 길이: {metrics['avg_path_length']} (랜덤: {metrics['random_path_length']})")
    print(f"밀도: {metrics['density']}")
    print(f"최대 CC 비율: {metrics['largest_cc_fraction']}")


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    metrics = measure_small_world(conn)
    print_report(metrics)
    save_report(metrics)
    conn.close()
```

---

## Triadic Closure — 클러스터링 유지 메커니즘

**이론:** A-B 강연결 + B-C 강연결 → A-C 연결 확률 높음 (실제 사회 네트워크 패턴)

**mcp-memory에서 자연 발생:** recall() 시 같은 세션에서 함께 나온 노드들이 Hebbian으로 연결됨 → 클러스터링 계수 자연 상승.

**수동 추천 SQL (주간 배치):**
```sql
-- A→B, B→C 인데 A→C 없는 삼각형 후보 (Triadic Closure 추천)
SELECT DISTINCT
    n_a.content AS node_A_preview,
    n_c.content AS node_C_preview,
    e1.source_id AS A,
    e2.target_id AS C,
    e1.relation   AS A_to_B_rel,
    e2.relation   AS B_to_C_rel,
    (e1.strength + e2.strength) / 2.0 AS avg_strength
FROM edges e1
JOIN edges e2 ON e1.target_id = e2.source_id
LEFT JOIN edges e3
    ON e3.source_id = e1.source_id
   AND e3.target_id = e2.target_id
JOIN nodes n_a ON n_a.id = e1.source_id
JOIN nodes n_c ON n_c.id = e2.target_id
WHERE e3.id IS NULL                    -- A→C 없는 경우
  AND e1.source_id != e2.target_id     -- 자기 참조 제외
  AND n_a.status = 'active'
  AND n_c.status = 'active'
  AND e1.strength > 0.5                -- 강한 연결만
  AND e2.strength > 0.5
ORDER BY avg_strength DESC
LIMIT 20;
```

**스크립트: `scripts/triadic_suggest.py`**
```python
#!/usr/bin/env python3
"""
Triadic Closure 추천 — 주간 배치 실행
실행: python scripts/triadic_suggest.py [--auto-insert]
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/memory.db")

TRIADIC_QUERY = """
SELECT DISTINCT
    e1.source_id AS A, e2.target_id AS C,
    n_a.content AS a_preview, n_c.content AS c_preview,
    e1.relation AS a_b_rel, e2.relation AS b_c_rel,
    (e1.strength + e2.strength) / 2.0 AS avg_strength,
    n_a.layer AS a_layer, n_c.layer AS c_layer
FROM edges e1
JOIN edges e2 ON e1.target_id = e2.source_id
LEFT JOIN edges e3
    ON e3.source_id = e1.source_id AND e3.target_id = e2.target_id
JOIN nodes n_a ON n_a.id = e1.source_id
JOIN nodes n_c ON n_c.id = e2.target_id
WHERE e3.id IS NULL
  AND e1.source_id != e2.target_id
  AND n_a.status = 'active' AND n_c.status = 'active'
  AND e1.strength > 0.5 AND e2.strength > 0.5
ORDER BY avg_strength DESC
LIMIT 20
"""

def suggest_triadic(conn) -> list[dict]:
    rows = conn.execute(TRIADIC_QUERY).fetchall()
    return [
        {
            "A": r[0], "C": r[1],
            "a_preview": r[2][:40], "c_preview": r[3][:40],
            "suggested_relation": _infer_relation(r[4], r[5]),
            "avg_strength": round(r[6], 3),
        }
        for r in rows
    ]

def _infer_relation(a_b_rel: str, b_c_rel: str) -> str:
    """A→B 관계 + B→C 관계로 A→C 추천 관계 추론 (단순 휴리스틱)"""
    TRANSITIVE = {"led_to", "caused_by", "resulted_in", "generated", "abstracted_from"}
    if a_b_rel in TRANSITIVE and b_c_rel in TRANSITIVE:
        return "led_to"
    SUPPORT = {"supports", "reinforces_mutually", "validates"}
    if a_b_rel in SUPPORT and b_c_rel in SUPPORT:
        return "reinforces_mutually"
    return "connects_with"  # 기본값

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-insert", action="store_true",
                        help="추천 엣지 자동 삽입 (주의: 검토 후 사용)")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    suggestions = suggest_triadic(conn)

    print(f"\n=== Triadic Closure 추천 ({len(suggestions)}개) ===")
    for i, s in enumerate(suggestions, 1):
        print(f"\n#{i} A: {s['a_preview']}")
        print(f"    C: {s['c_preview']}")
        print(f"    추천 관계: {s['suggested_relation']} (강도 기반: {s['avg_strength']})")

    conn.close()
```

---

## Swing-Toward Rewiring (월 1회)

**이론:** 차수를 보존하면서 클러스터링 계수를 올리는 rewiring 알고리즘.
출처: Journal of Complex Networks

```python
# scripts/rewire_small_world.py

import random
import networkx as nx

def swing_toward_rewire(
    G: nx.Graph,
    target_clustering: float = 0.3,
    max_iter: int = 1000
) -> nx.Graph:
    """
    차수 보존 + 클러스터링 계수 상승.
    그래프는 undirected 사본으로 작업 (원본 불변).
    """
    G = G.copy()
    edges = list(G.edges())
    n_rewired = 0

    for iteration in range(max_iter):
        current_C = nx.average_clustering(G)
        if current_C >= target_clustering:
            print(f"목표 클러스터링 {target_clustering} 달성 ({iteration} 반복)")
            break

        if len(edges) < 2:
            break

        # 두 엣지 무작위 선택
        e1, e2 = random.sample(edges, 2)
        A, B = e1
        C, D = e2

        # A, C가 공통 이웃 공유 → rewire 유리
        common_neighbors = set(G.neighbors(A)) & set(G.neighbors(C))
        if (common_neighbors
                and not G.has_edge(A, C)
                and not G.has_edge(B, D)
                and A != D and B != C):

            G.remove_edge(A, B)
            G.remove_edge(C, D)
            G.add_edge(A, C)
            G.add_edge(B, D)

            # 엣지 리스트 업데이트
            edges = list(G.edges())
            n_rewired += 1

    print(f"Rewiring 완료: {n_rewired}개 엣지 재연결, 최종 C={nx.average_clustering(G):.4f}")
    return G
```

**주의:** Swing-toward는 무방향 그래프 기반. mcp-memory는 방향 그래프이므로 적용 시:
1. `G.to_undirected()` 로 undirected 사본 생성
2. rewiring 후 σ 계산
3. 실제 DB 반영은 하지 않고 리포트만 (권장 방향만 제시)

---

## 목표 수치

| 지표 | 현재 (측정 필요) | 목표 |
|------|----------------|------|
| σ (Small World Index) | 미측정 | > 1.5 |
| 클러스터링 계수 C | 미측정 | > 0.2 |
| 평균 경로 길이 L | 미측정 | < log(n) |
| 최대 CC 비율 | 미측정 | > 0.85 |
| Triadic Closure 달성률 | 미측정 | 주간 상위 20개 처리 |
