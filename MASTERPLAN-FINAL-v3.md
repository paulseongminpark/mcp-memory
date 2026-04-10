# mcp-memory Masterplan v3
> 2026-04-10
> 기준: `MASTERPLAN-DIAGNOSIS.md` + live DB 재검증

---

## 1. Executive Verdict

v2보다 더 명확해진 사실은 아래다.

1. growth field는 이미 상당 부분 채워졌다.
   - `maturity`는 거의 전량 non-zero
   - `observation_count`도 일부 핵심 타입에서 활성화됨

2. 지금 가장 위험한 것은 growth 미구현이 아니라 **truth drift + pruning bug + search blind spot**이다.

3. cross-domain은 이미 양적으로 충분하다.
   - 이제 문제는 "얼마나 만들었나"가 아니라 "실제로 쓰이는가"다.

4. 문서 stale가 모든 판단을 오염시키고 있다.
   - `ONTOLOGY-MASTER-REPORT.md`
   - `STATE.md`
   - 이전 masterplan들
   모두 현재 DB보다 뒤처져 있다.

즉 v3의 핵심은 이것이다.

> 복구할 것은 growth field가 아니라, 시스템이 스스로 믿는 현실이다.

---

## 2. 현재 사실

live DB 재검증 기준:

| 항목 | 현재값 | 판단 |
|---|---:|---|
| active nodes | 3,229 | 계속 변동 중 |
| active edges | 7,443 | 계속 변동 중 |
| avg maturity | 0.497 | dead field 아님 |
| zero maturity | 3 | 사실상 전량 채워짐 |
| nonzero observation_count | 653 | 부분 활성화 |
| null direction | 492 / 7,443 = 6.61% | 전역 장애 아님 |
| cross-domain | 32.08% | 양적 목표 초과 |
| gemini-enrichment | 982 | enum drift 지속 |
| vector-similarity | 200 | enum drift 신규/지속 |
| deleted edges | 4,242 | pruning/query semantics 중요 |
| FTS live schema | 5컬럼 | code intent와 불일치 |

주의:
- 수치는 계속 움직이고 있다.
- 따라서 phase 설계는 "정적 숫자"가 아니라 "동적 drift"를 다뤄야 한다.

---

## 3. 최종 문제 목록

## P0

### P0-1. FTS truth drift
- live `nodes_fts`는 아직 5컬럼
- 코드/설계는 7컬럼 의도
- `domains`, `facets`가 실제 검색 인덱스에 안 들어감

### P0-2. Pruning query bug
- `daily_enrich.py`의 pruning edge scan이 `WHERE status='active'` 없이 전체 edge를 읽음
- `deleted` edge가 connectivity guard 판단을 왜곡할 수 있음

### P0-3. Hebbian lost-update risk
- `_get_graph()`의 5분 TTL 캐시 기반 `old_strength` 사용
- 연속 recall에서 lost update 가능

### P0-4. Search bottleneck unknown
- 채널별 기여도 미측정
- reranker 한국어 적합성 미측정
- goldset 재적합 위험 미분리

### P0-5. Document cascade stale
- report stale
- state stale
- masterplan stale
- stale 문서가 다음 의사결정을 다시 오염시킴

## P1

### P1-1. Growth semantics ambiguity
- `maturity`가 채워졌지만 canonical meaning이 고정되지 않음
- `get_becoming`과 `analyze_signals`가 다른 maturity 개념을 사용

### P1-2. Enum drift
- `gemini-enrichment`
- `vector-similarity`
- 필요 시 `quarantined` status도 vocabulary 검토

### P1-3. Cross-domain quality/usage mismatch
- 양은 충분
- 활용률과 정밀도는 미약

### P1-4. Strength semantics mismatch
- 일부 학습은 반영되지만, 대다수 edge는 여전히 generation-biased signal

---

## 4. v3 Priorities

최종 우선순위는 아래 순서다.

1. Reporting/Truth Recovery
2. Pruning bug fix
3. FTS rebuild
4. Enum drift fix
5. Hebbian integrity fix
6. Search diagnostics
7. Growth semantics audit
8. Promotion rewrite
9. Retrieval refactor
10. Cross-domain quality upgrade

v2와의 차이:
- `WS7`을 사실상 맨 앞으로 당김
- `WS6`은 양적 확대가 아니라 quality governance로 고정
- `WS3/WS4`는 복구가 아니라 audit/canonicalization

---

## 5. Workstreams v3

## WS0. Reporting & Truth Recovery

목표:
- stale cascade를 끊는다.

원자 작업:
- `WS0-A1` DB audit 스크립트 표준화
- `WS0-A2` `STATE.md` current metrics 자동 생성 강제
- `WS0-A3` master report appendix 자동 생성
- `WS0-A4` review/masterplan 입력 수치가 generated snapshot만 쓰도록 규칙화
- `WS0-A5` ontology/storage/report SoT 문서 확정

종료 기준:
- 사람이 수동으로 active counts를 적지 않음
- stale 문서가 다음 planning 입력이 되지 않음

## WS1. Edge Integrity

목표:
- edge 관련 실제 버그를 먼저 없앤다.

원자 작업:
- `WS1-A1` pruning scan에 `WHERE status='active'` 추가
- `WS1-A2` pruning report와 실제 DB action semantics 일치화
- `WS1-A3` `archive`/`delete` naming 정리
- `WS1-A4` orphan edge ref 1건 조사/정리
- `WS1-A5` edge status vocabulary 정리
  - `active`
  - `deleted`
  - `archived`
  - `quarantined` 여부 결정

종료 기준:
- pruning이 active edge만 기준으로 동작
- edge status semantics가 모호하지 않음

## WS2. FTS & Schema Recovery

목표:
- FTS truth drift 해소

원자 작업:
- `WS2-A1` live `nodes_fts` schema snapshot
- `WS2-A2` rebuild migration 작성
- `WS2-A3` trigger recreate routine 작성
- `WS2-A4` `domains`, `facets` backfill rebuild 실행
- `WS2-A5` active-only FTS 인덱싱 전략 검토

종료 기준:
- FTS schema가 code intent와 일치
- domain/facet 검색 가능

## WS3. Enum & Policy Cleanup

목표:
- config vocabulary와 live DB vocabulary를 맞춘다.

원자 작업:
- `WS3-A1` `gemini-enrichment` 추가
- `WS3-A2` `vector-similarity` 추가
- `WS3-A3` `GENERATION_METHOD_PENALTY` 정책 정의
- `WS3-A4` `GRAPH_EXCLUDED_METHODS` 재검토
- `WS3-A5` generation_method audit를 CI/verify에 포함

종료 기준:
- generation_method drift 0

## WS4. Hebbian & Strength Integrity

목표:
- strength를 usage-aware signal로 만든다.

원자 작업:
- `WS4-A1` `_hebbian_update()` atomic delta update
- `WS4-A2` graph cache invalidation/write-through
- `WS4-A3` repeated recall lost-update regression test
- `WS4-A4` strength lifecycle 정의
  - initial value
  - usage increment
  - decay
  - dormant penalty
- `WS4-A5` generation_method별 usage coverage report 작성

종료 기준:
- 연속 recall에서 lost update 없음
- strength가 생성 confidence만 반영하지 않음

## WS5. Search Diagnostics

목표:
- 병목을 설명 가능한 상태로 만든다.

원자 작업:
- `WS5-A1` channel attribution 측정
- `WS5-A2` query bucket별 failure 분석
- `WS5-A3` reranker on/off 비교
- `WS5-A4` reranker weight sweep
- `WS5-A5` 한국어 query subset 평가
- `WS5-A6` goldset drift audit

종료 기준:
- 검색 개선 전에 무엇을 고칠지 숫자로 설명 가능

## WS6. Growth Semantics Audit

목표:
- 이미 채워진 growth field의 의미를 canonicalize한다.

원자 작업:
- `WS6-A1` `maturity` 업데이트 경로 추적
- `WS6-A2` `observation_count` 업데이트 경로 추적
- `WS6-A3` `get_becoming`의 maturity 정의 정리
- `WS6-A4` `analyze_signals`의 maturity 정의 정리
- `WS6-A5` `maturity` vs `readiness_score` naming 결정
- `WS6-A6` type별 분포 보고서 작성

종료 기준:
- growth field가 "값은 있는데 뜻이 다른" 상태를 벗어남

## WS7. Promotion Rewrite

목표:
- promotion rule을 canonical semantics 위로 올린다.

원자 작업:
- `WS7-A1` current auto_promote 기준 분포 분석
- `WS7-A2` validated bulk 승격 기준 재검토
- `WS7-A3` canonical score 기반 promotion policy 설계
- `WS7-A4` multi-target promotion 정책 확정
- `WS7-A5` promotion audit report 작성

종료 기준:
- `validated`가 다시 epistemic distinction을 가짐

## WS8. Retrieval Refactor

목표:
- retrieval hot path를 단순화하고 실험 가능하게 만든다.

원자 작업:
- `WS8-A1` batch node fetch 도입
- `WS8-A2` candidate fetch N+1 제거
- `WS8-A3` 2-stage retrieval 명세
- `WS8-A4` graph를 feature stage로 이전
- `WS8-A5` source penalty 재설계

종료 기준:
- retrieval 구조가 명확해짐

## WS9. Cross-Domain Quality Upgrade

목표:
- cross-domain을 usage/quality governance 대상으로 전환

원자 작업:
- `WS9-A1` cross-domain KPI 교체
  - utilization
  - precision
  - large-project balance
- `WS9-A2` `gemini-enrichment` direction backfill
- `WS9-A3` `gemini-enrichment` usage audit
- `WS9-A4` candidate generation 정책 재설계
- `WS9-A5` provenance metadata 추가
- `WS9-A6` `remember()` 단계 lightweight cross-project suggestion 설계

종료 기준:
- cross-domain quantity KPI 졸업

---

## 6. v3 Phase Order

## Phase 0. Truth Freeze

- `WS0-A1`
- `WS0-A2`
- `WS0-A3`
- `WS0-A4`

## Phase 1. Integrity Hotfix

- `WS1-A1`
- `WS1-A2`
- `WS1-A3`
- `WS2-A1`
- `WS2-A2`
- `WS3-A1`
- `WS3-A2`

## Phase 2. Learning Fix

- `WS4-A1`
- `WS4-A2`
- `WS4-A3`
- `WS4-A4`
- `WS4-A5`

## Phase 3. Diagnostics

- `WS5-A1`
- `WS5-A2`
- `WS5-A3`
- `WS5-A4`
- `WS5-A5`
- `WS5-A6`

## Phase 4. Growth Audit

- `WS6-A1`
- `WS6-A2`
- `WS6-A3`
- `WS6-A4`
- `WS6-A5`
- `WS6-A6`

## Phase 5. Promotion

- `WS7-A1`
- `WS7-A2`
- `WS7-A3`
- `WS7-A4`
- `WS7-A5`

## Phase 6. Retrieval

- `WS8-A1`
- `WS8-A2`
- `WS8-A3`
- `WS8-A4`
- `WS8-A5`

## Phase 7. Cross-Domain

- `WS9-A1`
- `WS9-A2`
- `WS9-A3`
- `WS9-A4`
- `WS9-A5`
- `WS9-A6`

---

## 7. 지금 바로 할 3개

1. `STATE.md` / metrics generation 자동화
2. pruning `WHERE status='active'` hotfix
3. generation_method drift 정리

이 셋이 끝나야 나머지 판단이 다시 안 썩는다.

---

## 8. Final Line

v3의 핵심은 이 문장 하나다.

> 지금 필요한 것은 growth를 더 만드는 일이 아니라, 이미 움직이는 시스템이 무엇을 사실로 취급하는지 고정하는 일이다.

