#!/usr/bin/env python3
"""scripts/sprt_simulate.py — SPRT 파라미터 시뮬레이션 도구.

설계: c-r3-12 (C-12)
사용법:
  python scripts/sprt_simulate.py              # 기본 3가지 시나리오
  python scripts/sprt_simulate.py --p 0.7 0.3 0.5  # 지정 p_true 값
  python scripts/sprt_simulate.py --alpha 0.03 --beta 0.15

파라미터 기본값 (config.py):
  SPRT_ALPHA=0.05, SPRT_BETA=0.20, SPRT_P1=0.70, SPRT_P0=0.30, SPRT_MIN_OBS=5
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def sprt_simulate(
    p_true: float,
    n_sim: int = 10_000,
    alpha: float = 0.05,
    beta: float = 0.20,
    p1: float = 0.70,
    p0: float = 0.30,
    min_obs: int = 5,
    max_obs: int = 50,
) -> dict:
    """
    SPRT 시뮬레이션 — 결정까지 평균 단계 + 오율 계산.

    Args:
        p_true:  실제 관찰 확률 (0.7=진짜 Signal, 0.3=노이즈, 0.5=경계)
        n_sim:   시뮬레이션 횟수
        alpha:   오경보율 (False Positive: 노이즈 → 승격)
        beta:    누락율 (False Negative: Signal → 기각)
        p1:      H₁ 임계 확률 (Signal 기준)
        p0:      H₀ 임계 확률 (노이즈 기준)
        min_obs: 최소 관찰 수 (이전까지 결정 유보)
        max_obs: 최대 관찰 수 (초과 시 undecided)

    Returns:
        {promote_rate, reject_rate, undecided_rate, avg_steps, n_sim}
    """
    A = math.log((1 - beta) / alpha)    # 승격 임계
    B = math.log(beta / (1 - alpha))    # 기각 임계
    llr_pos = math.log(p1 / p0)
    llr_neg = math.log((1 - p1) / (1 - p0))

    promotes = 0
    rejects = 0
    undecided = 0
    total_steps: list[int] = []

    for _ in range(n_sim):
        cum = 0.0
        decided = False
        for step in range(1, max_obs + 1):
            obs = random.random() < p_true
            cum += llr_pos if obs else llr_neg
            if step < min_obs:
                continue  # 최소 관찰 수 미달 → 계속
            if cum >= A:
                promotes += 1
                total_steps.append(step)
                decided = True
                break
            if cum <= B:
                rejects += 1
                total_steps.append(step)
                decided = True
                break
        if not decided:
            undecided += 1

    avg_steps = sum(total_steps) / len(total_steps) if total_steps else 0.0

    return {
        "p_true": p_true,
        "promote_rate": promotes / n_sim,
        "reject_rate": rejects / n_sim,
        "undecided_rate": undecided / n_sim,
        "avg_steps": round(avg_steps, 1),
        "n_sim": n_sim,
    }


def print_report(result: dict) -> None:
    p = result["p_true"]
    print(
        f"p_true={p:.2f}: "
        f"promote={result['promote_rate']:.3f}, "
        f"reject={result['reject_rate']:.3f}, "
        f"undecided={result['undecided_rate']:.3f}, "
        f"avg_steps={result['avg_steps']}"
    )


def print_thresholds(alpha: float, beta: float, p1: float, p0: float) -> None:
    A = math.log((1 - beta) / alpha)
    B = math.log(beta / (1 - alpha))
    llr_pos = math.log(p1 / p0)
    llr_neg = math.log((1 - p1) / (1 - p0))
    print(f"\n=== SPRT Parameters ===")
    print(f"  alpha={alpha}, beta={beta}, p1={p1}, p0={p0}")
    print(f"  A (promote threshold) = {A:.4f}")
    print(f"  B (reject threshold)  = {B:.4f}")
    print(f"  LLR pos = {llr_pos:.4f}, LLR neg = {llr_neg:.4f}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SPRT parameter simulation")
    parser.add_argument(
        "--p",
        type=float,
        nargs="+",
        default=[0.7, 0.3, 0.5],
        metavar="P_TRUE",
        help="p_true values to simulate (default: 0.7 0.3 0.5)",
    )
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--beta", type=float, default=0.20)
    parser.add_argument("--p1", type=float, default=0.70)
    parser.add_argument("--p0", type=float, default=0.30)
    parser.add_argument("--min-obs", type=int, default=5)
    parser.add_argument("--max-obs", type=int, default=50)
    parser.add_argument("--n", type=int, default=10_000, help="시뮬레이션 횟수")
    args = parser.parse_args()

    print_thresholds(args.alpha, args.beta, args.p1, args.p0)
    print("=== Simulation Results ===")
    for p in args.p:
        result = sprt_simulate(
            p_true=p,
            n_sim=args.n,
            alpha=args.alpha,
            beta=args.beta,
            p1=args.p1,
            p0=args.p0,
            min_obs=args.min_obs,
            max_obs=args.max_obs,
        )
        print_report(result)
