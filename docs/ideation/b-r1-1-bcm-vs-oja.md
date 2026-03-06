# B-1: BCM vs Oja — 학습 규칙 선택

> 세션 B | 2026-03-05 | 참조: `storage/hybrid.py` `_hebbian_update()`

## 결론: **BCM 선택**

| 기준 | BCM | Oja |
|---|---|---|
| 레이어별 차등 적용 | 가능 (η per layer) | 어렵 |
| Runaway 방지 | 적응형 임계값(ν_θ) | 정규화(합=1) |
| 생물학적 정확성 | 높음 | 낮음 |
| 구현 복잡도 | 중간 | 낮음 |

Oja는 pruning 전처리 정규화에만 제한 사용.

---

## 현재 코드 문제

`_hebbian_update()` (`storage/hybrid.py`): `frequency += 1`만.
effective_strength 공식에 **상한 없음**.

DeepSeek 분석:
- 매일 recall 시 1년 후: `1.590×` 발산 (로그 무한)
- 미회수 노드 사망: ~921일(2.52년)
- decay rate `δ=0.005` 매우 보수적

---

## BCM 구현 스케치

```python
# storage/hybrid.py — _hebbian_update() 교체
# DB 변경: nodes 테이블에 θ_m REAL DEFAULT 0.5, activity_history TEXT 추가

LAYER_ETA = {0: 0.02, 1: 0.015, 2: 0.01, 3: 0.005, 4: 0.001, 5: 0.0001}
# L0(Obs): 빠른 변화 / L5(Value): 거의 고정
HISTORY_WINDOW = 20

def _bcm_update(result_ids: list[int], result_scores: list[float], all_edges: list[dict]):
    """BCM 규칙: dw_ij/dt = η · ν_i · (ν_i - ν_θ) · ν_j
    ν_i, ν_j = recall() 결과 score (0~1 정규화)
    ν_θ      = 노드별 적응형 임계값 → 슬라이딩 윈도우 제곱평균으로 갱신
    """
    score_map = dict(zip(result_ids, result_scores))
    id_set = set(result_ids)

    for edge in all_edges:
        src, tgt = edge['source_id'], edge['target_id']
        if src not in id_set or tgt not in id_set:
            continue

        ν_i = score_map[src]
        ν_j = score_map[tgt]
        node = sqlite_store.get_node(src)
        θ_m  = node.get('θ_m') or 0.5
        history = json.loads(node.get('activity_history') or '[]')
        η = LAYER_ETA.get(node.get('layer', 2), 0.01)

        delta_w = η * ν_i * (ν_i - θ_m) * ν_j
        new_freq = max(0.0, edge['frequency'] + delta_w * 10)

        # θ_m 업데이트 — 슬라이딩 제곱평균 (BCM 핵심: runaway 방지)
        history = (history + [ν_i])[-HISTORY_WINDOW:]
        new_θ = sum(h**2 for h in history) / len(history)

        conn.execute("UPDATE edges SET frequency=? WHERE id=?", (new_freq, edge['id']))
        conn.execute("UPDATE nodes SET θ_m=?, activity_history=? WHERE id=?",
                     (new_θ, json.dumps(history), src))
```

---

## Oja 역할 (제한적 — Pruning 전처리)

```python
def oja_normalize(source_id: int):
    """노드 출력 edge 총합=1 정규화. 기여도 낮은 edge → 삭제 후보."""
    outgoing = get_outgoing_edges(source_id)
    total = sum(e['frequency'] for e in outgoing) or 1
    budget_threshold = 1.0 / (len(outgoing) * 10)
    for e in outgoing:
        norm = e['frequency'] / total
        if norm < budget_threshold:
            mark_for_pruning(e['id'])
        else:
            update_edge_frequency(e['id'], norm)
```

---

## DB 변경

| 테이블 | 컬럼 | 타입 | 기본값 |
|---|---|---|---|
| nodes | `θ_m` | REAL | 0.5 |
| nodes | `activity_history` | TEXT | null |

## 검증
BCM 도입 후 3개월: `frequency` 분포 히스토그램 → 발산 없이 수렴 확인.
