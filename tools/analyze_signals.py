"""analyze_signals() — Signal 클러스터 분석 → 승격 후보 반환."""

import json
from collections import defaultdict

from config import VALID_PROMOTIONS
from storage import sqlite_store


def analyze_signals(
    domain: str = "",
    min_cluster_size: int = 2,
    top_k: int = 5,
) -> dict:
    """Signal 타입 노드를 클러스터링하여 승격 후보를 반환한다.

    태그·핵심개념·도메인 겹침으로 그룹핑한 뒤
    각 클러스터의 성숙도를 계산하여 승격 권고를 반환.
    """
    # 1. Signal 노드 조회
    sql = "SELECT * FROM nodes WHERE type = 'Signal' AND status = 'active'"
    params: list = []
    if domain:
        sql += " AND domains LIKE ?"
        params.append(f'%"{domain}"%')
    with sqlite_store._db() as conn:
        rows = conn.execute(sql, params).fetchall()

    signals = [dict(r) for r in rows]
    if not signals:
        return {
            "clusters": [], "total_signals": 0, "clustered_count": 0,
            "message": "No Signal nodes found.",
        }

    # 2. 피처 추출 (tags, key_concepts, domains)
    features: dict[int, set[str]] = {}
    for s in signals:
        feats: set[str] = set()
        for t in (s.get("tags") or "").split(","):
            t = t.strip().lower()
            if t:
                feats.add(f"tag:{t}")
        try:
            for c in json.loads(s.get("key_concepts") or "[]"):
                if isinstance(c, str):
                    feats.add(f"concept:{c.lower()}")
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            for d in json.loads(s.get("domains") or "[]"):
                if isinstance(d, str):
                    feats.add(f"domain:{d}")
        except (json.JSONDecodeError, TypeError):
            pass
        features[s["id"]] = feats

    # 3. 겹침 그래프 구성 (1+ 공통 피처 → 연결)
    adj: dict[int, set[int]] = defaultdict(set)
    id_list = list(features.keys())
    for i in range(len(id_list)):
        for j in range(i + 1, len(id_list)):
            common = features[id_list[i]] & features[id_list[j]]
            if common:
                adj[id_list[i]].add(id_list[j])
                adj[id_list[j]].add(id_list[i])

    # 4. Connected components → 클러스터
    visited: set[int] = set()
    raw_clusters: list[list[int]] = []
    for nid in id_list:
        if nid in visited:
            continue
        queue = [nid]
        cluster: list[int] = []
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            cluster.append(curr)
            for nb in adj.get(curr, []):
                if nb not in visited:
                    queue.append(nb)
        raw_clusters.append(cluster)

    # 5. min_cluster_size 이상만 + 성숙도 계산
    node_map = {s["id"]: s for s in signals}
    total_queries = _get_total_recall_count()
    results = []
    for cluster_ids in raw_clusters:
        if len(cluster_ids) < min_cluster_size:
            continue
        cluster_nodes = [node_map[nid] for nid in cluster_ids if nid in node_map]
        maturity = _compute_maturity(cluster_nodes)

        # Bayesian 클러스터 평균
        bayesian_p = _bayesian_cluster_score(cluster_nodes, total_queries)

        # SPRT 플래그 카운트
        sprt_flagged = sum(
            1 for n in cluster_nodes
            if n.get("promotion_candidate")
        )

        results.append({
            "node_ids": cluster_ids,
            "size": len(cluster_ids),
            "maturity": round(maturity, 2),
            "bayesian_p": round(bayesian_p, 3),
            "sprt_flagged": sprt_flagged,
            "recommendation": _recommend_v2(maturity, bayesian_p, sprt_flagged),
            "themes": [n.get("summary") or n["content"][:80] for n in cluster_nodes[:3]],
            "domains": _collect_domains(cluster_nodes),
            "can_promote_to": VALID_PROMOTIONS.get("Signal", []),
        })

    results.sort(key=lambda c: c["maturity"], reverse=True)

    return {
        "clusters": results[:top_k],
        "total_signals": len(signals),
        "clustered_count": sum(c["size"] for c in results),
        "message": f"Found {len(results)} cluster(s) from {len(signals)} Signal(s).",
    }


def _compute_maturity(nodes: list[dict]) -> float:
    """클러스터 성숙도 (0-1). 크기·품질·도메인 다양성 합산."""
    size_score = min(1.0, len(nodes) / 10)
    qs_list = [n.get("quality_score") or 0.5 for n in nodes]
    quality_avg = sum(qs_list) / len(qs_list) if qs_list else 0.5
    domain_count = len(_collect_domains(nodes))
    domain_score = min(1.0, domain_count / 3)
    return size_score * 0.5 + quality_avg * 0.3 + domain_score * 0.2


def _recommend(maturity: float) -> str:
    """레거시 — 하위호환용. 신규는 _recommend_v2() 사용."""
    if maturity > 0.9:
        return "auto_promote"
    elif maturity > 0.6:
        return "user_review"
    return "not_ready"


def _recommend_v2(maturity: float, bayesian_p: float, sprt_flagged: int) -> str:
    """기존 maturity + Bayesian P + SPRT flag 통합 판단.

    우선순위:
      auto_promote: maturity 매우 높음 AND Bayesian 강한 증거
      user_review: Bayesian 중간 증거 OR SPRT 2개 이상 플래그
      not_ready: 그 외
    """
    if maturity > 0.9 and bayesian_p > 0.6:
        return "auto_promote"
    if bayesian_p > 0.5 or sprt_flagged >= 2:
        return "user_review"
    if maturity > 0.6:
        return "user_review"
    return "not_ready"


def _bayesian_cluster_score(nodes: list[dict], total_queries: int) -> float:
    """클러스터 내 Signal들의 평균 Bayesian P(real pattern)."""
    if not nodes or total_queries <= 0:
        return 0.0
    probs = []
    for n in nodes:
        k = n.get("frequency") or 0
        n_total = max(total_queries, k)
        # Prior: Beta(1, 10)
        alpha_post = 1 + k
        beta_post = 10 + (n_total - k)
        probs.append(alpha_post / (alpha_post + beta_post))
    return sum(probs) / len(probs)


def _get_total_recall_count() -> int:
    """meta 테이블에서 글로벌 recall 횟수 조회. 없으면 0."""
    val = sqlite_store.get_meta("total_recall_count")
    try:
        return int(val) if val is not None else 0
    except (ValueError, TypeError):
        return 0


def _collect_domains(nodes: list[dict]) -> list[str]:
    domains: set[str] = set()
    for n in nodes:
        try:
            for d in json.loads(n.get("domains") or "[]"):
                if isinstance(d, str):
                    domains.add(d)
        except (json.JSONDecodeError, TypeError):
            pass
    return sorted(domains)
