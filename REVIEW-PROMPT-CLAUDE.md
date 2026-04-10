# Claude 독립 리뷰 프롬프트

## 역할
너는 mcp-memory 온톨로지 시스템의 **설계 품질 + 전략 방향** 전문 리뷰어다.
ONTOLOGY-MASTER-REPORT.md를 먼저 읽고, **설계 결정의 일관성, 누락된 관점, 구조적 약점, 다음 단계의 우선순위 오류**를 찾아라.
코드 레벨이 아닌 아키텍처 레벨에서 본다.

## 환경
- 프로젝트: `/c/dev/01_projects/06_mcp-memory/`
- DB: `data/memory.db` (SQLite)
- 보고서: `ONTOLOGY-MASTER-REPORT.md` (524줄)
- 코드 수정 금지. 분석만.

## 필수 읽기 (순서대로)
1. `ONTOLOGY-MASTER-REPORT.md` — 종합 보고서
2. `STATE.md` — 현재 상태
3. `CHANGELOG.md` — 전체 버전 이력
4. `config_ontology.py` — 온톨로지 상수 전체
5. `docs/01-design.md` — 초기 설계 문서

## 분석 항목 (전부 실행)

### A. 설계 일관성 검증 (태초 의도 vs 현재)
- 7가지 설계 원칙(다면분류/경계없는연결/살아있는강도/Becoming/데이터계층/도메인확장/다중관점)이 현재 코드에 실제로 구현되어 있는가?
- 각 원칙에 대해: 구현됨/부분구현/미구현 판정 + 근거
- "이색적 접합"이라는 태초 목표가 현재 시스템에서 실제로 발현되는 경로는 무엇인가?
- cross-domain 25.1%는 이 목표에 충분한가? 30%면 충분한가? 실제 목표는 뭐여야 하는가?

### B. 타입 시스템 비판
- 15개 타입이 정말 최적인가? 과도하거나 부족한 타입은?
- Correction(7개, visit=0, quality 0.579)은 왜 존재하는가? 삭제해야 하는가?
- Narrative(153개)는 정말 active여야 하는가? 전부 archive해도 되지 않는가?
- Identity(41개, visit 7.39)가 왜 Tier 1인가? 성격상 Tier 2가 아닌가?
- Observation(390개, 80.5% zero-visit)이 이렇게 방치되는 구조적 원인은?

### C. 검색 아키텍처 비판
- 3+1채널 RRF가 최선인가? 대안은?
- NDCG 0.425는 좋은 건가? 학술 기준으로 어느 수준인가?
- hit_rate 87.8%에서 나머지 12.2%가 실패하는 이유는?
- reranker weight 0.35는 최적인가? 어떻게 튜닝해야 하는가?
- SOURCE_BONUS가 obsidian -0.05인데, obsidian이 전체의 48%면 이 패널티가 너무 큰 것 아닌가?

### D. 성장 파이프라인 비판
- Obs→Signal→Pattern→Principle 승격 경로가 실제로 작동하는가?
- maturity 전부 0.0이면 이 필드의 존재 의의는?
- observation_count 전부 0이면 "Becoming" 원칙이 실현되고 있는가?
- auto_promote가 visit+edges+quality 기준인데, 이것이 "지식 성숙"의 올바른 프록시인가?
- 890건 대규모 승격(visit≥2, edges≥2, quality≥0.7)의 기준이 너무 관대하지 않은가?

### E. 전략 방향 비판
보고서 Section 8 "발견된 문제점"의 P0~P3 triage가 올바른가?
- P0-1 maturity가 정말 P0(즉시)인가? maturity 없이도 시스템이 돌아가고 있는데?
- P1-4 cross-domain 30%가 진짜 중요한가? 숫자 자체보다 연결의 질이 중요하지 않은가?
- 보고서에 없는 더 심각한 문제는 없는가?
- "다음 세션 작업 목록 15건"의 우선순위가 맞는가?

### F. DB 실측 기반 추가 분석 (SQL 실행)
```sql
-- 1. 프로젝트별 크로스도메인 에지 비율
SELECT n1.project, 
  COUNT(*) as total,
  SUM(CASE WHEN n1.project != n2.project THEN 1 ELSE 0 END) as cross,
  ROUND(100.0 * SUM(CASE WHEN n1.project != n2.project THEN 1 ELSE 0 END) / COUNT(*), 1) as pct
FROM edges e
JOIN nodes n1 ON e.source_id=n1.id
JOIN nodes n2 ON e.target_id=n2.id
WHERE e.status='active' AND n1.project != ''
GROUP BY n1.project ORDER BY total DESC LIMIT 10;

-- 2. 승격 경로 실제 작동 여부 (realized_as/crystallized_into 에지)
SELECT relation, COUNT(*) FROM edges 
WHERE status='active' AND relation IN ('realized_as','crystallized_into','triggered_by','abstracted_from')
GROUP BY relation;

-- 3. 가장 고립된 프로젝트 (다른 프로젝트와 연결 적은)
SELECT project, COUNT(DISTINCT id) as nodes,
  (SELECT COUNT(*) FROM edges e JOIN nodes n2 ON e.target_id=n2.id 
   WHERE e.source_id IN (SELECT id FROM nodes WHERE project=n.project) 
   AND n2.project != n.project AND e.status='active') as outgoing_cross
FROM nodes n WHERE status='active' AND project != '' 
GROUP BY project ORDER BY outgoing_cross ASC LIMIT 5;

-- 4. 실사용 대비 자동생성 에지 strength 비교
SELECT generation_method, COUNT(*), ROUND(AVG(strength),3), ROUND(AVG(co_retrieval_count),1)
FROM edges WHERE status='active' 
GROUP BY generation_method ORDER BY COUNT(*) DESC;
```

## 출력 형식
```markdown
# Claude 설계 리뷰 결과

## A. 설계 일관성
| 원칙 | 구현 상태 | 근거 |
|------|----------|------|

## B. 타입 시스템
| 판단 | 대상 | 이유 |
|------|------|------|

## C. 검색 아키텍처
| 질문 | 답변 | 근거 |
|------|------|------|

## D. 성장 파이프라인
| 판단 | 심각도 | 설명 |
|------|--------|------|

## E. 전략 비판
| 보고서 항목 | 동의/반박 | 이유 |
|------------|----------|------|

## F. DB 분석 결과
(SQL 결과 + 해석)

## 종합 제안
1. 보고서에서 가장 틀린 판단: ___
2. 보고서에 없는 가장 중요한 문제: ___
3. 우선순위 재배열 제안: ___
4. 구조적 전환이 필요한 곳: ___
```

**중요: 코드 수정하지 마라. git commit 하지 마라. 분석과 보고만.**
**비판적으로, 건설적으로. "좋다"만 하지 말고 "왜 이게 문제인지"를 말해라.**
