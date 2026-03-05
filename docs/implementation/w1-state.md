# W1 State (Storage + Foundation)

> W1 세션만 이 파일을 수정한다.
> compact 전 반드시 갱신. compact 후 이 파일을 가장 먼저 읽는다.

## 현재 상태

```
phase: 0
last_done: P0-W1-03
next: (Phase 0 W1 완료 — W2/W3/CX/GM 대기)
blocked_by: 없음
```

## 소유 파일

```
config.py
storage/hybrid.py
storage/action_log.py
storage/sqlite_store.py
storage/vector_store.py
scripts/migrate_v2_ontology.py
tests/test_action_log.py
tests/test_hybrid.py
tests/test_migration.py
```

## 비접촉 (절대 수정 금지)

```
tools/*
utils/*
server.py
scripts/enrich/*
scripts/eval/*
scripts/hub_monitor.py
scripts/pruning.py
scripts/daily_enrich.py
```

## Compact 후 재개 프롬프트

```
이 세션은 mcp-memory v2.1 구현의 W1(Storage) 세션이다.

1. docs/implementation/w1-state.md를 읽어라.
2. "현재 상태"의 next 태스크를 확인하라.
3. next 태스크의 Phase 문서(docs/implementation/0-impl-phase{N}.md)를 읽어라.
4. note가 있으면 이어서, 없으면 처음부터 진행하라.

규칙:
- 소유 파일만 수정: config.py, storage/*, scripts/migrate*, tests/test_action_log.py, tests/test_hybrid.py, tests/test_migration.py
- 절대 수정 금지: tools/, utils/, server.py, scripts/enrich/, scripts/eval/
- 태스크 완료 시: git commit "[W1] {태스크ID}: {설명}" → w1-state.md 갱신
- 태스크 도중 compact 시: git commit "[W1] {태스크ID}: WIP ({진행상황})" → w1-state.md에 note 기록 → /compact
```

## 이력

| 시각 | 태스크 | 결과 |
|------|--------|------|
| 19:05 | P0-W1-01 | ✅ config.py 상수 16개 추가 (2bc0904) |
| 19:15 | P0-W1-02 | ✅ migrate_v2_ontology.py 9단계 작성 + governs 추가 (0bdd2c9) |
| 19:34 | P0-W1-03 | ✅ DB 백업 + 마이그레이션 9/9 성공 + 멱등성 확인 (a429e60) |
| 20:45 | P0-CX-02-fix | ✅ relation_defs 50행 보정: contextualizes 추가 + schema.yaml governs 반영 (fef526f) |
