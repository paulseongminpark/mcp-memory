#!/usr/bin/env python3
"""
Exit 1 Runner — Day 6 Blind A/B 20 질문 자동 실행 헬퍼

SoT: 07_ontology-redesign_0410/30_build-r1/exit1_question_set.md
용도: context_pack 주입/비주입 2세션 응답 수집 + Paul blind 평가

사용법:
    # 1. 질문 + pack 상태 미리보기
    python tools/exit1_runner.py preview

    # 2. context_pack 스냅샷 (Day 6 A 세션용)
    python tools/exit1_runner.py snapshot

    # 3. 결과 기록 (수동 입력)
    python tools/exit1_runner.py record --q Q1 --variant A --text "..."

    # 4. Paul blind 평가 파일 생성
    python tools/exit1_runner.py evaluate-template

    # 5. 최종 집계
    python tools/exit1_runner.py tally
"""
import json
import sys
import re
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
QUESTION_FILE = ROOT / '07_ontology-redesign_0410' / '30_build-r1' / 'exit1_question_set.md'
RESULT_FILE = ROOT / '07_ontology-redesign_0410' / '30_build-r1' / 'exit1_results.json'
EVAL_FILE = ROOT / '07_ontology-redesign_0410' / '30_build-r1' / 'exit1_evaluate.md'


def parse_questions() -> list[dict]:
    """exit1_question_set.md에서 Q1-Q20 + 기대 답 파싱."""
    if not QUESTION_FILE.exists():
        return []
    text = QUESTION_FILE.read_text(encoding='utf-8')
    questions = []
    blocks = re.split(r'^### Q(\d+)\s*$', text, flags=re.MULTILINE)
    for i in range(1, len(blocks), 2):
        qnum = f'Q{blocks[i]}'
        body = blocks[i + 1] if i + 1 < len(blocks) else ''
        q_m = re.search(r'\*\*질문\*\*:\s*(.+)', body)
        a_m = re.search(r'\*\*기대 답\*\*:\s*(.+)', body)
        questions.append({
            'q': qnum,
            'question': q_m.group(1).strip() if q_m else '',
            'expected': a_m.group(1).strip() if a_m else '',
        })
    return questions


def cmd_preview(args) -> int:
    qs = parse_questions()
    print(f'Parsed {len(qs)} questions from {QUESTION_FILE.name}')
    for q in qs[:5]:
        print(f"  {q['q']}: {q['question'][:70]}")
    if len(qs) > 5:
        print(f"  ... ({len(qs) - 5} more)")

    # context_pack 상태 확인
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from context_pack import build_context_pack
        pack = build_context_pack(session_id='exit1-preview', log_to_db=False)
        print(f"\nContext pack preview:")
        print(f"  est tokens: {pack.get('_estimated_tokens', '?')}")
        for k in ('applicable_principles', 'preferences_and_boundaries'):
            items = pack.get(k, [])
            n = len(items) if isinstance(items, list) else 0
            print(f"  {k}: {n} items")
    except Exception as e:
        print(f"\n[WARN] context_pack 로드 실패: {e}")
    return 0


def cmd_snapshot(args) -> int:
    """Day 6 A 세션에 주입할 pack 스냅샷 파일 생성."""
    sys.path.insert(0, str(Path(__file__).parent))
    from context_pack import build_context_pack
    pack = build_context_pack(session_id='exit1-day6-A', log_to_db=True)
    snap = ROOT / '07_ontology-redesign_0410' / '30_build-r1' / 'exit1_pack_snapshot.json'
    snap.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Snapshot: {snap}")
    return 0


def cmd_record(args) -> int:
    if RESULT_FILE.exists():
        data = json.loads(RESULT_FILE.read_text(encoding='utf-8'))
    else:
        data = {}
    data.setdefault(args.q, {})[args.variant] = args.text
    RESULT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Recorded {args.q}/{args.variant}")
    return 0


def cmd_evaluate_template(args) -> int:
    qs = parse_questions()
    if not RESULT_FILE.exists():
        print(f"ERROR: {RESULT_FILE} 없음 — record 먼저")
        return 1
    data = json.loads(RESULT_FILE.read_text(encoding='utf-8'))

    lines = ['# Exit 1 Blind Evaluation\n', '> Paul blind — 각 질문에 어느 쪽이 "나를 아는" 답인지 [A]/[B] 마킹\n\n']
    for q in qs:
        qnum = q['q']
        entry = data.get(qnum, {})
        if 'A' not in entry or 'B' not in entry:
            continue
        lines.append(f"## {qnum}: {q['question']}\n\n")
        lines.append(f"**기대 답**: {q['expected']}\n\n")
        lines.append(f"**응답 X**:\n```\n{entry['A']}\n```\n\n")
        lines.append(f"**응답 Y**:\n```\n{entry['B']}\n```\n\n")
        lines.append(f"**선택**: [ ] X  [ ] Y\n\n---\n\n")

    EVAL_FILE.write_text(''.join(lines), encoding='utf-8')
    print(f"Evaluation template: {EVAL_FILE}")
    return 0


def cmd_tally(args) -> int:
    if not EVAL_FILE.exists():
        print(f"ERROR: {EVAL_FILE} 없음")
        return 1
    text = EVAL_FILE.read_text(encoding='utf-8')
    x_count = len(re.findall(r'\[x\] X', text, re.IGNORECASE))
    y_count = len(re.findall(r'\[x\] Y', text, re.IGNORECASE))
    total = x_count + y_count
    print(f"X: {x_count}, Y: {y_count}, Total: {total}/20")
    if total >= 14:
        print(f"Exit 1 PASS ✅ ({total}/20 = {total * 5}%)")
    else:
        print(f"Exit 1 FAIL ❌ ({total}/20, 14+ 필요)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest='cmd', required=True)

    subs.add_parser('preview', help='질문/pack 미리보기')
    subs.add_parser('snapshot', help='Day 6 A 세션 pack 스냅샷')

    r = subs.add_parser('record', help='응답 기록')
    r.add_argument('--q', required=True)
    r.add_argument('--variant', choices=['A', 'B'], required=True)
    r.add_argument('--text', required=True)

    subs.add_parser('evaluate-template', help='Paul blind 평가 파일 생성')
    subs.add_parser('tally', help='최종 집계')

    args = parser.parse_args()
    fn = {
        'preview': cmd_preview,
        'snapshot': cmd_snapshot,
        'record': cmd_record,
        'evaluate-template': cmd_evaluate_template,
        'tally': cmd_tally,
    }[args.cmd]
    return fn(args)


if __name__ == '__main__':
    sys.exit(main())
