# 세션 C — PyTorch #9: B세션 정합성 확인

> 2026-03-05 | B-1 BCM / B-2 SWR / B-8 RWR + C-2, C-3, C-4 교차 검증

---

## 1. B-1 LAYER_ETA vs C-2 BCM 파라미터 — 충돌 확인

### B-1 (정본)

```python
LAYER_ETA = {0: 0.02, 1: 0.015, 2: 0.01, 3: 0.005, 4: 0.001, 5: 0.0001}
HISTORY_WINDOW = 20
```
레이어별 차등 η: L0(Obs) 빠른 변화, L5(Value) 거의 고정.

### C-2 (초안)

```python
eta = 0.01  # 단일 스칼라 — 레이어 무관
tau = 0.1   # 임계값 시정수
```

### 판정: **C-2가 B-1로 교체되어야 함**

| 항목 | B-1 (정본) | C-2 (초안) | 결론 |
|---|---|---|---|
| 학습률 η | 레이어별 6단계 | 단일 0.01 | **B-1 채택** |
| 임계값 업데이트 | 슬라이딩 제곱평균 | `nu_theta += tau * (nu_i**2 - nu_theta)` | 동일 (표현만 다름) |
| history 저장 | `activity_history` (window=20) | — | **B-1 추가** |
| 컬럼명 | `θ_m` | `bcm_threshold` | **`θ_m` 통일** |

**수정 후 C-2 적용 파라미터:**
```python
# B-1 정본 그대로 사용
LAYER_ETA = {0: 0.02, 1: 0.015, 2: 0.01, 3: 0.005, 4: 0.001, 5: 0.0001}
HISTORY_WINDOW = 20
# 컬럼: θ_m (REAL), activity_history (TEXT)
```

---

## 2. B-2 SWR readiness → C-3 승격 모델의 "게이트" 역할

### 현재 B-2 설계

```python
swr_readiness(node_id) → (bool, float)
# = 0.6 × vec_ratio + 0.4 × cross_ratio > 0.55
# vec_ratio: FTS5→ChromaDB 의존도 전환 (의미적 연결 우세)
# cross_ratio: 이웃이 여러 project에 분포 (신피질 연결)
```

### C-3과의 결합 방식

세 게이트가 직렬로 작동:

```
Signal 노드 승격 결정 흐름:

┌─────────────────────────────────────────────┐
│  Gate 1: SWR readiness (B-2)                │
│  - 구조적 준비: 의미적 연결 우세 + 크로스도메인│
│  - readiness > 0.55 → Pass                  │
│  - 실패 시: {"status": "not_ready"}          │
└────────────────────┬────────────────────────┘
                     ▼
┌─────────────────────────────────────────────┐
│  Gate 2: Bayesian P(real) (C-3)             │
│  - 통계적 증거: recall 빈도가 충분한가        │
│  - P > 0.5 → Pass                           │
│  - 실패 시: {"status": "insufficient_evidence"}│
└────────────────────┬────────────────────────┘
                     ▼
┌─────────────────────────────────────────────┐
│  Gate 3: MDL compression (C-3)              │
│  - 의미적 중복도: embedding similarity > 0.75│
│  - Pass → promote_node() 실행               │
│  - 실패 시: {"status": "mdl_failed"}         │
└─────────────────────────────────────────────┘
```

**각 게이트의 역할 분리:**

| 게이트 | 측정 대상 | 실패 의미 |
|---|---|---|
| SWR (B-2) | 구조적 성숙도 | "아직 의미 연결 안 됨" |
| Bayesian (C-3) | 통계적 증거 | "관찰 횟수 부족" |
| MDL (C-3) | 의미적 중복 | "Pattern으로 압축 불가" |

**실제 코드 삽입 순서 (promote_node.py):**
```python
# 1번 게이트
ready, swr_score = swr_readiness(node_id)
if not ready:
    return {"status": "not_ready", "swr_score": swr_score}

# 2번 게이트
total_queries = get_total_recall_count()
p_real = promotion_probability(node, total_queries)
if p_real < 0.5:
    return {"status": "insufficient_evidence", "p_real": p_real}

# 3번 게이트
if related_ids:
    mdl_ok, mdl_reason = _mdl_gate(node, related_nodes)
    if not mdl_ok:
        return {"status": "mdl_failed", "reason": mdl_reason}

# 모든 게이트 통과 → 승격 실행
```

---

## 3. C-4 RRF k=30 + B-8 RWR surprise — 점수 분포 변화 예측

### 현재 점수 구성 (k=60)

```
최종 score = RRF_score(k=60) + enrichment_bonus + tier_bonus + RWR_surprise_bonus
           = 1/(60+rank) + qs×0.2 + tr×0.1 + tier_bonus + 0.1×surprise
```

### k=30으로 변경 시 상호작용

**수치 분석:**

| rank | k=60 RRF | k=30 RRF | 차이 |
|---|---|---|---|
| 1 | 0.016 | 0.032 | +0.016 |
| 5 | 0.015 | 0.029 | +0.014 |
| 10 | 0.014 | 0.025 | +0.011 |

RWR surprise 최대 보너스: `0.1 × 5.0 = 0.50` (놀라움 지수 5배 초과 시)
→ k=30 rank-1 점수(0.032) 대비 **최대 15.6배 보너스** 가능

**위험**: k=30 + 높은 RWR_SURPRISE_WEIGHT → 저차수 노드의 "의외성"이 관련성을 압도.

### 권장 조정

```python
# config.py — k=30 전환 시 동시 적용

RRF_K = 30
RWR_SURPRISE_WEIGHT = 0.05   # 0.1 → 0.05 (k 감소에 비례해 절반으로)
```

**근거**: k=30에서 rank-1 RRF 점수가 0.032로 상승. 기존 k=60(0.016) 대비 2배.
RWR 보너스가 이 절대값 기준으로 상대적으로 커지므로 절반으로 줄여 균형 유지.

### 예상 점수 분포 변화

| 노드 타입 | k=60 + w=0.1 | k=30 + w=0.05 | 변화 방향 |
|---|---|---|---|
| tier=0 (Principle/Value) | 중상위 | 상위 집중 | ↑ tier_bonus 0.15 유지 |
| 고차수 허브 | 높음 | 다소 하락 | ↓ RWR baseline↑ → surprise↓ |
| 저차수 이색 노드 | 가끔 등장 | 조금 억제 | → w=0.05로 과도한 boost 방지 |
| FTS5 강한 노드 | 중간 | 상승 | ↑ RRF 가중치 증가 |

**결론**: k=30 + RWR_SURPRISE_WEIGHT=0.05 조합이 안전. k=30 단독 먼저 실험 후 RWR 순차 도입 권장.

---

## 정합성 요약

| 항목 | 결론 |
|---|---|
| B-1 LAYER_ETA vs C-2 | C-2가 B-1로 교체. 단일 η=0.01 폐기 |
| 컬럼명 통일 | `θ_m`, `activity_history` (B-1 정본 기준) |
| SWR + Bayesian + MDL | 직렬 게이트. SWR→Bayesian→MDL 순서 고정 |
| RRF k=30 + RWR | k=30 변경 시 `RWR_SURPRISE_WEIGHT=0.1→0.05` 동반 조정 |
