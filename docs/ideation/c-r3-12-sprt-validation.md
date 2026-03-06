# 세션 C — R3-12: SPRT 파라미터 검증

> 2026-03-05 | R3 심화 | α=0.05, β=0.2, p1=0.7, p0=0.3 수학 분석

## 1. SPRT 기본 수식

Sequential Probability Ratio Test (Wald, 1945).
각 관찰 후 누적 log-likelihood ratio를 계산해 두 임계값 중 하나를 넘으면 결정.

### 임계값

```
A = log((1-β) / α)  = log(0.80 / 0.05) = log(16.000) =  2.773  ← 승격 임계
B = log(β / (1-α))  = log(0.20 / 0.95) = log(0.2105) = -1.558  ← 기각 임계
```

### 관찰당 LLR

```
score > 0.5  →  LLR = log(p1 / p0)         = log(0.7 / 0.3) =  0.847
score ≤ 0.5  →  LLR = log((1-p1)/(1-p0))  = log(0.3 / 0.7) = -0.847
```

---

## 2. 기대 결정 단계 수 (Wald 근사)

### H₁ (진짜 Signal: P(score>0.5) = p1 = 0.7)

```
기대 LLR per step:
  I₁ = p1 · log(p1/p0) + (1-p1) · log((1-p1)/(1-p0))
     = 0.7 × 0.847 + 0.3 × (-0.847)
     = 0.5929 - 0.2541
     = 0.3388 nats/step

기대 승격 단계:  E[N|H₁] ≈ A / I₁ = 2.773 / 0.3388 ≈ 8.2 steps
기대 기각 단계:  E[N|H₁, rejected] ≈ |B| / I₁ = 1.558 / 0.3388 ≈ 4.6 steps
```

### H₀ (노이즈: P(score>0.5) = p0 = 0.3)

```
기대 LLR per step:
  I₀ = p0 · log(p1/p0) + (1-p0) · log((1-p1)/(1-p0))
     = 0.3 × 0.847 + 0.7 × (-0.847)
     = 0.2541 - 0.5929
     = -0.3388 nats/step

기대 기각 단계:  E[N|H₀] ≈ |B| / |I₀| = 1.558 / 0.3388 ≈ 4.6 steps
기대 승격 단계:  E[N|H₀, promoted] ≈ A / |I₀| = 2.773 / 0.3388 ≈ 8.2 steps
```

### 요약

| 시나리오 | 기대 결정 단계 | 결과 |
|---|---|---|
| 진짜 Signal → 승격 | **~8.2 recalls** | 승격 |
| 진짜 Signal → (오)기각 | ~4.6 recalls | 기각 (β=20% 확률) |
| 노이즈 → 기각 | **~4.6 recalls** | 기각 |
| 노이즈 → (오)승격 | ~8.2 recalls | 승격 (α=5% 확률) |

**실용적 의미**: 최소 5회 관찰 컷오프 + 평균 8회면 결정.
주 1-2회 사용 시 → **4-8주 후 첫 승격 결정 가능**.

---

## 3. 3,230-노드 규모 추정

### 승격 후보 파이프라인

```
전체 노드: 3,230
  └─ Signal 타입 (추정 ~15%): ~485개
        └─ 활성(status=active): ~400개
              └─ score_history 5회 이상: ~50-150개  ← 초기 운영 시 적음
                    └─ 진짜 Pattern-worthy (~20%): ~10-30개
```

### Phase별 기대 승격 수

| 운영 기간 | 5회+ 자격 노드 | 진짜 Signal | 탐지(80%) | 오승격(5%) |
|---|---|---|---|---|
| 1개월 후 | ~20-30 | ~4-6 | **3-5개** | 0-1개 |
| 3개월 후 | ~80-120 | ~16-24 | **13-19개** | 1-3개 |
| 6개월 후 | ~150-200 | ~30-40 | **24-32개** | 2-5개 |

**결론**: 첫 1개월 안에 3-5개의 Signal→Pattern 승격 예상. 과다 승격 위험 낮음.

---

## 4. 민감도 분석 (파라미터 변형)

### 4.1 α 변경 (오경보율)

| α | A = log((1-β)/α) | 오승격 확률 | 승격까지 steps |
|---|---|---|---|
| **0.05** (현재) | 2.773 | 5% | ~8.2 |
| 0.03 | 3.219 | 3% | ~9.5 (+16%) |
| 0.01 | 4.382 | 1% | ~12.9 (+57%) |
| 0.10 | 2.197 | 10% | ~6.5 (-21%) |

### 4.2 β 변경 (누락율 / 검정력 = 1-β)

| β | B = log(β/(1-α)) | 누락 확률 | 기각까지 steps |
|---|---|---|---|
| **0.20** (현재) | -1.558 | 20% | ~4.6 |
| 0.10 | -2.248 | 10% | ~6.6 (+43%) |
| 0.30 | -1.097 | 30% | ~3.2 (-30%) |

### 4.3 p1, p0 변경 (분리도)

| 설정 | I₁ | 승격 steps | 특성 |
|---|---|---|---|
| p1=0.7, p0=0.3 (현재) | 0.339 | ~8.2 | 균형 |
| p1=0.8, p0=0.2 | 0.608 | ~4.6 | 빠른 결정, 높은 분리 요구 |
| p1=0.6, p0=0.4 | 0.082 | ~33.8 | 매우 느림, 잘 안 씀 |
| p1=0.7, p0=0.4 | 0.256 | ~10.8 | 보수적 |

**p1=0.6, p0=0.4는 사실상 작동 불능 수준** → 사용 금지.

---

## 5. 코드 검증 (Python 시뮬레이션)

```python
import math, random

def sprt_simulate(p_true, n_sim=10000,
                  alpha=0.05, beta=0.2, p1=0.7, p0=0.3,
                  min_obs=5, max_obs=50):
    """SPRT 시뮬레이션 — 결정까지 평균 단계 + 오율 계산."""
    A = math.log((1 - beta) / alpha)
    B = math.log(beta / (1 - alpha))
    llr_pos = math.log(p1 / p0)
    llr_neg = math.log((1 - p1) / (1 - p0))

    promotes = 0
    rejects = 0
    undecided = 0
    total_steps = []

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

    n = n_sim - undecided
    print(f"p_true={p_true}: promote={promotes/n_sim:.3f}, "
          f"reject={rejects/n_sim:.3f}, undecided={undecided/n_sim:.3f}, "
          f"avg_steps={sum(total_steps)/len(total_steps):.1f}")

# 실행 결과 예측:
sprt_simulate(0.7)   # H₁: promote ~0.80, avg ~8-9 steps
sprt_simulate(0.3)   # H₀: reject ~0.95, avg ~4-5 steps
sprt_simulate(0.5)   # 경계: undecided ~50%+ (많이 남음)
```

### 예상 출력

```
p_true=0.7: promote=0.795, reject=0.110, undecided=0.095, avg_steps=8.7
p_true=0.3: reject=0.950, promote=0.043, undecided=0.007, avg_steps=4.6
p_true=0.5: promote=0.285, reject=0.290, undecided=0.425, avg_steps=12.1
```

---

## 6. 파라미터 조정 가이드

### Phase 1 (1개월): 현재 파라미터 유지

```python
SPRT_ALPHA = 0.05
SPRT_BETA  = 0.20
SPRT_P1    = 0.70
SPRT_P0    = 0.30
SPRT_MIN_OBS = 5
```

**근거**: 새 시스템은 오승격이 더 위험. 보수적 시작.

### Phase 2 (1-3개월): 결과 보고 후 조정

첫 승격 결과를 보고 Paul이 판단:

| 관찰 | 조정 방향 |
|---|---|
| 오승격이 많다 (질 낮은 Pattern) | α=0.03으로 낮추기 |
| 승격이 너무 느리다 | α=0.08로 높이거나 min_obs=3으로 낮추기 |
| 진짜 Pattern인데 기각된다 | β=0.15로 낮춰 검정력 높이기 |
| 0.5 경계 노드가 너무 많다 | p1=0.75, p0=0.25로 분리도 높이기 |

### 절대 금지 파라미터

```python
# 금지: 분리도 너무 낮아 사실상 작동 안 함
p1=0.6, p0=0.4  # I₁=0.082 → avg 34 steps

# 금지: α너무 높아 False Positive 폭발
SPRT_ALPHA = 0.20  # 20% 오승격률

# 금지: min_obs 너무 낮아 노이즈 증폭
SPRT_MIN_OBS = 1  # 1회 관찰로 결정 → 극히 불안정
```

---

## 7. 적용 시 주의사항

### 현재 구현의 SPRT 방식

```python
# c-r3-11 코드에서 선택한 방식:
# 매 recall마다 전체 score_history 재계산 (Wald의 sequential 원본과 동일)
# → 단조 누적이 아닌 "history 전체로 다시 계산"

# 주의: 이는 정확한 SPRT가 아님 (과거 결정을 무시하고 재계산)
# 하지만 history 윈도우(50개)가 있어 오래된 관찰이 희석됨
# 실용적으로는 충분히 근사 가능
```

### 대안: Sliding Window SPRT

max 50개 history 전체로 누적합을 계산하면 window 내에서 "재시작"하는 효과.
완벽한 SPRT가 아니지만:
- 노이즈 노드가 오래전 높은 score로 누적된 경우 최신 데이터가 교정
- max_obs=50 이후 자동으로 최신 50개만 반영

→ **현재 설계 유지 권장**. 실용적 trade-off.

---

## 8. 핵심 수치 요약

| 파라미터 | 값 | 의미 |
|---|---|---|
| α | 0.05 | 노이즈 5%가 Pattern으로 오승격 |
| 1-β (검정력) | 0.80 | 진짜 Signal의 80%를 탐지 |
| 승격 임계 A | 2.773 | 누적 LLR이 이 값 초과 → 승격 |
| 기각 임계 B | -1.558 | 누적 LLR이 이 값 미만 → 기각 |
| 승격 평균 steps | ~8.2 | 진짜 Signal 탐지까지 recall 횟수 |
| 기각 평균 steps | ~4.6 | 노이즈 제거까지 recall 횟수 |
| 최소 관찰 컷오프 | 5 | 5회 미만은 결정 유보 |
