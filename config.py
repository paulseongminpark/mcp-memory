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
SIMILARITY_THRESHOLD = 0.3  # 자동 edge 생성 임계값
GRAPH_MAX_HOPS = 2
RRF_K = 18  # Reciprocal Rank Fusion 상수 (tuned 2026-03-08: 60→18, NDCG+12.5%)
GRAPH_BONUS = 0.005  # 그래프 이웃 보너스 (tuned 2026-03-08: 0.015→0.005, vector rank 우선)
ENRICHMENT_QUALITY_WEIGHT = 0.2   # recall() quality_score 가중치
ENRICHMENT_TEMPORAL_WEIGHT = 0.1  # recall() temporal_relevance 가중치
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
PROMOTION_SWR_THRESHOLD = 0.55   # SWR Gate 통과 기준
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
}

ALL_RELATIONS = [r for group in RELATION_TYPES.values() for r in group]

# ─── 규칙 기반 relation 매핑 (α) ─────────────────────────
# (source_type, target_type) → relation
# remember() auto_link + retroactive reclassification에서 사용
RELATION_RULES: dict[tuple[str, str], str] = {
    # 승격 경로 (layer 상승)
    ("Observation", "Signal"): "triggered_by",
    ("Signal", "Pattern"): "realized_as",
    ("Signal", "Insight"): "realized_as",
    ("Pattern", "Principle"): "crystallized_into",
    ("Insight", "Principle"): "crystallized_into",
    ("Pattern", "Framework"): "crystallized_into",
    ("Pattern", "Heuristic"): "crystallized_into",
    ("Insight", "Concept"): "crystallized_into",
    ("Principle", "Belief"): "crystallized_into",
    ("Principle", "Philosophy"): "crystallized_into",
    ("Principle", "Value"): "crystallized_into",
    # 인과
    ("Decision", "Pattern"): "led_to",
    ("Decision", "Insight"): "led_to",
    ("Decision", "Failure"): "resulted_in",
    ("Failure", "Decision"): "resolved_by",
    ("Failure", "Insight"): "led_to",
    ("Question", "Insight"): "resolved_by",
    ("Question", "Decision"): "resolved_by",
    ("Experiment", "Insight"): "led_to",
    ("Experiment", "Failure"): "resulted_in",
    ("Experiment", "Breakthrough"): "led_to",
    # 구조
    ("Tool", "Workflow"): "part_of",
    ("Skill", "Workflow"): "part_of",
    ("Agent", "Workflow"): "part_of",
    ("Workflow", "Framework"): "instantiated_as",
    ("Workflow", "Project"): "part_of",
    ("Project", "Goal"): "governed_by",
    ("Framework", "Principle"): "governed_by",
    # 의미
    ("Narrative", "Insight"): "exemplifies",
    ("Insight", "Narrative"): "expressed_as",
    ("Insight", "Breakthrough"): "led_to",
    ("Breakthrough", "Insight"): "led_to",
    ("Identity", "Principle"): "governed_by",
    ("Identity", "Value"): "governed_by",
    # 시스템
    ("SystemVersion", "Workflow"): "extends",
    ("SystemVersion", "Tool"): "contains",
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

    # 3. 같은 레이어
    if src_layer is not None and src_layer == tgt_layer:
        if src_type == tgt_type:
            return "supports"
        if src_project and tgt_project and src_project == tgt_project:
            return "part_of"
        return "parallel_with"

    # 4. 최종 fallback
    return "connects_with"


# 유효한 승격 경로
VALID_PROMOTIONS = {
    "Observation": ["Signal", "Evidence"],
    "Signal": ["Pattern", "Insight"],
    "Pattern": ["Principle", "Framework", "Heuristic"],
    "Insight": ["Principle", "Concept"],
    "Principle": ["Belief", "Philosophy", "Value"],
}

# Promotion 관련 layer 매핑 — 47 active 타입 (deprecated 3개 제외: Evidence, Heuristic, Concept)
PROMOTE_LAYER = {
    # ── Layer 0 (7) ───────────────────────────────────────────
    "Observation": 0, "Trigger": 0, "Context": 0,
    "Conversation": 0, "Narrative": 0, "Question": 0, "Preference": 0,
    # ── Layer 1 (18) ──────────────────────────────────────────
    "Decision": 1, "Plan": 1, "Workflow": 1, "Experiment": 1,
    "Failure": 1, "Breakthrough": 1, "Evolution": 1, "Signal": 1,
    "Goal": 1, "Ritual": 1, "Tool": 1, "Skill": 1,
    "AntiPattern": 1, "Constraint": 1, "Assumption": 1,
    "SystemVersion": 1, "Agent": 1, "Project": 1,
    # ── Layer 2 (7) ───────────────────────────────────────────
    "Pattern": 2, "Insight": 2, "Framework": 2, "Trade-off": 2,
    "Tension": 2, "Metaphor": 2, "Connection": 2,
    # ── Layer 3 (6) ───────────────────────────────────────────
    "Principle": 3, "Identity": 3, "Boundary": 3,
    "Vision": 3, "Paradox": 3, "Commitment": 3,
    # ── Layer 4 (4) ───────────────────────────────────────────
    "Belief": 4, "Philosophy": 4, "Mental Model": 4, "Lens": 4,
    # ── Layer 5 (4) ───────────────────────────────────────────
    "Axiom": 5, "Value": 5, "Wonder": 5, "Aporia": 5,
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
COMPOSITE_WEIGHT_RRF = 0.5
COMPOSITE_WEIGHT_DECAY = 0.3
COMPOSITE_WEIGHT_IMPORTANCE = 0.2
DECAY_LAMBDA = 0.01           # half-life ~69 days
PROMOTED_MULTIPLIER = 1.5     # reviewed-item boost (promotion_candidate=1)
LAYER_IMPORTANCE = {
    5: 1.0, 4: 0.8, 3: 0.6,
    2: 0.4, 1: 0.2, 0: 0.1,
    None: 0.1,  # Unclassified
}

# ── Type-aware search ────────────────────────────────────────
TYPE_CHANNEL_WEIGHT = 0.5   # typed vector RRF 채널 가중치 (1.0 = 일반 채널과 동일)
MAX_TYPE_HINTS = 2          # 쿼리당 최대 type hint 수 (API 호출 제한)

TYPE_KEYWORDS: dict[str, list[str]] = {
    "Workflow": ["워크플로우", "절차", "단계", "파이프라인", "프로세스", "체인", "실행 순서"],
    "Tool": ["도구", "툴", "CLI", "스크립트", "명령어", "플러그인"],
    "Agent": ["에이전트", "팀", "역할", "봇", "자동화 에이전트"],
    "Skill": ["스킬", "명령", "/", "슬래시"],
    "Failure": ["실패", "에러", "버그", "오류", "장애", "문제"],
    "Experiment": ["실험", "테스트", "검증", "비교", "시도"],
    "Decision": ["결정", "선택", "결단", "판단", "확정"],
    "Evolution": ["진화", "변경", "업데이트", "버전", "발전", "개선"],
    "Signal": ["신호", "관찰", "습관", "패턴 관찰", "징후"],
    "Goal": ["목표", "계획", "방향", "비전"],
    "Pattern": ["패턴", "반복", "규칙", "관례"],
    "Framework": ["프레임워크", "구조", "아키텍처", "설계", "스키마"],
    "Project": ["프로젝트", "레포", "저장소"],
    "Connection": ["연결", "관계", "대응", "매핑"],
    "Narrative": ["서사", "맥락", "이야기", "세션 기록"],
}
