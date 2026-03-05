# 세션 C — PyTorch/ML 실험 가능성 (인덱스)

> 2026-03-05 | 세션 C: Sonnet. 8개 질문 탐구.

상세 내용은 주제별 파일로 분할:

| 파일 | 내용 | 핵심 결론 |
|---|---|---|
| `c-pytorch-1-kg-embedding.md` | Q1+Q7: GNN 가능성, Link Prediction | TransE/R-GCN 불가. sklearn MLP 가능 |
| `c-pytorch-2-hebbian-bcm.md` | Q2: PyTorch Hebbian, BCM/Oja | PyTorch 불필요. BCM = NumPy |
| `c-pytorch-3-promotion-models.md` | Q3+Q4+Q5: MDL, Bayesian, SPRT | 3가지 모두 구현 가능. scipy/Python |
| `c-pytorch-4-rrf-experiment.md` | Q6: RRF k=30 A/B 테스트 | 1-line 변경 + 골드셋 20개 |
| `c-pytorch-5-roadmap.md` | Q8: 최종 로드맵 | PyTorch 불필요 지금. 60K+ edges 때 |

## 한줄 요약

6K edges 규모에서 PyTorch 불필요. BCM(NumPy) + Bayesian(scipy) + SPRT(Python) + RRF k=30(config 1줄)이 즉시 구현 가능한 ML.
