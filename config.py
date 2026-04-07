"""MCP Memory Server configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 3072

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "memory.db"
CHROMA_PATH = str(DATA_DIR / "chroma")

# 검색 기본값
DEFAULT_TOP_K = 5
SIMILARITY_THRESHOLD = 0.55  # 자동 edge 생성 임계값 (v3.2: 0.3→0.55 노이즈 에지 감소)
GRAPH_MAX_HOPS = 2
RRF_K = 18  # Reciprocal Rank Fusion 상수 (tuned 2026-03-08: 60→18, NDCG+12.5%)
GRAPH_BONUS = 0.03   # 그래프 이웃 보너스 (v3.2: 0.005→0.03, graph 발견 실질적 반영)

# v3.2: 관계 타입별 graph traversal 가중치
# 인과 관계가 가장 가치 높음, 구조 관계는 기본, co_retrieved는 최저
RELATION_WEIGHT: dict[str, float] = {
    # 인과 (1.3~1.5x) — "왜?"에 대한 답
    "caused_by": 1.5, "led_to": 1.5, "triggered_by": 1.5, "resulted_in": 1.5,
    "resolved_by": 1.5, "enabled_by": 1.3, "blocked_by": 1.3,
    "prevented_by": 1.3,
    # 승격 (1.2~1.3x) — 지식 성장 경로
    "realized_as": 1.3, "crystallized_into": 1.3, "abstracted_from": 1.3,
    "generalizes_to": 1.2, "constrains": 1.1, "generates": 1.1,
    # 의미 (1.1~1.2x) — 의미적 연결
    "supports": 1.2, "contradicts": 1.2, "reinforces_mutually": 1.2,
    "analogous_to": 1.1, "exemplifies": 1.1, "inspired_by": 1.1,
    "validates": 1.1, "contextualizes": 1.0,
    # cross-domain (1.0~1.1x)
    "mirrors": 1.1, "influenced_by": 1.0, "correlated_with": 1.0,
    "transfers_to": 1.1, "showcases": 0.9, "refuted_by": 1.2,
    # 구조 (0.8~1.0x)
    "contains": 1.0, "part_of": 1.0, "governed_by": 1.0, "governs": 1.0,
    "extends": 1.0, "composed_of": 1.0, "derived_from": 1.0,
    "instantiated_as": 0.9, "expressed_as": 0.9,
    # 시간/변화 (0.9~1.1x)
    "succeeded_by": 1.1, "preceded_by": 1.1, "evolved_from": 1.1,
    "assembles": 0.9, "born_from": 0.9, "differs_in": 0.8, "variation_of": 0.8,
    # perspective
    "interpreted_as": 0.9, "questions": 1.0, "viewed_through": 0.8,
    # semantic weak
    "parallel_with": 0.7, "connects_with": 0.5,
    # behavioral/derived (최저)
    "co_retrieved": 0.3,
    # unused but defined
    "simultaneous_with": 0.6,
}
RELATION_WEIGHT_DEFAULT = 1.0
ENRICHMENT_QUALITY_WEIGHT = 0.2   # recall() quality_score 가중치
ENRICHMENT_TEMPORAL_WEIGHT = 0.1  # recall() temporal_relevance 가중치

# unenriched 노드의 레이어별 기본 quality_score (enrichment 미완료 패널티 완화)
UNENRICHED_DEFAULT_QS: dict[int, float] = {
    0: 0.4,   # L0: Observation (원시 데이터)
    1: 0.55,  # L1: Decision/Failure/Workflow (경험 기록)
    2: 0.65,  # L2: Pattern/Framework (추상화)
    3: 0.75,  # L3: Principle/Value (핵심 원칙)
}

EXPLORATION_RATE = 0.1  # 그래프 탐색 시 약한 edge 탐험 확률

# ─── BCM + UCB (v2.1, B-14) ──────────────────────────────
UCB_C_FOCUS = 0.3       # focus 모드 탐험 계수
UCB_C_AUTO = 1.0        # auto 모드 (기본)
UCB_C_DMN = 2.5         # dmn 모드 (탐험 극대화)
BCM_HISTORY_WINDOW = 20          # BCM 이력 윈도우 크기
CONTEXT_HISTORY_LIMIT = 5        # 재공고화 ctx_log 최대 항목
LAYER_ETA = {0: 0.020, 1: 0.015, 2: 0.010, 3: 0.005, 4: 0.001, 5: 0.0001}

# ─── Recall (v2.1, B-15) ─────────────────────────────────
PATCH_SATURATION_THRESHOLD = 0.75  # 패치 포화 판정 비율

# ─── Promotion (v2.1, C-11, C-12) ────────────────────────
PROMOTION_SWR_THRESHOLD = 0.25   # SWR Gate 통과 기준 (v3: 0.55→0.25, cross_ratio만으로 통과 가능하게)
SPRT_ALPHA = 0.05                # 오승격 확률 상한
SPRT_BETA = 0.2                  # 놓침 확률 상한
SPRT_P1 = 0.7                    # 진짜 Signal 판정 기준
SPRT_P0 = 0.3                    # 노이즈 판정 기준
SPRT_MIN_OBS = 5                 # SPRT 최소 관측 수

# ─── Drift Detection (v2.1, D-12) ────────────────────────
DRIFT_THRESHOLD = 0.5            # semantic drift cosine sim 하한
SUMMARY_LENGTH_MULTIPLIER = 2.0  # summary 이상치 배수 기준
SUMMARY_LENGTH_MIN_SAMPLE = 10   # 이상치 판단 최소 샘플

# ─── Enrichment Pipeline (v2.0) ───────────────────────────

# 4-Model 배분 — Anthropic (claude-*) 또는 OpenAI 모델 사용 가능
# API_PROVIDER 환경변수로 전환: "anthropic" | "openai" (기본: openai)
API_PROVIDER = os.getenv("API_PROVIDER", "openai")

ENRICHMENT_MODELS_OPENAI = {
    "bulk":       "gpt-5-mini",   # Phase 1: 대량 enrichment (소형 풀)
    "reasoning":  "o3-mini",      # Phase 2: 배치 추론 (소형 풀)
    "verify":     "gpt-4.1",      # Phase 3: 정밀 검증 (대형 풀)
    "deep":       "gpt-5.2",      # Phase 4: 심층 생성 (대형 풀)
    "judge":      "o3",           # Phase 5: 깊은 추론 (대형 풀)
}

ENRICHMENT_MODELS_ANTHROPIC = {
    "bulk":       "claude-haiku-4-5-20251001",   # Phase 1: 구조화 추출
    "reasoning":  "claude-sonnet-4-6-20250514",  # Phase 2: 관계 추론
    "verify":     "claude-sonnet-4-6-20250514",  # Phase 3: 검증
    "deep":       "claude-sonnet-4-6-20250514",  # Phase 4: 심층 분석
    "judge":      "claude-sonnet-4-6-20250514",  # Phase 5: 승격 판단
}

ENRICHMENT_MODELS = (
    ENRICHMENT_MODELS_ANTHROPIC if API_PROVIDER == "anthropic"
    else ENRICHMENT_MODELS_OPENAI
)

# 토큰 예산 (일일 90% 목표)
TOKEN_BUDGETS = {
    "large": 225_000,   # 대형 풀: gpt-5.2, o3, gpt-4.1
    "small": 2_250_000, # 소형 풀: gpt-5-mini, o3-mini
}

# 배치 처리
BATCH_SIZE = 10
BATCH_SLEEP = 0.05      # 배치 간 대기 (초) — 유료 API용
CONCURRENT_WORKERS = 10  # 병렬 API 호출 수
MAX_RETRIES = 3         # API 실패 시 재시도
RETRY_BACKOFF = 2.0     # 재시도 백오프 배수

# 실행 모드
DRY_RUN = False         # True: DB 반영 없이 결과만 출력

# 디렉토리
REPORT_DIR = DATA_DIR / "reports"
BACKUP_DIR = DATA_DIR / "backup"
TOKEN_LOG_DIR = REPORT_DIR / "token_log"

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
}

ALL_RELATIONS = [r for group in RELATION_TYPES.values() for r in group]

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
    """타입+레이어 조합으로 relation 추론. 못 풀면 'connects_with' 반환."""
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
            return "influenced_by"
        if src_project and tgt_project and src_project == tgt_project:
            return "part_of"
        return "parallel_with"

    # 5. 최종 fallback
    return "transfers_to" if is_cross_project else "connects_with"


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

# ─── 검증 임계값 (v2.1.3) ─────────────────────────────────────
VERIFY_THRESHOLDS = {
    "ndcg@5": 0.25,       # goldset 75개 기준 (L1 쿼리 포함)
    "ndcg@10": 0.30,      # goldset 75개 기준
    "hit_rate": 0.50,     # goldset 75개 기준
    "null_layer_pct": 0.0,
    "enrichment_coverage": 0.60,
    "orphan_pct": 0.10,
    "content_hash_coverage": 0.95,
    "duplicate_pct": 0.0,
}

# ── Composite Scoring (Phase 2, 2026-03-08) ──────────────────
COMPOSITE_WEIGHT_RRF = 1.0       # base RRF 유지 (additive 모드)
COMPOSITE_WEIGHT_DECAY = 0.001   # recency bonus (tiebreaker)
COMPOSITE_WEIGHT_IMPORTANCE = 0.001  # layer bonus (tiebreaker)
DECAY_LAMBDA = 0.01           # half-life ~69 days
PROMOTED_MULTIPLIER = 1.5     # reviewed-item boost (promotion_candidate=1)

# v3.2: Source quality bonus (additive on base RRF)
# 의도적 저장(claude)이 자동 덤프보다 높은 정밀도
SOURCE_BONUS: dict[str, float] = {
    "claude": 0.05,        # 대화 중 Claude가 의도적 저장
    "save_session": 0.0,   # 세션 자동 덤프 (중립)
    "pdr": 0.0,            # post-deployment review
    "checkpoint": -0.02,   # checkpoint 덤프 (낮은 정밀도)
}
SOURCE_BONUS_DEFAULT = 0.0  # obsidian, hook 등 기타

# ── v3.3: 온톨로지 정책 상수 ─────────────────────────────────

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

# Edge generation method — fallback/session_anchor 구분
GENERATION_METHODS = {"manual", "rule", "semantic_auto", "fallback", "session_anchor", "co_retrieval", "migration", "external"}
GENERATION_METHOD_PENALTY: dict[str, float] = {
    "fallback": -0.03,
    "session_anchor": -0.05,  # recollection mode에서만 유지
    "co_retrieval": -0.02,
}

# Confidence → ranking 반영 (additive)
CONFIDENCE_WEIGHT = 0.05  # final_score += (confidence - 0.5) * CONFIDENCE_WEIGHT
CONTRADICTION_PENALTY = -0.10  # active contradicts edge 있을 때

# save_session knowledge gate
SAVE_SESSION_DECISION_MIN_LEN = 40   # 미만 → work_item
SAVE_SESSION_QUESTION_MIN_LEN = 40   # 미만 → work_item
SAVE_SESSION_SKIP_PATTERNS = {"미정", "확인", "검토", "점검", "여부", "TBD", "TODO"}

# Project defaults
PROJECT_DEFAULT_GLOBAL = "global"
PROJECT_DEFAULT_EXTERNAL = "external"

# Tag normalization
TAG_CANONICAL_CASE = "lower-kebab"
# v3: max layer = 3
LAYER_IMPORTANCE = {
    3: 0.6, 2: 0.4, 1: 0.2, 0: 0.1,
    None: 0.1,  # Unclassified
}

# ── Type-aware search ────────────────────────────────────────
TYPE_CHANNEL_WEIGHT = 0.5   # typed vector RRF 채널 기본 가중치 (fallback)
MAX_TYPE_HINTS = 2          # 쿼리당 최대 type hint 수 (API 호출 제한)

# 타입별 동적 가중치: 소수 타입은 강하게, 다수 타입(Principle 등)은 기본 검색에서 이미 우세
# v3: 15 active 타입 기준
TYPE_CHANNEL_WEIGHTS: dict[str, float] = {
    "Pattern": 1.0,
    "Decision": 1.0,
    "Signal": 0.8,
    "Failure": 0.8,
    "Experiment": 0.8,
    "Narrative": 0.8,
    "Goal": 0.8,
    "Observation": 0.8,
    "Question": 0.7,
    "Project": 0.7,
    "Identity": 0.7,
    "Insight": 0.6,
    "Framework": 0.6,
    "Principle": 0.5,
    "Tool": 0.5,
}

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
