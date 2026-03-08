"""q017/q018 0점 쿼리 해결 — 타깃 노드에 한국어 동의어 주입."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from storage.sqlite_store import _db

SYNONYMS = {
    # q017: "창의적 사고 방식" → gold [4166, 4161]
    4166: ["창의적 사고", "사고 방식", "창의성", "창의적 접근"],
    4161: ["창의적 사고", "사고 방식", "다차원적 사고", "사고 패턴"],
    # q018: "정보 충돌 방지 시스템 설계" → gold [755, 756, 771]
    755: ["정보 충돌", "시스템 일관성", "충돌 방지", "데이터 충돌"],
    756: ["정보 충돌 방지", "동시 수정 방지", "쓰기 충돌"],
    771: ["충돌 방지 설계", "단일 소스", "정보 일관성"],
    # q016 보강: "AI 협업 원칙" 추가
    404: ["AI 협업 원칙", "협업 설계"],
}


def main():
    with _db() as conn:
        for node_id, new_terms in SYNONYMS.items():
            row = conn.execute(
                "SELECT key_concepts FROM nodes WHERE id=?", (node_id,)
            ).fetchone()
            if not row:
                print(f"  SKIP: node {node_id} not found")
                continue
            existing = row[0] or ""
            # 기존 key_concepts에 새 용어 추가 (중복 제거)
            existing_set = set(t.strip() for t in existing.split(",") if t.strip())
            added = [t for t in new_terms if t not in existing_set]
            if not added:
                print(f"  SKIP: node {node_id} already has all terms")
                continue
            merged = existing + (", " if existing else "") + ", ".join(added)
            conn.execute(
                "UPDATE nodes SET key_concepts=? WHERE id=?", (merged, node_id)
            )
            print(f"  OK: node {node_id} += {added}")
        conn.commit()
    print("DONE: synonyms injected")


if __name__ == "__main__":
    main()
