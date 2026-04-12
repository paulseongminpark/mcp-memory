"""Growth score computation — canonical node maturity formula.

growth_score = quality(30%) + edge_density(20%) + visits(20%)
             + diversity(20%) + recency(10%) + contradiction_penalty

This is the single source of truth for individual node growth measurement.
DB column `nodes.maturity` stores the cached value of this computation.

Other "maturity" concepts in the codebase:
  - cluster_readiness: analyze_signals cluster-level readiness (different formula)
  - system_maturity_level: config_search system-wide level (knowledge_core count)
  - promotion_readiness: promote_node SWR structural readiness (vec/cross ratio)
"""

from __future__ import annotations

from datetime import datetime, timezone


def compute_growth_score(
    quality_score: float | None,
    active_edge_count: int,
    visit_count: int | None,
    neighbor_project_count: int,
    created_at: str | None,
    has_contradiction: bool = False,
) -> float:
    """Compute canonical growth score for a single node.

    Args:
        quality_score: Node quality (0-1). None treated as 0.5.
        active_edge_count: Number of active edges connected to this node.
        visit_count: Number of recall visits. None treated as 0.
        neighbor_project_count: Distinct projects among neighbors.
        created_at: ISO datetime string of node creation.
        has_contradiction: Whether any edge has relation='contradicts'.

    Returns:
        Float 0.0-1.0 representing growth readiness.
    """
    qs = quality_score if quality_score is not None else 0.5
    vc = visit_count or 0

    edge_density = min(1.0, active_edge_count / 10)
    visit_norm = min(1.0, vc / 10)
    diversity = min(1.0, neighbor_project_count / 3)

    # recency: 30-day window full score, 90-day cutoff
    if created_at:
        try:
            created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            days_old = (datetime.now(timezone.utc) - created_dt).days
            recency = max(0.0, 1.0 - days_old / 90)
        except Exception:
            recency = 0.5
    else:
        recency = 0.5

    contra_penalty = -0.2 if has_contradiction else 0.0

    score = (
        qs * 0.3
        + edge_density * 0.2
        + visit_norm * 0.2
        + diversity * 0.2
        + recency * 0.1
        + contra_penalty
    )
    return max(0.0, min(1.0, score))
