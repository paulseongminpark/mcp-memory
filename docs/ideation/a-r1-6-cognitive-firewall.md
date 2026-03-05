# Q6. 인지적 방화벽 + 유지보수성(제4조건)

## 위협 모델

L4/L5 노드(Belief, Philosophy, Value, Axiom)는 Paul의 **정체성**이다. 위협:

1. **Enrichment 환각**: LLM이 L4/L5 summary 왜곡 -> 의미 변질
2. **자동 edge**: L4/L5와 모순되는 새 노드에 `supports` edge 자동 생성
3. **Hebbian 편향**: Claude가 특정 가치를 자주 recall -> 다른 가치 약화
4. **승격 편향**: enrichment가 편향 반영 노드를 L3->L4 승격 제안

## 방화벽 규칙 F1-F6 (하드코딩)

| ID | 이름 | 규칙 | 적용 지점 |
|----|------|------|----------|
| F1 | immutable_core | L4/L5 content/type은 source='paul' 외 수정 불가 | update_node |
| F2 | enrichment_restriction | L4/L5 enrichment는 summary/key_concepts만 | node_enricher.py |
| F3 | auto_edge_prohibition | L4/L5 자동 edge 생성 불가 | remember() link() |
| F4 | promotion_human_gate | L3->L4, L4->L5 승격 시 Paul 확인 필수 | promote_node() |
| F5 | decay_immunity | L4/L5 edge decay_rate = 0 | _hebbian_update() |
| F6 | deletion_prohibition | L4/L5 자동 비활성화/아카이브 불가 | 아카이브 정책 |

-> 코드 삽입 지점 상세: [a-arch-10-firewall-code.md](a-arch-10-firewall-code.md)

## integrity_check() — 주기적 무결성 검증

```python
def integrity_check() -> dict:
    # 1. L4/L5 노드 수 변동 (baseline: 6개)
    # 2. content 해시 비교 (이전 스냅샷 대비)
    # 3. enrichment가 만든 L4/L5 edge 탐지
    # 4. Hebbian 편향 체크 (edge strength 분포)
```

## RBAC — 레이어별 차등 권한

```python
LAYER_PERMISSIONS = {
    (0, "create"):  ["paul", "claude", "enrichment"],
    (0, "modify"):  ["paul", "claude", "enrichment"],
    (0, "delete"):  ["paul", "claude", "system"],
    (1, "create"):  ["paul", "claude", "enrichment"],
    (1, "modify"):  ["paul", "claude", "enrichment"],
    (1, "delete"):  ["paul"],
    (2, "create"):  ["paul", "claude", "enrichment"],
    (2, "modify"):  ["paul", "claude", "enrichment"],
    (2, "delete"):  ["paul"],
    (3, "create"):  ["paul", "claude"],
    (3, "modify"):  ["paul", "claude"],
    (3, "delete"):  ["paul"],
    (4, "create"):  ["paul"],         # 방화벽
    (4, "modify"):  ["paul"],
    (4, "delete"):  ["paul"],
    (5, "create"):  ["paul"],         # 방화벽
    (5, "modify"):  ["paul"],
    (5, "delete"):  ["paul"],
}
```

## 유지보수성 (Gemini 제4조건)

Clark의 3조건(접근가능+신뢰+자동사용)에 추가:
> "AI가 사용자의 정체성/목적을 은연중에 왜곡하지 않도록 방어하는 제어/복원 능력"

이것이 F1-F6 방화벽과 integrity_check()의 이론적 근거다.
