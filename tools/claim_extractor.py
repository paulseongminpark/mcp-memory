#!/usr/bin/env python3
"""
Claim Extractor — captures → claims (v8 Phase 0 Loop 1)

SoT: 07_ontology-redesign_0410/30_build-r1/03_impl-plan.md Day 2 Stream B
프롬프트: prompts/claim_extraction.md (v2 검증됨, 2026-04-12 Day 1)
모델: Qwen2.5-7B-Instruct-Q4_K_M via Ollama (localhost:11434)

사용법:
    # unprocessed captures 10개 처리
    python tools/claim_extractor.py --batch 10

    # 특정 capture만 처리
    python tools/claim_extractor.py --capture-id <uuid>

    # dry-run (INSERT 없이 추출만 확인)
    python tools/claim_extractor.py --batch 5 --dry-run

규칙:
- captures.id ↔ claims.capture_id NOT NULL (불변식 2: shortcut 차단)
- 빈 array 출력 허용 (추출 안 됨은 정상 동작)
- Ollama 타임아웃 60초 (첫 호출은 모델 로딩 때문에 느릴 수 있음)
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

# D19: self-model dimension → epistemic claim_type 매핑
DIMENSION_TO_CLAIM_TYPE = {
    'preference': 'preference',
    'emotion': 'emotion',
    'decision_style': 'decision',
    'thinking_style': 'observation',
    'language': 'observation',
    'rhythm': 'observation',
    'metacognition': 'observation',
    'connection': 'observation',
}

SYSTEM_PROMPT = """Paul의 발화에서 claim들을 추출하세요.

규칙:
1. claim은 "Paul은 ~한다/생각한다/느낀다/선호한다/싫어한다" 형태의 명제입니다
2. 1개 발화에서 여러 claim을 추출할 수 있습니다 (보통 2-5개)
3. 반드시 JSON **array**로 출력합니다 — 단일 object 금지
4. 명확하지 않으면 추출하지 마세요 (빈 array OK)

dimension 후보 (하나 선택):
- thinking_style: 사고 방식, 처리 속도
- preference: 선호/반응
- emotion: 감정 신호
- decision_style: 결정 방식
- language: 언어/표현 패턴
- rhythm: 작업 리듬
- metacognition: 자기 인지/한계 인식
- connection: 관계/연결 방식

출력 스키마:
{"claims": [{"text": "Paul은 ...", "dimension": "...", "confidence": 0.0-1.0}]}"""


def uuid_v7() -> str:
    """UUID v7 (draft RFC 9562)."""
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


def extract_claims(content: str, timeout: int = 60) -> list[dict]:
    """Qwen2.5-7B에 capture content 보내고 claims JSON array 받기."""
    prompt = f'{SYSTEM_PROMPT}\n\n발화: "{content}"\n\nJSON:'

    r = requests.post(
        OLLAMA_URL,
        json={
            'model': MODEL,
            'prompt': prompt,
            'stream': False,
            'format': 'json',
            'options': {'temperature': 0.2},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    response = data.get('response', '{}')
    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        print(f"  [WARN] Qwen JSON parse 실패: {response[:100]}", file=sys.stderr)
        return []
    return result.get('claims', []) if isinstance(result, dict) else []


def process_capture(
    conn: sqlite3.Connection,
    capture_id: str,
    content: str,
    dry_run: bool = False,
) -> int:
    """capture 1건 → claims N건 INSERT. 반환: 삽입된 claim 수."""
    try:
        claims = extract_claims(content)
    except requests.RequestException as e:
        print(f"  [ERROR] Ollama {capture_id[:8]}: {e}", file=sys.stderr)
        return 0

    if not claims:
        # 0-claim도 "처리 완료" 마킹 — LEFT JOIN 재시도 방지
        if not dry_run:
            conn.execute(
                """
                INSERT INTO claims
                (id, capture_id, text, claim_type, confidence, extractor_model,
                 extracted_at, status, metadata)
                VALUES (?, ?, '[no extractable claims]', 'skip', 0, ?, datetime('now'), 'skip', ?)
                """,
                (
                    uuid_v7(),
                    capture_id,
                    MODEL,
                    json.dumps({'extractor_v': 1, 'reason': 'empty_extraction'}, ensure_ascii=False),
                ),
            )
            conn.commit()
        return 0

    inserted = 0
    for c in claims:
        text = c.get('text', '').strip()
        if not text:
            continue

        if dry_run:
            dim = c.get('dimension', '?')
            conf = c.get('confidence', 0)
            print(f"    [DRY] {text[:70]} (dim={dim}, conf={conf})")
            inserted += 1
            continue

        try:
            dimension = c.get('dimension', '')
            claim_type = DIMENSION_TO_CLAIM_TYPE.get(dimension, 'observation')
            conn.execute(
                """
                INSERT INTO claims
                (id, capture_id, text, claim_type, confidence, extractor_model,
                 extracted_at, status, metadata)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), 'provisional', ?)
                """,
                (
                    uuid_v7(),
                    capture_id,
                    text,
                    claim_type,
                    float(c.get('confidence', 0.5)),
                    MODEL,
                    json.dumps({'extractor_v': 1, 'source_dimension': dimension}, ensure_ascii=False),
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError as e:
            print(f"  [ERROR] insert {capture_id[:8]}: {e}", file=sys.stderr)

    if not dry_run:
        conn.commit()
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description='Qwen2.5 claim extractor')
    parser.add_argument('--batch', type=int, default=10,
                        help='한 번에 처리할 unprocessed capture 수')
    parser.add_argument('--capture-id', type=str,
                        help='특정 capture_id만 처리')
    parser.add_argument('--dry-run', action='store_true',
                        help='INSERT 없이 추출 결과만 출력')
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: DB 없음: {DB_PATH}", file=sys.stderr)
        return 1

    # Ollama 생존 확인
    try:
        requests.get('http://localhost:11434/', timeout=3)
    except requests.RequestException:
        print("ERROR: Ollama 서버 미기동 — `ollama serve` 또는 앱 실행", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    try:
        if args.capture_id:
            rows = conn.execute(
                "SELECT id, content FROM captures WHERE id = ?",
                (args.capture_id,),
            ).fetchall()
        else:
            # Unprocessed: captures 중 claims에 매핑 없는 것
            rows = conn.execute(
                """
                SELECT c.id, c.content FROM captures c
                LEFT JOIN claims cl ON cl.capture_id = c.id
                WHERE cl.id IS NULL
                ORDER BY c.created_at DESC
                LIMIT ?
                """,
                (args.batch,),
            ).fetchall()

        if not rows:
            print("Nothing to process.")
            return 0

        print(f"Processing {len(rows)} capture(s)...")
        total = 0
        for cap_id, content in rows:
            print(f"\n  [{cap_id[:8]}] {(content or '')[:70]}")
            n = process_capture(conn, cap_id, content, args.dry_run)
            total += n
            print(f"    → {n} claim(s)")

        mode = '(dry-run)' if args.dry_run else 'inserted'
        print(f"\n{'=' * 40}")
        print(f"Total: {total} claim(s) {mode}")
        print(f"{'=' * 40}")
    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
