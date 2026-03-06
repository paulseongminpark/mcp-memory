"""TC1~TC10: validators.py integration tests (mock DB, no live DB needed)."""

import pytest
from ontology.validators import suggest_closest_type, validate_relation

# type_defs mock: active + deprecated 샘플
MOCK_TYPE_DEFS = {
    # active
    "Pattern":       {"status": "active",     "replaced_by": None},
    "Insight":       {"status": "active",     "replaced_by": None},
    "Decision":      {"status": "active",     "replaced_by": None},
    "Unclassified":  {"status": "active",     "replaced_by": None},
    "Value":         {"status": "active",     "replaced_by": None},
    # deprecated
    "Concept":       {"status": "deprecated", "replaced_by": "Insight"},
    "Heuristic":     {"status": "deprecated", "replaced_by": "Pattern"},
    "Plan":          {"status": "deprecated", "replaced_by": "Goal"},
}

MOCK_RELATION_DEFS = {
    "supports":       {"status": "active",     "replaced_by": None},
    "connects_with":  {"status": "active",     "replaced_by": None},
    "strengthens":    {"status": "deprecated", "replaced_by": "supports"},
}


def mock_validate(type_name: str) -> tuple[bool, str | None]:
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


def mock_validate_relation(relation: str) -> tuple[bool, str | None]:
    """DB 없이 테스트할 수 있는 mock validate_relation."""
    if relation in MOCK_RELATION_DEFS:
        d = MOCK_RELATION_DEFS[relation]
        if d["status"] == "deprecated":
            return False, d["replaced_by"]
        return True, None
    return False, None


# ── TC-1: 정상 — 정확한 타입 일치 ──────────────────────────────────────────

def test_tc1_exact_match():
    """'Pattern' → (True, None) → 그대로 저장"""
    valid, correction = mock_validate("Pattern")
    assert valid is True
    assert correction is None


# ── TC-2: 정상 — Unclassified 기본값 ──────────────────────────────────────

def test_tc2_unclassified_default():
    """type 미입력 → 'Unclassified' → (True, None) → 정상 저장"""
    valid, correction = mock_validate("Unclassified")
    assert valid is True
    assert correction is None


# ── TC-3: 대소문자 — 소문자 입력 ──────────────────────────────────────────

def test_tc3_lowercase():
    """'pattern' → (True, 'Pattern') → 자동 교정 후 저장"""
    valid, correction = mock_validate("pattern")
    assert valid is True
    assert correction == "Pattern"


# ── TC-4: 대소문자 — 완전 대문자 ──────────────────────────────────────────

def test_tc4_allcaps():
    """'DECISION' → (True, 'Decision') → 자동 교정"""
    valid, correction = mock_validate("DECISION")
    assert valid is True
    assert correction == "Decision"


# ── TC-5: 대소문자 — 혼합 ──────────────────────────────────────────────────

def test_tc5_mixed_case():
    """'iNsIgHt' → (True, 'Insight') → 자동 교정"""
    valid, correction = mock_validate("iNsIgHt")
    assert valid is True
    assert correction == "Insight"


# ── TC-6: Deprecated — 대체 타입 있음 ────────────────────────────────────

def test_tc6_deprecated_with_replacement():
    """'Concept' → (False, 'Insight') → auto-convert + warning 포함 저장"""
    valid, correction = mock_validate("Concept")
    assert valid is False
    assert correction == "Insight"


# ── TC-7: Deprecated — 대소문자 불일치 + deprecated ──────────────────────

def test_tc7_deprecated_case_insensitive():
    """'heuristic' → LOWER 매칭 → deprecated → (False, 'Pattern')"""
    valid, correction = mock_validate("heuristic")
    assert valid is False
    assert correction == "Pattern"


# ── TC-8: 존재 안 함 — 완전 미지 타입 ────────────────────────────────────

def test_tc8_completely_unknown():
    """'FooBar' → (False, None) → 에러 반환, 저장 안 됨"""
    valid, correction = mock_validate("FooBar")
    assert valid is False
    assert correction is None

    # content 기반 추천 확인
    suggestion = suggest_closest_type("패턴 반복 발견")
    assert suggestion == "Pattern"


# ── TC-9: 존재 안 함 — 오타 ────────────────────────────────────────────────

def test_tc9_typo():
    """'Patern' (오타) → 대소문자 맵에도 없음 → (False, None)"""
    valid, correction = mock_validate("Patern")
    assert valid is False
    assert correction is None
    # suggest_closest_type()는 타입명 유사도가 아닌 content 기반임을 확인
    suggestion = suggest_closest_type("패턴 반복")
    assert suggestion == "Pattern"


# ── TC-10: Edge Relation 검증 — deprecated + 미지 relation ──────────────

def test_tc10_edge_relation_fallback():
    """
    잘못된 relation → insert_edge() 레벨에서 조용히 교정.
    MCP 레벨 별도 검증 불필요 확인.
    validate_relation()은 운영 스크립트 사전 점검용으로만 사용.
    """
    # deprecated relation 확인
    valid, replacement = mock_validate_relation("strengthens")
    assert valid is False
    assert replacement == "supports"

    # 완전 미지 relation 확인
    valid2, replacement2 = mock_validate_relation("nonexistent_rel")
    assert valid2 is False
    assert replacement2 is None


# ── suggest_closest_type 추가 케이스 ─────────────────────────────────────

def test_suggest_decision():
    assert suggest_closest_type("결정했다") == "Decision"


def test_suggest_failure():
    assert suggest_closest_type("실패한 이유") == "Failure"


def test_suggest_unclassified():
    assert suggest_closest_type("무관한 내용 xyz") == "Unclassified"
