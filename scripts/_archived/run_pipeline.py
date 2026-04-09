"""온톨로지 완성 파이프라인 — 전체 자동 실행."""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def run(cmd: list, desc: str) -> int:
    print(f"\n{'='*60}")
    print(f"[PHASE] {desc}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"STDERR: {result.stderr}")
        print(f"WARNING: {desc} returned code {result.returncode}")
    return result.returncode


def main() -> int:
    start = time.time()

    # Phase A: 데이터 수정
    run([sys.executable, "scripts/pipeline/inject_synonyms.py"], "동의어 주입")
    run([sys.executable, "scripts/pipeline/cleanup_duplicates.py"], "중복 정리")

    # Phase B: FTS 인덱스 리빌드 (동의어 주입 후 필요)
    run([sys.executable, "-c", """
import sys; sys.path.insert(0, '.')
from storage.sqlite_store import _db
with _db() as conn:
    conn.execute("INSERT INTO nodes_fts(nodes_fts) VALUES('rebuild')")
    conn.commit()
print("FTS index rebuilt")
"""], "FTS 인덱스 리빌드")

    # Phase C: 테스트
    code = run([sys.executable, "-m", "pytest", "tests/", "-x", "-q"], "pytest")
    if code != 0:
        print("ABORT: tests failed")
        return 1

    # Phase D: NDCG 측정
    run([sys.executable, "scripts/eval/ab_test.py", "--k", "18", "--top-k", "10"], "NDCG 측정")

    # Phase E: 검증 시스템 실행
    run([sys.executable, "scripts/eval/verify.py"], "전체 검증")

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE in {elapsed:.1f}s")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
