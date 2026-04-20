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
    """고도화: 파이프라인 00_index.md + STATE.md에서 현재 작업 맥락 동적 로드."""
    import re
    frame = {'session_id': session_id, 'task_hint': task_hint}
    root = DB_PATH.parent.parent  # data/ → mcp-memory root

    # 활성 파이프라인 00_index.md 파싱
    for idx_path in sorted(root.glob('*/00_index.md'), reverse=True):
        try:
            text = idx_path.read_text(encoding='utf-8')
            if 'status: ACTIVE' not in text:
                continue
            for pat, key in [
                (r'pipeline:\s*([^|]+)', 'pipeline'),
                (r'phase:\s*([^|]+)', 'phase'),
                (r'current_task:\s*([^|]+)', 'current_task'),
                (r'next:\s*([^|]+)', 'next'),
            ]:
                m = re.search(pat, text)
                if m:
                    frame[key] = m.group(1).strip()

            # Decisions 섹션 (최근 5개)
            decisions = []
            in_dec = False
            for line in text.split('\n'):
                if line.startswith('## Decisions'):
                    in_dec = True
                    continue
                if in_dec and line.startswith('## '):
                    break
                if in_dec and line.startswith('- '):
                    decisions.append(line[2:].strip()[:120])
            frame['recent_decisions'] = decisions[-5:]
            break
        except Exception:
            pass

    # 활성 파이프라인의 02_context.md CONFIRMED DECISIONS 전체 로드
    if 'pipeline' in frame:
        for pipeline_dir in sorted(root.glob('*'), reverse=True):
            if not pipeline_dir.is_dir():
                continue
            if frame['pipeline'].replace('-', '_') not in pipeline_dir.name.replace('-', '_'):
                continue
            # 최신 build-r1 또는 현재 phase의 02_context.md
            for ctx_path in sorted(pipeline_dir.glob('*/02_context.md'), reverse=True):
                try:
                    ctx_text = ctx_path.read_text(encoding='utf-8')
                    # CONFIRMED DECISIONS 섹션 추출
                    lines = ctx_text.split('\n')
                    in_confirmed = False
                    confirmed = []
                    for line in lines:
                        if '## CONFIRMED DECISIONS' in line:
                            in_confirmed = True
                            continue
                        if in_confirmed and line.startswith('## ') and 'CONFIRMED' not in line:
                            break
                        if in_confirmed:
                            confirmed.append(line)
                    if confirmed:
                        frame['confirmed_decisions_full'] = '\n'.join(confirmed).strip()

                    # CARRY FORWARD 섹션도 로드
                    in_carry = False
                    carry = []
                    for line in lines:
                        if '## CARRY FORWARD' in line:
                            in_carry = True
                            continue
                        if in_carry and line.startswith('## '):
                            break
                        if in_carry:
                            carry.append(line)
                    if carry:
                        frame['carry_forward'] = '\n'.join(carry).strip()

                    frame['context_source'] = str(ctx_path.relative_to(root))
                    break
                except Exception:
                    pass
            break

    # STATE.md에서 현재 프로젝트 상태 요약
    state_path = root / 'STATE.md'
    if state_path.exists():
        try:
            text = state_path.read_text(encoding='utf-8')
            lines = text.split('\n')
            section = []
            capture = False
            for line in lines:
                if 'Ontology Redesign' in line or 'v8' in line:
                    capture = True
                if capture:
                    section.append(line)
                    if len(section) >= 8:
                        break
                if capture and line.startswith('## ') and 'Ontology' not in line and 'v8' not in line:
                    break
            if section:
                frame['project_state'] = '\n'.join(section[:8])
        except Exception:
            pass

    return frame


def get_relevant_episodes(conn: sqlite3.Connection, limit: int = 5) -> list[dict]:
    """고도화: 최근 Paul 발화 원문 + 세션 요약."""
    episodes = []

    # 최근 Paul 발화 원문 (세션 맥락 핵심)
    rows = conn.execute(
        """
        SELECT content, created_at, session_id FROM captures
        WHERE actor='paul' AND LENGTH(content) > 10
        ORDER BY created_at DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    for r in rows:
        episodes.append({
            'type': 'paul_message',
            'content': (r[0] or '')[:200],
            'at': r[1],
            'session': r[2],
        })

    # 최근 세션 요약 (기존 sessions 테이블)
    sessions = conn.execute(
        """
        SELECT session_id, summary, project FROM sessions
        WHERE summary != '' AND summary IS NOT NULL
        ORDER BY started_at DESC LIMIT 3
        """
    ).fetchall()
    for s in sessions:
        episodes.append({
            'type': 'session_summary',
            'session': s[0],
            'summary': (s[1] or '')[:200],
            'project': s[2],
        })

    return episodes


def get_applicable_principles(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """고도화: verified traits + 프로젝트 최근 결정 + 8차원 균형."""
    result = []

    # 1. 8차원에서 골고루 (차원당 최대 2개, 다양성 확보)
    dims = conn.execute(
        """
        SELECT DISTINCT dimension FROM self_model_traits
        WHERE status='verified' AND approval='approved' AND dimension != 'unclassified'
        """
    ).fetchall()
    for (dim,) in dims:
        rows = conn.execute(
            """
            SELECT id, dimension, content FROM self_model_traits
            WHERE status='verified' AND approval='approved' AND dimension=?
            ORDER BY verified_at DESC LIMIT 2
            """,
            (dim,),
        ).fetchall()
        for r in rows:
            result.append({'trait_id': r[0], 'dimension': r[1], 'content': r[2][:200]})

    # 2. 프로젝트 최근 결정 (Decision 타입 nodes, mcp-memory/ontology/v8 관련)
    decisions = conn.execute(
        """
        SELECT id, content FROM nodes
        WHERE type='Decision' AND status='active'
          AND (content LIKE '%mcp-memory%' OR content LIKE '%ontology%' OR content LIKE '%v8%'
               OR content LIKE '%Phase 0%' OR content LIKE '%redesign%')
        ORDER BY created_at DESC LIMIT 5
        """
    ).fetchall()
    for d in decisions:
        result.append({
            'type': 'project_decision',
            'node_id': d[0],
            'content': (d[1] or '')[:200],
        })

    return result[:limit + 5]  # traits + decisions 합산


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
    # Harden R1 (L): 깨진 JSON 한 개가 전체 pack을 무음 실패시키지 않도록 rule 단위 격리.
    pack_path = POLICY_DIR / 'packs' / f'{pack_name}.json'
    if not pack_path.exists():
        return {'pack': pack_name, 'rules': [], '_errors': []}
    try:
        pack = json.loads(pack_path.read_text(encoding='utf-8'))
    except (ValueError, OSError) as e:
        return {'pack': pack_name, 'rules': [], '_errors': [f'pack_parse: {e}']}
    rules: list[dict] = []
    errors: list[str] = []
    for rule_name in pack.get('rules', []):
        rule_path = POLICY_DIR / 'rules' / f'{rule_name}.json'
        if not rule_path.exists():
            continue
        try:
            rules.append(json.loads(rule_path.read_text(encoding='utf-8')))
        except (ValueError, OSError) as e:
            errors.append(f'{rule_name}: {e}')
    out = {'pack': pack.get('name', pack_name), 'rules': rules}
    if errors:
        out['_errors'] = errors
    return out


def get_open_conflicts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, trait_id, description FROM self_trait_conflicts
        WHERE resolved=0
        LIMIT 5
        """
    ).fetchall()
    return [{'id': r[0], 'trait_id': r[1], 'description': r[2]} for r in rows]


def apply_slot_precedence(pack: dict, active_rejects: set[str], conn: sqlite3.Connection) -> dict:
    """D18 slot precedence — reject + temporal + conflict escalation + open_questions.

    1순위: protected boundary / explicit latest correction
    2순위: approved principle / verified preference
    3순위: current project workflow
    4순위: relevant episodes
    """
    # 1. Reject blacklist
    for slot in ('applicable_principles', 'preferences_and_boundaries'):
        items = pack.get(slot, [])
        pack[slot] = [it for it in items if it.get('trait_id') not in active_rejects]

    # 2. Temporal precedence: latest correction wins (verified_at DESC)
    for slot in ('applicable_principles', 'preferences_and_boundaries'):
        items = pack.get(slot, [])
        trait_items = [it for it in items if it.get('trait_id')]
        non_trait = [it for it in items if not it.get('trait_id')]
        if trait_items:
            trait_ids = [it['trait_id'] for it in trait_items]
            ph = ','.join('?' * len(trait_ids))
            rows = conn.execute(
                f"SELECT id, verified_at FROM self_model_traits WHERE id IN ({ph})",
                trait_ids,
            ).fetchall()
            vmap = {r[0]: r[1] or '' for r in rows}
            trait_items.sort(key=lambda it: vmap.get(it['trait_id'], ''), reverse=True)
        pack[slot] = trait_items + non_trait

    # 3. Conflict escalation: unresolved conflicts for pack traits → open_conflicts
    conflicts = list(pack.get('open_conflicts', []))
    all_trait_ids = [
        it['trait_id']
        for slot in ('applicable_principles', 'preferences_and_boundaries')
        for it in pack.get(slot, []) if it.get('trait_id')
    ]
    if all_trait_ids:
        ph = ','.join('?' * len(all_trait_ids))
        unresolved = conn.execute(
            f"""SELECT id, trait_id, description FROM self_trait_conflicts
            WHERE resolved=0 AND trait_id IN ({ph})""",
            all_trait_ids,
        ).fetchall()
        existing_ids = {c.get('id') for c in conflicts if c.get('id')}
        for row in unresolved:
            if row[0] not in existing_ids:
                conflicts.append({
                    'id': row[0], 'trait_id': row[1],
                    'description': row[2], 'escalated_from': 'slot_precedence',
                })

    # 4. Open questions → context pack (Governance Plane)
    open_q = conn.execute(
        """SELECT id, content FROM nodes
        WHERE type='Question' AND status='active'
        ORDER BY created_at DESC LIMIT 3"""
    ).fetchall()
    for q in open_q:
        conflicts.append({
            'type': 'open_question', 'node_id': q[0],
            'content': (q[1] or '')[:150],
        })

    pack['open_conflicts'] = conflicts
    pack['_precedence'] = [
        'preferences_and_boundaries',
        'applicable_principles',
        'project_workflows',
        'relevant_episodes',
    ]
    return pack


def trim_to_budget(pack: dict, budget: int) -> dict:
    # Harden R1 (P): D18 Slot Precedence — 우선순위 높은 것 먼저 예산 할당, 초과 시 낮은 것 trim.
    # 1순위=boundary, 2순위=principle, 3순위=workflow, 4순위=episode, 5순위=conflict, task_frame=최우선 맥락
    priority_order = [
        'task_frame',
        'preferences_and_boundaries',
        'applicable_principles',
        'open_conflicts',
        'project_workflows',
        'relevant_episodes',
    ]
    # 예산 할당은 우선순위대로, trim은 역순(낮은 것 먼저)
    sizes = {k: _tokens(json.dumps(pack[k], ensure_ascii=False)) for k in priority_order if k in pack}
    total = sum(sizes.values())
    if total <= budget:
        pass  # 전체 수용
    else:
        # 낮은 우선순위부터 trim 하며 예산 내로 축소
        for key in reversed(priority_order):
            if key not in pack:
                continue
            if total <= budget:
                break
            pack[key] = {'_trimmed': True, '_count': len(pack[key]) if isinstance(pack[key], list) else 1}
            total -= sizes[key]
            total += _tokens(json.dumps(pack[key], ensure_ascii=False))
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
    token_budget: int = 12000,
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
        pack = apply_slot_precedence(pack, active_rejects, conn)
        pack = trim_to_budget(pack, token_budget)

        if log_to_db:
            pack_id = uuid_v7()
            slot_dist = {
                k: (len(v) if isinstance(v, list) else 1)
                for k, v in pack.items() if not k.startswith('_')
            }
            # Harden R1 (B): 실제 pack에 들어간 id 수집
            returned: list[str] = []
            for slot_key, slot_val in pack.items():
                if slot_key.startswith('_') or not isinstance(slot_val, list):
                    continue
                for item in slot_val:
                    if not isinstance(item, dict):
                        continue
                    nid = item.get('node_id') or item.get('trait_id') or item.get('id')
                    if nid:
                        returned.append(str(nid))
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
                    json.dumps(returned, ensure_ascii=False),
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
