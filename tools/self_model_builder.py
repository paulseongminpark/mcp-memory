#!/usr/bin/env python3
"""
Self-Model Builder — dimension 분류 + 신규 trait 추출 (v8 Phase 0 Loop 2)

SoT: 07_ontology-redesign_0410/30_build-r1/03_impl-plan.md Day 3 Stream A
모델: Qwen2.5-7B-Instruct-Q4_K_M via Ollama

사용법:
    # classify: 기존 self_model_traits 중 unclassified → 8차원 분류
    python tools/self_model_builder.py classify [--batch 50] [--dry-run]

    # extract: concepts(=nodes) 중 Paul 관련 → 신규 trait 후보 (Day 3 Stream B)
    python tools/self_model_builder.py extract [--limit 20] [--dry-run]

규칙:
- classify는 UPDATE만 (기존 trait 수정)
- extract는 INSERT + self_trait_evidence 자동 생성 (D20 bridge)
- Qwen 실패 시 dimension='unclassified' 유지
- 8차원 외 값은 거부
"""
import json
import sys
import sqlite3
import time
import uuid
import secrets
import argparse
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests 패키지 필요 — pip install requests", file=sys.stderr)
    sys.exit(1)

DB_PATH = Path(__file__).parent.parent / 'data' / 'memory.db'
OLLAMA_URL = 'http://localhost:11434/api/generate'
MODEL = 'qwen2.5:7b-instruct-q4_K_M'

VALID_DIMENSIONS = {
    'thinking_style', 'preference', 'emotion', 'decision_style',
    'language', 'rhythm', 'metacognition', 'connection',
}

CLASSIFY_SYSTEM = """Paul의 특성을 표현한 문장을 다음 8차원 중 하나로 분류하세요.

차원 정의:
- thinking_style: 사고 방식, 처리 속도, 정보 처리 패턴 (예: "느리다", "축 분해", "제약 깨기", "원자 단위 요구")
- preference: 선호/반응 (예: "풍부함 우선", "응답 말미 요약 싫어함", "간결 출력")
- emotion: 감정 신호 (예: "축소 시 보호적 불안", "좌절 패턴", "UI 시각 의도 좌절")
- decision_style: 결정 방식 (예: "확신 시 일괄 승인", "탐색 후 수렴", "양자택일 거부")
- language: 언어/표현 패턴 (예: "ㄱㄱ", "가보자", "DONE/FILES/NEXT")
- rhythm: 작업 리듬 (예: "단일 세션 완주", "마감 시 가속", "멀티세션 안전 규칙")
- metacognition: 자기 인지/한계 인식 (예: "LLM 한계 인정", "갭 명시", "내 속도 한계")
- connection: 관계/연결 방식 (예: "이종 분야 연결", "유추 사고", "AI+삶 수직통합")

출력 스키마:
{"dimension": "<하나>", "confidence": 0.0-1.0, "reason": "분류 근거 한 줄"}

가장 적합한 **하나의** 차원을 선택합니다. 애매하면 confidence를 낮추세요."""


def uuid_v7() -> str:
    ts_ms = int(time.time() * 1000)
    ts_bytes = ts_ms.to_bytes(6, 'big')
    rand = secrets.token_bytes(10)
    b = (
        ts_bytes
        + bytes([0x70 | (rand[0] & 0x0f)])
        + bytes([rand[1]])
        + bytes([0x80 | (rand[2] & 0x3f)])
        + bytes([rand[3]])
        + rand[4:]
    )
    return str(uuid.UUID(bytes=b))


def call_qwen(system: str, user: str, timeout: int = 30) -> dict:
    """Qwen2.5-7B JSON format 호출."""
    prompt = f'{system}\n\n입력: "{user[:600]}"\n\nJSON:'
    r = requests.post(
        OLLAMA_URL,
        json={
            'model': MODEL,
            'prompt': prompt,
            'stream': False,
            'format': 'json',
            'options': {'temperature': 0.1},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    response = r.json().get('response', '{}')
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {}


def cmd_classify(args) -> int:
    if not DB_PATH.exists():
        print(f"ERROR: DB 없음: {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT id, content, metadata FROM self_model_traits
        WHERE dimension='unclassified' AND status != 'archived'
        ORDER BY created_at
        LIMIT ?
        """,
        (args.batch,),
    ).fetchall()

    print(f"Classifying {len(rows)} trait(s)...\n")

    dim_counts: dict[str, int] = {}
    updated = 0
    errors = 0

    for trait_id, content, metadata_json in rows:
        try:
            result = call_qwen(CLASSIFY_SYSTEM, content or '')
        except requests.RequestException as e:
            print(f"  [ERROR] {trait_id[:8]}: {e}", file=sys.stderr)
            errors += 1
            continue

        dim = result.get('dimension', 'unclassified')
        conf = float(result.get('confidence', 0.0))
        reason = result.get('reason', '')

        # 8차원 외 값 거부
        if dim not in VALID_DIMENSIONS:
            dim = 'unclassified'
            conf = 0.0

        short = (content or '').replace('\n', ' ').strip()[:60]
        print(f"  [{trait_id[:8]}] {short}")
        print(f"    → {dim:15s} (conf={conf:.2f}) {reason[:50]}")

        dim_counts[dim] = dim_counts.get(dim, 0) + 1

        if not args.dry_run and dim != 'unclassified':
            try:
                existing = json.loads(metadata_json or '{}')
                existing['dimension_confidence'] = conf
                existing['dimension_reason'] = reason
                existing['classified_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
                existing['classifier_model'] = MODEL
                cur.execute(
                    """
                    UPDATE self_model_traits
                    SET dimension=?, metadata=?
                    WHERE id=?
                    """,
                    (dim, json.dumps(existing, ensure_ascii=False), trait_id),
                )
                updated += 1
            except sqlite3.Error as e:
                print(f"    [UPDATE ERROR] {e}", file=sys.stderr)
                errors += 1

    if not args.dry_run:
        conn.commit()

    print(f"\n{'=' * 50}")
    print('=== Dimension distribution ===')
    for d in sorted(VALID_DIMENSIONS | {'unclassified'}):
        c = dim_counts.get(d, 0)
        mark = '✅' if c >= 3 else ('⚠️' if c > 0 else '❌')
        if d == 'unclassified':
            mark = '⚠️' if c > 0 else '✅'
        print(f"  {mark} {d:15s} {c}")

    mode = '(dry-run)' if args.dry_run else 'updated'
    print(f"\nTotal: {updated} trait(s) {mode}, errors: {errors}")
    print(f"{'=' * 50}")

    conn.close()
    return 0


EXTRACT_SYSTEM = """다음 문서에서 Paul의 특성(trait)을 추출하세요.

규칙:
1. trait은 "Paul은 ~한다/생각한다/느낀다/선호한다/싫어한다" 형태의 명제
2. 문서에서 명시적으로 표현된 Paul의 사고방식/선호/감정/결정스타일/언어/리듬/메타인지/연결 방식 중 하나
3. 0-5개 trait 추출 가능, 명확하지 않으면 추출 금지
4. 부족한 차원(decision_style, metacognition, emotion, connection, rhythm)을 특히 주목

차원 정의:
- thinking_style: 사고 방식, 처리 속도, 정보 처리 패턴
- preference: 선호/반응
- emotion: 감정 신호 (좌절, 불안, 보호 등)
- decision_style: 결정 방식 (확신 시 일괄 승인, 탐색 후 수렴 등)
- language: 언어/표현 패턴
- rhythm: 작업 리듬 (단일 세션 완주, 마감 시 가속 등)
- metacognition: 자기 인지/한계 인식 (LLM 한계 인정, 갭 명시 등)
- connection: 관계/연결 방식 (이종 분야 연결, 유추 사고 등)

출력 스키마:
{"traits": [{"content": "Paul은 ...", "dimension": "...", "confidence": 0.0-1.0, "reason": "근거"}]}"""


def cmd_extract(args) -> int:
    """Paul 관련 concepts(nodes)에서 신규 trait 추출 (Day 3 Stream B)."""
    if not DB_PATH.exists():
        print(f"ERROR: DB 없음: {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Paul 관련 + trait 후보 타입 + 길이 50-800
    rows = cur.execute(
        """
        SELECT id, type, content FROM nodes
        WHERE status='active'
          AND (content LIKE '%Paul%' OR content LIKE '%저는%' OR content LIKE '%나는%' OR content LIKE '% 내가 %')
          AND type IN ('Insight', 'Pattern', 'Principle', 'Observation', 'Decision', 'Failure', 'Experiment', 'Goal', 'Framework')
          AND LENGTH(content) BETWEEN 50 AND 800
        ORDER BY COALESCE(quality_score, 0) DESC, COALESCE(maturity, 0) DESC
        LIMIT ?
        """,
        (args.limit,),
    ).fetchall()

    print(f"Extracting from {len(rows)} concept(s)...\n")

    extracted = 0
    new_by_dim: dict[str, int] = {}
    errors = 0

    for node_id, node_type, content in rows:
        try:
            result = call_qwen(EXTRACT_SYSTEM, content or '', timeout=60)
        except requests.RequestException as e:
            print(f"  [ERROR] node={node_id}: {e}", file=sys.stderr)
            errors += 1
            continue

        traits = result.get('traits', []) if isinstance(result, dict) else []
        if not traits:
            continue

        short = (content or '').replace('\n', ' ')[:60]
        print(f"  [node {node_id}] ({node_type}) {short}")

        for t in traits:
            dim = t.get('dimension', '')
            if dim not in VALID_DIMENSIONS:
                continue
            trait_content = (t.get('content') or '').strip()
            if not trait_content:
                continue
            conf = float(t.get('confidence', 0.5))
            reason = t.get('reason', '')

            print(f"    → {dim:15s} {trait_content[:60]} (conf={conf:.2f})")
            new_by_dim[dim] = new_by_dim.get(dim, 0) + 1

            if args.dry_run:
                extracted += 1
                continue

            trait_id = uuid_v7()
            metadata = {
                'extracted_from_node_id': node_id,
                'source_type': node_type,
                'extraction_model': MODEL,
                'dimension_reason': reason,
                'dimension_confidence': conf,
                'extracted_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            }
            try:
                cur.execute(
                    """
                    INSERT INTO self_model_traits
                    (id, dimension, content, status, approval, created_at, metadata)
                    VALUES (?, ?, ?, 'provisional', 'pending', datetime('now'), ?)
                    """,
                    (trait_id, dim, trait_content,
                     json.dumps(metadata, ensure_ascii=False)),
                )
                # Evidence bridge (legacy concept placeholder — Phase 1 PG 이주 시 정리)
                cur.execute(
                    """
                    INSERT INTO self_trait_evidence
                    (id, trait_id, claim_id, strength, created_at)
                    VALUES (?, ?, ?, ?, datetime('now'))
                    """,
                    (uuid_v7(), trait_id, f'legacy:{node_type}:{node_id}', conf),
                )
                extracted += 1
            except sqlite3.Error as e:
                print(f"    [INSERT ERROR] {e}", file=sys.stderr)
                errors += 1

    if not args.dry_run:
        conn.commit()

    print(f"\n{'=' * 50}")
    print('=== New traits by dimension ===')
    for d in sorted(VALID_DIMENSIONS):
        c = new_by_dim.get(d, 0)
        mark = '✅' if c >= 3 else ('⚠️' if c > 0 else '❌')
        print(f"  {mark} {d:15s} {c}")

    mode = '(dry-run)' if args.dry_run else 'inserted'
    print(f"\nTotal new traits: {extracted} {mode}, errors: {errors}")
    print(f"{'=' * 50}")

    conn.close()
    return 0


def cmd_boost_evidence(args) -> int:
    """각 active trait에 관련 concept를 evidence로 추가 (LIKE 검색 기반).
    목표: avg evidence/trait >= 2 달성.
    """
    if not DB_PATH.exists():
        print(f"ERROR: DB 없음: {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # active traits 중 evidence < target인 것
    traits = cur.execute(
        """
        SELECT * FROM (
            SELECT t.id, t.content, t.dimension,
                   (SELECT COUNT(*) FROM self_trait_evidence e WHERE e.trait_id=t.id) AS ev_count
            FROM self_model_traits t
            WHERE t.status != 'archived'
        )
        WHERE ev_count < ?
        ORDER BY ev_count ASC
        """,
        (args.target,),
    ).fetchall()

    print(f"Boosting {len(traits)} trait(s) to evidence >= {args.target}...\n")

    added_total = 0
    for trait_id, content, dimension, ev_count in traits:
        needed = args.target - ev_count
        if needed <= 0:
            continue

        # trait content에서 키워드 2-3개 추출 (3자 이상 단어)
        words = [w for w in (content or '').split() if len(w) >= 3]
        keywords = words[:3]
        if not keywords:
            continue

        candidates = []
        for kw in keywords:
            like = f'%{kw}%'
            rows = cur.execute(
                """
                SELECT n.id, n.type FROM nodes n
                WHERE n.status='active'
                  AND n.content LIKE ?
                  AND n.type IN ('Insight','Pattern','Principle','Observation','Decision','Framework','Identity')
                  AND LENGTH(n.content) >= 30
                LIMIT ?
                """,
                (like, needed * 2),
            ).fetchall()
            candidates.extend(rows)

        # 중복 제거 + 이미 evidence 있는 것 제외
        existing = {
            r[0] for r in cur.execute(
                "SELECT claim_id FROM self_trait_evidence WHERE trait_id=?",
                (trait_id,),
            ).fetchall()
        }

        seen_concept = set()
        added_this_trait = 0
        for concept_id, concept_type in candidates:
            if added_this_trait >= needed:
                break
            if concept_id in seen_concept:
                continue
            seen_concept.add(concept_id)
            claim_placeholder = f'legacy:{concept_type}:{concept_id}'
            if claim_placeholder in existing:
                continue

            if args.dry_run:
                added_this_trait += 1
                added_total += 1
                continue

            try:
                cur.execute(
                    """
                    INSERT INTO self_trait_evidence
                    (id, trait_id, claim_id, strength, created_at)
                    VALUES (?, ?, ?, ?, datetime('now'))
                    """,
                    (uuid_v7(), trait_id, claim_placeholder, 0.6),
                )
                added_this_trait += 1
                added_total += 1
            except sqlite3.Error as e:
                print(f"  [ERROR] {trait_id[:8]}: {e}", file=sys.stderr)

    if not args.dry_run:
        conn.commit()

    # 최종 통계
    avg = cur.execute(
        """
        SELECT ROUND(CAST(COUNT(e.id) AS REAL) / COUNT(DISTINCT t.id), 2)
        FROM self_model_traits t
        LEFT JOIN self_trait_evidence e ON e.trait_id=t.id
        WHERE t.status != 'archived'
        """
    ).fetchone()[0]

    mode = '(dry-run)' if args.dry_run else 'inserted'
    print(f"\n{'=' * 50}")
    print(f"Total evidences added: {added_total} {mode}")
    print(f"New avg evidence/trait: {avg}")
    print(f"{'=' * 50}")

    conn.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='v8 Self-Model Builder')
    subs = parser.add_subparsers(dest='cmd', required=True)

    c = subs.add_parser('classify', help='기존 traits dimension 분류')
    c.add_argument('--batch', type=int, default=50)
    c.add_argument('--dry-run', action='store_true')

    e = subs.add_parser('extract', help='concepts에서 신규 trait 추출')
    e.add_argument('--limit', type=int, default=20)
    e.add_argument('--dry-run', action='store_true')

    b = subs.add_parser('boost_evidence', help='trait에 관련 concept evidence 추가')
    b.add_argument('--target', type=int, default=2,
                   help='trait당 최소 evidence 목표 (default 2)')
    b.add_argument('--dry-run', action='store_true')

    args = parser.parse_args()

    # Ollama 서버 생존 확인
    try:
        requests.get('http://localhost:11434/', timeout=3)
    except requests.RequestException:
        print("ERROR: Ollama 미기동", file=sys.stderr)
        return 1

    if args.cmd == 'classify':
        return cmd_classify(args)
    elif args.cmd == 'extract':
        return cmd_extract(args)
    elif args.cmd == 'boost_evidence':
        return cmd_boost_evidence(args)
    return 1


if __name__ == '__main__':
    sys.exit(main())
