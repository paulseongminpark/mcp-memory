"""recall() — 3중 하이브리드 검색으로 기억을 검색한다.

Phase 1: mode 파라미터 (B-12), 패치 전환 (B-4), total_recall_count 갱신.
"""

from storage.hybrid import hybrid_search, post_search_learn
from storage import sqlite_store
from config import DEFAULT_TOP_K, PATCH_SATURATION_THRESHOLD, GENERIC_RECALL_EXCLUDE_ROLES

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


    # v4: intent modes — 검색 의도별 필터/부스트 분리
INTENT_MODES = {"generic", "recollection", "troubleshooting", "correction"}
SEARCH_MODES = {"auto", "focus", "dmn"}
GENERIC_EXCLUDED_SOURCE_TYPES = {
    ("pdr", "Narrative"),
    ("pdr", "Observation"),
    ("hook:PreCompact:relay", "Narrative"),
}
TROUBLESHOOTING_EXCLUDED_SOURCE_TYPES = {
    ("pdr", "Narrative"),
    ("hook:PreCompact:relay", "Narrative"),
}


def _resolve_mode(mode: str) -> tuple[str, str]:
    """mode → (search_mode, intent_mode) 분리.

    intent modes는 search_mode=auto로 매핑.
    search modes는 intent_mode=generic으로 매핑.
    """
    if mode in INTENT_MODES:
        return "auto", mode
    if mode in SEARCH_MODES:
        return mode, "generic"
    return "auto", "generic"


def _collect_seed_ids(results: list[dict]) -> list[int]:
    """Collect hidden hybrid-search seed ids from raw results."""
    ordered_ids: list[int] = []
    seen: set[int] = set()
    for result in results:
        for seed_id in result.get("_seed_ids", []):
            if isinstance(seed_id, int) and seed_id not in seen:
                seen.add(seed_id)
                ordered_ids.append(seed_id)
    return ordered_ids


def _apply_intent_filters(results: list[dict], intent: str) -> list[dict]:
    """Intent별 node_role 필터링."""
    if intent == "generic":
        return [
            r for r in results
            if r.get("node_role", "") not in GENERIC_RECALL_EXCLUDE_ROLES
            and (r.get("source", ""), r.get("type", "")) not in GENERIC_EXCLUDED_SOURCE_TYPES
        ]
    if intent == "recollection":
        exclude = {"work_item", "external_noise"}
        return [
            r for r in results
            if r.get("node_role", "") not in exclude
        ]
    if intent == "troubleshooting":
        return [
            r for r in results
            if r.get("node_role", "") != "external_noise"
            and (r.get("source", ""), r.get("type", "")) not in TROUBLESHOOTING_EXCLUDED_SOURCE_TYPES
        ]
    return results


def _dedupe_results_by_id(results: list[dict]) -> list[dict]:
    """Keep highest-ranked occurrence for each node id."""
    seen: set[int] = set()
    unique: list[dict] = []
    for result in results:
        node_id = result.get("id")
        if node_id in seen:
            continue
        seen.add(node_id)
        unique.append(result)
    return unique


def _record_edge_contribution(results: list[dict], seed_ids: list[int]) -> None:
    """Increment frequency for active edges that supported top recall results."""
    if not results or not seed_ids:
        return

    top_ids = [result["id"] for result in results[:5] if result.get("id") is not None]
    if not top_ids:
        return

    try:
        with sqlite_store._db() as conn:
            ph_top = ",".join("?" * len(top_ids))
            ph_seed = ",".join("?" * len(seed_ids))
            conn.execute(
                f"""
                UPDATE edges
                   SET frequency = COALESCE(frequency, 0) + 1
                 WHERE status = 'active'
                   AND ((source_id IN ({ph_seed}) AND target_id IN ({ph_top}))
                    OR  (target_id IN ({ph_seed}) AND source_id IN ({ph_top})))
                """,
                seed_ids + top_ids + seed_ids + top_ids,
            )
            conn.commit()
    except Exception:
        pass


def recall(
    query: str,
    type_filter: str = "",
    project: str = "",
    top_k: int = DEFAULT_TOP_K,
    mode: str = "auto",   # search: "auto"|"focus"|"dmn"  intent: "generic"|"recollection"|"troubleshooting"|"correction"
    mutate: bool = True,
) -> dict:
    """기억 검색.

    mode (search):
      "auto"  — 쿼리 길이로 탐험 계수 자동 결정 (기본)
      "focus" — 강한 연결 우선, 집중 검색
      "dmn"   — 미탐색 연결 우선, 연상 검색

    mode (intent, v4):
      "generic"         — 일반 검색. work_item/session_anchor 억제
      "recollection"    — 세션 회고. session_anchor 포함
      "troubleshooting" — 문제 해결. Failure/Pattern 부스트
      "correction"      — 교정 검색. Correction 최우선, contradicts 포함
    """
    search_mode, intent = _resolve_mode(mode)

    # H1: deprecated type_filter canonicalization
    type_filter = _canonicalize_type_filter(type_filter)

    # v4 troubleshooting: Failure 타입 우선 검색
    if intent == "troubleshooting" and not type_filter:
        # 메인 검색 + Failure 전용 검색 병합
        results_main = hybrid_search(
            query, type_filter=type_filter, project=project,
            top_k=top_k * 3, mode=search_mode,
        )
        results_failure = hybrid_search(
            query, type_filter="Failure", project=project,
            top_k=top_k * 3, mode=search_mode,
        )
        # 병합: Failure 결과에 부스트 (+0.05)
        seen = set()
        results = []
        for r in results_failure:
            r["score"] = r.get("score", 0) + 0.05
            results.append(r)
            seen.add(r["id"])
        for r in results_main:
            if r["id"] not in seen:
                results.append(r)
        results.sort(key=lambda r: r.get("score", 0), reverse=True)
    else:
        # 1차 검색 (overfetch: 후처리 필터 후에도 top_k 확보)
        results = hybrid_search(
            query, type_filter=type_filter, project=project,
            top_k=top_k * 3, mode=search_mode,
        )

    if not results:
        return {"results": [], "count": 0, "message": "No memories found."}

    # v3.2→WS-fix: scoring 단순화 후 score 범위 0.05~0.17. 0.3 threshold 제거.
    # 노이즈 방지는 overfetch + role 필터 + top_k 절단으로 충분.
    if not results:
        return {"results": [], "count": 0, "message": "No memories found."}

    # v4: intent별 node_role 필터링
    results = _apply_intent_filters(results, intent)

    # overfetch 후 필터 완료 → top_k로 절단
    results = results[:top_k]

    # B-4: 패치 전환 (Marginal Value Theorem)
    # project 명시 시 전환 생략 (사용자 의도 존중)
    # top_k < 3 시 포화 판단 불가 → 생략
    if not project and _is_patch_saturated(results):
        dominant = _dominant_project(results)
        alt = hybrid_search(
            query,
            top_k=top_k,
            mode=search_mode,
            excluded_project=dominant,
        )
        alt = _apply_intent_filters(alt, intent)
        # 원본 상위 절반 + 새 패치 결과 절반
        results = results[:top_k // 2] + alt[:top_k - top_k // 2]
        results = _dedupe_results_by_id(results)
        results.sort(key=lambda r: r["score"], reverse=True)
        results = results[:top_k]

    # 학습/통계 write-back 경로는 read-only 평가에서 비활성화 가능
    if mutate:
        # 학습 경로: BCM + SPRT + action_log (검색과 분리)
        post_search_learn(results, query)

    # v4 correction mode: contradicts edge 정보 결과에 주입
    if intent == "correction":
        for r in results:
            contradicts = sqlite_store.get_edges(r["id"])
            contra_info = [
                {"relation": e["relation"], "target_id": e["target_id"],
                 "source_id": e["source_id"]}
                for e in contradicts
                if e.get("relation") == "contradicts" and e.get("status") == "active"
            ]
            if contra_info:
                r["_contradicts"] = contra_info

    # P2-W2-02: Correction top-inject — 사용자 교정 노드 최우선 삽입
    # type_filter 명시 시 Correction 주입 스킵 (필터 의도 존중)
    # v4 correction mode: threshold 낮춤 (0.5→0.3) + 더 많이 주입
    correction_threshold = 0.3 if intent == "correction" else 0.5
    if intent == "correction" and not type_filter:
        corrections_raw = hybrid_search(
            query, type_filter="Correction", project=project, top_k=top_k, mode=search_mode
        )
        corrections_filtered = [c for c in corrections_raw if c.get("score", 0) > correction_threshold]
        if corrections_filtered:
            existing_ids = {r["id"] for r in results}
            corrections_new = [c for c in corrections_filtered if c["id"] not in existing_ids]
            results = (corrections_new + results)[:top_k]

    results = _dedupe_results_by_id(results)

    if mutate:
        _record_edge_contribution(results, _collect_seed_ids(results))

        # total_recall_count 갱신 (통계/UCB 정규화용)
        _increment_recall_count()

        # recall_log 기록 (Gate 1 SWR input)
        _log_recall_results(query, results, intent)

        # v8: retrieval_logs 기록 (Governance Plane)
        _write_retrieval_log(query, results)

    # v3.2: context package — seed별 1홉 이웃을 관계 라벨과 함께 구조화
    formatted = []
    for r in results:
        edges = sqlite_store.get_edges(r["id"])
        # active 에지만, co_retrieved 제외 (노이즈), 최대 5개
        meaningful_edges = [
            e for e in edges
            if e.get("status") == "active" and e.get("relation") != "co_retrieved"
        ][:5]

        context = []
        for e in meaningful_edges:
            neighbor_id = e["target_id"] if e["source_id"] == r["id"] else e["source_id"]
            direction = "→" if e["source_id"] == r["id"] else "←"
            neighbor = sqlite_store.get_node(neighbor_id)
            if neighbor and neighbor.get("status") == "active":
                context.append({
                    "relation": f"{direction}{e['relation']}",
                    "id": neighbor_id,
                    "type": neighbor["type"],
                    "content": (neighbor.get("content") or "")[:100],
                })

        entry = {
            "id": r["id"],
            "type": r["type"],
            "content": r["content"][:200],
            "project": r["project"],
            "tags": r["tags"],
            "score": round(r["score"], 3),
            "created_at": r["created_at"],
            # v3.2: 품질 신호 — Claude가 신뢰도 판단 가능
            "layer": r.get("layer", 1),
            "confidence": round(r.get("confidence") or 0.5, 2),
            "source": r.get("source", ""),
            "quality": round(r.get("quality_score") or 0.0, 2),
            # v3.3: role/status 신호
            "node_role": r.get("node_role", ""),
            "epistemic_status": r.get("epistemic_status", "provisional"),
            "context": context,
        }
        # v4: correction mode — contradicts 정보 포함
        if r.get("_contradicts"):
            entry["contradicts"] = r["_contradicts"]
        formatted.append(entry)

    # v3.2: multi-hop 경로 합성 — 결과 간 인과 체인 감지
    chains = _detect_chains(results)

    response = {
        "results": formatted,
        "count": len(formatted),
        "message": f"Found {len(formatted)} memory(ies) for '{query}'",
    }
    if chains:
        response["chains"] = chains
    return response


# ─── multi-hop chain 감지 (v3.2) ──────────────────────────────────

CAUSAL_RELATIONS = {
    "led_to", "caused_by", "triggered_by", "resulted_in",
    "resolved_by", "realized_as", "crystallized_into",
    "evolved_from", "succeeded_by",
}


def _detect_chains(results: list[dict]) -> list[dict]:
    """결과 노드 간 인과 체인 감지. A→led_to→B→resulted_in→C."""
    if len(results) < 2:
        return []

    id_set = {r["id"] for r in results}
    chains = []

    for r in results:
        edges = sqlite_store.get_edges(r["id"])
        for e in edges:
            if e.get("status") != "active":
                continue
            rel = e.get("relation", "")
            if rel not in CAUSAL_RELATIONS:
                continue
            # 결과 내 다른 노드로의 인과 연결
            other_id = e["target_id"] if e["source_id"] == r["id"] else e["source_id"]
            if other_id in id_set and other_id != r["id"]:
                direction = "→" if e["source_id"] == r["id"] else "←"
                chains.append({
                    "from": r["id"],
                    "to": other_id,
                    "relation": f"{direction}{rel}",
                })

    # 중복 제거 (A→B, B→A 동시 감지 방지)
    seen = set()
    unique = []
    for c in chains:
        key = tuple(sorted([c["from"], c["to"]]))
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return unique


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
    v3.1: sources 컬럼 추가 (Gate 1 source 태깅).
    실패해도 graceful skip.
    """
    import json
    import uuid

    recall_id = uuid.uuid4().hex[:8]
    try:
        with sqlite_store._db() as conn:
            # sources 컬럼 존재 확인 + 없으면 추가 (migration)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(recall_log)").fetchall()}
            if "sources" not in cols:
                conn.execute("ALTER TABLE recall_log ADD COLUMN sources TEXT DEFAULT NULL")

            conn.executemany(
                """INSERT INTO recall_log (query, node_id, rank, score, mode, recall_id, sources)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        query, str(r["id"]), rank, r["score"], mode, recall_id,
                        json.dumps(r.get("_sources", []))
                    )
                    for rank, r in enumerate(results, start=1)
                ],
            )
            conn.commit()
    except Exception:
        pass  # recall_log 미생성 시 graceful skip


def _write_retrieval_log(query: str, results: list[dict]) -> None:
    """v8 retrieval_logs 테이블에 검색 이벤트 기록 (Governance Plane).

    retrieval_logs schema:
      id, session_id, query, context_pack_id, returned_ids,
      slot_distribution, cross_domain, feedback_linked, created_at
    """
    import json
    import uuid

    try:
        returned_ids = [r["id"] for r in results]
        # cross-domain: 결과에 포함된 고유 프로젝트 수
        projects = set(r.get("project", "") for r in results if r.get("project"))
        cross_domain = len(projects) > 1

        # type 분포
        type_dist = {}
        for r in results:
            t = r.get("type", "?")
            type_dist[t] = type_dist.get(t, 0) + 1

        with sqlite_store._db() as conn:
            conn.execute(
                """INSERT INTO retrieval_logs
                   (id, session_id, query, returned_ids, slot_distribution,
                    cross_domain, feedback_linked, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 0, datetime('now'))""",
                (
                    uuid.uuid4().hex,
                    "",  # session_id는 호출자가 알 수 없으면 빈 문자열
                    query[:500],
                    json.dumps(returned_ids),
                    json.dumps(type_dist),
                    1 if cross_domain else 0,
                ),
            )
            conn.commit()
    except Exception:
        pass  # retrieval_logs 실패해도 검색 결과에 영향 없음
