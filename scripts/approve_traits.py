#!/usr/bin/env python3
"""
Trait Approval Parser — trait_approval_review.md → self_model_traits 업데이트

SoT: 07_ontology-redesign_0410/30_build-r1/03_impl-plan.md Day 3 Stream B

마킹 규칙:
  - [x] or [X]  → approve (approval='approved', status='verified')
  - [r] or [R]  → reject (status='archived')
  - [ ]          → skip (변경 없음)

id 매칭: 체크박스 다음 줄 "id=XXXXXXXX" (8자 prefix)

사용법:
    cd /c/dev/01_projects/06_mcp-memory
    python scripts/approve_traits.py [--dry-run]
"""
import re
import sys
import sqlite3
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
REVIEW_FILE = ROOT / '07_ontology-redesign_0410' / '30_build-r1' / 'trait_approval_review.md'
DB_PATH = ROOT / 'data' / 'memory.db'

CHECKBOX_RE = re.compile(r'^\s*-\s*\[([xXrR\s])\]\s*(.+)$')
ID_RE = re.compile(r'id=([a-f0-9]{8})')


def parse_review(path: Path) -> list[tuple[str, str, str]]:
    """리턴: [(mark, id_prefix, content_preview), ...]"""
    text = path.read_text(encoding='utf-8')
    lines = text.split('\n')
    results = []
    in_pending = False

    for i, line in enumerate(lines):
        if line.strip().startswith('## Pending Traits'):
            in_pending = True
            continue
        if line.strip().startswith('## 완료 후'):
            in_pending = False
            continue
        if not in_pending:
            continue

        m = CHECKBOX_RE.match(line)
        if not m:
            continue
        raw_mark = m.group(1).strip().lower()
        content = m.group(2).strip()
        if not raw_mark:
            raw_mark = 'skip'

        # 다음 줄에서 id 탐색
        if i + 1 < len(lines):
            id_m = ID_RE.search(lines[i + 1])
            if id_m:
                results.append((raw_mark, id_m.group(1), content[:80]))

    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not REVIEW_FILE.exists():
        print(f"ERROR: review 파일 없음: {REVIEW_FILE}", file=sys.stderr)
        return 1
    if not DB_PATH.exists():
        print(f"ERROR: DB 없음: {DB_PATH}", file=sys.stderr)
        return 1

    results = parse_review(REVIEW_FILE)
    print(f"Parsed {len(results)} trait marking(s) from review file")

    counts = {'x': 0, 'r': 0, 'skip': 0}
    for mark, _, _ in results:
        counts[mark] = counts.get(mark, 0) + 1

    print(f"  approve (x): {counts.get('x', 0)}")
    print(f"  reject  (r): {counts.get('r', 0)}")
    print(f"  skip:        {counts.get('skip', 0)}")
    print()

    if args.dry_run:
        print("(dry-run — DB 변경 없음)")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    approved = rejected = missing = 0

    for mark, id_prefix, content in results:
        like = f'{id_prefix}%'
        if mark == 'x':
            r = cur.execute(
                """
                UPDATE self_model_traits
                SET approval='approved', status='verified',
                    verified_at=datetime('now')
                WHERE id LIKE ? AND status != 'archived'
                """,
                (like,),
            )
            if r.rowcount:
                approved += r.rowcount
            else:
                missing += 1
                print(f"  [MISS] approve id={id_prefix}: {content}")
        elif mark == 'r':
            r = cur.execute(
                """
                UPDATE self_model_traits
                SET status='archived', approval='rejected',
                    metadata=json_set(COALESCE(metadata, '{}'), '$.rejected_at', datetime('now'))
                WHERE id LIKE ? AND status != 'archived'
                """,
                (like,),
            )
            if r.rowcount:
                rejected += r.rowcount
            else:
                missing += 1

    conn.commit()

    # 최종 상태
    verified_total = cur.execute(
        "SELECT COUNT(*) FROM self_model_traits WHERE status='verified' AND approval='approved'"
    ).fetchone()[0]
    active_total = cur.execute(
        "SELECT COUNT(*) FROM self_model_traits WHERE status != 'archived'"
    ).fetchone()[0]

    print(f"\n{'=' * 50}")
    print(f"DB Updated: {approved} approved, {rejected} rejected, {missing} missing")
    print(f"Verified total: {verified_total}")
    print(f"Active total:   {active_total}")
    target = "✅" if verified_total >= 20 else f"❌ {20 - verified_total} more"
    print(f"Exit 3 verified ≥ 20: {target}")
    print(f"{'=' * 50}")

    conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
