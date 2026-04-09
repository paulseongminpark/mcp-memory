"""STATE.md Current 블록 자동 생성 — live DB + eval 기준."""
import sqlite3
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
os.chdir(ROOT)

DB = os.path.join(ROOT, "data", "memory.db")

from scripts.health_metrics import get_health_snapshot


def generate():
    conn = sqlite3.connect(DB)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    health = get_health_snapshot(conn)
    total_n = health["active_nodes"]
    total_e = health["active_edges"]

    signal = conn.execute("SELECT COUNT(*) FROM nodes WHERE type='Signal' AND status='active'").fetchone()[0]
    correction = conn.execute("SELECT COUNT(*) FROM nodes WHERE type='Correction' AND status='active'").fetchone()[0]
    contradicts = conn.execute("SELECT COUNT(*) FROM edges WHERE relation='contradicts' AND status='active'").fetchone()[0]
    validated = conn.execute("SELECT COUNT(*) FROM nodes WHERE epistemic_status='validated' AND status='active'").fetchone()[0]
    kc = conn.execute("SELECT COUNT(*) FROM nodes WHERE node_role='knowledge_core' AND status='active'").fetchone()[0]

    nr_filled = conn.execute("SELECT COUNT(*) FROM nodes WHERE status='active' AND node_role IS NOT NULL AND node_role != ''").fetchone()[0]
    gm_filled = conn.execute("SELECT COUNT(*) FROM edges WHERE status='active' AND generation_method IS NOT NULL AND generation_method != ''").fetchone()[0]

    merged = conn.execute("SELECT COUNT(*) FROM nodes WHERE status='active' AND metadata LIKE '%merged_to%'").fetchone()[0]

    type_rows = conn.execute("SELECT type, COUNT(*) FROM nodes WHERE status='active' GROUP BY type ORDER BY COUNT(*) DESC").fetchall()
    types_active = len(type_rows)

    conn.close()

    lines = [
        f"_Auto-generated: {now}_\n",
        "## Current",
        f"- **Active Nodes**: {total_n:,}",
        f"- **Active Edges**: {total_e:,}",
        f"- **Signal**: {signal}",
        f"- **Correction**: {correction} (contradicts: {contradicts})",
        f"- **Validated**: {validated} | knowledge_core: {kc}",
        f"- **Orphan**: {health['true_orphans']} ({health['true_orphans']*100/total_n:.1f}%)",
        f"- **Stale 30d / zero-visit**: created_at {health['stale_zero_visit_created_30d']:,} | updated_at {health['stale_zero_visit_updated_30d']:,}",
        f"- **Metadata fill**: node_role {nr_filled*100/total_n:.0f}%, generation_method {gm_filled*100/total_e:.0f}%",
        f"- **Merged**: {merged}",
        f"- **Types**: {types_active} active",
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    print(generate())
