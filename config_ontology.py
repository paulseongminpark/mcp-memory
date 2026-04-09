"""Ontology-related configuration constants.

Separated from config.py for maintainability.
Includes: RELATION_TYPES, RELATION_RULES, VALID_PROMOTIONS, PROMOTE_LAYER,
          TYPE_KEYWORDS, NODE_ROLES, infer_relation(), and related ontology definitions.
"""

# Allowlists (환각 방지)
FACETS_ALLOWLIST = [
    "philosopher", "developer", "designer", "writer",
    "system-architect", "researcher", "aesthetician",
    "educator", "strategist",
]

DOMAINS_ALLOWLIST = [
    "orchestration", "portfolio", "tech-review", "monet-lab",
    "daily-memo", "mcp-memory", "philosophy", "literature",
    "art", "general",
]

# 48개 관계 타입
RELATION_TYPES = {
    "causal": [
        "caused_by", "led_to", "triggered_by", "resulted_in",
        "resolved_by", "prevented_by", "enabled_by", "blocked_by",
    ],
    "structural": [
        "part_of", "composed_of", "extends", "governed_by", "governs",
        "instantiated_as", "expressed_as", "contains", "derived_from",
    ],
    "layer_movement": [
        "realized_as", "crystallized_into", "abstracted_from",
        "generalizes_to", "constrains", "generates",
    ],
    "diff_tracking": [
        "differs_in", "variation_of", "evolved_from", "succeeded_by",
    ],
    "semantic": [
        "supports", "contradicts", "analogous_to", "parallel_with",
        "reinforces_mutually", "connects_with", "inspired_by", "exemplifies",
    ],
    "perspective": [
        "viewed_through", "interpreted_as", "questions", "validates",
        "contextualizes",
    ],
    "temporal": [
        "preceded_by", "simultaneous_with", "born_from", "assembles",
    ],
    "cross_domain": [
        "transfers_to", "mirrors", "influenced_by", "showcases",
        "correlated_with", "refuted_by",
    ],
    "behavioral": [
        "co_retrieved",
    ],
    "family": [
        "causes", "resolves", "supports", "contradicts", "abstracts",
        "expresses", "evolves", "mirrors", "influences", "governs",
        "contains", "co_occurs",
    ],
}

class _RelationAllowList(tuple):
    """Iterates schema relations only, but membership also accepts family aliases."""

    def __new__(cls, schema_relations: list[str], aliases: list[str] | None = None):
        obj = super().__new__(cls, schema_relations)
        obj._allowed = set(schema_relations)
        if aliases:
            obj._allowed.update(aliases)
        return obj

    def __contains__(self, item):
        return item in self._allowed


_SCHEMA_RELATIONS = [
    relation
    for group_name, group in RELATION_TYPES.items()
    if group_name != "family"
    for relation in group
]
ALL_RELATIONS = _RelationAllowList(
    _SCHEMA_RELATIONS,
    RELATION_TYPES.get("family", []),
)

RELATION_STORAGE_CANONICAL: dict[str, str] = {
    "abstracts": "generalizes_to",
    "co_occurs": "connects_with",
    "expresses": "expressed_as",
    "influences": "correlated_with",
    "realizes": "expressed_as",
}


def canonicalize_relation_for_storage(relation: str) -> str:
    """Map family aliases or legacy names to concrete relation_defs entries."""
    return RELATION_STORAGE_CANONICAL.get(relation, relation)

# ─── 규칙 기반 relation 매핑 (α) ─────────────────────────
# (source_type, target_type) → relation
# remember() auto_link + retroactive reclassification에서 사용
RELATION_RULES: dict[tuple[str, str], str] = {
    # v3.1: 15 active 타입 기준, 40+ 규칙
    #
    # ── 승격 경로 (layer 상승) ──────────────────────────
    ("Observation", "Signal"): "triggered_by",
    ("Signal", "Pattern"): "realized_as",
    ("Signal", "Insight"): "realized_as",
    ("Pattern", "Principle"): "crystallized_into",
    ("Insight", "Principle"): "crystallized_into",
    ("Pattern", "Framework"): "crystallized_into",
    ("Insight", "Framework"): "crystallized_into",
    #
    # ── 인과 (원인→결과) ────────────────────────────────
    ("Decision", "Pattern"): "led_to",
    ("Decision", "Insight"): "led_to",
    ("Decision", "Failure"): "resulted_in",
    ("Failure", "Decision"): "resolved_by",
    ("Failure", "Insight"): "led_to",
    ("Failure", "Pattern"): "led_to",
    ("Failure", "Question"): "led_to",
    ("Question", "Insight"): "resolved_by",
    ("Question", "Decision"): "resolved_by",
    ("Question", "Experiment"): "led_to",
    ("Question", "Goal"): "led_to",
    ("Experiment", "Insight"): "led_to",
    ("Experiment", "Failure"): "resulted_in",
    ("Experiment", "Pattern"): "led_to",
    ("Experiment", "Decision"): "led_to",
    ("Goal", "Experiment"): "led_to",
    ("Goal", "Decision"): "led_to",
    ("Goal", "Project"): "led_to",
    ("Insight", "Decision"): "led_to",
    #
    # ── 구조 (포함/소속) ────────────────────────────────
    ("Tool", "Framework"): "part_of",
    ("Tool", "Project"): "part_of",
    ("Project", "Goal"): "governed_by",
    ("Project", "Framework"): "governed_by",
    ("Project", "Decision"): "contains",
    ("Framework", "Principle"): "governed_by",
    ("Framework", "Tool"): "contains",
    #
    # ── 가이드 (상위→하위 통제) ─────────────────────────
    ("Pattern", "Decision"): "governs",
    ("Principle", "Decision"): "governs",
    ("Identity", "Goal"): "governs",
    ("Identity", "Decision"): "governs",
    ("Identity", "Principle"): "governed_by",
    #
    # ── 의미/예시 ───────────────────────────────────────
    ("Narrative", "Insight"): "exemplifies",
    ("Narrative", "Pattern"): "exemplifies",
    ("Narrative", "Failure"): "exemplifies",
    ("Narrative", "Decision"): "contains",
    ("Narrative", "Question"): "contains",
    ("Insight", "Narrative"): "expressed_as",
    #
    # ── Signal 경로 ─────────────────────────────────────
    ("Observation", "Question"): "led_to",
    ("Observation", "Experiment"): "triggered_by",
    ("Signal", "Experiment"): "led_to",
    ("Signal", "Decision"): "led_to",
    #
    # ── 기타 ────────────────────────────────────────────
    ("Decision", "Question"): "led_to",
}


def infer_relation(src_type: str, src_layer: int | None,
                   tgt_type: str, tgt_layer: int | None,
                   src_project: str = "", tgt_project: str = "") -> str:
    """타입+레이어 조합으로 relation family를 추론한다."""
    # 1. 정확한 타입 조합 매치
    key = (src_type, tgt_type)
    if key in RELATION_RULES:
        return RELATION_RULES[key]
    # 역방향 체크
    rev_key = (tgt_type, src_type)
    if rev_key in RELATION_RULES:
        rev_rel = RELATION_RULES[rev_key]
        # 역방향 매핑
        reverse_map = {
            "triggered_by": "led_to", "led_to": "triggered_by",
            "realized_as": "abstracted_from", "abstracted_from": "realized_as",
            "crystallized_into": "abstracted_from",
            "resulted_in": "caused_by", "caused_by": "resulted_in",
            "resolved_by": "led_to",
            "part_of": "contains", "contains": "part_of",
            "governed_by": "governs", "instantiated_as": "abstracted_from",
            "exemplifies": "expressed_as", "expressed_as": "exemplifies",
            "extends": "derived_from",
        }
        if rev_rel in reverse_map:
            return reverse_map[rev_rel]
        return rev_rel

    # 2. 레이어 기반 fallback
    if src_layer is not None and tgt_layer is not None:
        if src_layer < tgt_layer:
            return "generalizes_to"    # 낮은→높은: 구체가 추상으로 일반화
        if src_layer > tgt_layer:
            return "expressed_as"      # 높은→낮은: 추상이 구체로 표현

    # 3. Cross-project 관계 (v3.1: 프로젝트 간 의미 있는 관계 생성)
    is_cross_project = (src_project and tgt_project and src_project != tgt_project)

    # 4. 같은 레이어
    if src_layer is not None and src_layer == tgt_layer:
        if src_type == tgt_type:
            return "mirrors" if is_cross_project else "supports"
        if is_cross_project:
            return "correlated_with"
        if src_project and tgt_project and src_project == tgt_project:
            return "contains"
        return "connects_with"

    # 5. 최종 fallback
    return "connects_with"


# 유효한 승격 경로 — v3: 15 active 타입 기준
VALID_PROMOTIONS = {
    "Observation": ["Signal"],
    "Signal": ["Pattern", "Insight"],
    "Pattern": ["Principle", "Framework"],
    "Insight": ["Principle"],
}

# Promotion 관련 layer 매핑 — v3: 15 active 타입 + Workflow(Step 2 대기) + Unclassified
PROMOTE_LAYER = {
    # ── Layer 0 (3) ── surface ────────────────────────────────
    "Observation": 0, "Narrative": 0, "Question": 0,
    # ── Layer 1 (7) ── operational ────────────────────────────
    "Decision": 1, "Experiment": 1, "Failure": 1, "Signal": 1,
    "Goal": 1, "Tool": 1, "Project": 1,
    # ── Layer 2 (3) ── structural ─────────────────────────────
    "Pattern": 2, "Insight": 2, "Framework": 2,
    # ── Layer 3 (2) ── core ───────────────────────────────────
    "Principle": 3, "Identity": 3,
    # Workflow: v3에서 deprecated (LLM 재분류 → Pattern/Framework/Tool/Goal/Experiment)
    # ── Meta ──────────────────────────────────────────────────
    "Unclassified": None,  # layer 미배정
}

# ─── v3.3: 온톨로지 정책 상수 ─────────────────────────────────

# System types — generic recall에서 숨기되 correction-aware recall에서 우선 노출
SYSTEM_NODE_TYPES = {"Correction"}

# Node role — session/knowledge 분리의 핵심
NODE_ROLES = {
    "session_anchor",      # save_session Narrative
    "work_item",           # short Decision/Question (40자 미만)
    "knowledge_candidate", # 40자+ Decision/Question, 일반 remember()
    "knowledge_core",      # promoted nodes
    "signal_candidate",    # 반복 관찰에서 Signal 후보
    "correction",          # flag_node() 생성
    "external_noise",      # .venv/LICENSE 등 ingest noise
}

# Generic recall에서 제외하거나 강한 패널티를 줄 role
GENERIC_RECALL_EXCLUDE_ROLES = {"session_anchor", "work_item", "external_noise", "correction"}
GENERIC_RECALL_ROLE_PENALTY: dict[str, float] = {
    "session_anchor": -0.08,
    "work_item": -0.06,
    "external_noise": -0.10,
}

# Epistemic status — 지식 신뢰 상태
EPISTEMIC_STATUSES = {"provisional", "validated", "flagged", "outdated", "superseded"}

# Source kind — source 컬럼에서 분리
SOURCE_KINDS = {"save_session", "checkpoint", "claude", "obsidian", "pdr", "user", "hook", "external"}

# Edge generation method — live DB 값 기준 (v4.0)
GENERATION_METHODS = {
    # semantic (reasoning 기여)
    "manual", "rule", "semantic_auto",
    # structural
    "session_anchor", "co_retrieval",
    # derived (enrichment pipeline)
    "enrichment",
    # operational (기계적 — reasoning weight 최소)
    "fallback", "orphan_repair", "legacy_unknown",
    # legacy
    "migration", "external",
}
GENERATION_METHOD_PENALTY: dict[str, float] = {
    "orphan_repair": -0.08,
    "legacy_unknown": -0.05,
    "fallback": -0.03,
    "session_anchor": -0.05,
    "co_retrieval": -0.02,
    "enrichment": 0.0,
}

# save_session knowledge gate
SAVE_SESSION_DECISION_MIN_LEN = 40   # 미만 → work_item
SAVE_SESSION_QUESTION_MIN_LEN = 40   # 미만 → work_item
SAVE_SESSION_SKIP_PATTERNS = {"미정", "확인", "검토", "점검", "여부", "TBD", "TODO"}

# Project defaults
PROJECT_DEFAULT_GLOBAL = "global"
PROJECT_DEFAULT_EXTERNAL = "external"

# Tag normalization
TAG_CANONICAL_CASE = "lower-kebab"

# v3: 15 active 타입 기준
TYPE_KEYWORDS: dict[str, list[str]] = {
    "Tool": ["도구", "툴", "CLI", "스크립트", "명령어", "플러그인", "에이전트", "스킬"],
    "Failure": ["실패", "에러", "버그", "오류", "장애", "문제", "실수"],
    "Experiment": ["실험", "테스트", "검증", "비교", "시도"],
    "Decision": ["결정", "선택", "결단", "판단", "확정"],
    "Signal": ["신호", "징후", "조짐", "반복 관찰"],
    "Goal": ["목표", "계획", "방향", "비전"],
    "Pattern": ["패턴", "반복", "규칙", "관례", "워크플로우", "절차", "프로세스"],
    "Framework": ["프레임워크", "구조", "아키텍처", "설계", "스키마", "멘탈 모델"],
    "Project": ["프로젝트", "레포", "저장소", "버전"],
    "Narrative": ["서사", "맥락", "이야기", "세션 기록", "비유"],
    "Insight": ["통찰", "발견", "깨달음", "이해", "연결"],
    "Principle": ["원칙", "철학", "가치관", "기준", "믿음"],
    "Identity": ["정체성", "스타일", "습관", "선호", "성향"],
    "Observation": ["관찰", "기록", "증거", "데이터", "로그"],
    "Question": ["질문", "궁금", "미해결", "역설", "모순"],
}
