# Q8. 제1원칙과 빼기 — 무엇을 먼저 파악하고, 어떤 순서로 덜어내나

## "정확히 파악을 못 했기 때문에 빼기가 두렵다"

이 두려움은 합리적이다.

## 먼저 파악해야 할 3가지

### 1. 실제 사용 분포

```sql
SELECT type, COUNT(*) as cnt, AVG(quality_score) as avg_quality
FROM nodes WHERE status = 'active' GROUP BY type ORDER BY cnt DESC;

SELECT relation, COUNT(*) as cnt FROM edges GROUP BY relation ORDER BY cnt DESC;
```

-> 실제 결과: [a-arch-11-subtraction-data.md](a-arch-11-subtraction-data.md)

### 2. 연결 구조 — "뭘 빼면 뭐가 끊기는가"

```sql
-- 허브 노드 (edge 수 상위 20)
SELECT n.id, n.type, COUNT(e.id) as edge_count
FROM nodes n LEFT JOIN edges e ON n.id = e.source_id OR n.id = e.target_id
GROUP BY n.id ORDER BY edge_count DESC LIMIT 20;

-- 고립 노드 (edge 0)
SELECT n.id, n.type FROM nodes n
LEFT JOIN edges e ON n.id = e.source_id OR n.id = e.target_id
WHERE n.status = 'active' AND e.id IS NULL;
```

### 3. 검색 기여도

action_log(Q7) 없이는 측정 불가. **action_log를 먼저 구현해야 빼기의 근거를 만들 수 있다.**

## 덜어내는 순서

```
Phase 0: 데이터 수집 (1-2주)
  action_log 구현 -> recall 패턴 수집 -> 사용 분포 확인
  아무것도 빼지 않는다.

Phase 1: 확실한 것 (1주, 위험도 최소)
  - 사용 0 관계/노드 타입 -> deprecated
  - 고립 노드(edge 0, L0/L1) -> inactive
  - 중복 노드(유사도 > 0.95) -> merged

Phase 2: super-type 구조화 (2주, 위험도 낮음)
  - 50 타입 -> 7-10개 super-type 그룹화
  - 기존 타입은 sub-type으로 유지

Phase 3: 관계 원시화 (2주, 위험도 중간)
  - 48 관계 -> 12-15개 활성 + 나머지 deprecated
  - 기존 edge.relation은 그대로. 새 edge에만 적용.

Phase 4: enrichment 단순화 (1개월, 위험도 높음)
  - action_log 데이터 기반 기여도 측정 후에만 진행
```

## 핵심 원칙: "빼기"가 아니라 "비활성화"

> **물리적 삭제는 하지 않는다.** deprecated + archived로 검색에서 제외하되 데이터는 보존.
>
> 뇌의 시냅스 가지치기와 같다 — 시냅스를 "끊는" 것이지 뉴런을 "죽이는" 것이 아니다.
> 연결이 끊긴 뉴런은 나중에 다른 맥락에서 새 연결을 형성할 수 있다 (Storm et al., 2008).
>
> **빼기의 본질은 "존재"를 없애는 것이 아니라 "주의"에서 제외하는 것이다.**
