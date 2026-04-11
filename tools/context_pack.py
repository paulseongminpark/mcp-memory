#!/usr/bin/env python3
"""
Context Pack Builder — v8 Phase 0 Loop 3 (get_context 재설계)

SoT: 07_ontology-redesign_0410/foundation/workflow.md §Context Pack + principles.md §D18

슬롯 6개 (foundation/workflow.md):
1. task_frame                  현재 프로젝트/작업
2. relevant_episodes           유사 과거 세션 3-5
3. applicable_principles       검증된 Principle + Self Model traits
4. preferences_and_boundaries  Self Model (preference/emotion verified)
5. project_workflows           policy_pack rules
6. open_conflicts              self_trait_conflicts(unresolved) + open_questions

Slot Precedence (D18):
  1순위: protected boundary / explicit latest correction
  2순위: approved principle / verified preference
  3순위: current project workflow
  4순위: relevant episodes

토큰 예산: ~2000.
"""
import json
import sys
import sqlite3
import time
import uuid
import secrets
import argparse
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'data' / 'memory.db'
POLICY_DIR = Path.home() / '.claude' / 'policy'


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


def _tokens(text: str) -> int:
    """대략 토큰 (한국어 1글자 ≈ 0.5 token)."""
    return max(1, len(text) // 2)


def get_task_frame(session_id: str, task_hint: str) -> dict:
    return {
        'session_id': session_id,
        'task_hint': task_hint,
        'project': 'mcp-memory',
        'phase': 'Build R1 Phase 0',
    }


def get_relevant_episodes(conn: sqlite3.Connection, limit: int = 3) -> list[dict]:
    rows = conn.execute(
        """
        SELECT session_id, COUNT(*) AS cnt, MIN(created_at) AS started
        FROM captures
        WHERE session_id != ''
        GROUP BY session_id
        ORDER BY started DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [{'session_id': r[0], 'capture_count': r[1], 'started': r[2]} for r in rows]


def get_applicable_principles(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """verified Self Model traits + Epistemic Plane Principle 노드."""
    rows = conn.execute(
        """
        SELECT id, dimension, content FROM self_model_traits
        WHERE status='verified' AND approval='approved'
        ORDER BY verified_at DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [{'trait_id': r[0], 'dimension': r[1], 'content': r[2]} for r in rows]


def get_preferences_and_boundaries(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, dimension, content FROM self_model_traits
        WHERE status='verified' AND approval='approved'
          AND dimension IN ('preference', 'emotion')
        ORDER BY verified_at DESC LIMIT 8
        """
    ).fetchall()
    return [{'trait_id': r[0], 'dimension': r[1], 'content': r[2]} for r in rows]


def get_policy_pack(pack_name: str = 'default') -> dict:
    pack_path = POLICY_DIR / 'packs' / f'{pack_name}.json'
    if not pack_path.exists():
        return {'pack': pack_name, 'rules': []}
    pack = json.loads(pack_path.read_text(encoding='utf-8'))
    rules = []
    for rule_name in pack.get('rules', []):
        rule_path = POLICY_DIR / 'rules' / f'{rule_name}.json'
        if rule_path.exists():
            rules.append(json.loads(rule_path.read_text(encoding='utf-8')))
    return {'pack': pack.get('name', pack_name), 'rules': rules}


def get_open_conflicts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, trait_id, description FROM self_trait_conflicts
        WHERE resolved=0
        LIMIT 5
        """
    ).fetchall()
    return [{'id': r[0], 'trait_id': r[1], 'description': r[2]} for r in rows]


def apply_slot_precedence(pack: dict, active_rejects: set[str]) -> dict:
    """Phase 0 최소형: rejected trait_id 제외 + 순위 기록."""
    for slot in ('applicable_principles', 'preferences_and_boundaries'):
        items = pack.get(slot, [])
        pack[slot] = [it for it in items if it.get('trait_id') not in active_rejects]
    pack['_precedence'] = [
        'preferences_and_boundaries',
        'applicable_principles',
        'project_workflows',
        'relevant_episodes',
    ]
    return pack


def trim_to_budget(pack: dict, budget: int) -> dict:
    order = [
        'task_frame',
        'preferences_and_boundaries',
        'applicable_principles',
        'project_workflows',
        'open_conflicts',
        'relevant_episodes',
    ]
    total = 0
    for key in order:
        if key not in pack:
            continue
        size = _tokens(json.dumps(pack[key], ensure_ascii=False))
        if total + size > budget:
            pack[key] = {'_trimmed': True, '_count': len(pack[key]) if isinstance(pack[key], list) else 1}
        else:
            total += size
    pack['_estimated_tokens'] = total
    return pack


def get_active_rejects(conn: sqlite3.Connection) -> set[str]:
    """feedback_events에 reject 기록된 trait ids."""
    rows = conn.execute(
        """
        SELECT DISTINCT target_id FROM feedback_events
        WHERE feedback_type='reject' AND target_type='trait'
        """
    ).fetchall()
    return {r[0] for r in rows}


def build_context_pack(
    session_id: str = '',
    task_hint: str = '',
    token_budget: int = 2000,
    log_to_db: bool = True,
) -> dict:
    if not DB_PATH.exists():
        return {'error': 'db missing'}

    conn = sqlite3.connect(str(DB_PATH))
    try:
        active_rejects = get_active_rejects(conn)

        pack = {
            'task_frame': get_task_frame(session_id, task_hint),
            'relevant_episodes': get_relevant_episodes(conn),
            'applicable_principles': get_applicable_principles(conn),
            'preferences_and_boundaries': get_preferences_and_boundaries(conn),
            'project_workflows': get_policy_pack('default'),
            'open_conflicts': get_open_conflicts(conn),
        }
        pack = apply_slot_precedence(pack, active_rejects)
        pack = trim_to_budget(pack, token_budget)

        if log_to_db:
            pack_id = uuid_v7()
            slot_dist = {
                k: (len(v) if isinstance(v, list) else 1)
                for k, v in pack.items() if not k.startswith('_')
            }
            conn.execute(
                """
                INSERT INTO retrieval_logs
                (id, session_id, query, context_pack_id, returned_ids, slot_distribution, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    uuid_v7(),
                    session_id,
                    task_hint,
                    pack_id,
                    json.dumps([]),
                    json.dumps(slot_dist, ensure_ascii=False),
                ),
            )
            conn.commit()
            pack['_pack_id'] = pack_id

        return pack
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--session-id', default='manual-test')
    parser.add_argument('--task-hint', default='')
    parser.add_argument('--budget', type=int, default=2000)
    parser.add_argument('--no-log', action='store_true')
    args = parser.parse_args()

    pack = build_context_pack(
        args.session_id, args.task_hint, args.budget, not args.no_log
    )
    print(json.dumps(pack, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
