# W3 State (Utils + Scripts)

> W3 세션만 이 파일을 수정한다.
> compact 전 반드시 갱신. compact 후 이 파일을 가장 먼저 읽는다.

## 현재 상태

```
phase: 0
last_done: P0-W3-01 (완료, d116cf2)
next: (P0 W3 태스크 없음 — 다른 세션 완료 대기)
blocked_by: P0-W1-03, P0-W2-03 (W1/W2 세션 의존)
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
