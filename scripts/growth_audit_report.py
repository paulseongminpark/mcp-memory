#!/usr/bin/env python3
"""growth_audit_report.py — Type별 growth_score / observation_count 분포 보고서.

Usage:
  python scripts/growth_audit_report.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = f + 1
    if c >= len(sorted_vals):
        return sorted_vals[f]
    return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])


def growth_score_by_type(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT type, maturity FROM nodes WHERE status='active'"
    ).fetchall()

    by_type: dict[str, list[float]] = {}
    for r in rows:
        t = r["type"] or "NULL"
        by_type.setdefault(t, []).append(r["maturity"] or 0.0)

    results = []
    for t, vals in sorted(by_type.items()):
        vals.sort()
        results.append({
            "type": t,
            "count": len(vals),
            "mean": sum(vals) / len(vals),
            "min": vals[0],
            "max": vals[-1],
            "p50": _percentile(vals, 0.5),
            "p90": _percentile(vals, 0.9),
            "zero": sum(1 for v in vals if v == 0.0),
        })
    return results


def observation_count_by_type(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT type, observation_count FROM nodes WHERE status='active'"
    ).fetchall()

    by_type: dict[str, list[int]] = {}
    for r in rows:
        t = r["type"] or "NULL"
        by_type.setdefault(t, []).append(r["observation_count"] or 0)

    results = []
    for t, vals in sorted(by_type.items()):
        vals.sort()
        nonzero = sum(1 for v in vals if v > 0)
        results.append({
            "type": t,
            "count": len(vals),
            "nonzero": nonzero,
            "nonzero_pct": nonzero / len(vals) * 100 if vals else 0,
            "mean": sum(vals) / len(vals) if vals else 0,
            "max": vals[-1] if vals else 0,
            "p50": _percentile([float(v) for v in vals], 0.5),
        })
    return results


def visit_vs_growth_correlation(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT visit_count, maturity FROM nodes WHERE status='active' AND maturity IS NOT NULL"
    ).fetchall()

    if len(rows) < 2:
        return {"n": len(rows), "correlation": None}

    visits = [r["visit_count"] or 0 for r in rows]
    maturities = [r["maturity"] or 0.0 for r in rows]

    n = len(visits)
    mean_v = sum(visits) / n
    mean_m = sum(maturities) / n

    cov = sum((v - mean_v) * (m - mean_m) for v, m in zip(visits, maturities)) / n
    std_v = (sum((v - mean_v) ** 2 for v in visits) / n) ** 0.5
    std_m = (sum((m - mean_m) ** 2 for m in maturities) / n) ** 0.5

    if std_v == 0 or std_m == 0:
        return {"n": n, "correlation": 0.0}

    return {"n": n, "correlation": round(cov / (std_v * std_m), 4)}


def dead_field_detection(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM nodes WHERE status='active'").fetchone()[0]
    zero_maturity = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE status='active' AND COALESCE(maturity, 0) = 0"
    ).fetchone()[0]
    zero_obs = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE status='active' AND COALESCE(observation_count, 0) = 0"
    ).fetchone()[0]

    return {
        "total_active": total,
        "zero_maturity": zero_maturity,
        "zero_maturity_pct": zero_maturity / total * 100 if total else 0,
        "zero_observation": zero_obs,
        "zero_observation_pct": zero_obs / total * 100 if total else 0,
    }


def pipeline_health(conn: sqlite3.Connection) -> dict:
    last_update = conn.execute(
        "SELECT MAX(updated_at) FROM nodes WHERE status='active' AND maturity IS NOT NULL AND maturity > 0"
    ).fetchone()[0]

    return {"last_maturity_update": last_update or "never"}


def main():
    conn = connect_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"=== Growth Audit Report ({now}) ===\n")

    # 1. Growth Score by Type
    print("## Growth Score (DB maturity) by Type\n")
    print(f"{'Type':<20} {'N':>5} {'Mean':>6} {'Min':>6} {'Max':>6} {'P50':>6} {'P90':>6} {'Zero':>5}")
    print("-" * 75)
    for r in growth_score_by_type(conn):
        print(f"{r['type']:<20} {r['count']:>5} {r['mean']:>6.3f} {r['min']:>6.3f} "
              f"{r['max']:>6.3f} {r['p50']:>6.3f} {r['p90']:>6.3f} {r['zero']:>5}")

    # 2. Observation Count by Type
    print(f"\n## Observation Count by Type\n")
    print(f"{'Type':<20} {'N':>5} {'Nonzero':>8} {'%':>6} {'Mean':>6} {'Max':>5} {'P50':>5}")
    print("-" * 65)
    for r in observation_count_by_type(conn):
        print(f"{r['type']:<20} {r['count']:>5} {r['nonzero']:>8} {r['nonzero_pct']:>5.1f}% "
              f"{r['mean']:>6.1f} {r['max']:>5} {r['p50']:>5.0f}")

    # 3. Correlation
    print(f"\n## Visit Count vs Growth Score Correlation\n")
    corr = visit_vs_growth_correlation(conn)
    print(f"  N={corr['n']}, Pearson r={corr['correlation']}")

    # 4. Dead Field Detection
    print(f"\n## Dead Field Detection\n")
    df = dead_field_detection(conn)
    print(f"  Total active: {df['total_active']}")
    print(f"  Zero maturity: {df['zero_maturity']} ({df['zero_maturity_pct']:.1f}%)")
    print(f"  Zero observation_count: {df['zero_observation']} ({df['zero_observation_pct']:.1f}%)")

    # 5. Pipeline Health
    print(f"\n## Growth Pipeline Health\n")
    health = pipeline_health(conn)
    print(f"  Last maturity update: {health['last_maturity_update']}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
