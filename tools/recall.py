"""recall() — 3중 하이브리드 검색으로 기억을 검색한다.

Phase 1: mode 파라미터 (B-12), 패치 전환 (B-4), total_recall_count 갱신.
"""

from storage.hybrid import hybrid_search, post_search_learn
from storage import sqlite_store
from config import DEFAULT_TOP_K, PATCH_SATURATION_THRESHOLD

# H1: deprecated 타입 → replaced_by 캐시
_TYPE_CANON_CACHE: dict[str, str] | None = None


def _canonicalize_type_filter(type_filter: str) -> str:
    """H1: deprecated 타입을 v3 타입으로 자동 변환."""
    global _TYPE_CANON_CACHE
    if not type_filter:
        return type_filter

    if _TYPE_CANON_CACHE is None:
        try:
            conn = sqlite_store._connect()
            rows = conn.execute(
                "SELECT name, replaced_by FROM type_defs WHERE status='deprecated' AND replaced_by IS NOT NULL"
            ).fetchall()
            _TYPE_CANON_CACHE = {r[0]: r[1] for r in rows}
            conn.close()
        except Exception:
            _TYPE_CANON_CACHE = {}

    return _TYPE_CANON_CACHE.get(type_filter, type_filter)


def recall(
    query: str,
    type_filter: str = "",
    project: str = "",
    top_k: int = DEFAULT_TOP_K,
    mode: str = "auto",   # "auto" | "focus" | "dmn"
) -> dict:
    """기억 검색.

    mode:
      "auto"  — 쿼리 길이로 탐험 계수 자동 결정 (기본)
      "focus" — 강한 연결 우선 (UCB_C_FOCUS=0.3), 집중 검색
      "dmn"   — 미탐색 연결 우선 (UCB_C_DMN=2.5), 연상 검색
    """
    # H1: deprecated type_filter canonicalization
    type_filter = _canonicalize_type_filter(type_filter)

    # 1차 검색
    results = hybrid_search(
        query,
        type_filter=type_filter,
        project=project,
        top_k=top_k,
        mode=mode,
    )

    if not results:
        return {"results": [], "message": "No memories found."}

    # B-4: 패치 전환 (Marginal Value Theorem)
    # project 명시 시 전환 생략 (사용자 의도 존중)
    # top_k < 3 시 포화 판단 불가 → 생략
    if not project and _is_patch_saturated(results):
        dominant = _dominant_project(results)
        alt = hybrid_search(
            query,
            top_k=top_k,
            mode=mode,
            excluded_project=dominant,
        )
        # 원본 상위 절반 + 새 패치 결과 절반
        results = results[:top_k // 2] + alt[:top_k - top_k // 2]
        results.sort(key=lambda r: r["score"], reverse=True)

    # 학습 경로: BCM + SPRT + action_log (검색과 분리)
    post_search_learn(results, query)

    # P2-W2-02: Correction top-inject — 사용자 교정 노드 최우선 삽입
    # type_filter 명시 시 Correction 주입 스킵 (필터 의도 존중)
    if not type_filter:
        corrections_raw = hybrid_search(
            query, type_filter="Correction", project=project, top_k=top_k, mode=mode
        )
        corrections_filtered = [c for c in corrections_raw if c.get("score", 0) > 0.5]
        if corrections_filtered:
            existing_ids = {r["id"] for r in results}
            corrections_new = [c for c in corrections_filtered if c["id"] not in existing_ids]
            results = (corrections_new + results)[:top_k]

    # total_recall_count 갱신 (통계/UCB 정규화용)
    _increment_recall_count()

    # recall_log 기록 (Gate 1 SWR input)
    _log_recall_results(query, results, mode)

    # 포매팅 (기존 로직 유지)
    formatted = []
    for r in results:
        edges = sqlite_store.get_edges(r["id"])
        related = [
            f"{e['relation']}→#{e['target_id'] if e['source_id'] == r['id'] else e['source_id']}"
            for e in edges[:3]
        ]
        formatted.append({
            "id": r["id"],
            "type": r["type"],
            "content": r["content"][:200],
            "project": r["project"],
            "tags": r["tags"],
            "score": round(r["score"], 3),
            "created_at": r["created_at"],
            "related": related,
        })

    return {
        "results": formatted,
        "count": len(formatted),
        "message": f"Found {len(formatted)} memory(ies) for '{query}'",
    }


# ─── 패치 전환 헬퍼 (B-4) ─────────────────────────────────────────

def _is_patch_saturated(results: list[dict]) -> bool:
    """75% 이상이 동일 project → 패치 포화 판정.

    results < 3 → False (포화 판단 불충분).
    "" (빈 project) 노드는 포화 계산에 포함됨 — 개선 여지 있음.
    """
    if len(results) < 3:
        return False
    projects = [r.get("project", "") for r in results]
    dominant = max(set(projects), key=projects.count)
    return projects.count(dominant) / len(projects) >= PATCH_SATURATION_THRESHOLD


def _dominant_project(results: list[dict]) -> str:
    """가장 많이 등장한 project 반환."""
    projects = [r.get("project", "") for r in results]
    return max(set(projects), key=projects.count)


# ─── 통계 카운터 ─────────────────────────────────────────────────

def _increment_recall_count():
    """total_recall_count 증가 (stats 테이블 UPSERT).

    stats 테이블 미존재 시 graceful skip.
    향후 UCB 정규화, 사용 패턴 분석에 활용.
    """
    try:
        with sqlite_store._db() as conn:
            conn.execute("""
                INSERT INTO meta(key, value, updated_at)
                    VALUES('total_recall_count', '1', datetime('now'))
                ON CONFLICT(key) DO UPDATE SET
                    value = CAST(CAST(value AS INTEGER) + 1 AS TEXT),
                    updated_at = datetime('now')
            """)
            conn.commit()
    except Exception:
        pass  # meta 테이블 미생성 시 graceful skip


def _log_recall_results(query: str, results: list[dict], mode: str) -> None:
    """recall_log 테이블에 검색 결과 기록 (Gate 1 SWR input).

    v3: recall_id로 세션 식별 (H2).
    실패해도 graceful skip.
    """
    import uuid

    recall_id = uuid.uuid4().hex[:8]
    try:
        with sqlite_store._db() as conn:
            conn.executemany(
                """INSERT INTO recall_log (query, node_id, rank, score, mode, recall_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (query, str(r["id"]), rank, r["score"], mode, recall_id)
                    for rank, r in enumerate(results, start=1)
                ],
            )
            conn.commit()
    except Exception:
        pass  # recall_log 미생성 시 graceful skip
