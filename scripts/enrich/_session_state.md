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

## 첫 실행 순서
1. `python scripts/daily_enrich.py --dry-run` (API 없이 구조 확인)
2. Step 9 완료 후: `python scripts/daily_enrich.py --phase 1 --budget-small 100000` (소규모 테스트)
3. Paul 검토 후 전체 실행

## 코딩 패턴
- ROOT = Path(__file__).resolve().parent.parent.parent (enrich 내) 또는 .parent.parent (scripts 직접)
- sys.path.insert(0, str(ROOT)) 후 import config
- BudgetExhausted 예외로 배치 중단
- PYTHONIOENCODING=utf-8 (Windows cp949)
- config.ENRICHMENT_MODELS["bulk"|"reasoning"|"verify"|"deep"|"judge"]

## 스펙 참조
- docs/06-enrichment-pipeline-spec.md (전체)
- docs/05-full-architecture-blueprint.md (온톨로지)
