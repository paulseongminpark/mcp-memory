# 세션 B: 뉴럴 메커니즘 구현 설계 — 진행 인덱스

> compact 후 이 파일만 읽고 이어서 진행
> 참조 온톨로지: `docs/2026-03-05-ontology-claude-paul-v2.md` 섹션 2, 7

## 파일 네이밍 규칙

```
{세션}-r{라운드}-{번호}-{주제}.md
예: b-r3-14-주제.md  (B세션 Round 3, 14번부터)
```

- 인덱스 파일(`b-index.md`)은 라운드 없이 유지, 내용만 갱신
- **Round 3 완료: 14~16** (hybrid-final, recall-final, graph-optimization)
- R1: 1~9, R2: 10~13, R3: 14~16 — 모두 완료

## 완료 항목

| # | 파일 | 한 줄 요약 |
|---|---|---|
| 1 | [b-neural-1-bcm-vs-oja.md](b-neural-1-bcm-vs-oja.md) | BCM 선택 — 레이어별 차등 η + 적응형 임계값 ν_θ로 runaway 방지. Oja는 pruning 전처리만. |
| 2 | [b-neural-2-swr-transfer.md](b-neural-2-swr-transfer.md) | recall_log 테이블 필요. vec_ratio×0.6 + cross_domain×0.4 > 0.55 → 승격 허용. "3회 반복" 규칙 교체. |
| 3 | [b-neural-3-ucb-c.md](b-neural-3-ucb-c.md) | EXPLORATION_RATE=0.1 → UCB 교체. c=0.3(집중)/1.0(auto)/2.5(DMN). 쿼리 단어 수로 자동 전환. |
| 4 | [b-neural-4-patch-foraging.md](b-neural-4-patch-foraging.md) | recall() 후처리. 75% 동일 project 포화 시 다른 project 재검색. hybrid_search에 excluded_project 파라미터 추가. |
| 5 | [b-neural-5-reconsolidation.md](b-neural-5-reconsolidation.md) | 우선순위 1위. edges.description을 JSON 맥락 로그로 재사용. recall() 끝에 한 줄 추가. B-6의 데이터 소스. |
| 6 | [b-neural-6-pruning.md](b-neural-6-pruning.md) | Bäuml 맥락 다양성 + BSP Probation. strength<0.05 AND 맥락<2개 → archive/delete. B-5 완료 후 가능. |
| 7 | [b-neural-7-chen-sa.md](b-neural-7-chen-sa.md) | 성능 우선순위 1위. NetworkX BFS → SQLite Recursive CTE. build_graph() 제거 가능. 인덱스 확인 필요. |
| 8 | [b-neural-8-rwr-surprise.md](b-neural-8-rwr-surprise.md) | surprise = rwr/baseline - 1.0. WEIGHT=0.1로 hybrid_search 보너스. 30K+ 시 scipy.sparse 필요. |
| 9 | [b-neural-9-swing-toward.md](b-neural-9-swing-toward.md) | Maslov-Sneppen 변형. 로컬 CC 4노드만 계산. 200 rounds → ~10~30 swaps. daily_enrich 마지막 단계. |
| 10 | [b-neural-10-reconsolidation-impl.md](b-neural-10-reconsolidation-impl.md) | B-5 실제 구현: _hebbian_update()에 query 파라미터 추가, 단일 트랜잭션 통합. 삽입 위치 hybrid.py L116. 마이그레이션 SQL 포함. |
| 11 | [b-neural-11-cte-impl.md](b-neural-11-cte-impl.md) | B-7 실제 구현: hybrid.py L75-76 교체, build_graph는 visualize.py 때문에 유지. idx_edges_source/target 이미 존재. Phase2에서 all_edges 제거. |
| 12 | [b-neural-12-bcm-ucb-integration.md](b-neural-12-bcm-ucb-integration.md) | BCM+UCB 통합: UCB→탐색경로(L75-76), BCM→학습결과(L116). visit_count는 _bcm_update 내부. theta_m 초기화 UPDATE nodes SET 필요. |
| 13 | [b-neural-13-recall-flow.md](b-neural-13-recall-flow.md) | recall() 전체 흐름: 1 트랜잭션 3N+K UPDATEs. B-6 Pruning은 daily_enrich만. Phase1 구현 순서: B-10→B-11→B-4→B-12. |

| 14 | [b-r3-14-hybrid-final.md](b-r3-14-hybrid-final.md) | storage/hybrid.py 전체 교체 코드: _bcm_update+_ucb_traverse+_traverse_sql+_log_recall_activations. diff 포함. |
| 15 | [b-r3-15-recall-final.md](b-r3-15-recall-final.md) | tools/recall.py 전체 교체 코드: mode 파라미터, 패치 전환, total_recall_count(stats 테이블). |
| 16 | [b-r3-16-graph-optimization.md](b-r3-16-graph-optimization.md) | all_edges+build_graph 최적화: Option A(TTL 캐싱 즉시), Option B+C(Phase 2 SQL-only UCB). |

## 미완료 항목
없음 — 16개 전체 완료.

## 오케스트레이터 확정 사항
- BCM 직행 (D세션 tanh→BCM 단계 없음)
- B-5 재공고화: 전체 Phase 1 첫 번째 구현
- B-7 SQL CTE: 성능 1순위 확정

## Round 3 최종 심화 완료 (2026-03-05)

- B-14: hybrid.py 전체 교체 코드 — diff 포함, 7개 함수, 310줄
- B-15: recall.py 전체 교체 코드 — mode/패치전환/stats 테이블
- B-16: 최적화 로드맵 — Phase 1(TTL 캐싱), Phase 2(SQL-only UCB)

## 다음 세션: 구현 시작
Phase 1 구현 순서 (b-neural-13 기준):
1. **B-10**: `_hebbian_update()` 수정 + config `CONTEXT_HISTORY_LIMIT=5` + 마이그레이션 SQL
2. **B-11 Phase1**: `hybrid.py` L75-76 `_traverse_sql()` 교체 + import 정리
3. **B-4**: `recall.py` 패치 전환 + `hybrid_search` `excluded_project` 파라미터
4. **B-12**: DB 마이그레이션 (theta_m, activity_history, visit_count) + `_bcm_update()` + `_ucb_traverse()`

## DB 스키마 변경 전체 요약
- nodes: `theta_m REAL DEFAULT 0.5`, `activity_history TEXT DEFAULT '[]'`, `visit_count INTEGER DEFAULT 0`
- edges: `description` 재활용 (마이그레이션 필요), `archived_at TEXT`, `probation_end TEXT`
- 신규 테이블: `recall_log` (source: vector/fts5/graph, node_id, query_hash)

## 핵심 파일 변경 목록
| 파일 | 변경 내용 |
|---|---|
| `storage/hybrid.py` | `_hebbian_update` 확장, `_traverse_sql` 추가, `_ucb_traverse` 추가, `_bcm_update` 추가, L75-76 교체, L116 교체 |
| `tools/recall.py` | `mode` 파라미터, 패치 전환 로직 추가 |
| `config.py` | UCB_C_*, BCM_HISTORY_WINDOW, CONTEXT_HISTORY_LIMIT, PATCH_SATURATION_THRESHOLD 추가 |
| `graph/traversal.py` | 변경 없음 (build_graph, traverse 유지) |
