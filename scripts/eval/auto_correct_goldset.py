"""Goldset relevant_ids 자동 교정 — type-filtered 벡터 검색 기반.

q051~q075에 대해:
1. 현재 gold가 expected type과 매치하는지 확인
2. 불일치 시 type-filtered 벡터 검색 상위 3개로 교체 추천
3. 교정 전후 비교 테이블 출력
"""
import sys
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from storage.vector_store import search as vec_search
from storage.sqlite_store import _db

GOLDSET_PATH = ROOT / "scripts" / "eval" / "goldset.yaml"
OUTPUT_PATH = ROOT / "scripts" / "eval" / "goldset_corrected.yaml"

QUERY_TYPES = {
    "q051": ["Workflow"],
    "q052": ["Workflow"],
    "q053": ["Agent", "Workflow"],
    "q054": ["Agent"],
    "q055": ["Skill"],
    "q056": ["Skill", "Tool"],
    "q057": ["Project"],
    "q058": ["Tool"],
    "q059": ["Pattern"],
    "q060": ["Framework"],
    "q061": ["Narrative"],
    "q062": ["Connection"],
    "q063": ["Pattern", "Framework"],
    "q064": ["Pattern", "Framework"],
    "q065": ["Failure"],
    "q066": ["Failure"],
    "q067": ["Failure", "Experiment"],
    "q068": ["Experiment"],
    "q069": ["Experiment"],
    "q070": ["Evolution"],
    "q071": ["Evolution"],
    "q072": ["Decision"],
    "q073": ["Decision", "Framework"],
    "q074": ["Goal"],
    "q075": ["Signal"],
}


def get_node_types(node_ids: list[int]) -> dict[int, str]:
    if not node_ids:
        return {}
    with _db() as conn:
        ph = ",".join("?" * len(node_ids))
        rows = conn.execute(
            f"SELECT id, type FROM nodes WHERE id IN ({ph})", node_ids
        ).fetchall()
    return {r[0]: r[1] for r in rows}


def get_node_summary(node_ids: list[int]) -> dict[int, str]:
    if not node_ids:
        return {}
    with _db() as conn:
        ph = ",".join("?" * len(node_ids))
        rows = conn.execute(
            f"SELECT id, type, layer, summary, content FROM nodes WHERE id IN ({ph})",
            node_ids,
        ).fetchall()
    result = {}
    for r in rows:
        desc = (r[3] or r[4] or "")[:100].replace("\n", " ")
        result[r[0]] = f"[{r[1]}|L{r[2]}] {desc}"
    return result


def find_best_candidates(query: str, expected_types: list[str], top_k: int = 3) -> list[int]:
    """type-filtered 벡터 검색으로 최적 후보 찾기."""
    candidates = []
    seen = set()
    for t in expected_types:
        try:
            results = vec_search(query, top_k=top_k * 2, where={"type": t})
            for nid, score, meta in results:
                if nid not in seen:
                    candidates.append((nid, score))
                    seen.add(nid)
        except Exception:
            pass

    # 코사인 유사도 순 정렬 (vec_search는 거리 반환, 낮을수록 가까움)
    candidates.sort(key=lambda x: x[1])
    return [c[0] for c in candidates[:top_k]]


def main():
    data = yaml.safe_load(GOLDSET_PATH.read_text(encoding="utf-8"))
    queries = {q["id"]: q for q in data["queries"]}

    corrections = []
    unchanged = []

    print("=" * 80)
    print("GOLDSET RELEVANT_IDS 교정 리포트")
    print("=" * 80)

    for qid in sorted(QUERY_TYPES.keys()):
        if qid not in queries:
            continue
        q = queries[qid]
        expected_types = QUERY_TYPES[qid]
        current_ids = q.get("relevant_ids", [])
        current_also = q.get("also_relevant", [])

        # 현재 gold 타입 확인
        current_types = get_node_types(current_ids)
        type_match_count = sum(
            1 for nid in current_ids
            if current_types.get(nid, "") in expected_types
        )

        # 교정 필요 여부 판단
        needs_correction = type_match_count < len(current_ids) * 0.5  # 50% 미만 매치

        if needs_correction:
            new_ids = find_best_candidates(q["query"], expected_types, top_k=3)
            new_summaries = get_node_summary(new_ids)
            old_summaries = get_node_summary(current_ids)

            # also_relevant에 현재 gold 이동 (정보 보존)
            new_also = list(set(current_ids + current_also))
            # 새 gold에서 also 제거
            new_also = [x for x in new_also if x not in new_ids]

            corrections.append({
                "qid": qid,
                "query": q["query"][:60],
                "expected_types": expected_types,
                "old_ids": current_ids,
                "new_ids": new_ids,
                "old_summaries": old_summaries,
                "new_summaries": new_summaries,
            })

            # goldset 업데이트
            q["relevant_ids"] = new_ids
            q["also_relevant"] = new_also

            print(f"\n[CORRECT] {qid}: {q['query'][:50]}...")
            print(f"  기대 타입: {expected_types}")
            print(f"  OLD gold ({type_match_count}/{len(current_ids)} 매치):")
            for nid in current_ids:
                print(f"    {nid}: {old_summaries.get(nid, '?')}")
            print(f"  NEW gold:")
            for nid in new_ids:
                print(f"    {nid}: {new_summaries.get(nid, '?')}")
        else:
            unchanged.append(qid)
            print(f"\n[OK] {qid}: {type_match_count}/{len(current_ids)} 매치 — 유지")

    # 교정된 goldset 저장
    data["queries"] = list(queries.values())
    data["version"] = "2.1"
    data["correction_note"] = "q051-q075 relevant_ids를 type-filtered 벡터 검색으로 교정"

    OUTPUT_PATH.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    print(f"\n{'=' * 80}")
    print(f"교정: {len(corrections)}건, 유지: {len(unchanged)}건")
    print(f"교정된 goldset: {OUTPUT_PATH}")
    print(f"{'=' * 80}")

    # 간단 요약 테이블
    if corrections:
        print(f"\n{'─' * 80}")
        print("교정 요약 (Paul 확인용):")
        print(f"{'─' * 80}")
        for c in corrections:
            print(f"\n{c['qid']}: {c['query']}")
            print(f"  기대: {c['expected_types']}")
            for nid in c["new_ids"]:
                print(f"  → {nid}: {c['new_summaries'].get(nid, '?')}")


if __name__ == "__main__":
    main()
