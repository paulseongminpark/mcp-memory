"""L1 goldset 쿼리에 대해 다중 검색 방법으로 후보 생성.

3가지 검색 결과를 병합하여 편향 없는 후보 풀을 만든다:
  (a) hybrid_search — 현재 엔진 그대로
  (b) ChromaDB vector search + type 필터 — 해당 타입 노드만
  (c) FTS 단독 검색

출력: scripts/eval/candidates.yaml — Paul이 정답 선택용으로 리뷰
"""
import sys
import yaml
from pathlib import Path
from collections import OrderedDict

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from storage.hybrid import hybrid_search
from storage.vector_store import search as vec_search
from storage.sqlite_store import search_fts, _db

GOLDSET_PATH = ROOT / "scripts" / "eval" / "goldset.yaml"
OUTPUT_PATH = ROOT / "scripts" / "eval" / "candidates.yaml"

# q051~q075에서 쿼리별 기대 타입 매핑 (notes에서 추출)
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


def load_goldset():
    data = yaml.safe_load(GOLDSET_PATH.read_text(encoding="utf-8"))
    return {q["id"]: q for q in data["queries"]}


def get_node_info(node_ids: list[int]) -> dict[int, dict]:
    """DB에서 노드 메타 정보 조회."""
    if not node_ids:
        return {}
    with _db() as conn:
        placeholders = ",".join("?" * len(node_ids))
        rows = conn.execute(
            f"""SELECT id, type, layer, content, summary, key_concepts
                FROM nodes WHERE id IN ({placeholders})""",
            node_ids,
        ).fetchall()
    return {
        r[0]: {
            "id": r[0],
            "type": r[1],
            "layer": r[2],
            "content": (r[3] or "")[:120],
            "summary": (r[4] or "")[:120],
            "key_concepts": (r[5] or "")[:80],
        }
        for r in rows
    }


def search_candidates(query: str, expected_types: list[str]) -> dict[int, dict]:
    """3가지 방법으로 후보 수집 → 병합."""
    all_ids: OrderedDict[int, str] = OrderedDict()  # id → source

    # (a) hybrid_search top-10
    try:
        hybrid_results = hybrid_search(query, top_k=10)
        for r in hybrid_results:
            nid = r["id"]
            if nid not in all_ids:
                all_ids[nid] = "hybrid"
    except Exception as e:
        print(f"  hybrid_search error: {e}")

    # (b) ChromaDB vector search with type filter — 각 expected type별
    for t in expected_types:
        try:
            vec_results = vec_search(query, top_k=10, where={"type": t})
            for nid, score, meta in vec_results:
                if nid not in all_ids:
                    all_ids[nid] = f"vec:{t}"
        except Exception as e:
            print(f"  vec_search({t}) error: {e}")

    # (c) FTS 단독 검색 top-10
    try:
        fts_results = search_fts(query, top_k=10)
        for nid, content, rank in fts_results:
            if nid not in all_ids:
                all_ids[nid] = "fts"
    except Exception as e:
        print(f"  search_fts error: {e}")

    # 노드 정보 조회
    node_infos = get_node_info(list(all_ids.keys()))
    for nid, source in all_ids.items():
        if nid in node_infos:
            node_infos[nid]["source"] = source
        else:
            node_infos[nid] = {"id": nid, "source": source, "type": "?", "content": "NOT FOUND"}

    return node_infos


def main():
    goldset = load_goldset()
    output = {"version": "1.0", "purpose": "L1 goldset relevant_ids 교정용 후보", "queries": []}

    target_ids = [f"q{i:03d}" for i in range(51, 76)]
    # q026~q050도 포함 (이미 수동 매핑된 것들이지만 검증 목적)
    target_ids = [f"q{i:03d}" for i in range(26, 76)]

    for qid in target_ids:
        if qid not in goldset:
            continue
        q = goldset[qid]
        expected_types = QUERY_TYPES.get(qid, [])
        print(f"\n[{qid}] {q['query'][:50]}... (types: {expected_types})")

        candidates = search_candidates(q["query"], expected_types)
        current_ids = q.get("relevant_ids", []) + q.get("also_relevant", [])

        # 후보 정리
        candidate_list = []
        for nid, info in candidates.items():
            entry = {
                "id": info["id"],
                "type": info.get("type", "?"),
                "layer": info.get("layer", "?"),
                "source": info.get("source", "?"),
                "summary": info.get("summary", "") or info.get("content", "")[:100],
                "current_gold": nid in current_ids,
            }
            candidate_list.append(entry)

        query_entry = {
            "id": qid,
            "query": q["query"],
            "difficulty": q.get("difficulty", ""),
            "notes": q.get("notes", ""),
            "current_relevant_ids": q.get("relevant_ids", []),
            "current_also_relevant": q.get("also_relevant", []),
            "expected_types": expected_types,
            "candidates": candidate_list,
            "total_candidates": len(candidate_list),
        }
        output["queries"].append(query_entry)
        print(f"  → {len(candidate_list)} candidates ({len([c for c in candidate_list if c['current_gold']])} current gold)")

    # YAML 출력
    OUTPUT_PATH.write_text(
        yaml.dump(output, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    print(f"\n{'='*60}")
    print(f"DONE: {len(output['queries'])} queries → {OUTPUT_PATH}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
