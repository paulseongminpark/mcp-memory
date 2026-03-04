#!/usr/bin/env python3
"""
daily_enrich.py -- 4-Model Enrichment Pipeline main orchestrator

Phase 1: bulk enrichment (gpt-5-mini, 1800K)
Phase 2: batch reasoning (o3-mini, 450K)
Phase 3: precision verify (gpt-4.1, 50K)
Phase 4: deep generation (gpt-5.2, 100K)
Phase 5: deep reasoning (o3, 75K)
Phase 6: codex review (separate)
Phase 7: report generation

Usage:
  python scripts/daily_enrich.py
  python scripts/daily_enrich.py --dry-run
  python scripts/daily_enrich.py --phase 1
  python scripts/daily_enrich.py --budget-large 100000 --budget-small 1000000
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from scripts.enrich.token_counter import TokenBudget
from scripts.enrich.node_enricher import NodeEnricher, BudgetExhausted
from scripts.enrich.relation_extractor import RelationExtractor
from scripts.enrich.graph_analyzer import GraphAnalyzer

MAX_CONSECUTIVE_FAILURES = 3


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ─── Phase 1: bulk enrichment (gpt-5-mini) ───────────────

def phase1(conn: sqlite3.Connection, ne: NodeEnricher,
           re: RelationExtractor, budget: TokenBudget) -> dict:
    """Phase 1: E1-E5,E7-E11 + E13-E14,E16-E17."""
    stats = {"nodes": 0, "edges": 0, "errors": 0}
    small_budget = config.TOKEN_BUDGETS["small"]
    phase_limit = int(small_budget * 0.8)  # 80% of small pool

    # 1a. new nodes (enriched_at IS NULL) — 통합 1-call enrichment
    rows = conn.execute(
        "SELECT id FROM nodes WHERE enriched_at IS NULL AND status='active' "
        "ORDER BY created_at DESC"
    ).fetchall()
    new_ids = [r[0] for r in rows]

    if new_ids:
        try:
            results = ne.enrich_batch_combined(new_ids)
            stats["nodes"] += len(results)
        except BudgetExhausted:
            return stats

    # 1b. E7 embedding_text (needs E1,E2 done first)
    rows = conn.execute("""
        SELECT id FROM nodes
        WHERE summary IS NOT NULL AND key_concepts IS NOT NULL
          AND enrichment_status NOT LIKE '%"E7"%'
          AND status='active'
        LIMIT 100
    """).fetchall()
    e7_ids = [r[0] for r in rows]
    if e7_ids and not budget.budget_exhausted("small"):
        try:
            ne.enrich_batch(e7_ids, tasks=["E7"])
        except BudgetExhausted:
            pass

    # 1c. E13 cross-domain relations
    if not budget.budget_exhausted("small"):
        try:
            re.run_e13(limit=50)
            stats["edges"] += re.stats.get("e13_new_edges", 0)
        except BudgetExhausted:
            pass
        except Exception as e:
            print(f"  E13 error: {e}")

    # 1d. E14 refine generic edges
    if not budget.budget_exhausted("small"):
        try:
            re.run_e14(limit=6000)
        except BudgetExhausted:
            pass
        except Exception as e:
            print(f"  E14 error: {e}")

    # 1e. E17 merge duplicates
    if not budget.budget_exhausted("small"):
        try:
            re.run_e17()
        except BudgetExhausted:
            pass
        except Exception as e:
            print(f"  E17 error: {e}")

    # 1f. E16 strength recalibration
    if not budget.budget_exhausted("small"):
        try:
            re.run_e16(limit=50)
        except BudgetExhausted:
            pass
        except Exception as e:
            print(f"  E16 error: {e}")

    conn.commit()
    return stats


# ─── Phase 2: batch reasoning (o3-mini) ──────────────────

def phase2(conn: sqlite3.Connection, re: RelationExtractor,
           ga: GraphAnalyzer, budget: TokenBudget) -> dict:
    """Phase 2: E15 + E20-E22."""
    stats = {"processed": 0}

    # 2a. E21 contradiction detection
    if not budget.budget_exhausted("small"):
        try:
            ga.run_e21_all(limit=30)
        except BudgetExhausted:
            pass

    # 2b. E22 assemblage detection
    if not budget.budget_exhausted("small"):
        try:
            ga.run_e22_all(limit=40)
        except BudgetExhausted:
            pass

    # 2c. E20 temporal chains
    if not budget.budget_exhausted("small"):
        try:
            ga.run_e20_all()
        except BudgetExhausted:
            pass

    # 2d. E15 edge direction
    if not budget.budget_exhausted("small"):
        try:
            re.run_e15(limit=200)
        except BudgetExhausted:
            pass

    conn.commit()
    return stats


# ─── Phase 3: precision verify (gpt-4.1) ─────────────────

def phase3(conn: sqlite3.Connection, ne: NodeEnricher,
           budget: TokenBudget) -> dict:
    """Phase 3: E6 + E12."""
    stats = {"verified": 0}

    # 3a. E12 layer verification
    rows = conn.execute("""
        SELECT id FROM nodes
        WHERE layer IS NOT NULL
          AND enrichment_status NOT LIKE '%"E12"%'
          AND status='active'
        ORDER BY RANDOM() LIMIT 50
    """).fetchall()
    if rows and not budget.budget_exhausted("large"):
        try:
            ne.enrich_batch([r[0] for r in rows], tasks=["E12"])
            stats["verified"] += len(rows)
        except BudgetExhausted:
            pass

    # 3b. E6 secondary_types
    rows = conn.execute("""
        SELECT id FROM nodes
        WHERE enrichment_status NOT LIKE '%"E6"%'
          AND status='active'
        ORDER BY RANDOM() LIMIT 15
    """).fetchall()
    if rows and not budget.budget_exhausted("large"):
        try:
            ne.enrich_batch([r[0] for r in rows], tasks=["E6"])
        except BudgetExhausted:
            pass

    conn.commit()
    return stats


# ─── Phase 4: deep generation (gpt-5.2) ──────────────────

def phase4(conn: sqlite3.Connection, ga: GraphAnalyzer,
           budget: TokenBudget) -> dict:
    """Phase 4: E18 + E25."""
    stats = {}

    # 4a. E18 cluster themes
    if not budget.budget_exhausted("large"):
        try:
            ga.run_e18_all(limit=30)
        except BudgetExhausted:
            pass

    # 4b. E25 knowledge gaps
    if not budget.budget_exhausted("large"):
        try:
            ga.run_e25_all()
        except BudgetExhausted:
            pass

    # 4c. E19 missing links
    if not budget.budget_exhausted("large"):
        try:
            ga.run_e19_all(limit=30)
        except BudgetExhausted:
            pass

    # 4d. E24 merge candidates
    if not budget.budget_exhausted("large"):
        try:
            ga.run_e24_all()
        except BudgetExhausted:
            pass

    conn.commit()
    return stats


# ─── Phase 5: deep reasoning (o3) ────────────────────────

def phase5(conn: sqlite3.Connection, ga: GraphAnalyzer,
           budget: TokenBudget) -> dict:
    """Phase 5: E23 (promotion)."""
    stats = {}

    # E23 signal -> pattern promotion
    if not budget.budget_exhausted("large"):
        try:
            ga.run_e23_all()
        except BudgetExhausted:
            pass

    conn.commit()
    return stats


# ─── Phase 7: report ─────────────────────────────────────

def generate_report(budget: TokenBudget, phase_stats: dict,
                    conn: sqlite3.Connection) -> Path:
    """Daily report generation."""
    config.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = config.REPORT_DIR / f"{today}.md"

    # node stats
    total = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    enriched = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE enriched_at IS NOT NULL"
    ).fetchone()[0]
    edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

    util = budget.utilization()
    lines = [
        f"# Enrichment Report {today}",
        "",
        "## Token Usage",
        f"- Large pool: {util['large']['used']:,}/{util['large']['limit']:,} "
        f"({util['large']['pct']}%)",
        f"- Small pool: {util['small']['used']:,}/{util['small']['limit']:,} "
        f"({util['small']['pct']}%)",
        f"- Reasoning tokens: large={budget.reasoning_tokens['large']:,}, "
        f"small={budget.reasoning_tokens['small']:,}",
        f"- API calls: {len(budget.log)}",
        "",
        "## Database",
        f"- Total nodes: {total:,}",
        f"- Enriched: {enriched:,} ({enriched/(total or 1)*100:.1f}%)",
        f"- Edges: {edges:,}",
        "",
        "## Phase Results",
    ]

    for phase_name, stats in phase_stats.items():
        lines.append(f"- {phase_name}: {json.dumps(stats)}")

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ─── main ─────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="mcp-memory enrichment pipeline")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--phase", type=int, help="Run specific phase only (1-5)")
    ap.add_argument("--budget-large", type=int,
                    default=config.TOKEN_BUDGETS["large"])
    ap.add_argument("--budget-small", type=int,
                    default=config.TOKEN_BUDGETS["small"])
    args = ap.parse_args()

    dry_run = args.dry_run or config.DRY_RUN

    # init
    budget = TokenBudget(
        large_limit=args.budget_large,
        small_limit=args.budget_small,
        log_dir=config.TOKEN_LOG_DIR,
    )
    conn = connect_db()
    ne = NodeEnricher(conn, budget, dry_run=dry_run)
    re = RelationExtractor(conn, budget, dry_run=dry_run)
    ga = GraphAnalyzer(conn, budget, dry_run=dry_run)

    print("=" * 50)
    print(f"mcp-memory enrichment pipeline")
    print(f"dry_run={dry_run}  large={args.budget_large:,}  small={args.budget_small:,}")
    print("=" * 50)

    phase_stats = {}
    phases = [
        (1, "Phase 1: bulk", lambda: phase1(conn, ne, re, budget)),
        (2, "Phase 2: reasoning", lambda: phase2(conn, re, ga, budget)),
        (3, "Phase 3: verify", lambda: phase3(conn, ne, budget)),
        (4, "Phase 4: deep", lambda: phase4(conn, ga, budget)),
        (5, "Phase 5: judge", lambda: phase5(conn, ga, budget)),
    ]

    consecutive_failures = 0
    for num, name, fn in phases:
        if args.phase and args.phase != num:
            continue

        print(f"\n--- {name} ---")

        # skip if both pools exhausted
        if budget.budget_exhausted("large") and budget.budget_exhausted("small"):
            print("  Both pools exhausted. Stopping.")
            break

        try:
            stats = fn()
            phase_stats[name] = stats
            consecutive_failures = 0
            print(f"  {budget.summary()}")
        except BudgetExhausted as e:
            print(f"  Budget exhausted: {e}")
            phase_stats[name] = {"budget_exhausted": True}
            break
        except Exception as e:
            consecutive_failures += 1
            phase_stats[name] = {"error": str(e)}
            print(f"  Error: {e}")
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"  {MAX_CONSECUTIVE_FAILURES} consecutive failures. Stopping.")
                break

    # Phase 7: report
    print("\n--- Phase 7: report ---")
    report_path = generate_report(budget, phase_stats, conn)
    budget.save_log()
    print(f"  Report: {report_path}")
    print(f"  Final: {budget.summary()}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
