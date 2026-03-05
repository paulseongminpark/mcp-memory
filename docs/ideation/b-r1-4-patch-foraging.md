# B-4: 패치 전환 (Foraging / Marginal Value Theorem)

> 세션 B | 2026-03-05 | 참조: `tools/recall.py` `recall()`

## 설계 목표

현재 `recall()`은 벡터 유사도가 높은 동일 클러스터에서 계속 결과 반환.
인지과학 foraging theory: "패치 포화 → 새 패치로 이동"이 최적 전략.

뇌과학 매핑:
- **패치 포화**: 같은 project 노드 반복 = marginal value 감소
- **패치 전환**: 다른 project 탐색 = 새 먹이 영역 이동
- **Marginal Value Theorem**: 이동 비용(재검색)이 남은 기대수익보다 클 때 이동

---

## 구현 위치

`tools/recall.py` — `hybrid_search()` 호출 직후, 포매팅 직전.

```python
# config.py 추가:
PATCH_SATURATION_THRESHOLD = 0.75  # 75% 이상 동일 project → 포화

def recall(query, type_filter="", project="", top_k=5, mode="auto"):
    results = hybrid_search(query, type_filter=type_filter,
                            project=project, top_k=top_k, mode=mode)

    # Marginal Value Theorem: 수확 체감 → 새 패치로 이동
    # project가 명시된 경우 전환하지 않음 (사용자 의도 존중)
    if not project and _is_patch_saturated(results):
        dominant = _get_dominant_project(results)
        alt = hybrid_search(query, top_k=top_k, excluded_project=dominant, mode=mode)
        # 원본 상위 절반 + 새 패치 결과 절반
        results = results[:top_k // 2] + alt[:top_k - top_k // 2]
        results.sort(key=lambda r: r['score'], reverse=True)

    return _format(results)


def _is_patch_saturated(results: list[dict]) -> bool:
    """75% 이상이 동일 project → 패치 포화."""
    if len(results) < 3:
        return False
    projects = [r.get('project', '') for r in results]
    dominant = max(set(projects), key=projects.count)
    return projects.count(dominant) / len(projects) >= PATCH_SATURATION_THRESHOLD


def _get_dominant_project(results: list[dict]) -> str:
    projects = [r.get('project', '') for r in results]
    return max(set(projects), key=projects.count)
```

---

## hybrid_search 수정 필요

`excluded_project` 파라미터 추가:

```python
def hybrid_search(query, type_filter="", project="",
                  excluded_project="", top_k=5, mode="auto"):
    # ...기존 로직...

    # 5번 단계 (타입/프로젝트 필터)에 추가:
    if excluded_project and node['project'] == excluded_project:
        continue  # 포화된 패치 제외
```

---

## 한계 및 고려사항

- top_k=5 기본값에서는 절반 교체(2개+3개)가 다소 조악할 수 있음
  → top_k=10 이상에서 더 자연스럽게 작동
- `general` project 노드는 패치 계산에서 제외하는 것이 나을 수 있음
  → 모든 project에 걸쳐 있으므로 포화 계산 왜곡 가능성

---

## DB 변경
없음. 순수 로직 변경.

## 검증
`recall("포트폴리오")` → 결과 project 분포 확인.
단일 project 지배 해소 여부 + 교차 domain 결과 비율 증가 확인.
