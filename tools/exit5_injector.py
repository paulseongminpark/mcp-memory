#!/usr/bin/env python3
"""
Exit 5 Injector — Day 6 "의도적 잘못된 trait 주입 → reject → 24h 내 제외" 검증

SoT: 07_ontology-redesign_0410/30_build-r1/03_impl-plan.md Day 6 Exit 5

시나리오:
  Step 1: inject  — 잘못된 trait 삽입 (예: "Paul은 이모지 많이 사용을 좋아한다")
  Step 2: reject  — feedback_events에 reject 기록
  Step 3: verify  — 다음 context_pack에 해당 trait 부재 확인 → PASS

사용법:
    python tools/exit5_injector.py inject
    python tools/exit5_injector.py reject
    python tools/exit5_injector.py verify
    python tools/exit5_injector.py all     # 3단계 한 번에
"""
import json
import sys
import sqlite3
import time
import uuid
import secrets
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / 'data' / 'memory.db'
MARKER_FILE = ROOT / '07_ontology-redesign_0410' / '30_build-r1' / 'exit5_marker.json'

BAD_TRAIT = {
    'content': 'Paul은 이모지를 많이 사용하는 것을 좋아한다',
    'dimension': 'preference',
    'reason': 'intentionally wrong - opposite of reality (Exit 5 test)',
}


def uuid_v7() -> str:
    ts_ms = int(time.time() * 1000)
    rand = secrets.token_bytes(10)
    b = (
        ts_ms.to_bytes(6, 'big')
        + bytes([0x70 | (rand[0] & 0x0f)])
        + bytes([rand[1]])
        + bytes([0x80 | (rand[2] & 0x3f)])
        + bytes([rand[3]])
        + rand[4:]
    )
    return str(uuid.UUID(bytes=b))


def cmd_inject(args) -> int:
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    trait_id = uuid_v7()
    cur.execute(
        """
        INSERT INTO self_model_traits
        (id, dimension, content, status, approval, created_at, metadata)
        VALUES (?, ?, ?, 'provisional', 'pending', datetime('now'), ?)
        """,
        (
            trait_id,
            BAD_TRAIT['dimension'],
            BAD_TRAIT['content'],
            json.dumps(
                {'exit5_test': True, 'reason': BAD_TRAIT['reason']},
                ensure_ascii=False,
            ),
        ),
    )
    conn.commit()
    conn.close()

    marker = {
        'trait_id': trait_id,
        'content': BAD_TRAIT['content'],
        'injected_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'stage': 'injected',
    }
    MARKER_FILE.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[inject] trait_id={trait_id}")
    print(f"[inject] content={BAD_TRAIT['content']}")
    print(f"[inject] marker: {MARKER_FILE}")
    return 0


def cmd_reject(args) -> int:
    if not MARKER_FILE.exists():
        print("ERROR: marker 없음 — inject 먼저", file=sys.stderr)
        return 1
    marker = json.loads(MARKER_FILE.read_text(encoding='utf-8'))
    trait_id = marker['trait_id']

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO feedback_events
        (id, target_type, target_id, feedback_type, content, actor, created_at, metadata)
        VALUES (?, 'trait', ?, 'reject', ?, 'paul', datetime('now'), ?)
        """,
        (
            uuid_v7(),
            trait_id,
            'Exit 5 test — intentionally wrong trait, rejecting',
            json.dumps({'exit5_test': True}, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()

    marker['stage'] = 'rejected'
    marker['rejected_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    MARKER_FILE.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[reject] feedback_events reject 기록 for trait_id={trait_id}")
    return 0


def cmd_verify(args) -> int:
    if not MARKER_FILE.exists():
        print("ERROR: marker 없음")
        return 1
    marker = json.loads(MARKER_FILE.read_text(encoding='utf-8'))
    trait_id = marker['trait_id']

    sys.path.insert(0, str(Path(__file__).parent))
    from context_pack import build_context_pack
    pack = build_context_pack(session_id='exit5-verify', log_to_db=False)

    # applicable_principles + preferences_and_boundaries에서 trait_id 확인
    all_items = (
        pack.get('applicable_principles', [])
        + pack.get('preferences_and_boundaries', [])
    )
    found_ids = {
        it.get('trait_id') for it in all_items if isinstance(it, dict)
    }

    present = trait_id in found_ids
    print(f"[verify] trait_id in context_pack: {present}")

    if present:
        print("[verify] ❌ FAIL — 잘못된 trait이 여전히 pack에 포함됨")
        return 1
    else:
        print("[verify] ✅ PASS — 잘못된 trait이 context_pack에서 제외됨")
        marker['stage'] = 'verified_pass'
        marker['verified_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        MARKER_FILE.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding='utf-8')
        return 0


def cmd_all(args) -> int:
    rc = cmd_inject(args)
    if rc:
        return rc
    rc = cmd_reject(args)
    if rc:
        return rc
    return cmd_verify(args)


def main() -> int:
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest='cmd', required=True)
    subs.add_parser('inject')
    subs.add_parser('reject')
    subs.add_parser('verify')
    subs.add_parser('all')
    args = parser.parse_args()

    fn = {
        'inject': cmd_inject,
        'reject': cmd_reject,
        'verify': cmd_verify,
        'all': cmd_all,
    }[args.cmd]
    return fn(args)


if __name__ == '__main__':
    sys.exit(main())
