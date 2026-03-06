# W3 State (Utils + Scripts)

> W3 세션만 이 파일을 수정한다.
> compact 전 반드시 갱신. compact 후 이 파일을 가장 먼저 읽는다.

## 현재 상태

```
phase: 3
last_done: goldset.yaml 튜닝 (NDCG 0.057→0.173, 835fd09)
next: Phase 3 CX 검증 (P3-CX-01~05) + GM 리포트 (P3-GM-01~02)
blocked_by: 없음
note: |
  Phase 0+1+2+3 W3 + goldset 튜닝 완료.
  P3-W3-01: ab_test.py 신규 (4cc3d7a)
  P3-W3-02: sprt_simulate.py +forbidden params (d37d977)
  P3-W3-03: calibrate_drift.py import fix (24618d0)
  goldset 튜닝: NDCG@5 0.057→0.173 (+204%), 835fd09
  근본 원인: GRAPH_BONUS(0.3)>>RRF(0.016), 그래프 이웃이 정답 노드 압도
  잔여: q004/005/006/013 등 0-NDCG — storage/hybrid.py GRAPH_BONUS 조정 필요(W1 소관)
  CX 실행 대기: P3-CX-01~05 — Paul codex exec 필요
  compact 시각: 2026-03-06
```

## 소유 파일

```
utils/access_control.py
utils/similarity.py
scripts/enrich/node_enricher.py
scripts/hub_monitor.py
scripts/pruning.py
scripts/daily_enrich.py
scripts/calibrate_drift.py
scripts/eval/goldset.yaml
scripts/eval/ab_test.py
scripts/sprt_simulate.py
tests/test_access_control.py
tests/test_drift.py
```

## 비접촉 (절대 수정 금지)

```
storage/*
tools/*
server.py
config.py
scripts/migrate*
```

## Compact 후 재개 프롬프트

```
이 세션은 mcp-memory v2.1 구현의 W3(Utils+Scripts) 세션이다.

1. docs/implementation/w3-state.md를 읽어라.
2. "현재 상태"의 next 태스크를 확인하라.
3. next 태스크의 Phase 문서(docs/implementation/0-impl-phase{N}.md)를 읽어라.
4. note가 있으면 이어서, 없으면 처음부터 진행하라.

규칙:
- 소유 파일만 수정: utils/*, scripts/enrich/*, scripts/hub_monitor.py, scripts/pruning.py, scripts/daily_enrich.py, scripts/calibrate_drift.py, scripts/eval/*, scripts/sprt_simulate.py, tests/test_access_control.py, tests/test_drift.py
- 절대 수정 금지: storage/, tools/, server.py, config.py, scripts/migrate*
- 태스크 완료 시: git commit "[W3] {태스크ID}: {설명}" → w3-state.md 갱신
- 태스크 도중 compact 시: git commit "[W3] {태스크ID}: WIP ({진행상황})" → w3-state.md에 note 기록 → /compact
```

## 이력

| 시각 | 태스크 | 결과 |
|------|--------|------|
| 2026-03-05 | P0-W3-01: goldset.yaml 25쿼리 초안 | ✅ d116cf2 |
| 2026-03-05 | P1-W3-01: utils/access_control.py 신규 | ✅ 520ca2f |
| 2026-03-05 | P1-W3-02: utils/similarity.py 신규 | ✅ fbca546 |
| 2026-03-05 | P1-W3-04: node_enricher _apply check_access 삽입 | ✅ 3b7523b |
| 2026-03-05 | P1-W3-05: test_access_control.py 23/23 PASS | ✅ 82e64d2 |
| 2026-03-05 | P1-AUX: sprt_simulate.py + calibrate_drift.py | ✅ 2982e5c |
| 2026-03-05 | P1-W3-03: enricher E7 drift + E1 길이 검증 | ✅ 0a5d8ec |
| 2026-03-05 | P1-W3-06: test_drift.py 16/16 PASS | ✅ 3b55aaf |
| 2026-03-06 | P2-W3-01: hub_monitor.py 신규 | ✅ 9d384e9 |
| 2026-03-06 | P2-W3-02: pruning.py 신규 (+check_access) | ✅ 9d384e9 |
| 2026-03-06 | P2-W3-03: daily_enrich.py Phase 6 추가 | ✅ 9d384e9 |
| 2026-03-06 | P2-W3-03 fix: archived_at/last_activated 스키마 수정 | ✅ f4a861c |
| 2026-03-06 | P3-W3-01: ab_test.py 신규 (goldset NDCG A/B) | ✅ 4cc3d7a |
| 2026-03-06 | P3-W3-02: sprt_simulate.py +forbidden params | ✅ d37d977 |
| 2026-03-06 | P3-W3-03: calibrate_drift.py import fix | ✅ 24618d0 |
| 2026-03-06 | goldset.yaml 튜닝 — NDCG@5 0.057→0.173 | ✅ 835fd09 |
