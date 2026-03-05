#!/usr/bin/env python3
"""scripts/calibrate_drift.py — DRIFT_THRESHOLD 기준선 측정.

설계: d-r3-12 (D-12)
사용법:
  python scripts/calibrate_drift.py            # 기본 50개 샘플
  python scripts/calibrate_drift.py --n 100    # 100개 샘플 (API 비용 주의)
  python scripts/calibrate_drift.py --dry-run  # DB 접근만, API 미호출

목적:
  같은 content에 OpenAI 임베딩을 2번 생성 → cosine_similarity 측정.
  → DRIFT_THRESHOLD = mean - 2*stdev (자연 변동의 2sigma 아래)
  OpenAI text-embedding-3: 동일 텍스트 재실행 안정성 ~0.999
  실질적 drift 감지 범위: 0.3-0.7

비용: sample_size당 OpenAI API 2회 호출.
      50개 × $0.00002/1K tokens ≈ $0.01 (무시 가능)
"""
from __future__ import annotations

import argparse
import sqlite3
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "data" / "memory.db"


def measure_embedding_stability(
    sample_size: int = 50,
    dry_run: bool = False,
) -> dict:
    """
    활성 노드 sample_size개를 랜덤 선택.
    summary (또는 content) 텍스트로 임베딩 2회 생성 → cosine_similarity 측정.

    Returns:
        {
          "mean_stability": float,      # 평균 유사도 (이상적으로 ~0.999)
          "stdev": float,               # 표준편차
          "suggested_threshold": float, # mean - 2*stdev
          "current_threshold": float,   # config.py 현재값
          "n_sampled": int,
          "min_sim": float,
          "max_sim": float,
        }
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    nodes = conn.execute(
        "SELECT id, content, summary FROM nodes "
        "WHERE status='active' AND summary IS NOT NULL "
        "ORDER BY RANDOM() LIMIT ?",
        (sample_size,),
    ).fetchall()

    if not nodes:
        conn.close()
        return {"error": "활성 노드(summary 있는)를 찾을 수 없습니다."}

    print(f"샘플 {len(nodes)}개 선택됨.")

    if dry_run:
        conn.close()
        print("[DRY-RUN] API 호출 건너뜀. 실제 측정 없음.")
        return {
            "dry_run": True,
            "n_sampled": len(nodes),
            "note": "dry-run: 실제 임베딩 미생성",
        }

    from storage.vector_store import get_node_embedding
    from storage.embedding import openai_embed
    from utils.similarity import cosine_similarity

    similarities: list[float] = []
    errors = 0

    for i, node in enumerate(nodes):
        text = node["summary"] or node["content"]
        if not text:
            continue

        try:
            # 같은 텍스트로 임베딩 2번 생성 (자연 변동 측정)
            emb1 = openai_embed(text)
            emb2 = openai_embed(text)
            sim = cosine_similarity(emb1, emb2)
            similarities.append(sim)
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  임베딩 오류 (node {node['id']}): {e}")

        if (i + 1) % 10 == 0:
            print(f"  진행: {i + 1}/{len(nodes)}")

    conn.close()

    if not similarities:
        return {"error": "임베딩 생성 실패. API 키 확인 필요."}

    from config import DRIFT_THRESHOLD

    mean = statistics.mean(similarities)
    stdev = statistics.stdev(similarities) if len(similarities) > 1 else 0.0
    suggested = mean - 2 * stdev

    return {
        "mean_stability": round(mean, 6),
        "stdev": round(stdev, 6),
        "suggested_threshold": round(suggested, 6),
        "current_threshold": DRIFT_THRESHOLD,
        "n_sampled": len(similarities),
        "n_errors": errors,
        "min_sim": round(min(similarities), 6),
        "max_sim": round(max(similarities), 6),
    }


def print_report(result: dict) -> None:
    print("\n=== Drift Threshold Calibration Report ===")
    for k, v in result.items():
        print(f"  {k}: {v}")

    if "suggested_threshold" in result and "current_threshold" in result:
        suggested = result["suggested_threshold"]
        current = result["current_threshold"]
        if suggested > current:
            print(f"\n  권장: DRIFT_THRESHOLD를 {current} → {suggested:.3f}로 올릴 것")
        elif suggested < current - 0.1:
            print(f"\n  권장: DRIFT_THRESHOLD를 {current} → {suggested:.3f}로 낮출 것")
        else:
            print(f"\n  현재 threshold({current}) 적절함.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drift threshold calibration")
    parser.add_argument("--n", type=int, default=50, help="샘플 수 (기본 50)")
    parser.add_argument("--dry-run", action="store_true", help="DB 접근만, API 미호출")
    args = parser.parse_args()

    result = measure_embedding_stability(sample_size=args.n, dry_run=args.dry_run)
    print_report(result)
