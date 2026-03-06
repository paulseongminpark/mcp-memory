# 세션A Index — 아키텍처 & 팔란티어 벤치마크

> Opus 4.6 | 2026-03-05 | mcp-memory v2.0 온톨로지 설계
> 기준: 3,230 nodes, 6,020 edges, 50 types, 48 relations, 실제 코드 기반.

## 파일 목록 + 핵심 결론

| # | 파일 | 주제 | 유형 | 핵심 결론 |
|---|------|------|------|----------|
| 1 | a-arch-1-palantir.md | Q1. 팔란티어 벤치마크 (스키마/인제스트 분리) | 설계 | type_defs/relation_defs 메타 테이블 분리 + remember()를 classify/store/link 3함수로 분리. API 하위호환 유지 |
| 2 | a-arch-2-validation-gate.md | Q2. 검증-게이트 학습 | 설계 | 4차원 검증(consistency/grounding/novelty/alignment). Phase 0: enrichment에 validated:false 즉시. LLM 없이 규칙 기반 우선 |
| 3 | a-arch-3-pkg-representation.md | Q3. PKG 접근 레벨 + 프로비넌스 | 설계 | access_level 4단계(private/session/shared/model) + provenance 테이블. action_log 먼저 → provenance 후속 |
| 4 | a-arch-4-ontology-versioning.md | Q4. 온톨로지 버전 관리 | 설계 | Wikidata 3-rank + GO obsolete 하이브리드. deprecate_type()/migrate_type() 워크플로우. 물리삭제 없음 |
| 5 | a-arch-5-archive-policy.md | Q5. 아카이브 정책 | 설계 | active→inactive→archived 3단계. L3+ 자동비활성 불가. recall시 inactive 노드 자동 발견(재공고화) |
| 6 | a-arch-6-cognitive-firewall.md | Q6. 인지적 방화벽 + 유지보수성 | 설계 | F1-F6 하드코딩 방화벽. L4/L5 content/edge/승격/decay 전부 보호. LAYER_PERMISSIONS RBAC |
| 7 | a-arch-7-energy-tracking.md | Q7. 에너지 추적 | 설계 | Prigogine 산일구조 → action_log 기반 세션 에너지(generative/consolidation/exploratory). enrichment 정책 자동화 |
| 8 | a-arch-8-subtraction.md | Q8. 제1원칙과 빼기 | 설계 | "빼기가 아니라 비활성화". Phase 0(데이터수집) → Phase 1(확실한 것) → Phase 4(enrichment 축소). action_log 선행 필수 |
| 9 | a-arch-9-action-log-deep.md | 심화1: action_log 정밀 설계 | 심화 | action_log 스키마 24 action types, 6개 코드 삽입지점, record() 구현, 세션 에너지 계산 구현체 |
| 10 | a-arch-10-firewall-code.md | 심화2: 방화벽 코드 삽입 지점 | 심화 | _check_firewall() 코드, update_node() 신규 필요, F1-F6 정확한 삽입지점, L4/L5 6개 전부 orphan — 수동 edge 복구 필수 |
| 11 | a-arch-11-subtraction-data.md | 심화3: 빼기 실행 (실제 DB 데이터) | 심화+데이터 | 19개 미사용 타입 즉시 deprecated(replaced_by 매핑), 6개 잘못된 관계 교정, 8개 super-type 구조, L1 과밀 58.5% |
| 12 | a-arch-12-actionlog-activation-merge.md | 심화4: action_log + activation_log 통합 | 심화 | D-5 activation_log를 action_log VIEW로 통합. node_activated 이벤트 + partial index. 별도 테이블 불필요 |
| 13 | a-arch-13-migration-sql.md | 심화5: type_defs/relation_defs 마이그레이션 SQL | 심화+SQL | 31 활성+19 deprecated 타입, 49 관계 INSERT, 6개 잘못된 관계 교정, 초기 스냅샷 v2.0-initial |
| 14 | a-arch-14-remember-refactor.md | 심화6: remember() 3함수 분리 실제 코드 | 심화+코드 | classify/store/link + ClassificationResult dataclass. API 100% 하위호환. 테스트 7개 시나리오 |
| 15 | a-arch-15-energy-enrichment.md | 심화7: 에너지 → enrichment 정책 자동화 | 심화+코드 | decide_enrichment_focus()가 daily_enrich.py Phase별 배치 크기 조절. 5가지 에너지 모드별 정책 |
| 16 | a-r3-16-migrate-script.md | Phase 0 단일 마이그레이션 스크립트 | 최종+코드 | 9단계 순차 실행, 각 단계 독립 트랜잭션+롤백, 멱등성 보장. action_log+meta+교정+JSON+VIEW+컬럼 |
| 17 | a-r3-17-actionlog-record.md | action_log.record() + 6개 삽입지점 | 최종+코드 | storage/action_log.py 신규, 25개 action taxonomy, 6개 파일 정확한 diff, 순환 import 방지 전략 |
| 18 | a-r3-18-remember-final.md | remember() 3함수 분리 완성 + F3 + action_log | 최종+코드 | classify/store/link + ClassificationResult + F3 L4/L5 자동 edge 차단 + 테스트 12개 |
| - | a-architecture.md | 원본 통합 파일 | 레퍼런스 | 분할 전 통합본 (플랜 파일과 동일 내용) |

## 상태

- [x] Q1. 팔란티어 벤치마크 — 스키마/인제스트 분리
- [x] Q2. 검증-게이트 학습
- [x] Q3. PKG Representation — 접근 레벨, 프로비넌스
- [x] Q4. 온톨로지 버전 관리
- [x] Q5. 아카이브 정책
- [x] Q6. 인지적 방화벽
- [x] Q7. 에너지 추적
- [x] Q8. 제1원칙과 빼기
- [x] 심화1: action_log 중심 설계
- [x] 심화2: 인지적 방화벽 코드 삽입지점
- [x] 심화3: 빼기 실행 계획 — 실제 DB 데이터
- [x] 심화4: action_log + activation_log 통합 (오케스트레이터 지시)
- [x] 심화5: type_defs/relation_defs 마이그레이션 SQL
- [x] 심화6: remember() 3함수 분리 실제 코드
- [x] 심화7: 에너지 → enrichment 정책 자동화
- [x] R3-16: Phase 0 단일 마이그레이션 스크립트 설계
- [x] R3-17: action_log.record() 구현 + 6개 삽입지점 diff
- [x] R3-18: remember() 3함수 분리 최종 — F3 방화벽 + action_log 통합

## 핵심 발견 (DB 진단)

- 31/50 타입 사용중, 19개 인스턴스 0 → 즉시 deprecated 가능
- L4/L5 6개 노드 전부 orphan (edge 0) → Paul 핵심 가치가 그래프에서 유리
- edge 95.2% enrichment 생성, remember() 자동 edge 0.5% → 에너지 불균형
- L1 과밀 58.5%, tier=2 미검증 77.5%
- 6개 잘못된 관계(enrichment E14 생성) → 교정 필요

## 구현 우선순위 종합

### 즉시 (1주 이내)

| # | 항목 | 근거 | 영향 |
|---|------|------|------|
| 1 | `action_log` 테이블 추가 | Q1+Q7+Q8의 기반 | 모든 후속 작업의 데이터 소스 |
| 2 | `type_defs` + `relation_defs` 테이블 추가 | Q1+Q4의 기반 | 메타-인스턴스 분리 시작 |
| 3 | L4/L5 방화벽 규칙 F1-F3 하드코딩 | Q6 | 정체성 보호 즉시 시작 |
| 4 | 사용 분포 진단 쿼리 실행 | Q8 Phase 0 | 빼기의 근거 확보 |

### 단기 (2-4주)

| # | 항목 | 근거 |
|---|------|------|
| 5 | remember() 3함수 분리 (classify/store/link) | Q1 |
| 6 | `access_level` 컬럼 + 기본 RBAC | Q3+Q6 |
| 7 | `provenance` 테이블 + 기록 시작 | Q3 |
| 8 | ValidationGate Phase 1 (grounding+novelty) | Q2 |
| 9 | 아카이브 정책 (inactive/archived 상태) | Q5 |
| 10 | 세션 에너지 측정 + context 출력 | Q7 |

### 중기 (1-3개월)

| # | 항목 | 근거 |
|---|------|------|
| 11 | 사용 0 타입/관계 deprecated 처리 | Q4+Q8 |
| 12 | super-type 구조화 | Q8 |
| 13 | ValidationGate Phase 2-3 | Q2 |
| 14 | ontology_snapshots + 버전 관리 | Q4 |
| 15 | 에너지 기반 enrichment 정책 | Q7 |

## 설계 원칙 요약

1. **메타-인스턴스 분리**: 타입/관계 정의는 별도 테이블. 인스턴스는 기존 구조 유지.
2. **비활성화 > 삭제**: 모든 "빼기"는 deprecated/inactive/archived. 물리 삭제 금지.
3. **하드코딩된 방화벽**: L4/L5 보호는 설정이 아니라 코드. 변경 시 코드 리뷰 필수.
4. **데이터 기반 결정**: action_log 없이 빼기 결정 금지. 최소 2주 수집 후.
5. **점진적 진화**: 기존 API 하위 호환 유지. remember()는 외부 인터페이스 불변.
6. **에너지 = 활동**: Prigogine의 산일 구조를 action_log로 구현.
