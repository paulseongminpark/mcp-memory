"""Ontology validation — type_defs 테이블 기반 (schema.yaml fallback 포함)."""

from __future__ import annotations

from config import SYSTEM_NODE_TYPES


def get_valid_node_types() -> list[str]:
    """type_defs 테이블에서 active 타입 목록 반환. fallback: schema.yaml."""
    from storage import sqlite_store

    try:
        conn = sqlite_store._connect()
        rows = conn.execute(
            "SELECT name FROM type_defs WHERE status='active' ORDER BY name"
        ).fetchall()
        conn.close()
        if rows:
            return [r["name"] for r in rows]
    except Exception:
        pass

    # fallback: schema.yaml
    return sorted(_get_types_from_schema())


def validate_node_type(type_name: str) -> tuple[bool, str | None]:
    """
    type_defs 테이블 기반 노드 타입 검증.

    반환값:
      (True,  None)        — 정확히 일치 (유효)
      (True,  canonical)   — 대소문자 교정 필요 (유효, canonical 사용)
      (False, replaced_by) — deprecated 타입 (replaced_by로 자동 교정 가능)
      (False, None)        — 완전히 없는 타입 (에러)

    참고: type_defs 테이블이 없으면 schema.yaml fallback 사용.
    """
    from storage import sqlite_store

    if type_name in SYSTEM_NODE_TYPES:
        return True, None

    lower_system_types = {name.lower(): name for name in SYSTEM_NODE_TYPES}
    if type_name.lower() in lower_system_types:
        canonical = lower_system_types[type_name.lower()]
        return True, canonical if canonical != type_name else None

    conn = sqlite_store._connect()
    try:
        # 1. 정확한 이름 매칭 (대소문자 포함)
        row = conn.execute(
            "SELECT name, status, replaced_by FROM type_defs WHERE name = ?",
            (type_name,),
        ).fetchone()

        if row:
            if row["status"] == "deprecated":
                return False, row["replaced_by"]  # deprecated → replaced_by 반환
            return True, None  # 정확 일치

        # 2. 대소문자 무시 매칭 (SQLite LOWER 사용)
        row2 = conn.execute(
            "SELECT name, status, replaced_by FROM type_defs WHERE LOWER(name) = LOWER(?)",
            (type_name,),
        ).fetchone()

        if row2:
            if row2["status"] == "deprecated":
                return False, row2["replaced_by"]  # deprecated (대소문자 불일치)
            return True, row2["name"]  # 교정된 canonical 이름

        # 3. type_defs에 없는 타입
        return False, None

    except Exception:
        # type_defs 테이블 미존재 시 schema.yaml 기반 fallback
        return _validate_via_schema_yaml(type_name)

    finally:
        conn.close()


def _validate_via_schema_yaml(type_name: str) -> tuple[bool, str | None]:
    """Fallback: type_defs 테이블 없을 때 schema.yaml 사용 (기존 로직 유지)."""
    valid_types = _get_types_from_schema()
    if type_name in valid_types:
        return True, None
    lower_map = {t.lower(): t for t in valid_types}
    if type_name.lower() in lower_map:
        return True, lower_map[type_name.lower()]
    return False, None


def _get_types_from_schema() -> set[str]:
    """schema.yaml에서 활성 타입 로드 (fallback용)."""
    import yaml
    from pathlib import Path

    schema_path = Path(__file__).parent / "schema.yaml"
    if not schema_path.exists():
        return {"Unclassified"}
    with open(schema_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return set(data.get("node_types", {}).keys())


def suggest_closest_type(content: str) -> str:
    """
    content 본문 키워드 기반 타입 추천.
    (type_defs에서 active 타입만 대상 — 향후 DB 조회로 전환 가능)

    입력: 저장하려는 content 본문
    출력: 추천 타입명 (str)
    """
    content_lower = content.lower()
    # v3: 15 active 타입 기준
    hints: dict[str, list[str]] = {
        "Decision":    ["결정", "decided", "decision", "chose", "선택", "확정"],
        "Failure":     ["실패", "fail", "error", "버그", "mistake", "실수", "오류"],
        "Pattern":     ["패턴", "pattern", "반복", "recurring", "규칙", "매번"],
        "Insight":     ["통찰", "insight", "발견", "깨달음", "이해", "알게"],
        "Principle":   ["원칙", "principle", "기준", "철학", "approach", "방침"],
        "Framework":   ["프레임워크", "framework", "구조", "체계", "설계"],
        "Goal":        ["목표", "goal", "달성", "aim", "objective"],
        "Signal":      ["신호", "signal", "조짐", "경향", "징후"],
        "Experiment":  ["실험", "experiment", "테스트", "시도", "검증"],
        "Observation": ["관찰", "observation", "noticed", "봤다", "기록"],
        "Identity":    ["정체성", "identity", "스타일", "선호", "습관"],
        "Narrative":   ["서사", "narrative", "이야기", "맥락", "비유"],
        "Question":    ["질문", "question", "궁금", "미해결", "역설"],
    }
    for type_name, keywords in hints.items():
        if any(kw in content_lower for kw in keywords):
            return type_name
    return "Unclassified"


def validate_relation(relation: str) -> tuple[bool, str | None]:
    """
    relation_defs 테이블 기반 관계 검증.
    insert_edge()에서 fallback이 이미 있으므로 MCP 레벨에서는 보조 역할만.

    반환: (True, None) | (True, canonical) | (False, replaced_by) | (False, None)
    """
    from storage import sqlite_store

    conn = sqlite_store._connect()
    try:
        row = conn.execute(
            "SELECT name, status, replaced_by FROM relation_defs WHERE name = ?",
            (relation,),
        ).fetchone()

        if not row:
            return False, None
        if row["status"] == "deprecated":
            return False, row["replaced_by"]
        return True, None

    except Exception:
        # relation_defs 미존재 시 — insert_edge fallback에 위임
        return True, None

    finally:
        conn.close()
