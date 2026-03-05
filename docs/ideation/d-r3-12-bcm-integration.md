# d-r3-12: BCM 통합 — _hebbian_update() BCM으로 교체

> 2026-03-05. 오케스트레이터 결정: tanh 철회 → BCM 직행 (B-1 설계 연계).
> B 세션 B-1: 레이어별 η + 적응형 θ_m + Oja pruning 전처리.
> 이 파일은 현재 코드에 BCM을 어떻게 통합하는지 D 관점 설계.

---

## 현재 코드 (storage/hybrid.py L14-44)

```python
def _hebbian_update(result_ids: list[int], all_edges: list[dict]):
    # 활성화된 edge 찾기
    for edge in all_edges:
        if src in id_set and tgt in id_set:
            activated.append(edge.get("id"))
    # 현재: frequency +1만, strength 변경 없음
    conn.execute(
        "UPDATE edges SET frequency = COALESCE(frequency, 0) + 1, "
        "last_activated = ? WHERE id = ?",
        (now, eid),
    )
```

**문제:** frequency는 무한 증가, strength는 아예 미변경.
strength가 처음 설정값(1.0) 그대로 → Hebbian 학습이 실질적으로 없는 상태.

---

## BCM 공식

```
BCM (Bienenstock-Cooper-Munro, 1982):
  dw/dt = η * y * (y - θ_m)

  y   = 시냅스 후 활성화 강도 = edge.strength
  θ_m = E[y²] = 최근 strength의 이동평균 제곱 (sliding threshold)
  η   = 학습률 (레이어별 다름)

  y > θ_m → dw > 0 (LTP: 강화)
  y < θ_m → dw < 0 (LTD: 약화)
  θ_m이 올라가면 더 강한 자극만 강화됨 → 자동 안정화
```

---

## edges 테이블 관련 컬럼 (실제 확인)

```sql
strength        REAL DEFAULT 1.0    -- 현재 강도 (BCM이 업데이트할 대상)
base_strength   REAL                -- 초기 강도 (BCM 기준점)
frequency       INTEGER DEFAULT 0   -- recall 횟수 (θ_m 계산 보조)
last_activated  TEXT                -- 마지막 활성화
decay_rate      REAL DEFAULT 0.005  -- 감쇠율
layer_distance  INTEGER             -- 레이어 거리 (η 결정 보조)
```

---

## BCM 통합 설계

### 레이어별 η 배정

```python
# B-1 설계 기반 (레이어 평균으로 결정)
ETA_BY_LAYER_DISTANCE = {
    0: 0.10,   # 같은 레이어 연결 (L0-L0, L1-L1 등)
    1: 0.07,   # 인접 레이어
    2: 0.05,   # 2단계 거리
    3: 0.03,
    4: 0.01,   # L0-L4 (원시↔가치) 연결: 매우 느린 학습
    5: 0.005,
}
DEFAULT_ETA = 0.05
```

### θ_m 계산 전략

```python
def _compute_theta_m(activated_edge_strengths: list[float]) -> float:
    """BCM sliding threshold = E[y²] of activated edges.

    local BCM: recall 시 활성화된 edge들만 기준으로 계산.
    전체 DB 스캔 없음 → 성능 유지.
    """
    if not activated_edge_strengths:
        return 0.25  # 기본값: strength 0.5의 제곱
    return sum(s ** 2 for s in activated_edge_strengths) / len(activated_edge_strengths)
```

### 완전 교체 코드

```python
# storage/hybrid.py 교체 대상: L14-44

ETA_BY_LAYER_DISTANCE = {0: 0.10, 1: 0.07, 2: 0.05, 3: 0.03, 4: 0.01, 5: 0.005}
BCM_STRENGTH_MIN = 0.05   # strength 하한 (LTD로 0이 되는 것 방지)
BCM_STRENGTH_MAX = 2.0    # strength 상한 (LTP 발산 방지)


def _compute_theta_m(strengths: list[float]) -> float:
    if not strengths:
        return 0.25
    return sum(s ** 2 for s in strengths) / len(strengths)


def _hebbian_update(result_ids: list[int], all_edges: list[dict]):
    """BCM 기반 Hebbian 학습.

    함께 recall된 edge의 strength를 BCM 공식으로 업데이트.
    레이어 거리에 따라 학습률(η) 차등 적용.
    θ_m = E[y²] of activated edges (local sliding threshold).
    """
    if not result_ids:
        return
    id_set = set(result_ids)
    now = datetime.now(timezone.utc).isoformat()

    # 활성화된 edge 수집
    activated = [
        edge for edge in all_edges
        if edge.get("source_id") in id_set and edge.get("target_id") in id_set
    ]
    if not activated:
        return

    # θ_m 계산 (local BCM)
    strengths = [e.get("strength", 1.0) or 1.0 for e in activated]
    theta_m = _compute_theta_m(strengths)

    conn = None
    try:
        conn = sqlite_store._connect()
        for edge in activated:
            eid = edge.get("id")
            y = edge.get("strength", 1.0) or 1.0
            layer_dist = edge.get("layer_distance") or 0
            eta = ETA_BY_LAYER_DISTANCE.get(min(layer_dist, 5), 0.05)

            # BCM 업데이트: dw = η * y * (y - θ_m)
            delta = eta * y * (y - theta_m)
            new_strength = max(BCM_STRENGTH_MIN, min(BCM_STRENGTH_MAX, y + delta))

            conn.execute(
                "UPDATE edges SET "
                "strength = ?, "
                "frequency = COALESCE(frequency, 0) + 1, "
                "last_activated = ? "
                "WHERE id = ?",
                (new_strength, now, eid),
            )
        conn.commit()
    except Exception:
        pass  # 검색 결과가 학습 실패로 중단되면 안 됨
    finally:
        if conn:
            conn.close()
```

---

## 동작 시뮬레이션

### 시나리오 1: 강한 edge (strength=0.8)가 자주 recall될 때

```
θ_m = E[y²] = 0.64 (activated edges 평균이 0.8인 경우)
y = 0.8, θ_m = 0.64
delta = η * 0.8 * (0.8 - 0.64) = η * 0.8 * 0.16 = 0.0128 (η=0.1 기준)
new_strength = 0.813 (+1.6%)
→ 강한 연결 더 강해짐 (LTP)
```

### 시나리오 2: 약한 edge (strength=0.3)가 강한 edges와 함께 recall될 때

```
θ_m = 0.64 (다른 강한 edges 때문에 높음)
y = 0.3, θ_m = 0.64
delta = η * 0.3 * (0.3 - 0.64) = η * 0.3 * (-0.34) = -0.0102 (η=0.1 기준)
new_strength = 0.290 (-3.4%)
→ 약한 연결 더 약해짐 (LTD) → 자연적 pruning 예비 단계
```

### 시나리오 3: 모든 edge가 비슷한 강도일 때

```
θ_m ≈ y² → (y - θ_m) ≈ 0 → delta ≈ 0
→ 균형 상태, 변화 없음 → 자동 안정화
```

---

## Oja Pruning 전처리 (B-1 연계)

B-1 설계에서 언급된 "Oja pruning 전처리"는 weight decay로 해석:

```python
# BCM 업데이트 전 Oja normalization (선택적)
# Oja: dw = η * y * (x - y * w)
# mcp-memory에 단순화 적용: weight decay = α * w²
OJA_ALPHA = 0.001  # 약한 decay

def _apply_oja_decay(strength: float) -> float:
    """Oja rule weight decay: 큰 weight를 자동으로 줄임."""
    return strength * (1 - OJA_ALPHA * strength)

# BCM 전에 적용
y = _apply_oja_decay(edge.get("strength", 1.0))
delta = eta * y * (y - theta_m)
new_strength = max(BCM_STRENGTH_MIN, min(BCM_STRENGTH_MAX, y + delta))
```

---

## 검증 방법

```python
# tests/test_bcm.py
def test_ltp_strong_edge():
    """강한 edge는 강화됨"""
    edges = [{"id": 1, "source_id": 1, "target_id": 2,
              "strength": 0.8, "layer_distance": 0}]
    # 모든 activated edges strength=0.8 → θ_m=0.64
    # delta > 0 → new_strength > 0.8

def test_ltd_weak_edge_in_strong_context():
    """강한 context에서 약한 edge는 약화됨"""
    # θ_m이 높을 때 약한 edge의 delta < 0

def test_stability_uniform_edges():
    """균일한 강도에서는 안정됨 (delta ≈ 0)"""

def test_strength_bounds():
    """strength가 항상 [0.05, 2.0] 범위 유지"""
```

---

## 구현 파일 위치

```
수정: storage/hybrid.py
  - L14-44 _hebbian_update() 전체 교체
  - 상단에 ETA_BY_LAYER_DISTANCE, BCM_STRENGTH_MIN/MAX 상수 추가

연관:
  - scripts/enrich/node_enricher.py: BCM과 무관 (enrichment는 별도)
  - ontology/validators.py: 무관
```

---

## 오케스트레이터 주의사항

**B-1 설계가 확정되면 확인할 것:**
1. B-1의 η 값이 위 설계와 다른지
2. θ_m 계산 범위 (local vs global)
3. Oja α 값
4. BCM_STRENGTH_MAX (B-1이 [0,1] 정규화를 요구하는지 확인)

**현재 design은 B-1 대기 상태. 위 코드는 B-1 확정 전 임시 참고용.**
