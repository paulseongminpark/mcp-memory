"""checks/schema_consistency.py — config vs schema.yaml vs DB 정합성 검증."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from checks import CheckResult


# config.py 주석: "47 active 타입 (deprecated 3개 제외: Evidence, Heuristic, Concept)"
# VALID_PROMOTIONS/RELATION_RULES에 남아있는 deprecated 타입은 허용
DEPRECATED_TYPES = {"Evidence", "Heuristic", "Concept"}


def _load_schema_yaml() -> dict:
    import yaml
    schema_path = ROOT / "ontology" / "schema.yaml"
    with open(schema_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run() -> list[CheckResult]:
    from config import PROMOTE_LAYER, ALL_RELATIONS, RELATION_RULES, VALID_PROMOTIONS
    from storage.sqlite_store import _db

    results = []

    try:
        schema = _load_schema_yaml()
        schema_node_types = set(schema.get("node_types", {}).keys())
        schema_relation_types = set(schema.get("relation_types", {}).keys())
    except Exception as e:
        return [CheckResult(name="schema_yaml_load", category="schema", status="FAIL",
                            details={"error": str(e)})]

    # 1. PROMOTE_LAYER keys ⊂ schema.yaml node_types
    promote_keys = set(PROMOTE_LAYER.keys()) - {"Unclassified"}
    missing_in_schema = promote_keys - schema_node_types - DEPRECATED_TYPES
    results.append(CheckResult(
        name="promote_layer_in_schema",
        category="schema",
        status="PASS" if not missing_in_schema else "FAIL",
        details={"missing": sorted(missing_in_schema)},
    ))

    # 2. schema.yaml node_types ⊂ PROMOTE_LAYER
    extra_in_schema = schema_node_types - promote_keys - DEPRECATED_TYPES - {"Unclassified"}
    results.append(CheckResult(
        name="schema_in_promote_layer",
        category="schema",
        status="PASS" if not extra_in_schema else "WARN",
        details={"extra": sorted(extra_in_schema)},
    ))

    # 3. ALL_RELATIONS == schema.yaml relation_types
    all_rel_set = set(ALL_RELATIONS)
    rel_diff = all_rel_set.symmetric_difference(schema_relation_types)
    results.append(CheckResult(
        name="all_relations_match_schema",
        category="schema",
        status="PASS" if not rel_diff else "FAIL",
        details={"diff": sorted(rel_diff)},
    ))

    # 4. type_defs 테이블 active count == schema.yaml count
    with _db() as conn:
        db_type_count = conn.execute(
            "SELECT COUNT(*) FROM type_defs WHERE status='active'"
        ).fetchone()[0]
        db_rel_count = conn.execute(
            "SELECT COUNT(*) FROM relation_defs WHERE status='active'"
        ).fetchone()[0]

    schema_type_count = len(schema_node_types)
    schema_rel_count = len(schema_relation_types)
    results.append(CheckResult(
        name="type_defs_count",
        category="schema",
        status="PASS" if db_type_count == schema_type_count else "WARN",
        details={"db": db_type_count, "schema_yaml": schema_type_count},
    ))
    results.append(CheckResult(
        name="relation_defs_count",
        category="schema",
        status="PASS" if db_rel_count == schema_rel_count else "WARN",
        details={"db": db_rel_count, "schema_yaml": schema_rel_count},
    ))

    # 5. RELATION_RULES 참조 타입이 모두 PROMOTE_LAYER에 존재 (deprecated 허용)
    valid_types = set(PROMOTE_LAYER.keys()) | DEPRECATED_TYPES
    bad_rule_types = set()
    for (src, tgt) in RELATION_RULES:
        if src not in valid_types:
            bad_rule_types.add(src)
        if tgt not in valid_types:
            bad_rule_types.add(tgt)
    results.append(CheckResult(
        name="relation_rules_types_valid",
        category="schema",
        status="PASS" if not bad_rule_types else "FAIL",
        details={"unknown_types": sorted(bad_rule_types)},
    ))

    # 6. VALID_PROMOTIONS 참조 타입이 모두 PROMOTE_LAYER에 존재 (deprecated 허용)
    bad_promo_types = set()
    for src, targets in VALID_PROMOTIONS.items():
        if src not in valid_types:
            bad_promo_types.add(src)
        for tgt in targets:
            if tgt not in valid_types:
                bad_promo_types.add(tgt)
    results.append(CheckResult(
        name="valid_promotions_types_valid",
        category="schema",
        status="PASS" if not bad_promo_types else "FAIL",
        details={"unknown_types": sorted(bad_promo_types)},
    ))

    return results
