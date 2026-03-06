# 세션 C — PyTorch #6: RRF k=30 골드셋 설계

> 2026-03-05 | Q6 심화 | DB 실제 조회 기반

---

## tier=0 노드 실제 조회 결과 (quality_score 상위)

```
[4163] Value    L4 qs=0.95 | 뇌의 다차원적 연결을 외부화하고 싶다는 욕구. '더, 더, 더!'
[4161] Belief   L4 qs=0.92 | 모든 현상을 다차원으로 해석하는 것이 사고의 본질이다
[4165] Philosophy L4 qs=0.92 | 의지에 의존하지 않고 환경과 규칙을 설계해서 관찰→분해→구조화
[4166] Value    L4 qs=0.92 | 이색적 접합 — 서로 다른 도메인의 개념을 연결해서 새로운 의미
[181]  Principle L3 qs=0.92 | Context = Currency: 토큰은 통화, 모든 baseline 비용 최소화
[378]  Principle L3 qs=0.92 | 세 가지 원칙: Baseline 최소화 / 오프로딩 / 계층적 위임
[406]  Principle L3 qs=0.92 | 7일이면 충분하다. 완벽한 설계를 기다리지 않고 만들면서 개선
[404]  Principle L3 qs=0.92 | 빼기가 더하기보다 어렵다. 어떤 에이전트를 없앨지 결정하는 것
[405]  Principle L3 qs=0.92 | AI는 도구가 아니라 팀원이다. 잘 설계된 시스템에서 AI는...
[43]   Principle L3 qs=0.95 | 단일 진실 소스: STATE.md가 유일한 진실
[377]  Principle L3 qs=0.95 | 토큰은 화폐다. 200K 토큰 컨텍스트 윈도우...
[755]  Principle L3 qs=0.92 | 1. 단일 진실 소스 — Obsidian에 쓰고 Claude에도 쓰면 충돌
[756]  Principle L3 qs=0.92 | 2. 쓰기 권한 분리 — 여러 AI가 동시에 파일 수정하면 충돌
[771]  Principle L3 qs=0.92 | SoT 원칙: 각 정보는 정확히 1곳에만 존재
```

→ **골드셋 후보: 40-50개 tier=0 노드 확보 가능.** L4/L5(Value, Philosophy, Belief)가 자연스러운 최우선 후보.

---

## 골드셋 라벨링 포맷

Paul이 작성할 YAML 파일: `scripts/eval/goldset.yaml`

```yaml
# scripts/eval/goldset.yaml
# 형식: query → 정답 node_id 목록 (rank-1 필수 포함)
# 복수 정답 허용 (같은 쿼리에 여러 관련 노드)

version: "1.0"
created: "2026-03-05"
queries:
  - id: "q001"
    query: "뇌의 다차원 연결을 외부화하고 싶다"
    relevant_ids: [4163]          # 필수 정답
    also_relevant: [4166, 4161]   # 부분 정답 (bonus)
    notes: "Paul의 근본 동기 노드"

  - id: "q002"
    query: "컨텍스트를 화폐처럼 관리하는 원칙"
    relevant_ids: [181, 377]
    also_relevant: [151, 282]
    notes: "토큰 = 화폐 원칙"

  - id: "q003"
    query: "AI는 도구가 아니라 팀원이다"
    relevant_ids: [405]
    also_relevant: [404, 406]
    notes: "AI 협업 철학"

  - id: "q004"
    query: "이색적 접합으로 창의성 만들기"
    relevant_ids: [4166]
    also_relevant: [4161, 4163]
    notes: "Value 노드 — 이색적 접합"

  - id: "q005"
    query: "단일 진실 소스 원칙"
    relevant_ids: [43, 755, 771]
    also_relevant: [276, 574]
    notes: "SoT 원칙 — 여러 노드가 동일 원칙"
  # ... 20-50개
```

---

## 라벨링 예시 3개 (Paul 참고용)

### 예시 1 — 명확한 단일 정답
```yaml
- id: "q010"
  query: "7일 만에 완성하는 반복 개발 방법"
  relevant_ids: [406]        # '7일이면 충분하다' Principle
  also_relevant: []
  notes: "v3.3 개발 당시 경험 노드"
```

### 예시 2 — 복수 정답 (같은 원칙의 여러 표현)
```yaml
- id: "q020"
  query: "orchestration 시스템 파일은 어디에 있나"
  relevant_ids: [1094]       # 주의사항 Principle
  also_relevant: [43, 571]   # 핵심 원칙들
  notes: "경로/구조 관련 Principle 클러스터"
```

### 예시 3 — 추상적 질문 (L4/L5 대상)
```yaml
- id: "q030"
  query: "왜 이 시스템을 만드는가"
  relevant_ids: [4163]       # Value: 뇌 확장 욕구
  also_relevant: [4166, 4165]
  notes: "근본 동기 — Value 레이어가 정답"
```

---

## 측정 스크립트: scripts/eval/

### scripts/eval/metrics.py

```python
"""NDCG@5, MRR, P@5 측정 유틸리티."""
import math
import yaml
from pathlib import Path


def ndcg_at_k(results: list[dict], relevant_ids: list[int],
              also_relevant: list[int] = None, k: int = 5) -> float:
    """NDCG@k. relevant=1.0, also_relevant=0.5."""
    also_relevant = also_relevant or []
    dcg = 0.0
    for i, r in enumerate(results[:k]):
        if r["id"] in relevant_ids:
            dcg += 1.0 / math.log2(i + 2)
        elif r["id"] in also_relevant:
            dcg += 0.5 / math.log2(i + 2)
    # IDCG: 이상적 배치
    ideal = sorted([1.0] * len(relevant_ids) + [0.5] * len(also_relevant),
                   reverse=True)
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal[:k]))
    return dcg / idcg if idcg > 0 else 0.0


def mrr(results: list[dict], relevant_ids: list[int]) -> float:
    for i, r in enumerate(results):
        if r["id"] in relevant_ids:
            return 1.0 / (i + 1)
    return 0.0


def precision_at_k(results: list[dict], relevant_ids: list[int],
                   k: int = 5) -> float:
    hits = sum(1 for r in results[:k] if r["id"] in relevant_ids)
    return hits / k
```

### scripts/eval/ab_test.py

```python
"""RRF k=30 vs k=60 A/B 테스트."""
import yaml
import statistics
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import config
from storage.hybrid import hybrid_search
from scripts.eval.metrics import ndcg_at_k, mrr, precision_at_k


def run_ab_test(goldset_path: str = "scripts/eval/goldset.yaml",
                k_values: list[int] = None) -> dict:
    k_values = k_values or [30, 60]
    with open(goldset_path, encoding="utf-8") as f:
        goldset = yaml.safe_load(f)

    results = {}
    for k in k_values:
        original_k = config.RRF_K
        config.RRF_K = k

        ndcg_scores, mrr_scores, p5_scores = [], [], []
        for item in goldset["queries"]:
            search_res = hybrid_search(item["query"], top_k=10)
            rel = item["relevant_ids"]
            also = item.get("also_relevant", [])
            ndcg_scores.append(ndcg_at_k(search_res, rel, also))
            mrr_scores.append(mrr(search_res, rel))
            p5_scores.append(precision_at_k(search_res, rel))

        results[f"k={k}"] = {
            "NDCG@5": round(statistics.mean(ndcg_scores), 4),
            "MRR":    round(statistics.mean(mrr_scores),  4),
            "P@5":    round(statistics.mean(p5_scores),   4),
            "n_queries": len(goldset["queries"]),
        }
        config.RRF_K = original_k

    # 승자 판정
    best_k = max(results, key=lambda k: results[k]["NDCG@5"])
    results["winner"] = best_k
    results["delta_ndcg"] = round(
        results["k=30"]["NDCG@5"] - results["k=60"]["NDCG@5"], 4
    )
    return results


if __name__ == "__main__":
    r = run_ab_test()
    for k, v in r.items():
        print(f"{k}: {v}")
```

### 실행 방법

```bash
cd /c/dev/01_projects/06_mcp-memory
python scripts/eval/ab_test.py
```

예상 출력:
```
k=30: {'NDCG@5': 0.72, 'MRR': 0.68, 'P@5': 0.48, 'n_queries': 30}
k=60: {'NDCG@5': 0.65, 'MRR': 0.61, 'P@5': 0.42, 'n_queries': 30}
winner: k=30
delta_ndcg: 0.07
```

---

## 필요 파일 구조

```
scripts/
└── eval/
    ├── goldset.yaml   ← Paul 라벨링 (수동)
    ├── metrics.py     ← NDCG/MRR/P@5 함수
    └── ab_test.py     ← A/B 실행 스크립트
```

`scripts/` 폴더 없으면 생성 필요.
