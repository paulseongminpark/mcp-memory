#!/usr/bin/env python3
"""scripts/eval/diagnose.py — 온톨로지 시스템 전체 진단."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import storage.sqlite_store as store


def main():
    results = {}

    # PATH 1: remember
    print("=== PATH 1: remember() ===")
    try:
        from tools.remember import remember
        r = remember("diag-test-node-2026-03-08", project="diag")
        node_id = r.get("node_id")
        results["remember"] = "OK"
        print(f"  OK: node_id={node_id}, type={r.get('type')}")
        # dedup
        r2 = remember("diag-test-node-2026-03-08", project="diag")
        dedup = r2.get("status") == "duplicate"
        results["dedup"] = "OK" if dedup else "FAIL"
        print(f"  Dedup: {'OK' if dedup else 'FAIL'}")
    except Exception as e:
        results["remember"] = f"FAIL: {e}"
        print(f"  FAIL: {e}")

    # PATH 2: recall + side effects
    print("\n=== PATH 2: recall() ===")
    try:
        from tools.recall import recall
        r = recall("단일 진실 소스", top_k=5)
        count = len(r.get("results", []))
        results["recall"] = "OK" if count > 0 else "FAIL"
        print(f"  Results: {count}")
        with store._db() as conn:
            meta_count = conn.execute("SELECT COUNT(*) FROM meta").fetchone()[0]
            recall_log_count = conn.execute("SELECT COUNT(*) FROM recall_log").fetchone()[0]
        results["meta_populated"] = "OK" if meta_count > 0 else "FAIL"
        results["recall_log_populated"] = "OK" if recall_log_count > 0 else "FAIL (not implemented)"
        print(f"  meta={meta_count}, recall_log={recall_log_count}")
    except Exception as e:
        results["recall"] = f"FAIL: {e}"
        print(f"  FAIL: {e}")

    # PATH 3: promote_node
    print("\n=== PATH 3: promote_node() ===")
    try:
        from tools.promote_node import promote_node
        with store._db() as conn:
            sig = conn.execute("SELECT id, type, layer FROM nodes WHERE type='Signal' LIMIT 1").fetchone()
        if sig:
            r = promote_node(sig[0], target_type="Pattern")
            results["promote_node"] = "OK (ran)"
            print(f"  Node {sig[0]}: {str(r)[:150]}")
        else:
            results["promote_node"] = "SKIP (no Signal)"
            print("  SKIP: No Signal node")
    except Exception as e:
        results["promote_node"] = f"FAIL: {e}"
        print(f"  FAIL: {e}")

    # PATH 4: analyze_signals
    print("\n=== PATH 4: analyze_signals() ===")
    try:
        from tools.analyze_signals import analyze_signals
        r = analyze_signals()
        results["analyze_signals"] = "OK"
        print(f"  signals={r.get('total_signals', 0)}, clusters={len(r.get('clusters', []))}")
    except Exception as e:
        results["analyze_signals"] = f"FAIL: {e}"
        print(f"  FAIL: {e}")

    # PATH 5: get_context, inspect_node
    print("\n=== PATH 5: get_context / inspect_node ===")
    try:
        from tools.get_context import get_context
        r = get_context()
        results["get_context"] = "OK"
        print(f"  get_context keys: {list(r.keys())[:5]}")
    except Exception as e:
        results["get_context"] = f"FAIL: {e}"
        print(f"  FAIL: {e}")
    try:
        from tools.inspect_node import inspect_node
        r = inspect_node(43)
        results["inspect_node"] = "OK"
        print(f"  inspect_node(43): type={r.get('type')}")
    except Exception as e:
        results["inspect_node"] = f"FAIL: {e}"
        print(f"  FAIL: {e}")

    # PATH 6: access_control
    print("\n=== PATH 6: access_control ===")
    try:
        from utils.access_control import check_access
        with store._db() as conn:
            l4 = conn.execute("SELECT id FROM nodes WHERE layer >= 4 LIMIT 1").fetchone()
        if l4:
            paul = check_access(l4[0], "write", "paul")
            system = check_access(l4[0], "write", "system")
            results["access_control"] = "OK" if paul and not system else f"UNEXPECTED paul={paul} system={system}"
            print(f"  L4 node: paul={paul}, system={system}")
        else:
            results["access_control"] = "SKIP (no L4+)"
            print("  No L4+ node")
    except Exception as e:
        results["access_control"] = f"FAIL: {e}"
        print(f"  FAIL: {e}")

    # PATH 7: validators
    print("\n=== PATH 7: validators ===")
    try:
        from ontology.validators import validate_node_type, validate_relation
        v1 = validate_node_type("Principle")
        v2 = validate_node_type("NonexistentXYZ")
        v3 = validate_relation("supports")
        results["validators"] = "OK"
        print(f"  Principle={v1}, NonexistentXYZ={v2}, supports={v3}")
    except Exception as e:
        results["validators"] = f"FAIL: {e}"
        print(f"  FAIL: {e}")

    # PATH 8: BCM/UCB/SPRT
    print("\n=== PATH 8: BCM/UCB/SPRT ===")
    try:
        import storage.hybrid as hybrid
        hybrid.hybrid_search("테스트 BCM", top_k=3)
        with store._db() as conn:
            bcm = conn.execute("SELECT COUNT(*) FROM nodes WHERE theta_m != 0 AND theta_m IS NOT NULL").fetchone()[0]
            visit = conn.execute("SELECT COUNT(*) FROM nodes WHERE visit_count > 0").fetchone()[0]
            meta_rows = conn.execute("SELECT * FROM meta").fetchall()
        results["bcm_active"] = f"OK ({bcm} nodes)" if bcm > 0 else "FAIL (theta_m all 0)"
        results["visit_count"] = f"OK ({visit} nodes)" if visit > 0 else "FAIL (all 0)"
        results["meta_data"] = f"OK ({len(meta_rows)} rows)" if meta_rows else "FAIL (empty)"
        print(f"  theta_m active: {bcm}, visit_count active: {visit}")
        print(f"  meta: {meta_rows[:3]}")
    except Exception as e:
        results["bcm_ucb"] = f"FAIL: {e}"
        print(f"  FAIL: {e}")

    # PATH 9: schema consistency
    print("\n=== PATH 9: schema consistency ===")
    try:
        from config import ALL_RELATIONS, PROMOTE_LAYER
        import yaml
        with open(ROOT / "ontology" / "schema.yaml", encoding="utf-8") as f:
            schema = yaml.safe_load(f)
        raw_types = schema.get("node_types", {})
        raw_rels = schema.get("relation_types", {})
        s_types = set(raw_types.keys()) if isinstance(raw_types, dict) else {t["name"] for t in raw_types}
        s_rels = set(raw_rels.keys()) if isinstance(raw_rels, dict) else {r["name"] for r in raw_rels}
        promote_types = set(PROMOTE_LAYER.keys())
        diff1 = promote_types - s_types
        diff2 = s_types - promote_types
        results["schema_sync"] = "OK" if not diff1 else f"MISMATCH promote-schema={diff1}"
        results["promote_coverage"] = f"OK ({len(PROMOTE_LAYER)}/{len(s_types)})"
        print(f"  PROMOTE_LAYER: {len(PROMOTE_LAYER)}, schema types: {len(s_types)}")
        print(f"  ALL_RELATIONS: {len(ALL_RELATIONS)}, schema rels: {len(s_rels)}")
        if diff1: print(f"  In PROMOTE not schema: {diff1}")
        if diff2: print(f"  In schema not PROMOTE: {diff2}")
    except Exception as e:
        results["schema"] = f"FAIL: {e}"
        print(f"  FAIL: {e}")

    # PATH 10: layer distribution
    print("\n=== PATH 10: layer distribution ===")
    try:
        with store._db() as conn:
            dist = conn.execute("SELECT layer, COUNT(*) FROM nodes GROUP BY layer ORDER BY layer").fetchall()
            # Unclassified는 layer=None이 의도적 설계 → 제외
            null_count = conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE layer IS NULL AND type != 'Unclassified'"
            ).fetchone()[0]
        results["null_layers"] = "OK (0)" if null_count == 0 else f"FAIL ({null_count} NULL)"
        for layer, count in dist:
            print(f"  L{layer}: {count}")
        print(f"  NULL: {null_count}")
    except Exception as e:
        results["layer_dist"] = f"FAIL: {e}"
        print(f"  FAIL: {e}")

    # SUMMARY
    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    fails = {k: v for k, v in results.items() if "FAIL" in str(v)}
    warns = {k: v for k, v in results.items() if "SKIP" in str(v) or "MISMATCH" in str(v) or "UNEXPECTED" in str(v)}
    oks = {k: v for k, v in results.items() if k not in fails and k not in warns}
    print(f"PASS: {len(oks)}")
    for k, v in oks.items():
        print(f"  {k}: {v}")
    print(f"FAIL: {len(fails)}")
    for k, v in fails.items():
        print(f"  {k}: {v}")
    print(f"WARN: {len(warns)}")
    for k, v in warns.items():
        print(f"  {k}: {v}")

    # Cleanup
    with store._db() as conn:
        conn.execute("DELETE FROM nodes WHERE content LIKE '%diag-test-node%'")
        conn.commit()
    print("\nCleanup done.")


if __name__ == "__main__":
    main()
