# 세션 C — PyTorch #2: Hebbian in PyTorch + BCM/Oja 정규화

> 2026-03-05 | Q2

---

## Q2. Hebbian KG를 PyTorch로 옮기면 이점이 있나

**판정: 없음. 오히려 복잡성만 증가.**

### 현재 구현 (hybrid.py)

```python
def _hebbian_update(result_ids, all_edges):
    # SQLite: UPDATE edges SET frequency = frequency + 1
    # 병목: SQLite I/O, not compute
```

### 왜 PyTorch가 무의미한가

- 6,020 edges 전체 매트릭스: CPU에서 100ms 미만
- GPU 데이터 전송 오버헤드 > 계산 이득
- SQLite I/O가 병목 → GPU가 해결 못 함

**PyTorch Hebbian이 의미 있는 시점: 100K+ edges (현재의 17x)**

---

## BCM Rule — NumPy로 충분

### 왜 BCM인가

순수 Hebbian의 문제: runaway reinforcement.
- 매일 recall 시 1년 후 strength 1.590배 (로그 발산)
- BCM은 **적응형 임계값 ν_θ**로 발산 방지

### BCM 구현 (NumPy)

```python
import numpy as np

class BCMHebbian:
    def __init__(self, eta=0.01, tau=0.1):
        self.eta = eta    # 학습률
        self.tau = tau    # 임계값 시정수

    def update(self, w: float, nu_i: float, nu_j: float,
               nu_theta: float) -> tuple[float, float]:
        """
        w: edge strength
        nu_i: source node 활성화 (최근 recall score)
        nu_j: target node 활성화
        nu_theta: 적응형 임계값 (노드별 유지)
        """
        dw = self.eta * nu_i * (nu_i - nu_theta) * nu_j
        new_w = max(0.0, w + dw)  # 음수 방지

        # 임계값 자동 조절: 높은 활동 → 임계값 상승 → 강화 어려워짐
        new_theta = nu_theta + self.tau * (nu_i**2 - nu_theta)

        return new_w, new_theta
```

### Oja Rule (대안)

```python
def oja_update(w: float, nu_i: float, nu_j: float, eta=0.01) -> float:
    """단순 정규화. BCM보다 구현 쉬움."""
    dw = eta * (nu_i * nu_j - nu_i**2 * w)
    return w + dw
```

### BCM vs Oja 비교

| | BCM | Oja |
|---|---|---|
| 복잡도 | 중간 (임계값 상태 유지) | 낮음 |
| 안정성 | 높음 (LTP/LTD 전환) | 중간 (정규화만) |
| 생물학적 근거 | 강함 | 약함 |
| mcp-memory 적합성 | 높음 | 보통 |

**권장**: BCM. 임계값은 nodes 테이블에 `bcm_threshold REAL` 컬럼 추가.

---

## 구현 경로

1. `nodes` 테이블: `bcm_threshold REAL DEFAULT 0.5` 추가
2. `_hebbian_update()`: frequency++ 대신 BCM update 호출
3. `effective_strength` 계산식: `base_strength × (1 + BCM_weight)` 반영
