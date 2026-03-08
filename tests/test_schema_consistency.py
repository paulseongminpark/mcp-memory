"""Schema/config consistency checks for promotion and relations."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import ALL_RELATIONS, PROMOTE_LAYER, RELATION_RULES, VALID_PROMOTIONS

SCHEMA_PATH = ROOT / "ontology" / "schema.yaml"
DEPRECATED_EXCEPTIONS = {"Evidence", "Heuristic", "Concept"}


def _load_schema() -> dict:
    return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_all_promote_layer_keys_exist_in_schema_node_types():
    schema = _load_schema()
    schema_types = set(schema["node_types"])
    missing = set(PROMOTE_LAYER) - schema_types

    assert missing == set()


def test_all_active_schema_node_types_are_mapped_in_promote_layer_except_deprecated_three():
    schema = _load_schema()
    schema_types = set(schema["node_types"])
    missing = schema_types - set(PROMOTE_LAYER) - DEPRECATED_EXCEPTIONS

    assert missing == set()


def test_all_relations_match_schema_relation_types():
    schema = _load_schema()
    schema_relations = set(schema["relation_types"])

    assert set(ALL_RELATIONS) == schema_relations


def test_relation_rules_only_reference_promote_layer_types():
    relation_rule_types = set()
    for source_type, target_type in RELATION_RULES:
        relation_rule_types.add(source_type)
        relation_rule_types.add(target_type)

    promote_types = set(PROMOTE_LAYER)

    assert relation_rule_types - promote_types - DEPRECATED_EXCEPTIONS == set()


def test_valid_promotions_only_reference_promote_layer_types():
    valid_promotion_types = set(VALID_PROMOTIONS)
    for targets in VALID_PROMOTIONS.values():
        valid_promotion_types.update(targets)

    promote_types = set(PROMOTE_LAYER)

    assert valid_promotion_types - promote_types - DEPRECATED_EXCEPTIONS == set()
