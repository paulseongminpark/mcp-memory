# E2E Review — Codex (gpt-5.3-codex xhigh)

## Summary
- Overall completeness: 48/100
- Critical issues: 8
- Major issues: 11
- Minor issues: 7

## Critical Issues
### C-1: Phase 2/4 호출 시그니처 불일치로 런타임 즉시 실패
- File: scripts/daily_enrich.py:133
- Expected (from spec): 오케스트레이터가 E18/E19/E21/E22를 정상 호출하여 Phase 2,4가 수행되어야 함.
- Actual (in code): `run_e21_all(limit=30)`, `run_e22_all(limit=40)`, `run_e18_all(limit=30)`, `run_e19_all(limit=30)` 호출. 그러나 callee는 limit 인자를 받지 않음 (`scripts/enrich/graph_analyzer.py:665,681,737,761`).
- Impact: TypeError로 Phase 2/4가 중단되어 E18/E19/E21/E22가 E2E로 실행되지 않음.

### C-2: E7(embedding_text) 결과가 저장/반영되지 않음
- File: scripts/enrich/node_enricher.py:356
- Expected (from spec): E7 결과로 Chroma 문서/임베딩 업데이트 + `enrichment_status` 반영.
- Actual (in code): E7에서 `_apply`가 `pass`이며, 업데이트가 없으면 DB write 블록 자체가 실행되지 않음 (`scripts/enrich/node_enricher.py:296`).
- Impact: provisional embedding이 최종 embedding으로 교체되지 않고, E7 단독 실행 시 완료 상태도 기록되지 않음.

### C-3: v2 스키마가 기본 init_db에 반영되지 않음
- File: storage/sqlite_store.py:23
- Expected (from spec): nodes/edges/FTS5가 v2 컬럼(요약·개념·품질·enrichment_status·direction/base_strength 등)을 기본 제공.
- Actual (in code): init_db는 v1 컬럼만 생성. v2 확장은 `scripts/migrate_v2.py`에만 존재.
- Impact: 신규 DB에서 마이그레이션 미실행 시 enrichment/신규 도구가 컬럼 오류로 동작 불가.

### C-4: 필수 구현 파일 다수 누락
- File: storage/chroma_store.py
- Expected (from spec): 지정된 파일 경로/구조가 존재해야 함.
- Actual (in code): `storage/chroma_store.py`, `tools/relate.py`, `scripts/enrich/daily_enrich.py`, `scripts/enrich/type_enricher.py`, `scripts/enrich/summarizer.py` 없음.
- Impact: 스펙 추적성 붕괴, 문서 기준 E2E 검증/운영 자동화 경로 단절.

### C-5: E24가 오케스트레이션에 연결되지 않음
- File: scripts/enrich/graph_analyzer.py:810
- Expected (from spec): E1~E25 전 작업이 daily pipeline에서 연결 실행.
- Actual (in code): `run_e24_all()`은 정의만 있고 호출 지점 없음.
- Impact: 병합 후보 탐지(E24) 미실행으로 중복/차이 관리 루프가 완성되지 않음.

### C-6: 온톨로지 스키마가 v2 설계와 불일치
- File: ontology/schema.yaml:7
- Expected (from spec): 45 활성 타입(+예약 7), 48 관계 타입.
- Actual (in code): schema.yaml은 26 node_types, 33 relation_types(v1). `remember()`는 이 스키마로 타입 검증 수행 (`tools/remember.py:18`).
- Impact: v2 타입/관계 분류 및 승격 경로가 설계와 구조적으로 충돌.

### C-7: MCP 인터페이스에 수동 관계 생성(연결) 경로 부재
- File: server.py:39
- Expected (from spec): relate/connect 계열 MCP 도구로 수동 edge 생성 지원.
- Actual (in code): `tools/relate.py` 및 대응 MCP 등록 없음. 또한 `remember` 시그니처는 v2 다면 필드(layer/secondary/domains/facets/tier)를 직접 받지 않음.
- Impact: 설계된 실시간 경로(경로1)에서 핵심 메타/관계를 API 인터페이스로 완전 전달 불가.

### C-8: 리좀적 검색 핵심 메커니즘(헤비안/감쇠/유효강도)이 미구현
- File: storage/hybrid.py:40
- Expected (from spec): effective_strength 기반 전파, frequency 증가, decay, tier/layer 페널티, 탐험 모드.
- Actual (in code): 단순 BFS 이웃 보너스(`GRAPH_BONUS`) + RRF + enrichment 보너스만 사용. frequency/decay 갱신 코드 없음.
- Impact: v2 검색 동학의 핵심 가치(성장형 연결/편향 제어/폭발 제어)가 동작하지 않음.

## Major Issues
### M-1: analyze_signals()가 E23(o3 추론) 경로를 사용하지 않음
- File: tools/analyze_signals.py:10
- Expected (from spec): analyze_signals 내부에서 E23 성격의 깊은 추론 기반 승격 분석.
- Actual (in code): 태그/개념/도메인 겹침 + 휴리스틱 maturity 계산만 수행.
- Impact: 승격 판단 정밀도 및 근거 품질 저하.

### M-2: Phase 5 범위가 스펙 대비 축소
- File: scripts/daily_enrich.py:237
- Expected (from spec): Phase5에 이색적 접합 최종 판단, 승격 논증, 온톨로지 메타검증 포함.
- Actual (in code): `ga.run_e23_all()`만 실행.
- Impact: 깊은 추론 단계의 2개 핵심 산출물이 누락.

### M-3: Phase 6(codex_review) 미연결
- File: scripts/daily_enrich.py:10
- Expected (from spec): daily_enrich 실행 흐름에 Codex 검증 단계 포함.
- Actual (in code): 주석에 "separate"만 있고 실제 phases 목록엔 없음 (`scripts/daily_enrich.py:327`).
- Impact: 프롬프트/코드/온톨로지 일일 검증 루프 단절.

### M-4: E13 클러스터링 전략에서 Chroma 유사도 경로 미구현
- File: scripts/enrich/relation_extractor.py:260
- Expected (from spec): Chroma distance 기반 + key_concept + facet 3전략.
- Actual (in code): key_concept, facet, random fallback만 수행.
- Impact: 토큰 낭비 증가 및 크로스도메인 edge 품질 저하.

### M-5: RPM/TPM 리밋은 기록만 하고 실제 제어를 안 함
- File: scripts/enrich/token_counter.py:53
- Expected (from spec): 모델별 RPM/TPM 한도 기반 adaptive throttling.
- Actual (in code): rpm/tpm 계산 함수는 있으나 임계치 기반 차단/슬립 정책 없음(429 발생 후 backoff 중심).
- Impact: S9 완화 미흡, burst 시 rate-limit 취약.

### M-6: Atomicity/재시작 복구가 노드 단위로 완결되지 않음
- File: scripts/enrich/node_enricher.py:382
- Expected (from spec): 작업 상태가 크래시에도 안정적으로 축적되어 멱등 재실행 가능해야 함.
- Actual (in code): 노드 update에서 즉시 commit하지 않아 phase 단위 크래시 시 진행분 유실 가능.
- Impact: C6/S4 완화가 부분적.

### M-7: 승격 이력 저장 위치/경로가 설계와 불일치
- File: tools/promote_node.py:40
- Expected (from spec): 승격 이력/성숙도 체계가 일관 컬럼 체계로 관리되고 상위 승격 경로가 충족돼야 함.
- Actual (in code): `promotion_history`를 metadata JSON에만 저장, `VALID_PROMOTIONS` 경로도 제한적 (`config.py:107`).
- Impact: 장기 Becoming 추적 및 상위 레이어 승격 확장성 저하.

### M-8: remember()-E7 연동이 설계 목적(최종 embedding 교체)을 달성하지 못함
- File: tools/remember.py:27
- Expected (from spec): provisional embedding 이후 E7 결과로 재임베딩/교체.
- Actual (in code): provisional 플래그만 저장되고 교체 경로 없음.
- Impact: S5/C7 완화 실질 미완성.

### M-9: recall 랭킹이 일부 가중치만 반영
- File: storage/hybrid.py:68
- Expected (from spec): tier, edge 유효강도, 전파 제약을 포함한 다요소 랭킹.
- Actual (in code): `quality_score*0.2 + temporal_relevance*0.1`만 추가.
- Impact: 검색 품질/안정성/편향제어 목표 미달.

### M-10: MCP 도구 수는 13개지만 스펙 도구셋과 구성 불일치
- File: server.py:38
- Expected (from spec): v2 도구셋 기준(search_nodes/get_relations/get_session/connect 포함)과 일치.
- Actual (in code): legacy 성격 도구(suggest_type/visualize/dashboard/ontology_review/ingest_obsidian) 포함, 일부 핵심 도구 부재.
- Impact: 문서-구현 괴리로 운영/자동화 혼선.

### M-11: CRUD 계층 우회가 많아 데이터 일관성 리스크 증가
- File: storage/sqlite_store.py:91
- Expected (from spec): 스키마 변화(v2 컬럼, correction_log 포함)에 맞는 저장소 API 일원화.
- Actual (in code): enrichment 도구들이 raw SQL로 직접 조작, sqlite_store는 v1 중심 CRUD만 제공.
- Impact: 스키마 진화 시 회귀 위험 상승.

## Minor Issues
### m-1: 사용되지 않는 phase_limit 변수
- File: scripts/daily_enrich.py:57
- Expected (from spec): phase budget 제어 로직에 사용.
- Actual (in code): 계산만 하고 미사용.
- Impact: 유지보수 혼선.

### m-2: `_last_inserted` 통계 참조 무효
- File: scripts/daily_enrich.py:94
- Expected (from spec): 실제 삽입 edge 수 집계.
- Actual (in code): RelationExtractor에 `_last_inserted` 없음.
- Impact: 리포트 정확도 저하.

### m-3: get_becoming 도메인 필터가 JSON 파싱 없이 문자열 포함 검사
- File: tools/get_becoming.py:32
- Expected (from spec): 정확한 도메인 배열 매칭.
- Actual (in code): substring 매칭.
- Impact: 오탐/누락 가능.

### m-4: SQLite `NULLS LAST` 호환성 리스크
- File: tools/get_becoming.py:24
- Expected (from spec): SQLite 버전 간 안정 동작.
- Actual (in code): `ORDER BY ... NULLS LAST` 사용.
- Impact: 환경별 SQL 오류 가능.

### m-5: PromptLoader가 템플릿 누락 변수 오류를 삼킴
- File: scripts/enrich/prompt_loader.py:46
- Expected (from spec): 프롬프트 변수 누락 시 명시적 실패/로그.
- Actual (in code): KeyError를 무시하고 원문 반환.
- Impact: 조용한 품질 저하.

### m-6: recall에서 미사용 import 존재
- File: tools/recall.py:5
- Expected (from spec): 불필요 코드 제거.
- Actual (in code): `get_relation_path` import 후 미사용.
- Impact: 코드 위생 저하.

### m-7: E25 타입 샘플 명명 불일치
- File: scripts/enrich/graph_analyzer.py:617
- Expected (from spec): 온톨로지 타입 명명 일관성(`Mental Model`).
- Actual (in code): `MentalModel` 표기.
- Impact: 프롬프트 해석 혼선 가능.

## Completeness Matrix
| Step | Description | Status | Notes |
|------|-------------|--------|-------|
| 1 | `migrate_v2.py` (C4, C8, S8, S10) | Partial | 스크립트 존재. 하지만 `init_db`와 기본 스키마가 분리되어 신규 환경 자동 보장 안 됨. |
| 2 | `config.py` enrichment 설정 | Mostly Done | 모델/예산/allowlist/가중치 반영됨. |
| 3 | `token_counter.py` | Partial | usage/429/backoff는 있음. RPM/TPM 임계치 기반 실제 제어 부재. |
| 4 | `node_enricher.py` (E1-E12) | Partial | E1-E12 메서드 존재. E7 저장/재임베딩/상태기록 결함. |
| 5 | `relation_extractor.py` (E13-E17) | Partial | E13-E17 구현. Chroma 전략 누락, 일부 저장소 계약 의존성 큼. |
| 6 | `graph_analyzer.py` (E18-E25) | Partial | E18-E25 정의됨. E24 미연결, 일부 결과 영속화/통합 약함. |
| 7 | `daily_enrich.py` 오케스트레이션 | Failed/Partial | Phase2/4 시그니처 오류로 실질 실패. Phase6 미연결. |
| 8 | `codex_review.py` | Done (Standalone) | 스크립트 구현됨. daily pipeline에서 자동 호출 안 함. |
| 9 | 프롬프트 25개 + 표본 테스트 | Partial | 25개 YAML 존재. 50표본 회귀 게이트가 파이프라인에 결합되지 않음. |
| 10 | MCP 도구 통합 (S5) | Partial | 점수 가중치/provisional 플래그는 반영. relate/connect 및 v2 실시간 필드 인터페이스 미흡. |

## Conclusions
- 현재 구현은 "구성요소 존재" 수준은 높지만, 오케스트레이션 연결과 계약 정합성에서 치명 결함이 있어 설계 문서 기준 E2E 파이프라인으로 보기는 어렵습니다.
- 최우선 수정 순서: `C-1`(시그니처), `C-2`(E7 실동작), `C-3`(기본 스키마 정합), `C-5`(E24 연결), `C-6`(온톨로지 v2 동기화), `C-8`(리좀 검색 메커니즘)입니다.
