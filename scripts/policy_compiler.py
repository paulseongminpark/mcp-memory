#!/usr/bin/env python3
"""policy_compiler.py — verified self_model_traits → policy_rules JSON 컴파일.

v8 Phase 0 Loop 3: traits → rules → packs → context_pack → Claude 행동 변화.

사용법:
    python scripts/policy_compiler.py           # 컴파일 + 파일 생성
    python scripts/policy_compiler.py --dry-run # 생성할 규칙만 출력

규칙:
- verified + approved traits만 컴파일
- dimension → rule_type 매핑: preference→prefer, emotion→avoid/prefer, 나머지→do/dont
- 기존 수동 생성 rule (metadata.manual=true)은 덮어쓰지 않음
- default.json pack에 자동 등록
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
import uuid
import secrets
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / 'data' / 'memory.db'
POLICY_DIR = Path.home() / '.claude' / 'policy'
RULES_DIR = POLICY_DIR / 'rules'
PACKS_DIR = POLICY_DIR / 'packs'

# dimension → default rule_type
DIMENSION_RULE_TYPE = {
    'preference': 'prefer',
    'emotion': 'avoid',
    'thinking_style': 'do',
    'decision_style': 'do',
    'language': 'prefer',
    'rhythm': 'do',
    'metacognition': 'do',
    'connection': 'do',
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


def _rule_name(trait_id: str, content: str) -> str:
    """trait content에서 rule 파일명 생성."""
    # 한글/영문에서 키워드 추출 → snake_case
    clean = re.sub(r'[^a-zA-Z가-힣0-9\s]', '', content[:60])
    words = clean.split()[:5]
    name = '_'.join(w.lower() for w in words if w)
    if not name:
        name = f'trait_{trait_id[:8]}'
    return f'auto_{name}'


def _infer_rule_type(dimension: str, content: str) -> str:
    """content에서 부정적 패턴 감지 → dont/avoid, 아니면 dimension 기본값."""
    negative_patterns = ['싫어', '금지', '하지 마', '안 한다', '거부', '불필요', '낭비']
    for pat in negative_patterns:
        if pat in content:
            return 'dont' if dimension not in ('emotion',) else 'avoid'
    return DIMENSION_RULE_TYPE.get(dimension, 'do')


def compile_traits(dry_run: bool = False) -> list[dict]:
    """verified traits → policy rule JSON 파일 생성."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    traits = conn.execute(
        """
        SELECT id, dimension, content, verified_at, metadata
        FROM self_model_traits
        WHERE status='verified' AND approval='approved'
        ORDER BY dimension, verified_at DESC
        """
    ).fetchall()

    conn.close()

    if not traits:
        print("No verified traits to compile.")
        return []

    RULES_DIR.mkdir(parents=True, exist_ok=True)
    PACKS_DIR.mkdir(parents=True, exist_ok=True)

    compiled = []
    for trait in traits:
        name = _rule_name(trait['id'], trait['content'])
        rule_path = RULES_DIR / f'{name}.json'

        # 기존 수동 생성 rule 보호
        if rule_path.exists():
            existing = json.loads(rule_path.read_text(encoding='utf-8'))
            if existing.get('metadata', {}).get('manual'):
                continue

        rule_type = _infer_rule_type(trait['dimension'], trait['content'])

        rule = {
            'id': uuid_v7(),
            'version': 1,
            'name': name,
            'rule_type': rule_type,
            'content': trait['content'],
            'priority': 'standard',
            'trigger': ['session_start'],
            'compiled_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'metadata': {
                'source_trait_id': trait['id'],
                'source_dimension': trait['dimension'],
                'auto_compiled': True,
                'verified_at': trait['verified_at'],
            },
        }

        if dry_run:
            print(f"  [{rule_type:>6}] {name}: {trait['content'][:70]}")
        else:
            rule_path.write_text(
                json.dumps(rule, indent=2, ensure_ascii=False),
                encoding='utf-8',
            )

        compiled.append(rule)

    return compiled


def update_pack(compiled_rules: list[dict]) -> None:
    """default.json pack에 컴파일된 rule 이름 등록."""
    pack_path = PACKS_DIR / 'default.json'
    if pack_path.exists():
        pack = json.loads(pack_path.read_text(encoding='utf-8'))
    else:
        pack = {'id': 'default_v1', 'name': 'Default Context Pack', 'version': 1, 'rules': []}

    existing_rules = set(pack.get('rules', []))
    for rule in compiled_rules:
        existing_rules.add(rule['name'])

    pack['rules'] = sorted(existing_rules)
    pack['compiled_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    pack['version'] = pack.get('version', 0) + 1
    pack['metadata'] = pack.get('metadata', {})
    pack['metadata']['auto_compiled_count'] = len(compiled_rules)
    pack['metadata']['total_rules'] = len(pack['rules'])

    pack_path.write_text(
        json.dumps(pack, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description='Policy compiler: traits → rules')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    print(f"Policy compiler — {'DRY RUN' if args.dry_run else 'LIVE'}")
    compiled = compile_traits(dry_run=args.dry_run)
    print(f"\nCompiled {len(compiled)} rules from verified traits.")

    if not args.dry_run and compiled:
        update_pack(compiled)
        print(f"Updated default.json pack ({len(compiled)} rules added).")

    return 0


if __name__ == '__main__':
    sys.exit(main())
