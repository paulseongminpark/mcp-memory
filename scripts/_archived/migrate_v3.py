"""Ontology v3 마이그레이션 — Step 1: 타입 축소 + layer/tier 정규화.

실행: python scripts/migrate_v3.py [--dry-run]
의존: Step 0 (recall_id, edges index) 완료 상태

설계: 02_impl-design-v2.md D-1
"""

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH
from storage.sqlite_store import _db, _connect


# ── 전타입 매핑표 (51개) ──
# action: keep=유지, merge=1:1매핑, edge=edge전환, llm=Step2에서 LLM 재분류
# layer: 0=surface, 1=operational, 2=structural, 3=core, 4=deep, 5=foundation
# layer는 target 타입의 PROMOTE_LAYER 값 사용
TYPE_MAP = {
    # Tier 1 유지 (7) — layer는 기존 PROMOTE_LAYER 유지
    "Decision":   {"action": "keep", "tier": 1, "layer": 1},
    "Pattern":    {"action": "keep", "tier": 1, "layer": 2},
    "Principle":  {"action": "keep", "tier": 1, "layer": 3},
    "Failure":    {"action": "keep", "tier": 1, "layer": 1},
    "Insight":    {"action": "keep", "tier": 1, "layer": 2},
    "Goal":       {"action": "keep", "tier": 1, "layer": 1},
    "Experiment": {"action": "keep", "tier": 1, "layer": 1},

    # Tier 2 유지 (5)
    "Project":    {"action": "keep", "tier": 2, "layer": 1},
    "Tool":       {"action": "keep", "tier": 2, "layer": 1},
    "Framework":  {"action": "keep", "tier": 2, "layer": 2},
    "Narrative":  {"action": "keep", "tier": 2, "layer": 0},
    "Identity":   {"action": "keep", "tier": 2, "layer": 3},

    # Tier 3 유지 (3)
    "Signal":      {"action": "keep", "tier": 3, "layer": 1},
    "Observation": {"action": "keep", "tier": 3, "layer": 0},
    "Question":    {"action": "keep", "tier": 3, "layer": 0},

    # 단순 merge (12) — layer는 target의 PROMOTE_LAYER
    "Skill":          {"action": "merge", "target": "Tool",       "tier": 2, "layer": 1},
    "Agent":          {"action": "merge", "target": "Tool",       "tier": 2, "layer": 1},
    "SystemVersion":  {"action": "merge", "target": "Project",    "tier": 2, "layer": 1},
    "Breakthrough":   {"action": "merge", "target": "Insight",    "tier": 1, "layer": 2},
    "Conversation":   {"action": "merge", "target": "Observation","tier": 3, "layer": 0},
    "Tension":        {"action": "merge", "target": "Question",   "tier": 3, "layer": 0},
    "AntiPattern":    {"action": "merge", "target": "Failure",    "tier": 1, "layer": 1},
    "Preference":     {"action": "merge", "target": "Identity",   "tier": 2, "layer": 3},
    "Philosophy":     {"action": "merge", "target": "Principle",  "tier": 1, "layer": 3},
    "Value":          {"action": "merge", "target": "Principle",  "tier": 1, "layer": 3},
    "Belief":         {"action": "merge", "target": "Principle",  "tier": 1, "layer": 3},
    "Axiom":          {"action": "merge", "target": "Principle",  "tier": 1, "layer": 3},

    # edge 전환 (2) — type→target, layer=target의 PROMOTE_LAYER
    "Evolution":  {"action": "edge", "target": "Pattern",  "edge_type": "evolved_from",
                   "tier": 1, "layer": 2},
    "Connection": {"action": "edge", "target": "Insight",  "edge_type": "connects",
                   "tier": 1, "layer": 2},

    # LLM 재분류 (Step 2)
    "Workflow": {"action": "llm", "candidates": ["Pattern", "Framework", "Tool",
                 "Goal", "Experiment", "ARCHIVED"]},

    # C3 누락 20개 — layer는 target의 PROMOTE_LAYER
    "Aporia":       {"action": "merge", "target": "Question",    "tier": 3, "layer": 0},
    "Assumption":   {"action": "merge", "target": "Principle",   "tier": 1, "layer": 3},
    "Boundary":     {"action": "merge", "target": "Decision",    "tier": 1, "layer": 1},
    "Commitment":   {"action": "merge", "target": "Goal",        "tier": 1, "layer": 1},
    "Concept":      {"action": "merge", "target": "Insight",     "tier": 1, "layer": 2},
    "Constraint":   {"action": "merge", "target": "Decision",    "tier": 1, "layer": 1},
    "Context":      {"action": "merge", "target": "Observation", "tier": 3, "layer": 0},
    "Correction":   {"action": "merge", "target": "Failure",     "tier": 1, "layer": 1},
    "Evidence":     {"action": "merge", "target": "Observation", "tier": 3, "layer": 0},
    "Heuristic":    {"action": "merge", "target": "Pattern",     "tier": 1, "layer": 2},
    "Lens":         {"action": "merge", "target": "Framework",   "tier": 2, "layer": 2},
    "Mental Model": {"action": "merge", "target": "Framework",   "tier": 2, "layer": 2},
    "Metaphor":     {"action": "merge", "target": "Narrative",   "tier": 2, "layer": 0},
    "Paradox":      {"action": "merge", "target": "Question",    "tier": 3, "layer": 0},
    "Plan":         {"action": "merge", "target": "Goal",        "tier": 1, "layer": 1},
    "Ritual":       {"action": "merge", "target": "Pattern",     "tier": 1, "layer": 2},
    "Trade-off":    {"action": "merge", "target": "Decision",    "tier": 1, "layer": 1},
    "Trigger":      {"action": "merge", "target": "Signal",      "tier": 3, "layer": 1},
    "Vision":       {"action": "merge", "target": "Goal",        "tier": 1, "layer": 1},
    "Wonder":       {"action": "merge", "target": "Question",    "tier": 3, "layer": 0},

    # 안전망
    "Unclassified": {"action": "keep", "tier": 3, "layer": None},
}


def backup_db() -> Path:
    """G3: DB 백업."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = Path(f"{DB_PATH}.v2_final_{ts}")
    shutil.copy2(str(DB_PATH), str(backup))
    return backup


def migrate_step1(dry_run: bool = False) -> dict:
    """Step 1: 타입 축소 + layer/tier 정규화 + type_defs deprecated."""
    stats = {"merge": 0, "edge": 0, "layer_tier": 0, "deprecated_defs": 0, "skipped_llm": 0}
    now = datetime.now(timezone.utc).isoformat()

    with _db() as conn:
        for old_type, spec in TYPE_MAP.items():
            action = spec["action"]

            if action == "keep":
                # layer/tier 정규화
                tier = spec["tier"]
                layer = spec["layer"]
                if layer is None:
                    # Unclassified 등 layer 미배정 타입 — tier만 갱신
                    cnt = conn.execute("""
                        UPDATE nodes SET tier=?
                        WHERE type=? AND status='active' AND tier!=?
                    """, (tier, old_type, tier)).rowcount
                else:
                    cnt = conn.execute("""
                        UPDATE nodes SET layer=?, tier=?
                        WHERE type=? AND status='active' AND (layer IS NULL OR layer!=? OR tier!=?)
                    """, (layer, tier, old_type, layer, tier)).rowcount
                stats["layer_tier"] += cnt
                if cnt > 0:
                    print(f"  [keep] {old_type}: layer/tier 정규화 {cnt}개")
                continue

            if action == "llm":
                cnt = conn.execute(
                    "SELECT COUNT(*) FROM nodes WHERE type=? AND status='active'",
                    (old_type,)
                ).fetchone()[0]
                stats["skipped_llm"] += cnt
                print(f"  [llm] {old_type}: {cnt}개 → Step 2에서 LLM 재분류")
                continue

            # merge 또는 edge
            target = spec["target"]
            tier = spec["tier"]
            layer = spec["layer"]

            # type_defs deprecated
            conn.execute("""
                UPDATE type_defs SET
                    status='deprecated',
                    deprecated_reason=?,
                    replaced_by=?,
                    deprecated_at=?,
                    updated_at=?,
                    version=COALESCE(version, 0)+1
                WHERE name=? AND status='active'
            """, (f"v3 타입 축소: {old_type} → {target}", target, now, now, old_type))
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                stats["deprecated_defs"] += 1

            # C2: type + layer + tier 동시 갱신
            count = conn.execute("""
                UPDATE nodes SET type=?, layer=?, tier=?
                WHERE type=? AND status='active'
            """, (target, layer, tier, old_type)).rowcount

            if count > 0:
                print(f"  [{action}] {old_type} → {target}: {count}개 (layer={layer}, tier={tier})")
            stats["merge" if action == "merge" else "edge"] += count

        if not dry_run:
            conn.commit()
            print(f"\n커밋 완료.")
        else:
            print(f"\n[DRY RUN] 롤백.")

    return stats


def verify_migration(conn=None) -> dict:
    """마이그레이션 검증."""
    close = False
    if conn is None:
        conn = _connect()
        close = True

    try:
        # active 타입별 분포
        rows = conn.execute("""
            SELECT type, COUNT(*) as cnt FROM nodes
            WHERE status='active' GROUP BY type ORDER BY cnt DESC
        """).fetchall()
        dist = {r[0]: r[1] for r in rows}

        # deprecated 타입이 남아있는지
        v3_targets = {s["target"] for s in TYPE_MAP.values() if "target" in s}
        v3_deprecated = {k for k, v in TYPE_MAP.items() if v["action"] in ("merge", "edge")}
        leaked = {t: c for t, c in dist.items() if t in v3_deprecated}

        # layer/tier NULL 확인
        null_layer = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE status='active' AND layer IS NULL"
        ).fetchone()[0]

        return {
            "distribution": dist,
            "total_active": sum(dist.values()),
            "leaked_types": leaked,
            "null_layer_count": null_layer,
            "ok": len(leaked) == 0,
        }
    finally:
        if close:
            conn.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv

    print("=== Ontology v3 Migration — Step 1 ===\n")

    # G3: 백업
    if not dry_run:
        backup = backup_db()
        print(f"DB 백업: {backup}\n")

    # Step 1 실행
    stats = migrate_step1(dry_run=dry_run)
    print(f"\n결과: {json.dumps(stats, indent=2)}")

    if not dry_run:
        # 검증
        print("\n=== 검증 ===")
        v = verify_migration()
        print(f"Total active: {v['total_active']}")
        print(f"Leaked types: {v['leaked_types']}")
        print(f"Null layer: {v['null_layer_count']}")
        print(f"OK: {v['ok']}")

        print(f"\nTop 10 타입:")
        for t, c in sorted(v["distribution"].items(), key=lambda x: -x[1])[:10]:
            print(f"  {t}: {c}")
