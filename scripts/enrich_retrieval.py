#!/usr/bin/env python3
"""retrieval_queries + atomic_claims enrichment — 실시간 진행 표시.

PowerShell에서 직접 실행:
  python scripts\enrich_retrieval.py
"""
import sys, os, sqlite3, json, time, re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from config import OPENAI_API_KEY
from openai import OpenAI

client = OpenAI(api_key=OPENAI_API_KEY, timeout=60.0)
DB = os.path.join(ROOT, "data", "memory.db")

BATCH_SIZE = 10
MAX_RETRIES = 5


def get_remaining():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, type, content, summary, key_concepts, project
        FROM nodes WHERE status='active'
          AND (retrieval_queries IS NULL OR retrieval_queries = '')
        ORDER BY id
    """).fetchall()
    conn.close()
    return rows


def parse_json_response(raw):
    """여러 방법으로 JSON 추출 시도."""
    text = raw.strip()

    # 1. 마크다운 코드블록 제거
    if '```' in text:
        match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    # 2. 직접 파싱
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. [ ] 범위 추출
    start = raw.find('[')
    end = raw.rfind(']') + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass

    return None


def process_batch(batch):
    nodes_text = ""
    for j, node in enumerate(batch):
        content = (node['content'] or '')[:200]
        summary = node['summary'] or ''
        nodes_text += (
            f"\n---{j+1}---\n"
            f"ID:{node['id']} Type:{node['type']} Project:{node['project'] or 'system'}\n"
            f"Summary:{summary}\nContent:{content}\n"
        )

    prompt = (
        f"각 노드에 대해:\n"
        f"1. retrieval_queries: 이 노드를 찾을 질문 3개 (한국어)\n"
        f"2. atomic_claims: 핵심 사실 2개 (한국어, 1문장)\n"
        f"{nodes_text}\n"
        f'반드시 JSON array만 출력. 마크다운/설명 없이:\n'
        f'[{{"id":N,"retrieval_queries":["q1","q2","q3"],"atomic_claims":["c1","c2"]}}]'
    )

    resp = client.chat.completions.create(
        model="gpt-4.1",
        max_tokens=1500,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = resp.choices[0].message.content
    results = parse_json_response(raw)
    if results is None:
        raise ValueError(f"JSON parse failed: {raw[:80]}")
    return results


def main():
    rows = get_remaining()
    total_remaining = len(rows)
    total_all = sqlite3.connect(DB).execute(
        "SELECT COUNT(*) FROM nodes WHERE status='active'"
    ).fetchone()[0]

    already_done = total_all - total_remaining
    print(f"=== Retrieval Enrichment (gpt-4.1) ===")
    print(f"Total: {total_all} | Done: {already_done} | Remaining: {total_remaining}")
    print(f"Batch: {BATCH_SIZE} | Calls: {(total_remaining + BATCH_SIZE - 1) // BATCH_SIZE}")
    print()

    processed = 0
    errors = 0
    start_time = time.time()

    conn = sqlite3.connect(DB)

    for i in range(0, total_remaining, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        success = False

        for attempt in range(MAX_RETRIES):
            try:
                results = process_batch(batch)

                for result in results:
                    nid = result.get('id')
                    rq = result.get('retrieval_queries', [])
                    ac = result.get('atomic_claims', [])
                    if nid and (rq or ac):
                        conn.execute(
                            "UPDATE nodes SET retrieval_queries=?, atomic_claims=? WHERE id=?",
                            (json.dumps(rq, ensure_ascii=False),
                             json.dumps(ac, ensure_ascii=False), nid)
                        )
                        processed += 1

                conn.commit()
                success = True
                break

            except Exception as e:
                err = str(e)
                if '429' in err or 'rate' in err.lower():
                    wait = 15 * (attempt + 1)
                    print(f"\n  rate limit — {wait}s...", flush=True)
                    time.sleep(wait)
                elif 'timeout' in err.lower() or 'ssl' in err.lower() or 'connection' in err.lower():
                    wait = 5 * (attempt + 1)
                    print(f"\n  network error — retry {attempt+1}/{MAX_RETRIES} in {wait}s", flush=True)
                    time.sleep(wait)
                elif 'JSON' in err or 'json' in err:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2)
                    else:
                        print(f"\n  JSON fail after {MAX_RETRIES} attempts, skipping batch", flush=True)
                        break
                else:
                    print(f"\n  Error: {err[:80]}", flush=True)
                    break

        if not success:
            errors += len(batch)

        # Progress
        done = already_done + processed
        pct = done * 100 / total_all
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        eta = (total_remaining - i - BATCH_SIZE) / rate / 60 if rate > 0 else 0
        print(
            f"\r  [{done}/{total_all}] {pct:.1f}% | "
            f"+{processed} ok, {errors} err | "
            f"{rate:.1f}/s | ETA {eta:.0f}min   ",
            end="", flush=True
        )

    conn.close()

    print(f"\n\nDone: +{processed} enriched, {errors} errors")
    print(f"Total fill: {already_done + processed}/{total_all}")


if __name__ == "__main__":
    main()
