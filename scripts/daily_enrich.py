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


# ─── Phase 6: pruning (edge → node) ─────────────────────

def phase6_pruning(conn: sqlite3.Connection, dry_run: bool = True) -> dict:
    """
    Phase 6: Pruning (edge → node 순서)

    Step A: B-6 edge pruning (Bäuml ctx_log 기반 strength 평가)
    Step B: D-6 node BSP Stage 2 (pruning_candidate 표시)
    Step C: D-6 node BSP Stage 3 (30일 경과 → archived)
    Step D: action_log 기록

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
    results: dict = {"dry_run": dry_run}

    # Step A: Edge Pruning
    print("\n[Phase 6-A] Edge pruning (Bäuml ctx_log)...")
    edge_stats = _run_edge_pruning(conn, dry_run=dry_run)
    results["edges"] = edge_stats
    print(
        f"  edges → keep={edge_stats['keep']} "
        f"archive={edge_stats['archive']} delete={edge_stats['delete']}"
    )

    # Step B: Node Pruning Stage 2
    print("\n[Phase 6-B] Node pruning Stage 2 (BSP candidate 표시)...")
    node_stage2 = _run_node_stage2(conn, dry_run=dry_run)
    print(
        f"  nodes → candidates={node_stage2['candidates']} "
        f"protected={node_stage2['protected']} "
        f"marked={node_stage2['marked_probation']}"
    )

    # Step C: Node Pruning Stage 3
    print("\n[Phase 6-C] Node pruning Stage 3 (30일 경과 archive)...")
    archived_ids = _run_node_stage3(conn, dry_run=dry_run)
    print(f"  archived={len(archived_ids)}")

    results["nodes"] = {
        "candidates": node_stage2["candidates"],
        "protected": node_stage2["protected"],
        "marked_probation": node_stage2["marked_probation"],
        "archived": len(archived_ids),
    }

    # Step D: action_log 기록
    if not dry_run:
        _log_pruning_action(conn, results)

    return results


def _run_edge_pruning(conn: sqlite3.Connection, dry_run: bool) -> dict:
    """
    B-6 edge pruning: strength 평가 → archive / delete / keep.

    ctx_log: edges.description 컬럼에 JSON 배열로 저장된 쿼리 맥락 로그.
    """
    import math
    from datetime import timedelta

    PRUNE_STRENGTH_THRESHOLD = 0.05
    PRUNE_MIN_CONTEXT_DIVERSITY = 2

    stats = {"keep": 0, "archive": 0, "delete": 0}

    active_edges = conn.execute(
        "SELECT id, source_id, target_id, relation, strength, "
        "       frequency, last_activated, description, archived_at "
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

        # source 노드 tier/layer 조회
        src_row = conn.execute(
            "SELECT tier, layer FROM nodes WHERE id = ?", (edge["source_id"],)
        ).fetchone()
        src_tier = src_row["tier"] if src_row and src_row["tier"] is not None else 2
        src_layer = src_row["layer"] if src_row and src_row["layer"] is not None else 0

        # L3+(tier=0) 또는 layer>=2: archive (복구 가능)
        if src_tier == 0 or src_layer >= 2:
            decision = "archive"
        else:
            decision = "delete"

        if not dry_run:
            if decision == "archive":
                probation_dt = (now_utc + timedelta(days=30)).isoformat()
                conn.execute(
                    "UPDATE edges SET archived_at=?, probation_end=? WHERE id=?",
                    (now_str, probation_dt, edge_id),
                )
            else:
                conn.execute("DELETE FROM edges WHERE id=?", (edge_id,))

        stats[decision] += 1

    if not dry_run:
        conn.commit()

    return stats


def _run_node_stage2(conn: sqlite3.Connection, dry_run: bool) -> dict:
    """
    D-6 BSP Stage 2: pruning 후보 식별 → pruning_candidate 표시.
    check_access()로 L4/L5 + Top-10 허브 자동 보호.
    """
    from utils.access_control import check_access

    candidates = conn.execute("""
        SELECT
            n.id, n.content, n.type, n.layer, n.quality_score,
            n.observation_count, n.last_activated, n.tier,
            COUNT(e.id) AS edge_count
        FROM nodes n
        LEFT JOIN edges e ON (e.source_id = n.id OR e.target_id = n.id)
        WHERE n.status = 'active'
          AND COALESCE(n.quality_score, 0) < 0.3
          AND COALESCE(n.observation_count, 0) < 2
          AND (n.last_activated IS NULL OR n.last_activated < datetime('now', '-90 days'))
          AND n.layer IN (0, 1)
        GROUP BY n.id
        HAVING edge_count < 3
        ORDER BY COALESCE(n.quality_score, 0) ASC
        LIMIT 100
    """).fetchall()

    total_candidates = len(candidates)
    protected = 0
    allowed_ids = []

    for c in candidates:
        if check_access(c["id"], "write", "system:daily_enrich", conn):
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
                "(node_id, field, old_value, new_value, reason, corrected_by, created_at) "
                "VALUES (?, 'status', 'active', 'pruning_candidate', "
                "'BSP Stage 2: q<0.3 + obs<2 + inactive 90d + edge<3', "
                "'system:daily_enrich', datetime('now'))",
                (nid,),
            )
        conn.commit()

    return {
        "candidates": total_candidates,
        "protected": protected,
        "marked_probation": len(allowed_ids) if not dry_run else 0,
    }


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
            "(node_id, field, old_value, new_value, reason, corrected_by, created_at) "
            "VALUES (?, 'status', 'pruning_candidate', 'archived', "
            "'BSP Stage 3: 30-day grace period expired', "
            "'system:daily_enrich', datetime('now'))",
            (nid,),
        )
    conn.commit()

    return expired_ids


def _log_pruning_action(conn: sqlite3.Connection, results: dict) -> None:
    """A-9 action_log에 pruning 결과 기록."""
    try:
        from storage import action_log as al
        al.record(
            action_type="archive",
            actor="system:daily_enrich",
            target_type="graph",
            params=json.dumps({"phase": 6, "description": "BSP pruning + edge cleanup"}),
            result=json.dumps({
                "edges_keep":        results["edges"]["keep"],
                "edges_archive":     results["edges"]["archive"],
                "edges_delete":      results["edges"]["delete"],
                "nodes_candidates":  results["nodes"]["candidates"],
                "nodes_protected":   results["nodes"]["protected"],
                "nodes_probation":   results["nodes"]["marked_probation"],
                "nodes_archived":    results["nodes"]["archived"],
            }),
        )
    except Exception:
        pass  # action_log 실패는 무음 처리


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
    ap.add_argument("--phase", type=int, help="Run specific phase only (1-6)")
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
        (6, "Phase 6: pruning", lambda: phase6_pruning(conn, dry_run=dry_run)),
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
