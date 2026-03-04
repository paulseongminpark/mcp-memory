# mcp-memory v2.0 구현 세션 상태

> compact/세션전환 후 컨텍스트 복원용. 완료 후 삭제 가능.

## 완료 (Step 1-10)

| Step | 파일 | 내용 |
|------|------|------|
| 1 | scripts/migrate_v2.py | nodes +12, edges +9, correction_log, FTS5 재구축, layer 배정 |
| 2 | config.py | ENRICHMENT_MODELS(5), TOKEN_BUDGETS, ALLOWLISTS, RELATION_TYPES(48) |
| 3 | scripts/enrich/token_counter.py | TokenBudget, RateLimiter, o3 reasoning 추적, save_log |
| 4 | scripts/enrich/node_enricher.py | NodeEnricher E1-E12, conflict resolution, dry_run |
| 5 | scripts/enrich/relation_extractor.py | RelationExtractor E13-E17, 3-strategy clustering |
| 6 | scripts/enrich/graph_analyzer.py | GraphAnalyzer E18-E25, pure SQL (no NetworkX/ChromaDB) |
| 7 | scripts/daily_enrich.py | Phase 1-5+7 orchestrator, CLI args, report generation |
| 8 | scripts/codex_review.py | Codex CLI 4-target review, --dry-run, report gen |
| 9 | prompt_loader.py + 25 YAML + test_prompts.py | 프롬프트 외부화, 600건 에러 0 |
| 10 | hybrid.py + remember.py + 4 tools + server.py | MCP 통합: scoring, provisional, 4 신규 도구 |

## e2e 리뷰 + Fix (2026-03-04)

- 3종 리뷰: Sonnet(78/100), Opus(B+), Codex(48/100)
- 19개 Fix 적용 (F-1~F-25), 10개 파일, 검증 PASS
- 리포트: data/reports/e2e-fix-summary.md
- checkpoint: #4082~#4086
- v2.1 defer: F-5(감쇠), F-10(init_db), F-11(schema), F-16(relate도구), F-17/19/22(minor)

## 전체 완료 (Step 1-10)

### Step 8: scripts/codex_review.py - 완료
- Codex CLI(v0.106.0)로 4개 리뷰: prompts(skip-empty), pipeline, ontology, modules

### Step 9: 프롬프트 YAML 외부화 + 50개 표본 - 완료
- prompt_loader.py: YAML로드, format_map 치환, (system,user) 반환
- 25개 YAML: scripts/enrich/prompts/e01-e25*.yaml
- node_enricher.py, relation_extractor.py, graph_analyzer.py → PromptLoader 전환
- test_prompts.py: 50표본 x 12task = 600 프롬프트, 에러 0건

### Step 10: MCP 도구 통합 - 완료
- 10a: hybrid.py RRF 후 quality_score*0.2 + temporal_relevance*0.1 가중치, 재정렬
- 10b: remember.py metadata + ChromaDB에 embedding_provisional=true
- 10c: 4개 신규 도구 구현 (tools/ 4파일 + server.py 등록)
  - analyze_signals: Signal 클러스터링(tag/concept/domain overlap) → maturity 계산 → 승격 권고
  - promote_node: 타입 승격 + realized_as edge + promotion_history in metadata
  - get_becoming: 승격 가능 노드 현황 (maturity 순)
  - inspect: 노드 전체 상세 (메타, 연결, enrichment, 승격 이력)
- config.py에 VALID_PROMOTIONS, PROMOTE_LAYER, ENRICHMENT_*_WEIGHT 추가
- MCP 도구 수: 9 → 13

## 파일 구조 (현재)
```
config.py                        [2+10] 설정 + VALID_PROMOTIONS, PROMOTE_LAYER
server.py                        [10] 13개 MCP 도구 등록
storage/
  hybrid.py                      [10a] RRF + enrichment 가중치
tools/
  remember.py                    [10b] provisional embedding
  recall.py                      기존
  analyze_signals.py             [10c] Signal 클러스터 분석
  promote_node.py                [10c] 타입 승격
  get_becoming.py                [10c] Becoming 현황
  inspect_node.py                [10c] 노드 상세
scripts/
  migrate_v2.py                  [1] DB migration
  daily_enrich.py                [7] main orchestrator
  codex_review.py                [8] Codex CLI review
  test_prompts.py                [9] 50표본 dry-run
  enrich/
    __init__.py
    token_counter.py             [3] budget + rate limiting
    node_enricher.py             [4] E1-E12
    relation_extractor.py        [5] E13-E17
    graph_analyzer.py            [6] E18-E25
    prompt_loader.py             [9] YAML 로더
    prompts/                     [9] 25개 YAML
    _session_state.md            (this file)
```

## 수리+활성화 (2026-03-04)

### 버그 수정 8건
- temperature=0.3 제거 (3파일) — 최신 모델 전부 미지원
- "json" 키워드 자동 추가 (3파일) — response_format=json_object 필수
- hebbian conn.close() (hybrid.py)
- recall.py 중복 코드 제거
- E7 상태 저장 조건 수정 (node_enricher.py)
- target_id 존재 검증 + _insert_edge safety guard (graph_analyzer.py)
- session_context.py SQL f-string → parameterized query
- init_db() v2 컬럼 포함 (sqlite_store.py)

### 스키마 확장
- schema.yaml v2.0: 50 node types, 48 relation types (config.py 완전 동기화)
- migrate_v2.py 실행: nodes 15/15, edges 9/9, layer 98.8% — READY

### 속도 최적화
- enrich_node_combined(): 9 API → 1 API (7x 속도향상)
- enrich_batch_combined(): ThreadPoolExecutor(10 workers) 병렬 API + 순차 DB 쓰기 (10x 추가)
- E14 batch: 30개 엣지/API 호출 (e14_batch.yaml), 병렬 처리
- run_e14(): 병렬 batch API + 순차 DB 쓰기
- BATCH_SLEEP 0.3→0.05, CONCURRENT_WORKERS=10
- daily_enrich.py phase1 → enrich_batch_combined 사용
- 전체 E13-E25 프로그레스 바 추가

### 버그 수정 (세션 2)
- daily_enrich.py E13/E14/E16/E17: except Exception 추가 (NoneType 에러 방지)
- _e14_batch_classify: None 반환 방어 코드

### 인프라
- orchestration Stop hook에 save_session() 자동 호출 추가
- checkpoint 18건 저장 (#4093-#4100, #4127-#4136)

### 실행 결과 (1차)
- Phase 1: 노드 1,973/3,171 enriched (62%), small pool 100% 소진
- Phase 2: E21(9/9) + E22(35/40) + E20(5/5) + E15(진행중)
- Phase 3-5: 진행중 또는 대기
- 엣지: 5,643개, generic 93.5% → E14 미실행
- 비용: 1차 무료 풀, 2차 유료 $2-4 예상

### 실행 상태
- Phase 2-7 실행 중 (E15→Phase 3→4→5→7)
- 완료 후: Phase 1 병렬 재실행 (노드 1,185 + E14 5,194개)

## 실행 명령
```powershell
cd C:\dev\01_projects\06_mcp-memory
$env:PYTHONIOENCODING="utf-8"
python -u scripts/daily_enrich.py --budget-small 10000000 --budget-large 2000000  # 유료 전체
python -u scripts/daily_enrich.py --phase 1 --budget-small 10000000 --budget-large 2000000  # Phase 1만
```

## 코딩 패턴
- ROOT = Path(__file__).resolve().parent.parent.parent (enrich 내) 또는 .parent.parent (scripts 직접)
- sys.path.insert(0, str(ROOT)) 후 import config
- BudgetExhausted 예외로 배치 중단
- PYTHONIOENCODING=utf-8 (Windows cp949)
- config.ENRICHMENT_MODELS["bulk"|"reasoning"|"verify"|"deep"|"judge"]

## 스펙 참조
- docs/06-enrichment-pipeline-spec.md (전체)
- docs/05-full-architecture-blueprint.md (온톨로지)
