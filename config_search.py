"""Search-related configuration constants.

Separated from config.py for maintainability.
Includes: RRF, Graph bonus, UCB, BCM, Composite scoring, Reranker, Source bonus,
          type-aware search weights, maturity gating.
"""

# ─── 검색 기본값 ──────────────────────────────────────────────
DEFAULT_TOP_K = 5
SIMILARITY_THRESHOLD = 0.55  # 자동 edge 생성 임계값 (v3.2: 0.3→0.55 노이즈 에지 감소)
GRAPH_MAX_HOPS = 2
RRF_K = 18  # Reciprocal Rank Fusion 상수 (tuned 2026-03-08: 60→18, NDCG+12.5%)
GRAPH_BONUS = 0.005  # 복원 (0.364 baseline 시점 값). graph neighbor가 vector rank를 밀어내지 않도록
# v5: edge class별 graph bonus (RRF 합산 시 차등 적용)
GRAPH_BONUS_BY_CLASS: dict[str, float] = {
    "semantic": 0.015,
    "evidence": 0.012,
    "temporal": 0.005,
    "structural": 0.002,
    "operational": 0.0,
}
GRAPH_BONUS_DEFAULT_CLASS = 0.005

# WS-1.2: reasoning graph에서 제외할 operational edge
GRAPH_EXCLUDED_METHODS = {
    "session_anchor", "legacy_unknown", "orphan_repair",
    "co_retrieval", "fallback",
}

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

# v5: read-time relation family mapping (legacy relations -> compact families)
RELATION_FAMILY: dict[str, str] = {
    # causes
    "led_to": "causes", "resulted_in": "causes", "triggered_by": "causes",
    "caused_by": "causes", "causes": "causes",
    # resolves
    "resolved_by": "resolves", "enabled_by": "resolves",
    "blocked_by": "resolves", "prevented_by": "resolves",
    "resolves": "resolves",
    # contains
    "contains": "contains", "part_of": "contains",
    "composed_of": "contains", "assembles": "contains",
    # supports
    "supports": "supports", "reinforces_mutually": "supports",
    "validates": "supports",
    # contradicts
    "contradicts": "contradicts", "refuted_by": "contradicts",
    # abstracts
    "generalizes_to": "abstracts", "abstracted_from": "abstracts",
    "crystallized_into": "abstracts", "abstracts": "abstracts",
    # expresses
    "expressed_as": "expresses", "instantiated_as": "expresses",
    "exemplifies": "expresses", "realizes": "expresses",
    "realized_as": "expresses", "showcases": "expresses",
    "expresses": "expresses",
    # evolves
    "succeeded_by": "evolves", "preceded_by": "evolves",
    "evolved_from": "evolves", "derived_from": "evolves",
    "born_from": "evolves", "extends": "evolves", "evolves": "evolves",
    # mirrors
    "mirrors": "mirrors", "analogous_to": "mirrors",
    "parallel_with": "mirrors", "variation_of": "mirrors",
    "differs_in": "mirrors",
    # influences
    "influenced_by": "influences", "inspired_by": "influences",
    "transfers_to": "influences", "correlated_with": "influences",
    "influences": "influences",
    # governs
    "governed_by": "governs", "governs": "governs",
    "constrains": "governs", "generates": "governs",
    "contextualizes": "governs", "questions": "governs",
    # co_occurs
    "co_retrieved": "co_occurs", "connects_with": "co_occurs",
    "simultaneous_with": "co_occurs", "interpreted_as": "co_occurs",
    "viewed_through": "co_occurs", "co_occurs": "co_occurs",
}

RELATION_FAMILY_WEIGHT: dict[str, float] = {
    "causes": 1.5,
    "resolves": 1.3,
    "supports": 1.2,
    "contradicts": 1.2,
    "abstracts": 1.1,
    "expresses": 1.0,
    "evolves": 1.0,
    "governs": 1.0,
    "mirrors": 0.8,
    "influences": 0.8,
    "contains": 0.7,
    "co_occurs": 0.3,
}

# v5: Edge class 분류 — reasoning graph에서 semantic/evidence만 주력 사용
EDGE_CLASS: dict[str, str] = {
    # semantic — reasoning 핵심 (supports, led_to, governs 등)
    "supports": "semantic", "contradicts": "semantic", "reinforces_mutually": "semantic",
    "led_to": "semantic", "caused_by": "semantic", "triggered_by": "semantic",
    "resulted_in": "semantic", "resolved_by": "semantic", "enabled_by": "semantic",
    "blocked_by": "semantic", "prevented_by": "semantic",
    "generalizes_to": "semantic", "constrains": "semantic", "generates": "semantic",
    "governed_by": "semantic", "governs": "semantic",
    "analogous_to": "semantic", "inspired_by": "semantic", "contextualizes": "semantic",
    "mirrors": "semantic", "influenced_by": "semantic", "transfers_to": "semantic",
    "correlated_with": "semantic", "refuted_by": "semantic",
    "questions": "semantic", "validates": "semantic",
    # evidence — 지식 성장 경로
    "realized_as": "evidence", "crystallized_into": "evidence",
    "abstracted_from": "evidence", "exemplifies": "evidence",
    "expressed_as": "evidence", "instantiated_as": "evidence",
    "derived_from": "evidence", "showcases": "evidence",
    # temporal — 시간/구조
    "succeeded_by": "temporal", "preceded_by": "temporal", "evolved_from": "temporal",
    "assembles": "temporal", "born_from": "temporal",
    "contains": "structural", "part_of": "structural", "extends": "structural",
    "composed_of": "structural",
    # operational — reasoning에서 약하게
    "co_retrieved": "operational", "parallel_with": "operational",
    "connects_with": "operational", "simultaneous_with": "operational",
    "differs_in": "operational", "variation_of": "operational",
    "interpreted_as": "operational", "viewed_through": "operational",
    # v5 families
    "causes": "semantic", "resolves": "semantic", "supports": "semantic",
    "contradicts": "semantic", "governs": "semantic", "mirrors": "semantic",
    "influences": "semantic", "abstracts": "evidence", "expresses": "evidence",
    "evolves": "temporal", "contains": "structural", "co_occurs": "operational",
}
EDGE_CLASS_DEFAULT = "semantic"
# generic reasoning에서 사용할 class (operational 제외)
REASONING_EDGE_CLASSES = {"semantic", "evidence", "temporal", "structural"}
ENRICHMENT_QUALITY_WEIGHT = 0.2   # recall() quality_score 가중치

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
# NOTE: COMPOSITE_WEIGHT_RRF removed (unused)
COMPOSITE_WEIGHT_DECAY = 0.001   # recency bonus (tiebreaker)
COMPOSITE_WEIGHT_IMPORTANCE = 0.001  # layer bonus (tiebreaker)
DECAY_LAMBDA = 0.01           # half-life ~69 days
PROMOTED_MULTIPLIER = 1.5     # reviewed-item boost (promotion_candidate=1)

# ── Conditional Reranker (local GGUF cross-encoder) ─────────
RERANKER_ENABLED = True       # False면 reranker 완전 비활성
RERANKER_WEIGHT = 0.35        # CE score 가중치 (0=RRF only, 1=CE only)
RERANKER_GAP_THRESHOLD = 0.05 # top1-top2 gap이 이 미만이면 rerank 실행
RERANKER_CANDIDATE_MULT = 3   # top_k * N개 후보를 reranker에 전달

# v4: Source quality bonus — 데이터 계층 분리 (ontology-repair 2026-04-09)
# Tier 0 (core): Paul 직접 입력 + validated → 최고 가중치
# Tier 1 (experiential): Claude 대화 중 판단 + checkpoint → 표준
# Tier 2 (automated): save_session + pdr → 낮은 가중치
# Tier 3 (reference): obsidian 벌크 인제스트 → 최저 가중치
SOURCE_BONUS: dict[str, float] = {
    "user": 0.12,          # Paul 직접 입력 (최고 가치)
    "claude": 0.08,        # 대화 중 Claude 판단 (경험적)
    "checkpoint": 0.04,    # checkpoint 추출 (반자동)
    "save_session": -0.02, # 세션 자동 덤프 (저활용)
    "pdr": -0.02,          # PDR 자동 생성 (저활용)
    "obsidian": -0.05,     # 벌크 인제스트 (참조용)
    "hook": -0.04,         # 훅 자동 (미사용)
}
SOURCE_BONUS_DEFAULT = -0.03  # 기타 자동 소스

# Confidence → ranking 반영 (additive)
CONFIDENCE_WEIGHT = 0.05  # final_score += (confidence - 0.5) * CONFIDENCE_WEIGHT
CONTRADICTION_PENALTY = -0.10  # active contradicts edge 있을 때

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

# ── WS-4.1: Maturity Gating ─────────────────────────────────
# 데이터가 준비되지 않은 기능은 자동 비활성

def get_maturity_level() -> int:
    """DB 상태 기반 성숙도 레벨.
    0: bootstrap (core < 20)
    1: growing (20 <= core < 50)
    2: mature (50 <= core < 100)
    3: full (core >= 100)
    """
    try:
        import sqlite3
        from config import DB_PATH
        conn = sqlite3.connect(str(DB_PATH))
        core = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE node_role='knowledge_core' AND status='active'"
        ).fetchone()[0]
        conn.close()
        if core >= 100:
            return 3
        if core >= 50:
            return 2
        if core >= 20:
            return 1
        return 0
    except Exception:
        return 0

MATURITY_GATES = {
    0: {"graph_channel": False, "complex_scoring": False},
    1: {"graph_channel": True, "complex_scoring": False},
    2: {"graph_channel": True, "complex_scoring": True},
    3: {"graph_channel": True, "complex_scoring": True},
}
