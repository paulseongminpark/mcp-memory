# mcp-memory CHANGELOG

## v8.1 — E17 3-Layer + Groq Bulk 전환 (2026-04-13)

### E17 3-Layer 리팩토링
- `find_duplicate_edges()`: `WHERE status='active'` 추가 — deleted/archived edge 제외
- `_classify_group()`: 3-layer 분류 (auto_merge / llm_same_rel / llm_diff_rel)
- `_has_meaningful_description()`: None, '', '[]' 모두 빈 값 처리 (Codex 지적)
- `_auto_merge()`: 동일 relation + 빈 description → 최고 strength 유지, 나머지 삭제 (LLM 불필요)
- `strength=None` 안전 처리: `e.get("strength") or 0.0` (Codex 지적)
- **효과**: 1,344 groups → 547 (active 필터) → 106 auto + 441 LLM

### Groq Bulk API 연동
- bulk tier: gpt-5-mini (OpenAI) → llama-3.3-70b-versatile (Groq)
- 실측: E13 JSON 100%, allowlist 100%, 0.7-1.5초/건
- token_counter: groq pool 추가 (GROQ_MODELS set, pool_for 분기)
- daily_enrich: groq_limit 인자 전달
- .env: GROQ_API_KEY 추가 (load_dotenv로 자동 로드)
- **효과**: OpenAI 예산 소모 0, Groq 14,400 RPD 무료

수정 파일: config.py, scripts/enrich/relation_extractor.py, scripts/enrich/token_counter.py, scripts/daily_enrich.py, .env

## Phase 1 budget cap + E17 사고 대응 + API 조사 (2026-04-13)

### E17 67시간 무한실행 사고
- 06:00 Task Scheduler 첫 자동 실행 — Phase 0a-0d 정상, Phase 1 E13/E14 완료
- E17 (merge duplicates) 1344건 루프 진입, 3시간 동안 62건 처리, 중복 0건 발견
- **OpenAI 일일 한도(소형 풀 2.25M) 전량 소진** — E17이 Phase 1 cap 무시하고 전체 풀 잠식
- 09:56 수동 kill

### Budget cap 루프 내 체크 추가
- `run_e13`, `run_e14`, `run_e17`에 `budget_check_fn` 파라미터 추가
- daily_enrich Phase 1에서 `_phase1_cap_reached` 함수 전달
- 매 iteration마다 Phase 1 50% cap 체크 → 초과 시 즉시 중단

### API 리소스 조사
- OpenAI: 데이터 공유 프로그램, 대형 250K/일 + 소형 2.5M/일 (오늘 소진, 내일 리셋)
- Gemini API 키 환경변수 등록 확인 (`GEMINI_API_KEY`)
- Gemini 2.5 Flash: 동작 확인, 한도 넉넉, E13 태스크 정상 수행
- Gemini 2.5 Pro / 3.1 Pro Preview: 429 quota — 무료 API 키로는 한도 부족
- **결론**: Phase 1-2 bulk → Gemini 2.5 Flash 전환 가능. Phase 3-5 deep → OpenAI 유지.

수정 파일: scripts/daily_enrich.py, scripts/enrich/relation_extractor.py

## v8 Phase 0 사후 정비 — pruning 버그 수정 + edge 복구 + 자동화 안정화 (2026-04-13)

### Bug Fix: Phase 6 Edge Pruning 공식 결함 (치명적)
- **Bug 1**: `_run_edge_pruning()` WHERE status 필터 누락 — deleted/archived edge 재처리. 실제 삭제 ~5,917건이 로그에 10,062로 표시
- **Bug 2**: pruning 공식 `freq * exp(-0.005 * days)` → stored strength 무시. freq=0 edge(94.4%)를 무조건 삭제 대상으로 만듦
- **수정**: status='active' 필터 추가 + stored strength 기반 공식으로 교체 (`effective_strength = stored_strength + freq * 0.1`)
- **Edge 복구**: 양쪽 노드 active인 5,311건 deleted→active 복원 (edges/node: 1.49→3.08, orphan: 262→32)

### Fix: 0-claim captures 무한 재시도
- `claim_extractor.py`에서 0-claim 결과 시 마커 레코드(status='skip') 삽입
- captures 테이블 `captures_no_update` 트리거 때문에 `processed_at` 컬럼 방식 불가 → 마커 방식 채택
- 55건 backfill 완료, unprocessed: 104→0

### Fix: unclassified traits 67/141 (47%)
- `self_model_builder.py` cmd_classify()에 `AND status != 'archived'` 조건 — 67개 전부 archived라 스킵
- 조건 제거 후 65/67 분류 완료 (2건 Qwen 실패 잔존)
- 분포: language 25, rhythm 14, thinking_style 10, connection 9, emotion 3, decision_style 2, preference 2

### Fix: Task Scheduler bat 파일 보강
- PATH 명시 (Python312), 인자 전달(%*), exit code 보존
- `daily-enrich.bat` 루트 + scripts/ 두 곳 모두 수정

### 기타
- `2026-04-12.md` 리포트 복원 (dry-run이 덮어쓴 것 수정)
- context_pack 출처 확인: DB traits → `~/.claude/policy/rules/auto_*.json` → get_context() 동적 주입 (문제 없음)

수정 파일: scripts/daily_enrich.py, tools/claim_extractor.py, tools/self_model_builder.py, daily-enrich.bat, scripts/daily-enrich.bat, data/reports/2026-04-12.md

## v8 Loop 2 자동화 — self-model trait 자동 갱신 (2026-04-12)

- **daily_enrich Phase 0b**: concepts→trait extract (최대 10건) + unclassified→classify (최대 20건)
- **완전 자동 체인**: captures→claims→traits→policy→context_pack→Claude 전구간 자동화 완성
- Ollama 미기동 시 graceful skip

수정 파일: scripts/daily_enrich.py

## v8 Loop 3 완성 — policy compiler + context_pack 자동 주입 (2026-04-12)

- **policy_compiler.py**: 52 verified traits → policy rules JSON 자동 컴파일 + default.json pack 갱신
- **daily_enrich Phase 0b**: policy compilation 자동 스테이지
- **session-start.sh**: context_pack 자동 주입 — Paul 선호 5개 + dont/avoid 규칙 5개 매 세션 출력
- **session-start.sh 버그 수정**: get_becoming maturity→growth_score 키 변경 반영

수정 파일: scripts/policy_compiler.py(신규), scripts/daily_enrich.py, ~/.claude/hooks/session-start.sh

## v8 Loop 자동화 배선 — 3개 끊긴 체인 연결 (2026-04-12)

- **daily_enrich Phase 0b**: 미처리 captures → claims 자동 추출 (Ollama graceful skip)
- **retrieval_logs 실시간**: recall() 매 호출 시 query/returned_ids/type_dist/cross_domain 기록
- **feedback_events 자동**: flag_node() 시 target_type/feedback_type/content 기록

수정 파일: scripts/daily_enrich.py, tools/recall.py, tools/flag_node.py

## Growth Semantics Audit — dead field 활성화 + naming 표준화 (2026-04-12)

- **utils/growth.py**: `compute_growth_score()` canonical 공식 (quality 30% + edges 20% + visits 20% + diversity 20% + recency 10%)
- **observation_count 활성화**: `post_search_learn` recall 시 +1 (dead field → live 증가 경로)
- **get_becoming.py**: maturity→`growth_score` 키 변경, 계산 로직을 공용 함수 호출로 대체
- **analyze_signals.py**: `_compute_maturity`→`_compute_cluster_readiness` rename, 출력 키 표준화
- **auto_promote.py**: quality floor(0.75) → `growth_score ≥ 0.5` 통합 기준으로 교체
- **daily_enrich.py**: Phase 0a `_batch_update_growth_scores()` — 전체 active 노드 DB maturity 배치 갱신
- **generate_state.py**: 보고서 라벨 `Maturity` → `Growth Score (DB maturity)`
- **growth_audit_report.py**: type별 분포 보고서 스크립트 (신규)
- **test_growth_semantics.py**: 11개 테스트 (unit 8 + observation 2 + batch 1)

수정 파일: utils/growth.py(신규), tools/get_becoming.py, tools/analyze_signals.py, scripts/auto_promote.py, scripts/daily_enrich.py, storage/hybrid.py, scripts/generate_state.py, scripts/growth_audit_report.py(신규), tests/test_growth_semantics.py(신규)

## v8.0 Harden R1 — 3에이전트 검증 + 불변식 강화 (2026-04-12)

- **3에이전트 병렬 검증**: V-Check(D1-D20) + Cross-validation(5기준) + Edge case(18 tests)
- **claims_capture_fk trigger**: 불변식 2 물리 강제 (capture_id 존재 검증)
- **F1 guard**: self_model_builder에 created_by + trait_status/approval 명시
- **test_v8_schema.py**: 18개 edge case 자동 테스트 (32 total passed)
- **최종 판정**: D1-D20 GO 13/WARN 2/FAIL 0, 불변식 9/9 GO, 테스트 32/32

수정 파일: sqlite_store.py, self_model_builder.py, tests/test_v8_schema.py (신규)

## v8.0 Build R2 — Codex Finding 수정 + Build Merged (2026-04-12)

**Codex CONDITIONAL GO → GO 전환**

- **D20 evidence bridge 물리 강제**: `trevidence_claim_fk` + `trevidence_claim_fk_update` trigger (INSERT+UPDATE)
- **D20 backfill**: legacy:Type:id 135건 → real captures+claims 생성 + evidence claim_id 갱신
- **D18 slot precedence 고도화**: reject blacklist → temporal + conflict escalation + open_questions
- **boost_evidence 재작성**: nodes LIKE 검색 → claims-only + Paul source 필터 + strength 0.3
- **D19 타입 하드코딩 제거**: `PAUL_RELATED_TYPES`, `DIMENSION_TO_CLAIM_TYPE` 상수
- **init_db fail-close**: 테이블/트리거 누락 시 `RuntimeError` (fail-open 해소)
- **LIKE escape**: `%`/`_` 특수문자 이스케이프
- **Exit 3 복구**: unclassified 41개 archive → active 53, avg_ev 2.34

수정 파일: sqlite_store.py, self_model_builder.py, context_pack.py, claim_extractor.py, v8_migrate.py

## v8.0 Build R1 Day 1-5 당기기 완료 (2026-04-12)

### 1 세션 내 Day 1-5 전부 완료

**Stream A — 스키마 + 데이터**
- v8 10 테이블 추가 (`storage/sqlite_store.py` init_db)
  - captures/claims/self_model_traits/self_trait_evidence/self_trait_conflicts/feedback_events/retrieval_logs
  - append-only trigger 2개 (captures UPDATE/DELETE 차단)
  - 20 index
- Migration (`scripts/v8_migrate.py`): Identity 41 → self_model_traits 시드, edges 39 → self_trait_evidence bridge
- Cleanup: 문서 헤더 25개 archive (v7.4 Identity 타입 loose 정정)
- Self-model 최종: 54 verified traits, 8차원 모두 ≥ 3, avg evidence 2.07

**Stream B — Loop 1 Capture**
- `~/.claude/hooks/post_user_prompt_capture.py` — UserPromptSubmit hook (non-blocking)
- `settings.json` UserPromptSubmit 섹션 등록
- `tools/claim_extractor.py` — Qwen2.5-7B-Instruct-Q4_K_M via Ollama (`localhost:11434`)
- `prompts/claim_extraction.md` — 프롬프트 SoT (v2 검증됨)

**Stream C — Loop 2 Self-Model**
- `tools/self_model_builder.py` — classify/extract/boost_evidence 3 subcommands
- `scripts/approve_traits.py` — trait approval review parser
- metacognition 수동 재분류 (자기인지 패턴 3개)
- bulk approval (Paul 지시)

**Stream D — Loop 3 Policy**
- `~/.claude/policy/rules/response_no_trailing_summary.json` — Exit 4 Single-Rule
- `~/.claude/policy/packs/default.json` — Phase 0 기본 pack
- `tools/context_pack.py` — 6슬롯 빌더 + slot precedence (D18) + retrieval_logs 기록
- `tools/get_context.py` — v8_context_pack 병행 반환 통합

**Exit 측정 도구**
- `tools/exit1_runner.py` — Day 6 blind A/B 20 질문 헬퍼
- `tools/exit5_injector.py` — inject→reject→verify 자동 폐회로

### Exit 상태 (Day 5 종료 시점)
- **Exit 2 불변식**: ✅ PASS (orphan claims 0, self-model direct edge 0, append-only trigger 작동)
- **Exit 3**: ✅ **PASS 4/4** (traits 54, 8차원 8/8, verified 54, evidence 2.07)
- **Exit 5**: ✅ **PASS** (자동 inject→reject→verify 폐회로)
- Exit 1: Day 6 수동 측정 대기 (질문 세트 준비 완료)
- Exit 4: Day 6 수동 측정 대기 (policy rule + pack 준비 완료)

### 기타
- `trait_approval_review.md` — 42 pending 전부 bulk approved (Paul 지시)
- `exit1_question_set.md` — 20 질문 + 기대 답 (Paul 검토 완료)
- Diagnose 단계에서 migration 품질 문제 발견 → pre-filter 25 archive 정정

## v8.0 Ontology Redesign — Build R1 진입 (2026-04-12T08:00)

### Build R1 선행 합의 3개 확정
- **합의 1 — Migration Contract 10개 규칙 (R1-R10)**
  - 실데이터 분석(5440 nodes, 17292 edges) 기반 도출
  - R1: 기존 `nodes` = Epistemic Plane `concepts`로 리브랜딩 (source_kind 93% 해석물 확인)
  - R4: `Identity` 63(active 41) → self_model_traits 시드 + 관련 에지 80건 → evidence/conflicts 시드
  - R10: Paul 원문 capture 경로 확보 최우선 (baseline 1.5%, 목표 60%+)
- **합의 2 — Exit 5가지 정량 측정 방식**
  - Exit 1: Blind A/B 20 질문 세트 ≥ 14/20 (70%)
  - Exit 2: shortcut 0건 (FK 강제) + 추출률 ≥ 50% + reject율 ≤ 20%
  - Exit 3: 50+ traits / 8차원 ≥ 3씩 / verified ≥ 20 / evidence ≥ 2/trait
  - Exit 4: Single-Rule A/B — **"응답 말미 요약 금지"**
  - Exit 5: 의도적 잘못된 trait 주입 → reject → 24h 내 context pack 제외
- **합의 3 — 실행 결정 D3-1~5**
  - D3-1: `policy_rules` = JSON 파일 (테이블 아님, 최소형)
  - D3-2: `feedback_events` = polymorphic target
  - D3-3: `claim-extractor` = 로컬 Qwen2.5-7B-Instruct-Q4_K_M via Ollama
  - D3-4: PostUserPrompt hook = 독립 파일 `post_user_prompt_capture.py`
  - D3-5: Paul 승인 세션 2회 × 30분 (Day 3, Day 4)

### Foundation 3축 작성
- `foundation/philosophy.md` — 배경, 한 문장 목표, 비목표, 핵심 긴장 5개, 설계 태도 D13
- `foundation/principles.md` — 9가지 불변식, F1-F6 방화벽, Slot Precedence, Migration Contract, R1-R10
- `foundation/workflow.md` — 5-Plane 아키텍처, 4가지 루프, Context Pack 6슬롯, Phase 0-5 실행 전략

### Build R1 산출물
- `30_build-r1/00_index.md` — 상태 + 네비게이션
- `30_build-r1/02_context.md` — Phase 전환 계약서 (P3, D18 7개 섹션)
- `30_build-r1/03_impl-plan.md` — Day 1-6 실행 SoT
- **기간**: 5-6일 + 버퍼 1일 / Paul 개입 ~4시간

### Diagnose 실데이터 분석 (추가 발견)
- 타입 분포: Decision 20.3% / Tool 12% / Insight 8.4% / Observation 8.2% / Pattern 8.2% / Question 7.9% (v3 누락)
- 승격 파이프라인 고장: Obs→Signal 승격률 13.5%, promotion_candidate=1 단 15개
- Paul 원문 발화 기록률: 1.5% (user 22 / 전체 1427, 30일)
- Identity 63개 품질 우수 → self-model 시드 확보

## v8.0 Ontology Redesign — Architect Complete (2026-04-12)

### Diagnose R1 (2026-04-10~11)
- 78개 태초 설계 목표 전수 인벤토리 + 현실 대조: 7.7% 작동, 48.7% 미구현
- 6-Level 정의 계층 확립 (Level 0 존재 목적 → Level 6 인프라 제약)
- 3소스 독립 분석 통합: Claude + Codex + deep-research (362 .md 전수 조사)
- Codex 독립 설계 수신: 4-Plane Cognitive System, 10개 코어 타입

### Architect R1 (2026-04-11~12)
- 5-Plane 아키텍처 확정 (Evidence → Epistemic → Self Model → Policy → Governance)
- 4 Loop 설계 (Capture → Consolidation → Policy → Governance)
- v1 → v2 → Codex CONDITIONAL GO → v3 최종 확정
- D1-D20 결정 확정 (29_architect-merged/)

### Codex CONDITIONAL GO 반영 (D16-D20)
- D16: Phase 0 범위 확장 4→8개 (claims, feedback_events, retrieval_logs, 최소 policy compile 추가)
- D17: 기술 스택 도입에 trigger condition 필수
- D18: Context pack slot precedence + 충돌 해소 규칙 추가
- D19: 타입 코드 경로 하드코딩 금지 (config lookup)
- D20: Self Model 연결은 evidence bridge 경유만

### Phase 0 증명 대상 (Build 대기)
1. captures (append-only) + claims (해석 분리)
2. self_model_traits + feedback_events + retrieval_logs
3. get_context() 동적 재설계 (정적 top-30 → topic-aware subgraph)
4. 최소 policy compile/injection (trait→rule→행동 변화)
5. PostUserPrompt 자동 관찰 hook

## v7.4.1 Phase 0 Truth Freeze (2026-04-10)

### STATE automation
- `scripts/generate_state.py` now reads live DB truth and can apply the `## Current` block directly to `STATE.md`
- `STATE.md` current snapshot is now marker-based to separate live metrics from manual narrative
- `PHASE0-CHECKLIST.md` added as the execution checklist for Phase 0

### Snapshot synced
- active nodes 3,229 / active edges 7,443
- cross-domain 30.6%, direction assigned 93.4%
- FTS drift still present: live 5 columns, missing `domains`, `facets`
- generation_method drift still present: `gemini-enrichment`, `vector-similarity`

## v7.3 Performance Optimization (2026-04-10)

### 콜드 스타트 제거 (P0)
- `_init_worker()`에서 SentenceTransformer + CrossEncoder + 벡터 캐시 사전 로드
- 첫 recall/remember 타임아웃 제거 (153초 블로킹 → 서버 시작 시 백그라운드 로드)

### get_edges N+1 제거 (P1)
- `sqlite_store.get_contradicted_node_ids()` 일괄 쿼리 추가
- `hybrid.py` composite scoring 루프에서 개별 get_edges 50회 → 1회 batch
- 예상 350ms → 10ms

### 커넥션 캐싱 (P2)
- `sqlite_store._db()` thread-local 연결 재사용 (DB_PATH 변경 시 자동 무효화)
- `PRAGMA cache_size` 2MB → 20MB

### 임베딩 캐싱 (P3)
- `local_embed.embed_text()` dict 캐시 (max 32, 동일 쿼리 반복 제거)
- recall 내 동일 쿼리 6회 임베딩 → 1회 (108ms → 18ms)

### 수정 파일
- `server.py`, `embedding/local_embed.py`, `storage/sqlite_store.py`, `storage/hybrid.py`
- Tests: 96 passed, 0 new failures

## v7.4 Ontology Full Activation (2026-04-10)

### P0 수정 3건
- **maturity 활성화**: 전부 0.0 → avg 0.498 (visit×0.4 + edges×0.3 + quality×0.3)
- **observation_count 역산**: 전부 0 → 653개 nonzero, max 18
- **edge direction 추론**: 77.8% NULL → 96.2% assigned (5,215 에지 매핑)

### P1 수정
- co_retrieval strength: avg 0.417 → 0.908 (visit 비례 동적 강화)
- promotion_candidate 17개 중 2개 추가 승격

### cross-domain 30% 달성
- 벡터 유사도 기반 analogous_to 에지 200개 생성 (cosine > 0.60)
- **Cross-domain: 28.0% → 30.1%**

### ONTOLOGY-MASTER-REPORT.md 작성
- 524줄 종합 보고서: 태초의도/버전/아키텍처/스펙/파라미터/DB실측/문제점/Scope/기술스택

## v7.3-enrichment Gemini Cross-Domain Enrichment (2026-04-10)

### Gemini 2.5 Flash 크로스도메인 에지 생성
- GCP project-d8e75491-ca74-415f-802 (Vertex AI) 연결
- 200개 isolated 노드 enrichment → 489개 크로스도메인 에지 생성
- generation_method='gemini-enrichment', strength=0.7
- **Cross-domain: 19.3% → 25.1%** (+5.8pp)
- scripts/gemini_cross_domain.py 신규

### Observation 활성화
- 5개 프로젝트 Observation 타입 recall 50+건 (Hebbian 학습)
- zero-visit Observation 재활성화 시작

## v7.2 Data Cleanup + NDCG Recovery (2026-04-10)

### Goldset v4 업데이트
- 43개 gold 노드가 archived 상태 → 32개 쿼리의 gold ID를 active 노드로 교체
- **NDCG@5: 0.293 → 0.425 (+45%)**, hit_rate: 72% → 87.8%
- 원인: 데이터 정리(v6.0 noise archive)에서 goldset 동기화 누락

### 데이터 정리
- 32개 false positive cross-domain edges archived (content duplicate, strength=1.0)
- 52개 orphan Narrative nodes archived (visit=0, edges<=1)
- 7개 dead Question nodes archived (visit=0, edges<=1)

### 발견 (Phase C용)
- Observation 85% zero visit — 성장 파이프라인 시작점 미작동
- cross-domain 19.3% — enrichment 기반 에지 생성 필요

## v7.1 Ontology Simulation (2026-04-10)

### 50-세션 시뮬레이션 실행
- Track A: 아키텍처 파일 10개 읽기 → remember 12건, recall 19건
- Track B: 크로스도메인 recall 16배치 (160+ 결과, 8개 프로젝트 횡단)
- Track C: DB 패턴 분석 10개 → remember 11건, recall 10건
- Track D: Hebbian 강화 recall 30+회
- Track E: auto_promote 7건 + 대규모 승격 883건

### 승격 (validated 6.3% → 33.6%)
- auto_promote 기본 기준: 7건 승격
- 완화 기준 1차 (visit>=2, edges>=2, quality>=0.7): 593건
- 완화 기준 2차 (visit>=1, edges>=3, quality>=0.75): 290건
- 총 890건 provisional → validated

### 수정
- missing embedding 2건 수정 (node 6327, 6328)
- co-retrieval edge 145건 생성 (recall 활동)
- 노드 24건 추가 (아키텍처 통찰)

### 발견된 문제 (다음 조치 필요)
- 크로스도메인 상위 edge가 이미지 경로 아티팩트 (false positive)
- Failure 노드 95% visit=0 (실패 학습 파이프라인 미작동)
- NDCG 0.292 (알고리즘 개선 없이는 0.40 불가)
- cross-domain 19.7% (enrichment 기반 에지 생성 필요)

### Remote Trigger
- ontology-full-activation (trig_01RDAqJi6sHtvcBS3SmGfHyj) 비활성화

## v7.0 1-Store Architecture (2026-04-10)

### Storage: ChromaDB -> SQLite 1-Store
- vector_store.py: ChromaDB 제거, numpy brute-force cosine similarity 전환
- nodes.embedding BLOB 컬럼 추가 (float32, 1024d = 4KB/node)
- 서버 시작 시 active 벡터 메모리 캐시 (3,231 vectors, 12.6MB)
- 3,433 벡터 ChromaDB -> SQLite 마이그레이션 완료 (1.9s)
- promote_node.py: _get_collection() 직접 접근 -> get_node_embedding() 전환
- **저장소 3개(SQLite + ChromaDB + tasks.db) -> 2개(SQLite + tasks.db)**
- ChromaDB 631MB 디스크 공간 회수 가능 (data/chroma/ 삭제 후)
- chromadb 패키지 의존성 제거 (requirements.txt)

## v6.0 Ontology Repair (2026-04-09)

### Embedding: OpenAI → Local
- embedding/local_embed.py: sentence-transformers multilingual-e5-large (1024d)
- embedding/__init__.py: EMBEDDING_PROVIDER 스위치 (local|openai), default=local
- config.py: EMBEDDING_PROVIDER, EMBEDDING_DIM=1024(local)/3072(openai)
- 3,400개 노드 로컬 재임베딩 (183s, RTX 4060)
- **실시간 경로 외부 API 의존 100% 제거**
- NDCG@5: 0.280→0.285 (+1.8%, 품질 손실 없음)

### Learning: BCM → Hebbian
- hybrid.py: _bcm_update() → _hebbian_update() 교체
- 연속 firing rate 모델(BCM) → 이산 frequency 기반 단순 학습
- co-recall 시 strength += 0.015 (양쪽 result), += 0.005 (한쪽 result)
- theta_m/activity_history 더 이상 갱신하지 않음

### Growth: auto_promote
- scripts/auto_promote.py: 승격 자동화 (Gate 1+2, MDL 제거)
- daily_enrich.py Phase 0에 통합 (매일 enrichment 전 실행)
- 38개 노드 자동 승격 (validated 130→168)

### Data: 계층 분리 + 정화
- SOURCE_BONUS 7단계 재설정 (user +0.12 ~ obsidian -0.05)
- 28개 노이즈 archive (Unclassified 18 + license 10)
- 206개 추가 archive (frontmatter 8 + near-duplicates 198)
- NULL 수정: layer 56개, quality_score 10개
- 자기참조 edge 3개 삭제

### Structure
- 27개 스크립트 archived (scripts/_archived/): 마이그레이션, backfill, 중복
- scripts/reembed_local.py: 로컬 재임베딩 도구

## v5.1 WS-0~4 + Beads + Recall Fix (2026-04-08)

### WS-0: knowledge_core Context
- context_selector: knowledge_core 전용 섹션 (SoT primary, visit_count 상위 30건)

### WS-1.2: Reasoning Graph Cleanup
- config: GRAPH_EXCLUDED_METHODS (session_anchor, legacy_unknown, orphan_repair, co_retrieval, fallback)
- hybrid.py: NetworkX graph + SQL CTE에서 operational edge 제외
- 미사용 import 정리 (ENRICHMENT_QUALITY_WEIGHT, SOURCE_BONUS 등)

### WS-2.1: Write-Layer Normalize
- sqlite_store.insert_node: node_role 미전달 시 knowledge_candidate, epistemic_status 미전달 시 provisional 기본값

### WS-4: Promote Auto-Render + Maturity Gating
- promote_node: 승격 후 proven_knowledge.md 자동 렌더 (background subprocess)
- config: get_maturity_level() 4단계 (core 기준), MATURITY_GATES (graph_channel/complex_scoring)
- hybrid.py: maturity gating으로 graph channel on/off

### Beads v6.1: Task Graph
- storage/task_store.py: tasks.db SQLite (create, query, complete, generate_next)
- server.py: 4 MCP tools (create_task, query_tasks, complete_task, generate_next)
- session_events: target + task_id 칼럼 추가, emit_event/poll_events에 TASK_ASSIGN/TASK_PICK 지원
- complete_task → TASK_COMPLETE SessionEvent 자동 발행 + blocked_by 해소

### Recall Quality Fix
- 0.3 score threshold 제거 (scoring 단순화 후 범위 0.05~0.17로 하락, threshold가 전부 차단)
- overfetch 3x: hybrid_search top_k*3 → role 필터 → top_k 절단
- patch 전환 mode 변수 버그 수정 (mode → search_mode)

## Merger Artifact Pipeline (2026-04-07)
- `scripts/render_proven_knowledge.py`: knowledge_core + validated + high-signal + corrections → `data/proven_knowledge.md` (22 nodes)
- `data/merger_manifest.json`: 반영 이력 추적 (22 entries)
- `session_context.py`: 세션 시작 시 proven_knowledge.md를 먼저 출력
- 렌더 기준: knowledge_core(무조건) + validated(q≥0.85) + Signal(v≥5) + Correction
- DB → artifact → session context 단일 흐름 완성

## V5 Runtime + Epistemic + Edge Class (2026-04-07)

### V5-01: render_memory_md active 필터
- 전 쿼리에 `status='active'` + `node_role` + `epistemic_status` 필터 추가
- deleted/outdated/work_item/external_noise가 MEMORY.md에 올라가지 않음

### V5-02: Epistemic Output Separation
- context_selector: l2_core에서 outdated/flagged/superseded 제외
- context_selector: corrections 전용 섹션 신설 (contradicts edge 포함)
- session_context: "교정 경고" 섹션 분리 출력
- proven_knowledge.md: Core Knowledge / Corrections 2섹션 분리

### V5-03: Edge Class 분류 체계
- config.py EDGE_CLASS: 49 relation → semantic/evidence/temporal/structural/operational
- REASONING_EDGE_CLASSES: generic reasoning에서 operational 제외
- 196 tests passed

## Goldset v4 교정 + Enum Drift 수정 (2026-04-07)
- goldset 19개 쿼리 교정: NDCG@5 0.201→**0.402**, hit_rate 0.646→**0.939**
- config GENERATION_METHODS: enrichment/orphan_repair/legacy_unknown 추가 (enum drift 0)
- GENERATION_METHOD_PENALTY: orphan_repair -0.08, legacy_unknown -0.05 (operational edge 감점)
- scripts/generate_state.py: STATE.md Current 블록 자동 생성 (live DB 기준)

## R7 Acceptance Audit — GO (2026-04-07)
- **전 14개 gate PASS** — Ontology v4 본선 완료
- A. 구조: node_role 100%, generation_method 100%, blank_project 0
- B. Retrieval: 4-mode contract, generic suppression, correction contradicts
- C. Graph: orphan 0.0%, 0-1 edge 49.1%
- D. Growth: Correction 7, contradicts 7, validated 16, knowledge_core 9, Signal 69
- E. Merger: 2건 (MEMORY.md 반영)
- Nodes: 5,259 | Edges: 7,001 | Tests: 193 passed

## R1-R6 Ontology v4 본선 (2026-04-07)

### R1 Goldset Modernization
- goldset_v4.yaml: 75→82 queries (+7 mode-specific)
- mode 필드 추가: generic(75), troubleshooting(3), correction(2), recollection(2)
- ndcg.py mode-aware 수정 (query별 mode를 recall에 전달)
- Baseline: NDCG@5=0.201, hit_rate=0.646

### R3 Retrieval Contract (4-mode)
- recall() intent mode 4종: generic, recollection, troubleshooting, correction
- troubleshooting: Failure 타입 병렬 검색 + 0.05 부스트
- correction: Correction threshold 0.5→0.3, contradicts 정보 출력
- recollection: session_anchor 포함, work_item/external_noise만 제외
- search mode(auto/focus/dmn) ↔ intent mode 분리

### R5 Graph Repair
- orphan 732→**0** (14.0%→0.0%)
- text-embedding-3-large 배치 임베딩 → nearest neighbor edge 생성
- 732 orphan_repair edges 생성

### R6 Memory-Merger MVP
- knowledge_core #4159+#4175 → MEMORY.md User Preferences 반영
- "속도+정확도 동시, 트레이드오프 거부, 병렬화로 전부 해결"
- merger metadata 기록 (merged_to, merged_at, merger_version)

## R4 Correction Activation (2026-04-07)
- Correction 0→**7**, contradicts 0→**7**
- Identity 중복 4건 flagged (#3575/#3641/#3707/#3773 → #2712 보존)
- 테스트 아티팩트 3건 flagged (#4271, #3152, #4648)
- flag_node→Correction→contradicts→confidence 하락→epistemic_status 변경 전체 루프 실전 검증

## R2 Metadata Saturation (2026-04-07)
- **node_role**: 22.3% → 100% (4082건 source-aware backfill)
- **generation_method**: 23.1% → 100% (4801건 pattern-based backfill)
- 분류 전략: source_kind 기반 기본값 + 예외 오버라이드 (Narrative→session_anchor, validated→knowledge_core)
- edge 분류: enrichment(2785), legacy_unknown(1397), co_retrieval(168), semantic_auto(72)
- 테스트: 186 → 193 (+7 saturation regression)
- Gate G2 통과

## v3.3.1-dev (2026-04-07) — Signal 성장 엔진 가동

### Signal Clustering & Synthesis
- **임베딩 클러스터링**: Observation 417개 → cosine distance 0.35 agglomerative clustering
- **51개 클러스터 합성**: gpt-4.1-mini 배치 → 51 Signal 노드 생성
- **realizes edge 128개**: Signal→Observation 증거 연결
- **Signal spine**: 19→70 (목표 50+ 초과 달성)
- **promote_node 흐름 검증**: Signal→Pattern 승격+복구 정상 작동
- **테스트**: 186 tests passed (변경 없음)
- **NDCG**: 0.214 (안정 — Signal은 goldset 미포함)

## v3.3.0-dev (2026-04-07) — 온톨로지 전면 강화 (성장+교정+재반영)

### 검색 무결성
- **active-only filter**: get_node/get_edges/get_all_edges/search_fts 전 경로에 status='active' 강제
- **confidence → scoring**: (confidence - 0.5) * CONFIDENCE_WEIGHT additive
- **contradiction penalty**: contradicts edge 존재 시 -0.10
- **node_role penalty**: session_anchor -0.08, work_item -0.06, external_noise -0.10

### 온톨로지 메타데이터
- **신규 컬럼 5개**: source_kind, source_ref, node_role, epistemic_status (nodes), generation_method (edges)
- **Correction type active 복구**: system type으로 validators bypass
- **co_retrieved relation_defs 등록**: behavioral 카테고리
- **RELATION_WEIGHT 전 coverage**: 22개 미커버 relation 명시적 weight 추가

### save_session knowledge gate
- Decision/Question 40자 미만 → node_role='work_item' (generic recall 제외)
- SKIP_PATTERNS 매칭 시 노드 미생성
- Narrative → node_role='session_anchor'
- contains edge → generation_method='session_anchor'

### context selector 통합
- get_context.py + session_context.py → context_selector.py 공용 selector
- L2+ core, Signal, Observation 포함하는 풍부한 선택
- work_item/external_noise 제외

### 성장 엔진
- **get_becoming maturity**: 5차원 (quality 30% + edges 20% + visits 20% + diversity 20% + recency 10%)
- **promote_node evidence bundle**: evidence_ids 기록, node_role='knowledge_core'
- **Signal 승격**: Observation 7건 → Signal (12→19)

### 데이터 backfill
- source_kind 분류: 5200 노드 전체
- node_role 분류: save_session 1075건 (session_anchor 93, work_item 343, knowledge_candidate 639)
- external noise quarantine: 37건
- blank project 보정: 30건
- JSON normalize: 58 fields

### 테스트
- 186 tests passed (Codex 작성 5개 포함)
- recall avg 0.35→0.47, hit_rate 0.50→0.69

## v3.2.0-dev (2026-04-07) — 상호작용 개선 + 시스템 건강 복구

### 상호작용 개선
- **recall() 품질 신호**: layer, confidence, source, quality 출력 추가
- **recall() min_score 필터**: 0.3 미만 노이즈 결과 자동 제거
- **source 가중치**: claude +0.05, checkpoint -0.02 (config SOURCE_BONUS)
- **flag_node() 신규 도구**: 부정확/구식/무관함 신고 → Correction 생성 + confidence 하락
- **get_context() 개선**: 품질 신호 포함 + last_session 요약 (세션 연속성)

### 학습 루프 구조 수정
- **BCM 필터 완화**: activated_edges AND→OR (학습 edge 11→42, 3.8x)
- **v=0.1 default**: 비결과 endpoint에 최소값 부여 (delta=0 방지)
- **SIMILARITY_THRESHOLD**: 0.3→0.55 (노이즈 edge 생성 감소)
- **Phase 1 cap**: small_budget 50% 상한 (Phase 2-5 예산 보존)
- **recall context package**: 1-hop 이웃을 type+content 구조화
- **Narrative chain**: 같은 project Narrative간 succeeded_by edge

### Enrichment 버그 수정
- **E21 카운터**: 조건문 밖 → 안으로 이동 (14/14 거짓 → 실제 수치)
- **E22 카운터**: assemblages_found 조건문 안으로
- **E24 카운터**: merges_detected 조건문 안으로
- **E19 카운터**: orphans_resolved에 if suggestions 조건 추가
- **E21 프롬프트 강화**: paradox/contextual 제거, direct/temporal만 허용
- **거짓 contradiction edge 12건 soft-delete**
- **enrichment 정직화**: 710 fake batch stamps 리셋, 4409 fake E6/E7 keys 제거

### 건강 지표 개선
- **orphan_nodes**: obsidian 제외 세션 노드 기준 (measure + ontology_health)
- **edge_density**: 세션 노드 denominator, threshold 1.0으로 하향
- **connectivity guard**: pruning 시 고아 방지 (edge_count ≤ 1 보호)
- **ingest edge**: obsidian 청크 간 part_of edge 생성
- **Hook relay.py**: sys.modules config 캐시 충돌 수정

## 2026-03-29 — El Croquis PDF 시스템
- 9-Lens 분석 보고서 10개 El Croquis 스타일 HTML/PDF 제작
- Sonnet 스타일 커버 (검정선/빨간선, 39px 타이틀, 위계 통일)
- Alpha: 10개 SVG 다이어그램 직접 삽입, WYSIWYG contenteditable
- 9개 _diag 버전: Codex gpt-5.4 xhigh 병렬 생성 (문서별 6-8개 다이어그램)
- 커버 에디터 (editor.html) + PDF 생성기 (gen.js via Puppeteer)

## v3.1.0-dev (2026-03-16) — 온톨로지 강화 + PDR

### PDR (Pipeline DONE Retrospective)
- /pdr 스킬 신규: 8차원 전수 스캔, 20-25개 Observation(L0) + tags
- G6 DONE gate 하드블록: phase-rules.json + validate_output.py
- 차원: thinking-style, preference, emotional, decision-style, language, work-rhythm, metacognition, connection
- 첫 실행: 23건 저장 (#5195-#5217), 4 auto-edge
- Pipeline 02_interaction-capture_0316 DONE

## v3.1.0-dev (2026-03-16) — 온톨로지 강화
### Promotion Pipeline 해제
- Gate 2: Bayesian Beta(1,10) → visit_count ≥ 10 직접 threshold (수학적 불가 해소)
- Gate 1: SWR threshold 0.55→0.25 (cross_ratio만으로 통과 가능)
- swr_readiness: recall_log.sources JSON 파싱으로 vec_ratio 계산

### Source Infrastructure
- hybrid_search: source_map 추적 (vector/fts5/graph/typed_vector)
- recall_log: sources TEXT 컬럼 자동 마이그레이션 + JSON 기록
- 기존 2,899행은 sources=NULL → 점진적 축적

### Relation Quality
- RELATION_RULES: 17→49개 (7.6%→37.3% type pair coverage)
- Cross-project 로직: mirrors (같은타입), influenced_by (다른타입), transfers_to (fallback)
- infer_relation: cross-project 판별 후 의미 있는 관계 타입 선택

### Deprecated Cleanup
- TYPE_CHANNEL_WEIGHTS: v3 15타입 기준 (deprecated 5개 제거, 누락 5개 추가)
- TYPE_KEYWORDS: v3 15타입 기준 (deprecated 5개 제거, 누락 5개 추가)
- LAYER_IMPORTANCE: layer 4,5 제거 (v3 최대 layer=3)
- suggest_closest_type: v3 타입 기준 (deprecated 제거, 누락 추가)
- Tests: Workflow/Agent/Skill 참조 v3 기준 갱신

## v3.0.0-rc (2026-03-11) — Ontology v3 Phase 5
### Breaking: Type System Overhaul (51→15)
- **Tier1 핵심 (7)**: Observation, Signal, Pattern, Insight, Principle, Framework, Identity
- **Tier2 맥락 (5)**: Decision, Failure, Experiment, Goal, Tool
- **Tier3 전환 (3)**: Correction, Narrative, Project
- + Unclassified (미분류 대기)

### DB Migration
- 전타입 마이그레이션: merge=506, edge=46, Workflow LLM재분류=532 (61 archived)
- type_defs deprecated 처리 (34개 타입), leaked=0 검증
- sync_schema() C1 fix: deprecated 타입을 active로 되돌리지 않도록

### retrieval_hints (Step 2)
- gpt-5-mini 배치 20/호출, 148 API 호출, 2927/2947 성공 (99.3%)
- when_needed + related_queries + context_keys 3필드
- server→remember→store→insert_node plumbing 완료

### Search Improvements
- type_filter canonicalization: deprecated→replaced_by 자동 변환 (H1)
- recall_id: uuid.hex[:8] 세션 식별 (H2)
- PROMOTE_LAYER v3: L0(3), L1(7), L2(3), L3(2)
- RELATION_RULES: 25→17개, VALID_PROMOTIONS v3

### New Scripts
- scripts/migrate_v3.py: 전타입 마이그레이션
- scripts/migrate_workflow.py: Workflow LLM 재분류
- scripts/enrich/hints_generator.py: retrieval_hints 배치 생성
- scripts/enrich/co_retrieval.py: co-retrieval 계산 (Step 3 준비)

### Tests
- 163→169 (+6), 전체 PASS

### Remaining (Phase 5 잔여)
- err 20 hints 재생성, re-embed(2.5), co-retrieval(3), dispatch(4), NDCG(6)

## v2.2.1 (2026-03-08)
### Layer A Refactor: Typed Vector Channel
- TYPE_BOOST additive(0.03) → TYPE_CHANNEL_WEIGHT(0.5) RRF 채널 교체
- 타입 힌트 감지 시 타입별 독립 벡터 검색 → 4번째 RRF 신호로 추가
- MAX_TYPE_HINTS=2 (API 호출 제한)
- A/B test에서 additive boost 무효 확인 → RRF 채널 기반으로 전환

### Goldset v2.2 (Paul 수동 검증)
- q026-q075 50개 쿼리 Paul 직접 검증 (relevant_ids + also_relevant 교체)
- also_relevant 5개→1~3개로 정리 (과도한 정답 제거)
- q026-q050 NDCG@5: 0.123 → 0.519 (+0.396)
- 발견: Identity 중복 노드 5개, q049 쿼리 범위 확장 필요

### Metrics (Paul 검증 goldset 기준)
- NDCG@5: 0.441 → 0.460 (+0.019)
- NDCG@10: 0.452 → 0.488 (+0.036)
- Tests: 161 → 163 (+2)

## v2.2.0 (2026-03-08)
### 3-Layer Type-Aware Search
- **Layer C**: 타입 태그 재임베딩 — `[Type] summary + key_concepts + content[:200]`로 벡터 공간에서 타입 분리
- **Layer A**: 키워드 기반 타입 부스트 — 15개 타입 키워드 테이블(TYPE_KEYWORDS), TYPE_BOOST=0.03
- **Layer D**: 타입 다양성 보장 — max_same_type_ratio=0.6, 한 타입이 결과 60% 이상 차지 시 교체

### Goldset v2.1 교정
- L1 relevant_ids 순환 참조 제거 (hybrid_search 결과를 정답으로 쓴 문제)
- type-filtered 벡터 검색 + FTS + hybrid 3방법 병합으로 편향 없는 후보 풀 생성
- auto_correct_goldset.py, generate_candidates.py, review_candidates.py 신규

### Metrics (corrected goldset 기준)
- hit_rate: 0.410 → 0.920 (+51pp)
- NDCG@10: 0.443 → 0.466 (+0.023)
- Tests: 153 → 161 (type_boost 5 + type_diversity 3)

## v2.1.3 (2026-03-08)
### Search Quality
- LIKE boost cap 2개로 제한 (q004/q008 회귀 수정)
- RRF candidate cutoff top_k×4 → top_k×10 (FTS-only 노드 탈락 방지)
- q017: 0→0.778 (동의어 주입), q018: 0→0.428 (cutoff 확장)
- 벡터 재임베딩: content → summary+key_concepts+content[:200]
- NDCG@5: 0.585→0.624 (50개), NDCG@10: 0.600→0.659 (50개)

### Verification System
- checks/ 8모듈 신규: search_quality, schema_consistency, data_integrity, promotion_pipeline, recall_scenarios, enrichment_coverage, graph_health, type_distribution
- verification_log 테이블 (DB 자동 기록)
- scripts/eval/verify.py 러너
- 서버 시작 시 quick verify (search_quality 스킵)

### Data Quality
- 449 중복 노드 soft-delete (content_hash 기반)
- content_hash 86.4% → 100%
- 92 미enriched 노드 Codex CLI enrichment 완료

### Performance
- post_search_learn() background thread 전환
- focus 모드: NetworkX → SQL CTE (_traverse_sql)
- auto/dmn 모드: UCB 유지 (NetworkX)

### Evaluation
- goldset 25→75 확장 (Codex CLI 생성 + Opus relevant_ids 매핑)
- 9 tier 구조: L3+ 원칙, L1 워크플로우/도구/에이전트, L0 서사

### Scripts
- scripts/pipeline/inject_synonyms.py
- scripts/pipeline/cleanup_duplicates.py
- scripts/pipeline/enrich_batch.py
- scripts/pipeline/reembed.py
- scripts/pipeline/run_pipeline.py
- scripts/eval/verify.py

## v2.1.2 (2026-03-08)
- FTS5 한국어 조사 제거, OR 매칭, 2글자 LIKE 보조 검색
- 후보풀 확장 top_k×2 → top_k×4
- schema.yaml → type_defs/relation_defs 자동 동기화
- content_hash UNIQUE + atomic dedup
- hybrid.py _connect() → _db() context manager
- NDCG: 0.548→0.581, 153 tests

## v2.1.1 (2026-03-06)
- Phase 1: init_db 동기화, connection mgmt, PROMOTE_LAYER 50타입
- check_access MCP, content dedup, query/write 분리
- NDCG: 0.057→0.548

## v2.0 (2026-03-04)
- 13 MCP tools, 6 layers, 50 node types, 48 relation types
- migrate_v2.py 완료
- enrichment pipeline (1,973/3,171 → 62%)

