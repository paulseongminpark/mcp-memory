"""중복 content 노드 soft-delete (status='deleted')."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from storage.sqlite_store import _db


def main():
    deleted = 0
    with _db() as conn:
        # 동일 content_hash를 가진 노드 그룹 찾기
        groups = conn.execute("""
            SELECT content_hash, GROUP_CONCAT(id) as ids, COUNT(*) as cnt
            FROM nodes
            WHERE content_hash IS NOT NULL AND status='active'
            GROUP BY content_hash
            HAVING cnt > 1
        """).fetchall()
        print(f"Found {len(groups)} duplicate groups")
        for row in groups:
            ids = sorted(int(x) for x in row[1].split(","))
            keep = ids[0]  # 가장 오래된 노드 유지
            remove = ids[1:]
            for rid in remove:
                conn.execute(
                    "UPDATE nodes SET status='deleted' WHERE id=?", (rid,)
                )
                # 해당 노드의 edge도 soft-delete
                conn.execute(
                    "UPDATE edges SET status='deleted' WHERE source_id=? OR target_id=?",
                    (rid, rid),
                )
                deleted += 1
        conn.commit()
    print(f"DONE: {deleted} duplicate nodes soft-deleted")


if __name__ == "__main__":
    main()
