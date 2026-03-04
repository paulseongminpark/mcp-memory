"""Ontology validation — schema.yaml을 동적으로 읽어 타입/관계 검증."""

from pathlib import Path

import yaml

SCHEMA_PATH = Path(__file__).parent / "schema.yaml"

_schema: dict | None = None


def _load_schema() -> dict:
    global _schema
    if _schema is None:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            _schema = yaml.safe_load(f)
    return _schema


def reload_schema() -> None:
    """스키마 핫 리로드 (YAML 편집 후 재시작 없이 적용)."""
    global _schema
    _schema = None
    _load_schema()


def get_valid_node_types() -> list[str]:
    return list(_load_schema()["node_types"].keys())


def get_valid_relation_types() -> list[str]:
    return list(_load_schema()["relation_types"].keys())


def validate_node_type(node_type: str) -> tuple[bool, str]:
    """노드 타입 검증. (valid, message) 반환."""
    valid_types = get_valid_node_types()
    if node_type in valid_types:
        return True, ""
    # 대소문자 무시 매칭
    lower_map = {t.lower(): t for t in valid_types}
    if node_type.lower() in lower_map:
        return True, lower_map[node_type.lower()]
    return False, f"Unknown type '{node_type}'. Valid: {', '.join(valid_types)}"


def validate_relation_type(relation: str) -> tuple[bool, str]:
    """관계 타입 검증."""
    valid = get_valid_relation_types()
    if relation in valid:
        return True, ""
    return False, f"Unknown relation '{relation}'. Valid: {', '.join(valid)}"


def get_type_description(node_type: str) -> str:
    schema = _load_schema()
    type_def = schema["node_types"].get(node_type, {})
    return type_def.get("description", "")


def suggest_closest_type(content: str) -> str:
    """내용 기반 타입 추천 (키워드 휴리스틱). Claude가 직접 분류하므로 fallback용."""
    content_lower = content.lower()
    hints = {
        "Decision": ["결정", "decided", "decision", "chose", "선택"],
        "Failure": ["실패", "fail", "error", "버그", "mistake", "실수"],
        "Pattern": ["패턴", "pattern", "반복", "recurring", "규칙"],
        "Identity": ["가치", "철학", "philosophy", "성격", "스타일"],
        "Preference": ["선호", "prefer", "좋아", "싫어"],
        "Goal": ["목표", "goal", "비전", "vision", "방향"],
        "Insight": ["깨달", "insight", "발견", "realize"],
        "Question": ["질문", "question", "?", "어떻게", "왜"],
        "Principle": ["원칙", "principle", "규칙", "rule"],
        "AntiPattern": ["반복 실수", "anti-pattern", "주의"],
    }
    for type_name, keywords in hints.items():
        if any(kw in content_lower for kw in keywords):
            return type_name
    return "Unclassified"
