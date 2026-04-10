"""Generate and optionally apply the live STATE.md Current block."""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "memory.db"
STATE = ROOT / "STATE.md"
CURRENT_BEGIN = "<!-- CURRENT:BEGIN -->"
CURRENT_END = "<!-- CURRENT:END -->"
EXPECTED_FTS_COLUMNS = [
    "content",
    "tags",
    "project",
    "summary",
    "key_concepts",
    "domains",
    "facets",
]

sys.path.insert(0, str(ROOT))

from config_ontology import GENERATION_METHODS
from scripts.health_metrics import get_health_snapshot


def _branch_name() -> str:
    try:
        return subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=ROOT,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def _fts_columns(conn: sqlite3.Connection) -> list[str]:
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='nodes_fts'"
    ).fetchone()
    if not sql or not sql[0]:
        return []

    ddl = sql[0]
    prefix = "fts5("
    suffix = "content='nodes'"
    if prefix not in ddl or suffix not in ddl:
        return []

    inner = ddl.split(prefix, 1)[1].split(suffix, 1)[0]
    columns = []
    for chunk in inner.replace("\n", " ").split(","):
        value = chunk.strip()
        if not value or "=" in value:
            continue
        columns.append(value)
    return columns


def _fetch_metrics(conn: sqlite3.Connection) -> dict[str, object]:
    health = get_health_snapshot(conn)
    active_nodes = health["active_nodes"]
    active_edges = health["active_edges"]

    signal = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE type='Signal' AND status='active'"
    ).fetchone()[0]
    correction = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE type='Correction' AND status='active'"
    ).fetchone()[0]
    contradicts = conn.execute(
        "SELECT COUNT(*) FROM edges WHERE relation='contradicts' AND status='active'"
    ).fetchone()[0]
    validated = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE epistemic_status='validated' AND status='active'"
    ).fetchone()[0]
    knowledge_core = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE node_role='knowledge_core' AND status='active'"
    ).fetchone()[0]

    cross_domain = conn.execute(
        """
        SELECT COUNT(*)
        FROM edges e
        JOIN nodes s ON s.id = e.source_id
        JOIN nodes t ON t.id = e.target_id
        WHERE e.status = 'active'
          AND s.status = 'active'
          AND t.status = 'active'
          AND s.project IS NOT NULL
          AND s.project != ''
          AND t.project IS NOT NULL
          AND t.project != ''
          AND s.project != t.project
        """
    ).fetchone()[0]
    null_direction = conn.execute(
        """
        SELECT COUNT(*)
        FROM edges
        WHERE status = 'active'
          AND (direction IS NULL OR TRIM(direction) = '')
        """
    ).fetchone()[0]

    maturity_avg, maturity_min, maturity_max, zero_maturity = conn.execute(
        """
        SELECT
            AVG(COALESCE(maturity, 0)),
            MIN(COALESCE(maturity, 0)),
            MAX(COALESCE(maturity, 0)),
            SUM(CASE WHEN COALESCE(maturity, 0) = 0 THEN 1 ELSE 0 END)
        FROM nodes
        WHERE status = 'active'
        """
    ).fetchone()
    observation_nonzero, observation_max = conn.execute(
        """
        SELECT
            SUM(CASE WHEN COALESCE(observation_count, 0) > 0 THEN 1 ELSE 0 END),
            MAX(COALESCE(observation_count, 0))
        FROM nodes
        WHERE status = 'active'
        """
    ).fetchone()

    generation_rows = conn.execute(
        """
        SELECT generation_method, COUNT(*)
        FROM edges
        WHERE status = 'active'
          AND generation_method IS NOT NULL
          AND generation_method != ''
        GROUP BY generation_method
        ORDER BY COUNT(*) DESC
        """
    ).fetchall()
    drift_rows = [
        (method, count)
        for method, count in generation_rows
        if method not in GENERATION_METHODS
    ]
    drift_edges = sum(count for _, count in drift_rows)

    fts_columns = _fts_columns(conn)
    fts_missing = [column for column in EXPECTED_FTS_COLUMNS if column not in fts_columns]

    return {
        "branch": _branch_name(),
        "active_nodes": active_nodes,
        "active_edges": active_edges,
        "signal": signal,
        "correction": correction,
        "contradicts": contradicts,
        "validated": validated,
        "validated_ratio": (validated / active_nodes) if active_nodes else 0.0,
        "knowledge_core": knowledge_core,
        "cross_domain": cross_domain,
        "cross_domain_ratio": (cross_domain / active_edges) if active_edges else 0.0,
        "null_direction": null_direction,
        "direction_assigned_ratio": 1.0 - (null_direction / active_edges) if active_edges else 0.0,
        "maturity_avg": maturity_avg or 0.0,
        "maturity_min": maturity_min or 0.0,
        "maturity_max": maturity_max or 0.0,
        "zero_maturity": zero_maturity or 0,
        "observation_nonzero": observation_nonzero or 0,
        "observation_max": observation_max or 0,
        "true_orphans": health["true_orphans"],
        "stale_created": health["stale_zero_visit_created_30d"],
        "stale_updated": health["stale_zero_visit_updated_30d"],
        "fts_columns": fts_columns,
        "fts_missing": fts_missing,
        "drift_rows": drift_rows,
        "drift_edges": drift_edges,
    }


def render_current(metrics: dict[str, object]) -> str:
    fts_missing = ", ".join(metrics["fts_missing"]) if metrics["fts_missing"] else "none"
    drift_rows = metrics["drift_rows"]
    drift_detail = ", ".join(
        f"{method} {count:,}" for method, count in drift_rows
    ) or "none"

    lines = [
        f"- **Branch**: {metrics['branch']}",
        f"- **Active Nodes / Edges**: {metrics['active_nodes']:,} / {metrics['active_edges']:,}",
        (
            "- **Cross-domain / Direction**: "
            f"{metrics['cross_domain_ratio'] * 100:.1f}% / "
            f"{metrics['direction_assigned_ratio'] * 100:.1f}% assigned"
        ),
        (
            "- **Validated / knowledge_core**: "
            f"{metrics['validated']:,} ({metrics['validated_ratio'] * 100:.1f}%) / "
            f"{metrics['knowledge_core']:,}"
        ),
        (
            "- **Signal / Correction**: "
            f"{metrics['signal']:,} / {metrics['correction']:,} "
            f"(contradicts {metrics['contradicts']:,})"
        ),
        (
            "- **Maturity**: "
            f"avg {metrics['maturity_avg']:.3f}, "
            f"min {metrics['maturity_min']:.3f}, "
            f"max {metrics['maturity_max']:.3f}, "
            f"zero {metrics['zero_maturity']:,}"
        ),
        (
            "- **Growth**: "
            f"observation_count nonzero {metrics['observation_nonzero']:,}, "
            f"max {metrics['observation_max']:,}, "
            f"direction NULL {metrics['null_direction']:,}"
        ),
        (
            "- **Health**: "
            f"orphans {metrics['true_orphans']:,}, "
            f"stale 30d created_at {metrics['stale_created']:,}, "
            f"updated_at {metrics['stale_updated']:,}"
        ),
        (
            "- **FTS Drift**: "
            f"live {len(metrics['fts_columns'])} cols, missing {fts_missing}"
        ),
        (
            "- **Enum Drift**: "
            f"{metrics['drift_edges']:,} active edges ({drift_detail})"
        ),
    ]
    return "\n".join(lines)


def apply_to_state(block: str) -> None:
    text = STATE.read_text(encoding="utf-8")
    if CURRENT_BEGIN not in text or CURRENT_END not in text:
        raise RuntimeError("STATE.md missing CURRENT markers")

    before, remainder = text.split(CURRENT_BEGIN, 1)
    _, after = remainder.split(CURRENT_END, 1)
    text = f"{before}{CURRENT_BEGIN}\n{block}\n{CURRENT_END}{after}"

    today = datetime.now().strftime("%Y-%m-%d")
    text = re.sub(r"^_Updated: .*_$", f"_Updated: {today}_", text, count=1, flags=re.M)
    STATE.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the generated Current block into STATE.md",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(DB)
    try:
        block = render_current(_fetch_metrics(conn))
    finally:
        conn.close()

    if args.apply:
        apply_to_state(block)

    print(block)


if __name__ == "__main__":
    main()
