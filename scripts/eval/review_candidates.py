"""candidates.yaml → 마크다운 리뷰 문서 생성.

각 쿼리별로:
- 현재 gold 노드 표시
- type-filtered 후보 중 현재 gold에 없는 것 표시 (핵심 비교 대상)
- hybrid/fts에서만 나온 후보 중 상위 표시
총 쿼리당 최대 15개로 제한.
"""
import yaml
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from storage.sqlite_store import _db

CANDIDATES_PATH = ROOT / "scripts" / "eval" / "candidates.yaml"
OUTPUT_PATH = ROOT / "scripts" / "eval" / "review.md"


def get_full_node_info(node_ids: list[int]) -> dict[int, dict]:
    if not node_ids:
        return {}
    with _db() as conn:
        ph = ",".join("?" * len(node_ids))
        rows = conn.execute(
            f"""SELECT id, type, layer, content, summary, key_concepts, project
                FROM nodes WHERE id IN ({ph}) AND status='active'""",
            node_ids,
        ).fetchall()
    return {
        r[0]: {
            "id": r[0], "type": r[1], "layer": r[2],
            "content": (r[3] or "")[:150].replace("\n", " "),
            "summary": (r[4] or "")[:150].replace("\n", " "),
            "kc": (r[5] or "")[:80], "project": r[6] or "",
        }
        for r in rows
    }


def main():
    data = yaml.safe_load(CANDIDATES_PATH.read_text(encoding="utf-8"))
    lines = [
        "# Goldset Relevant IDs 리뷰\n",
        "> 각 쿼리별로 현재 gold(G)와 새 후보를 비교.\n",
        "> **pick**: relevant_ids에 넣을 노드를 골라주세요.\n",
        "> **현재 gold가 맞으면 그대로, 아니면 새 후보에서 교체.**\n\n",
        "---\n\n",
    ]

    # q051~q075만 집중
    for q in data["queries"]:
        qid = q["id"]
        qnum = int(qid[1:])
        if qnum < 51:
            continue

        query = q["query"]
        notes = q.get("notes", "")
        current_gold = q.get("current_relevant_ids", [])
        current_also = q.get("current_also_relevant", [])
        expected_types = q.get("expected_types", [])
        candidates = q.get("candidates", [])

        # 모든 관련 노드 ID 수집
        all_ids = set()
        for c in candidates:
            all_ids.add(c["id"])
        for gid in current_gold + current_also:
            all_ids.add(gid)

        # 노드 상세 정보 조회
        infos = get_full_node_info(list(all_ids))

        lines.append(f"## {qid}: {query}\n")
        lines.append(f"**기대 타입**: {', '.join(expected_types)} | **난이도**: {q.get('difficulty', '')} | **notes**: {notes}\n\n")

        # 그룹 1: 현재 gold
        lines.append("### 현재 Gold\n")
        lines.append("| pick | ID | Type | Layer | Source | Summary |\n")
        lines.append("|------|-----|------|-------|--------|----------|\n")
        for gid in current_gold:
            info = infos.get(gid, {})
            desc = info.get("summary", "") or info.get("content", "")[:100]
            lines.append(f"| G | {gid} | {info.get('type', '?')} | {info.get('layer', '?')} | gold | {desc} |\n")
        for gid in current_also:
            info = infos.get(gid, {})
            desc = info.get("summary", "") or info.get("content", "")[:100]
            lines.append(f"| g | {gid} | {info.get('type', '?')} | {info.get('layer', '?')} | also | {desc} |\n")

        # 그룹 2: type-filtered 후보 (현재 gold에 없는 것)
        gold_set = set(current_gold + current_also)
        type_filtered = [c for c in candidates if c["source"].startswith("vec:") and c["id"] not in gold_set]
        other = [c for c in candidates if not c["source"].startswith("vec:") and c["id"] not in gold_set]

        if type_filtered:
            lines.append(f"\n### Type-Filtered 새 후보 ({len(type_filtered)}개)\n")
            lines.append("| pick | ID | Type | Layer | Source | Summary |\n")
            lines.append("|------|-----|------|-------|--------|----------|\n")
            for c in type_filtered[:10]:  # 최대 10개
                info = infos.get(c["id"], {})
                desc = info.get("summary", "") or info.get("content", "")[:100]
                lines.append(f"| ? | {c['id']} | {info.get('type', c.get('type', '?'))} | {info.get('layer', '?')} | {c['source']} | {desc} |\n")

        # 그룹 3: hybrid/fts 후보 중 상위 5개
        if other:
            lines.append(f"\n### 기타 후보 (상위 5개 / 전체 {len(other)}개)\n")
            lines.append("| pick | ID | Type | Layer | Source | Summary |\n")
            lines.append("|------|-----|------|-------|--------|----------|\n")
            for c in other[:5]:
                info = infos.get(c["id"], {})
                desc = info.get("summary", "") or info.get("content", "")[:100]
                lines.append(f"| ? | {c['id']} | {info.get('type', c.get('type', '?'))} | {info.get('layer', '?')} | {c['source']} | {desc} |\n")

        lines.append("\n---\n\n")

    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")
    print(f"DONE: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
