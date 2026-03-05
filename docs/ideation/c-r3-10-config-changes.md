# c-r3-10: config.py 실제 변경 사항

> Round 3 — 핵심 확정 사항을 코드에 반영

## 변경 내용

### config.py 수정 완료

```python
# 변경 전
RRF_K = 60

# 변경 후
RRF_K = 30  # rank-1 가중치 2배 (1/31 vs 1/61)
RWR_SURPRISE_WEIGHT = 0.05  # k=30 시 RRF 절대값 상승 → weight 절반
LAYER_ETA: dict[int, float] = {
    0: 0.02, 1: 0.015, 2: 0.01, 3: 0.005, 4: 0.001, 5: 0.0001
}
```

## 수학적 효과

| rank | k=60 score | k=30 score | 비율 |
|---|---|---|---|
| 1  | 0.01639 | 0.03226 | 1.97× |
| 5  | 0.01538 | 0.02857 | 1.86× |
| 10 | 0.01408 | 0.02500 | 1.77× |

상위 랭크일수록 k=30의 가중치가 더 크게 증가 → 관련성 높은 결과 집중 강화.

## RWR 연동

k 감소 → RRF 절대 점수 상승 → RWR 보너스의 상대적 영향 증가.
`RWR_SURPRISE_WEIGHT=0.1→0.05`로 균형 유지 (c-r2-9 확인).

hybrid.py에서 `cfg.RWR_SURPRISE_WEIGHT` 참조하도록 추후 수정 필요.

## LAYER_ETA

BCM 구현 시 `cfg.LAYER_ETA[node_layer]`로 직접 참조.
B-1 정본 채택 (c-r2-9 확인).
