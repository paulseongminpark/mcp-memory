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
RRF_K = 60  # Reciprocal Rank Fusion 상수
GRAPH_BONUS = 0.3  # 그래프 이웃 보너스
ENRICHMENT_QUALITY_WEIGHT = 0.2   # recall() quality_score 가중치
ENRICHMENT_TEMPORAL_WEIGHT = 0.1  # recall() temporal_relevance 가중치

# ─── Enrichment Pipeline (v2.0) ───────────────────────────

# 4-Model 배분
ENRICHMENT_MODELS = {
    "bulk":       "gpt-5-mini",   # Phase 1: 대량 enrichment (소형 풀)
    "reasoning":  "o3-mini",      # Phase 2: 배치 추론 (소형 풀)
    "verify":     "gpt-4.1",      # Phase 3: 정밀 검증 (대형 풀)
    "deep":       "gpt-5.2",      # Phase 4: 심층 생성 (대형 풀)
    "judge":      "o3",           # Phase 5: 깊은 추론 (대형 풀)
}

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
        "part_of", "composed_of", "extends", "governed_by",
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

# 유효한 승격 경로
VALID_PROMOTIONS = {
    "Observation": ["Signal", "Evidence"],
    "Signal": ["Pattern", "Insight"],
    "Pattern": ["Principle", "Framework", "Heuristic"],
    "Insight": ["Principle", "Concept"],
    "Principle": ["Belief", "Philosophy", "Value"],
}

# Promotion 관련 layer 매핑
PROMOTE_LAYER = {
    "Observation": 0, "Evidence": 0, "Signal": 1,
    "Pattern": 2, "Insight": 2, "Principle": 3,
    "Framework": 2, "Heuristic": 2, "Concept": 2,
    "Belief": 4, "Philosophy": 4, "Value": 5,
}
