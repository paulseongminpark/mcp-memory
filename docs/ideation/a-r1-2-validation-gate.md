# Q2. 검증-게이트 학습 — 현재 v2에서 치명적인가

## 현재 상태 진단

검증 부재의 구체적 증상:
1. `enrichment/node_enricher.py`: LLM 생성 summary/key_concepts/facets가 **무검증으로 DB 기록**
2. `insert_edge()`에서 `relation not in ALL_RELATIONS` 체크만 — **의미적 타당성 검증 없음**
3. `promote_node()`에서 `VALID_PROMOTIONS` 경로 체크만 — **승격 근거 품질 검증 없음**

## 치명적인가? — "예, 하지만 단계적으로"

**즉시 치명적**: 의미적 피드백 루프 (v2 문서 S2.7)
- enrichment 환각 facet → 임베딩 오염 → 잘못된 edge → 더 많은 환각
- `FACETS_ALLOWLIST`/`DOMAINS_ALLOWLIST`가 부분 방어하지만, summary/key_concepts에는 필터 없음

**아직 치명적이지 않음**: Hebbian 발산
- 3,230 노드에서 recall 빈도 낮아 실질적 발산 미발생 (DeepSeek: 921일 후 사망)
- 능동적 사용 시작 시(매일 recall 10회+) 문제 급격히 현실화

## 4차원 검증 게이트

```python
class ValidationGate:
    """토폴로지 변경 전 4차원 검증."""

    def validate(self, change: TopologyChange) -> ValidationResult:
        scores = {
            "consistency": self._check_consistency(change),   # 기존 그래프와 모순?
            "grounding": self._check_grounding(change),       # 출처가 있는가?
            "novelty": self._check_novelty(change),           # 기존에 없는 정보?
            "alignment": self._check_alignment(change),       # Paul의 가치와 정렬?
        }
        passed = all(s >= threshold for s in scores.values())
        return ValidationResult(passed=passed, scores=scores)

    def _check_consistency(self, change):
        # 신규 edge 양쪽 노드 -> 기존 contradicts edge 확인
        # contradicts + supports 동시 -> 점수 하락

    def _check_grounding(self, change):
        # source='paul' -> 1.0
        # source='claude' + session_context -> 0.7
        # source='enrichment' -> 0.5
        # source 없음 -> 0.0

    def _check_novelty(self, change):
        # 유사도 > 0.95 -> 0.0 (중복)
        # 유사도 0.7-0.95 -> 0.5 (관련)
        # 유사도 < 0.7 -> 1.0 (참신)

    def _check_alignment(self, change):
        # L4/L5 노드와 contradicts -> 0.0
        # 무관 -> 0.7
        # supports -> 1.0
```

## 적용 지점

1. `insert_edge()` — 모든 edge 생성 전
2. `enrichment` — LLM 출력 DB 반영 전
3. `promote_node()` — 승격 전
4. `remember()` 자동 edge — link() 단계

## 성능 고려

consistency/novelty: 벡터 검색 1회 (< 1ms). alignment: L4/L5 노드 ~6개 부하 무시. grounding: 메타데이터 체크만.

## 단계적 구현

1. **Phase 0 (즉시)**: enrichment 결과에 `validated: false` 플래그, 임베딩 반영 차단
2. **Phase 1 (1주)**: grounding + novelty 체크 (LLM 불필요, 규칙 기반)
3. **Phase 2 (2주)**: consistency 체크 (그래프 탐색 기반)
4. **Phase 3 (1월)**: alignment 체크 (L4/L5 벡터 유사도)
