"""MCP Memory Server configuration.

Core settings: env vars, paths, DB, API keys, embedding, enrichment pipeline.
Search constants → config_search.py
Ontology constants → config_ontology.py

All symbols are re-exported here so `from config import X` keeps working.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local")  # "local" or "openai"
EMBEDDING_MODEL = "text-embedding-3-large"  # OpenAI 모델 (EMBEDDING_PROVIDER=openai 시)
EMBEDDING_DIM = 1024 if EMBEDDING_PROVIDER == "local" else 3072
LOCAL_EMBEDDING_MODEL = "intfloat/multilingual-e5-large"  # 로컬 모델

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "memory.db"
TASKS_DB_PATH = DATA_DIR / "tasks.db"
CHROMA_PATH = str(DATA_DIR / "chroma")

# ─── Enrichment Pipeline (v2.0) ───────────────────────────

# 4-Model 배분 — Anthropic (claude-*) 또는 OpenAI 모델 사용 가능
# API_PROVIDER 환경변수로 전환: "anthropic" | "openai" (기본: openai)
API_PROVIDER = os.getenv("API_PROVIDER", "openai")

ENRICHMENT_MODELS_OPENAI = {
    "bulk":       "llama-3.1-8b-instant",  # Phase 1: Groq 8b (TPD 500K 무료, 70b TPD 100K는 부족)
    "reasoning":  "o3-mini",      # Phase 2: 배치 추론 (소형 풀)
    "verify":     "gpt-4.1",      # Phase 3: 정밀 검증 (대형 풀)
    "deep":       "gpt-5.2",      # Phase 4: 심층 생성 (대형 풀)
    "judge":      "o3",           # Phase 5: 깊은 추론 (대형 풀)
}

# Groq API 모델 — OpenAI 호환 API, 별도 클라이언트 사용
# TPD: llama-3.3-70b=100K/일, llama-3.1-8b=500K/일
GROQ_MODELS = {"llama-3.3-70b-versatile", "llama-3.1-8b-instant"}

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
    "large": 225_000,    # 대형 풀: gpt-5.2, o3, gpt-4.1
    "small": 2_250_000,  # 소형 풀: gpt-5-mini, o3-mini
    "groq":  10_000_000, # Groq 무료: RPD 14,400 기준, 토큰은 넉넉
}

# 배치 처리
BATCH_SIZE = 10
BATCH_SLEEP = 0.05      # 배치 간 대기 (초) — 유료 API용
CONCURRENT_WORKERS = 3  # 병렬 API 호출 수 (Groq 무료 RPM 30 기준)
MAX_RETRIES = 3         # API 실패 시 재시도
RETRY_BACKOFF = 2.0     # 재시도 백오프 배수
API_TIMEOUT = 30        # API 호출 timeout (초) — 무한 backoff 방지

# 실행 모드
DRY_RUN = False         # True: DB 반영 없이 결과만 출력

# 디렉토리
REPORT_DIR = DATA_DIR / "reports"
BACKUP_DIR = DATA_DIR / "backup"
TOKEN_LOG_DIR = REPORT_DIR / "token_log"

# ─── Re-exports ──────────────────────────────────────────────
# All symbols from sub-configs are re-exported so existing
# `from config import X` statements keep working unchanged.

from config_search import *     # noqa: F401,F403,E402
from config_ontology import *   # noqa: F401,F403,E402
