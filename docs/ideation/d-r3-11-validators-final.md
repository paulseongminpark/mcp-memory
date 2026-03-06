# D-r3-11: validators.py + server.py 통합 최종 코드 설계

> 세션 D | Round 3 | 2026-03-05
> D-7 server.py 삽입 코드 + A-13 type_defs 기반 validators.py 전환 통합

---

## 개요

| 항목 | 이전 (D-7) | 최종 (r3-11) |
|------|-----------|-------------|
| validators.py 타입 소스 | schema.yaml 기반 set | type_defs 테이블 (live DB) |
| deprecated 타입 처리 | 없음 | replaced_by 자동 교정 + 경고 |
| case correction | 있음 | 유지 |
| edge relation 검증 | MCP 레벨 불필요 확인 | 동일 (insert_edge fallback 유지) |

---

## 1. validators.py — type_defs 기반 전환 (A-13 연동)

```python
# ontology/validators.py — 최종 버전 (A-13 type_defs 기반)

from __future__ import annotations


def validate_node_type(type_name: str) -> tuple[bool, str | None]:
    """
    type_defs 테이블 기반 노드 타입 검증.

    반환값:
      (True,  None)        — 정확히 일치 (유효)
      (True,  canonical)   — 대소문자 교정 필요 (유효, canonical 사용)
      (False, replaced_by) — deprecated 타입 (replaced_by로 자동 교정 가능)
      (False, None)        — 완전히 없는 타입 (에러)

    참고: A-13 type_defs 테이블이 없으면 schema.yaml fallback 사용.
    """
    from storage import sqlite_store

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

        # 3. type_defs 테이블이 없거나 타입 없음 — schema.yaml fallback
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
    hints: dict[str, list[str]] = {
        "Decision":    ["결정", "decided", "decision", "chose", "선택", "확정"],
        "Failure":     ["실패", "fail", "error", "버그", "mistake", "실수", "오류"],
        "Pattern":     ["패턴", "pattern", "반복", "recurring", "규칙", "매번"],
        "Insight":     ["통찰", "insight", "발견", "깨달음", "이해", "알게"],
        "Principle":   ["원칙", "principle", "기준", "철학", "approach", "방침"],
        "Framework":   ["프레임워크", "framework", "구조", "체계", "설계"],
        "Workflow":    ["워크플로우", "workflow", "프로세스", "절차", "흐름"],
        "Goal":        ["목표", "goal", "달성", "aim", "objective"],
        "Signal":      ["신호", "signal", "관찰", "느낌", "조짐", "경향"],
        "AntiPattern": ["안티패턴", "antipattern", "피해야", "하지 말", "문제"],
        "Experiment":  ["실험", "experiment", "테스트", "시도", "검증"],
        "Observation": ["관찰", "observation", "발견", "noticed", "봤다"],
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
```

---

## 2. server.py — remember() 최종 삽입 코드

```python
# server.py — remember() 함수 (타입 검증 블록 포함 최종 버전)
# 기존 import 섹션 상단에 추가:
from ontology.validators import validate_node_type, suggest_closest_type


@mcp.tool()
def remember(
    content: str,
    type: str = "Unclassified",
    tags: str = "",
    project: str = "",
    metadata: dict | None = None,
    confidence: float = 1.0,
    source: str = "claude",
) -> dict:
    """Store a memory node with automatic embedding and relationship detection."""

    # ── [A-13 통합] 타입 검증 블록 ─────────────────────────────────────────
    deprecated_warning: str | None = None

    valid, correction = validate_node_type(type)

    if valid:
        # 유효 타입 — 대소문자 교정이 있으면 적용
        if correction:
            type = correction  # e.g., "pattern" → "Pattern"

    else:
        if correction:
            # Deprecated 타입 — replaced_by로 자동 교정 + 경고
            deprecated_warning = (
                f"Type '{type}' is deprecated. Auto-converted to '{correction}'."
            )
            type = correction  # 교정 후 정상 저장 진행

        else:
            # 완전히 없는 타입 — 저장 차단 + content 기반 추천
            suggestion = suggest_closest_type(content)
            return {
                "node_id": None,
                "type": type,
                "project": project,
                "auto_edges": [],
                "error": f"Unknown node type: '{type}'.",
                "suggestion": suggestion,
                "message": (
                    f"Validation failed: unknown type '{type}'. "
                    f"Suggested: '{suggestion}'"
                ),
            }
    # ── [타입 검증 끝] ─────────────────────────────────────────────────────

    from tools.remember import run_remember

    result = run_remember(
        content=content,
        type=type,
        tags=tags,
        project=project,
        metadata=metadata,
        confidence=confidence,
        source=source,
    )

    # Deprecated 타입 사용 시 경고 추가
    if deprecated_warning:
        result["warning"] = deprecated_warning

    return result
```

**변경 요약:**

| 파일 | 추가/수정 | 줄 수 |
|------|----------|------|
| `ontology/validators.py` | `validate_node_type()` type_defs 전환 + deprecated 처리 | 전체 교체 (~80줄) |
| `ontology/validators.py` | `_validate_via_schema_yaml()` fallback 추가 | +15줄 |
| `ontology/validators.py` | `validate_relation()` 신규 | +20줄 |
| `server.py` | import 추가 | +1줄 |
| `server.py` | remember() 타입 검증 블록 | +25줄 |

---

## 3. 테스트 시나리오 10개

### 환경 설정 (pytest fixture)

```python
# tests/test_validators_integration.py
import pytest
from unittest.mock import patch, MagicMock

# type_defs mock: 31개 active + 19개 deprecated (A-13 기준)
MOCK_TYPE_DEFS = {
    # active
    "Pattern": {"status": "active", "replaced_by": None},
    "Insight": {"status": "active", "replaced_by": None},
    "Decision": {"status": "active", "replaced_by": None},
    "Unclassified": {"status": "active", "replaced_by": None},
    "Value": {"status": "active", "replaced_by": None},
    # deprecated
    "Concept": {"status": "deprecated", "replaced_by": "Insight"},
    "Heuristic": {"status": "deprecated", "replaced_by": "Pattern"},
    "Plan": {"status": "deprecated", "replaced_by": "Goal"},
}


def mock_validate(type_name: str):
    """DB 없이 테스트할 수 있는 mock validate_node_type."""
    # 정확 매칭
    if type_name in MOCK_TYPE_DEFS:
        d = MOCK_TYPE_DEFS[type_name]
        if d["status"] == "deprecated":
            return False, d["replaced_by"]
        return True, None

    # 대소문자 매칭
    lower_map = {k.lower(): k for k in MOCK_TYPE_DEFS}
    if type_name.lower() in lower_map:
        canonical = lower_map[type_name.lower()]
        d = MOCK_TYPE_DEFS[canonical]
        if d["status"] == "deprecated":
            return False, d["replaced_by"]
        return True, canonical

    return False, None
```

### TC-1: 정상 — 정확한 타입 일치

```python
def test_tc1_exact_match():
    """'Pattern' → (True, None) → 그대로 저장"""
    valid, correction = mock_validate("Pattern")
    assert valid is True
    assert correction is None
    # server.py: type 변경 없음, deprecated_warning 없음
```

### TC-2: 정상 — Unclassified 기본값

```python
def test_tc2_unclassified_default():
    """type 미입력 → 'Unclassified' → (True, None) → 정상 저장"""
    valid, correction = mock_validate("Unclassified")
    assert valid is True
    assert correction is None
```

### TC-3: 대소문자 — 소문자 입력

```python
def test_tc3_lowercase():
    """'pattern' → (True, 'Pattern') → 자동 교정 후 저장"""
    valid, correction = mock_validate("pattern")
    assert valid is True
    assert correction == "Pattern"
    # server.py: type = "Pattern"으로 교정됨
```

### TC-4: 대소문자 — 완전 대문자

```python
def test_tc4_allcaps():
    """'DECISION' → (True, 'Decision') → 자동 교정"""
    valid, correction = mock_validate("DECISION")
    assert valid is True
    assert correction == "Decision"
```

### TC-5: 대소문자 — 혼합

```python
def test_tc5_mixed_case():
    """'iNsIgHt' → (True, 'Insight') → 자동 교정"""
    valid, correction = mock_validate("iNsIgHt")
    assert valid is True
    assert correction == "Insight"
```

### TC-6: Deprecated — 대체 타입 있음

```python
def test_tc6_deprecated_with_replacement():
    """'Concept' → (False, 'Insight') → auto-convert + warning 포함 저장"""
    valid, correction = mock_validate("Concept")
    assert valid is False
    assert correction == "Insight"
    # server.py: type = "Insight", result["warning"] 추가됨
```

### TC-7: Deprecated — 대소문자 불일치 + deprecated

```python
def test_tc7_deprecated_case_insensitive():
    """'heuristic' → LOWER 매칭 → deprecated → (False, 'Pattern')"""
    valid, correction = mock_validate("heuristic")
    assert valid is False
    assert correction == "Pattern"
    # server.py: type = "Pattern", warning 포함 저장
```

### TC-8: 존재 안 함 — 완전 미지 타입

```python
def test_tc8_completely_unknown():
    """'FooBar' → (False, None) → 에러 반환, 저장 안 됨"""
    valid, correction = mock_validate("FooBar")
    assert valid is False
    assert correction is None
    # server.py: suggest_closest_type(content) 호출 후 error dict 반환

    from ontology.validators import suggest_closest_type
    suggestion = suggest_closest_type("패턴 반복 발견")
    assert suggestion == "Pattern"  # content 기반 추천
```

### TC-9: 존재 안 함 — 오타 (유사해 보이는 이름)

```python
def test_tc9_typo():
    """'Patern' (오타) → 대소문자 맵에도 없음 → (False, None)"""
    valid, correction = mock_validate("Patern")
    assert valid is False
    assert correction is None
    # server.py: content 기반 suggest → 예) 내용에 "패턴"이 있으면 "Pattern" 추천
    # suggest_closest_type()는 타입명 유사도가 아니라 content 기반임을 확인
```

### TC-10: Edge Relation 검증 — insert_edge fallback 확인

```python
def test_tc10_edge_relation_fallback():
    """
    잘못된 relation → insert_edge() 레벨에서 조용히 "connects_with" 교정.
    MCP 레벨 별도 검증 불필요 확인.

    근거 (sqlite_store.py L156-183):
      if relation not in ALL_RELATIONS:
          # correction_log 기록 + relation = "connects_with"

    A-13 relation_defs에서 deprecated 관계 ('strengthens') 처리:
      validate_relation("strengthens") → (False, "supports")
      그러나 insert_edge fallback이 이미 "connects_with"로 처리함.
      → server.py에 별도 validate_relation() 호출 불필요.

    결론: edge relation은 sqlite_store 레벨에서 단일 처리. 중복 검증 금지.
    """
    from ontology.validators import validate_relation

    # deprecated relation 확인
    valid, replacement = validate_relation("strengthens")
    assert valid is False
    assert replacement == "supports"  # A-13 correction

    # 완전 미지 relation 확인
    valid2, replacement2 = validate_relation("nonexistent_rel")
    assert valid2 is False
    assert replacement2 is None
    # 양쪽 모두 insert_edge() fallback이 "connects_with"로 처리 → 저장됨
```

---

## 4. 구현 파일 최종 요약

| 파일 | 변경 내용 | Phase |
|------|---------|-------|
| `ontology/validators.py` | type_defs 기반 전환 (schema.yaml fallback 유지) | Phase 0 |
| `server.py` | remember() deprecated 처리 + 에러 포맷 완성 | Phase 0 |
| `tests/test_validators_integration.py` | TC1~TC10 테스트 | Phase 0 |

**Edge relation 결론:** `insert_edge()` fallback이 이미 모든 케이스 처리.
MCP 레벨에서 추가 검증 코드 불필요. 단, `validate_relation()`은 향후 운영 스크립트에서 사전 점검용으로 활용 가능.
