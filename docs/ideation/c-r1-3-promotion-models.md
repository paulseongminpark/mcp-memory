# 세션 C — PyTorch #3: 승격 모델 (MDL + Bayesian + SPRT)

> 2026-03-05 | Q3 + Q4 + Q5

---

## Q3. MDL 기반 승격 모델

**판정: 완전 구현 가능. PyTorch 불필요. LLM API 1회.**

### 현재 문제

"3회 반복 → Pattern 승격" — GPT: **"미신"**. 반복 횟수는 패턴의 증거가 아니다.
MDL 원리: Pattern이란 **압축**이다. Signal이 Pattern으로 통합되면 데이터가 더 짧게 기술되어야 한다.

### MDL 기준

```
승격 정당: len(Pattern) + n × δ < Σ len(Signal_i)
```

### 구현

```python
def should_promote_mdl(signals: list[dict],
                        llm_fn,
                        compression_ratio=0.7) -> bool:
    """
    signals: Signal 노드 리스트 (content 포함)
    llm_fn: LLM 요약 함수 (1회 API 호출)
    compression_ratio: 이 비율 미만으로 압축 시 승격
    """
    individual_cost = sum(len(s["content"]) for s in signals)

    # LLM으로 Pattern 요약 생성
    contents = [s["content"] for s in signals]
    pattern_summary = llm_fn(f"Summarize these related signals: {contents}")

    # 참조 포인터 비용 (노드 ID 참조)
    reference_cost = len(signals) * 10

    compressed_cost = len(pattern_summary) + reference_cost
    return compressed_cost < individual_cost * compression_ratio


def mdl_semantic_score(signals: list[dict], embeddings: dict) -> float:
    """
    더 정밀한 버전: 임베딩 pairwise cosine similarity로 의미적 중복도 측정.
    중복이 높을수록 Pattern 통합 가치 있음.
    """
    import numpy as np

    vecs = [np.array(embeddings[s["id"]]) for s in signals]
    n = len(vecs)
    total_sim = 0.0
    count = 0
    for i in range(n):
        for j in range(i+1, n):
            sim = np.dot(vecs[i], vecs[j]) / (
                np.linalg.norm(vecs[i]) * np.linalg.norm(vecs[j]))
            total_sim += sim
            count += 1
    return total_sim / count if count > 0 else 0.0

# avg_similarity > 0.8 → 고중복 → Pattern 통합 강력 권장
```

---

## Q4. 베이지안 증거 누적

**판정: 구현 가능. scipy.stats Beta-Binomial. 20줄.**

### 아이디어

Signal이 반복 등장할 때 "충분한 증거가 축적되었는가"를 베이지안으로 판단.

- **Prior**: Beta(1, 10) — 회의적 시작 (새 Signal은 10% 신뢰)
- **Evidence**: recall 결과에 Signal이 등장한 횟수 (= `frequency`)
- **Posterior**: 업데이트된 믿음

```python
from scipy.stats import beta as beta_dist

def promotion_probability(node: dict,
                           total_queries: int,
                           alpha0=1, beta0=10) -> float:
    """
    node: Signal 노드 (frequency, quality_score 포함)
    total_queries: 전체 recall 호출 횟수 (글로벌 카운터)
    """
    k = node.get("frequency", 0)       # recall 결과에 등장한 횟수
    n = total_queries                  # 전체 쿼리 수
    n = max(n, k)                      # n >= k 보장

    alpha_post = alpha0 + k
    beta_post = beta0 + (n - k)

    return beta_dist(alpha_post, beta_post).mean()  # = alpha/(alpha+beta)


def should_promote_bayesian(node: dict,
                             total_queries: int,
                             threshold=0.5) -> bool:
    p = promotion_probability(node, total_queries)
    return p > threshold
```

### 현재 데이터 활용

- `edges.frequency`: Hebbian 카운터 → 직접 k로 사용
- `nodes.quality_score`: 보조 근거 (prior 조정에 활용 가능)
- **missing**: `total_queries` 글로벌 카운터 → DB에 추가 필요

---

## Q5. 드리프트-확산 모델 (SPRT)

**판정: 구현 가능. 30줄 Python. 베이지안보다 더 즉각적 결정.**

### 아이디어

SPRT(Sequential Probability Ratio Test): 증거가 누적되어 임계값을 넘을 때 즉시 결정.
베이지안과 차이: SPRT는 **순차적** — 증거가 하나씩 들어올 때마다 판단.

```python
import math

def sprt_promote_decision(score_history: list[float],
                           alpha=0.05,
                           beta_err=0.20,
                           p1=0.7,
                           p0=0.3) -> str:
    """
    score_history: Signal 노드의 recall score 이력 (hybrid_search 반환값)
    alpha: 오탐율 (5%)
    beta_err: 미탐율 (20%)
    p1: H1(real pattern) 하에서 기대 score
    p0: H0(noise) 하에서 기대 score

    Returns: "promote" | "reject" | "inconclusive"
    """
    # Wald 임계값
    A = math.log((1 - beta_err) / alpha)   # 승격 임계 (≈ 2.77)
    B = math.log(beta_err / (1 - alpha))   # 기각 임계 (≈ -2.94)

    cumulative = 0.0
    for obs in score_history:
        if obs > 0.5:
            log_lr = math.log(p1 / p0)
        else:
            log_lr = math.log((1 - p1) / (1 - p0))
        cumulative += log_lr

        if cumulative >= A:
            return "promote"
        if cumulative <= B:
            return "reject"

    return "inconclusive"
```

### 현재 시스템에서의 구현 경로

- `hybrid_search()` 반환 `node["score"]` → 각 recall의 observation
- **필요한 추가**: `nodes` 테이블에 `score_history TEXT` (JSON array) 컬럼
- recall 시마다 append: `score_history = json.loads(node.score_history or '[]') + [score]`

---

## 세 모델 비교

| | MDL | Bayesian | SPRT |
|---|---|---|---|
| 결정 시점 | 배치 (여러 Signal 한번에) | 연속 (누적 후 판단) | 순차 (즉각) |
| 데이터 요구 | Signal content + LLM | frequency + total_queries | score_history |
| 구현 비용 | 중간 (LLM 호출) | 낮음 (scipy) | 낮음 (Python math) |
| 권장 용도 | promote_node() 호출 시 검증 | analyze_signals() 자동 스캔 | recall() 실시간 감지 |

**권장**: Bayesian으로 상시 모니터링 → SPRT로 실시간 감지 → MDL로 최종 검증.
