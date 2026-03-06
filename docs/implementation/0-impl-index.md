# 구현 인덱스 — mcp-memory v2.1 온톨로지 구현

> compact 후 이 파일만 읽고 이어서 진행한다.
> 역할: 세션 관리, 태스크 추적, Phase 간 전환 제어

---

## 워크플로우

```
[Phase 0] Main → W1(Foundation) → CX/GM 검증 → Main 체크포인트
[Phase 1] Main → W1+W2+W3 병렬 → CX/GM 검증 → Main 체크포인트
[Phase 2] Main → W2+W3 병렬 → CX/GM 검증 → Main 체크포인트
[Phase 3] Main → CX+GM 검증 전용 → Main 최종 보고
```

**Phase N 완료 검증 전에 Phase N+1 시작 금지.** (ideation 안전 규칙 적용)

---

## 세션 구성

| 세션 | 도구 | 모델 | 역할 | 소유 파일 | 코드 수정 |
|------|------|------|------|----------|----------|
| **Main** | Claude Code | Opus | 오케스트레이터: 태스크 관리, 인덱스, 체크포인트 | `docs/implementation/*.md` | 문서만 |
| **W1** | Claude Code | Opus | Storage 레이어 + Foundation | `storage/*.py`, `config.py`, `scripts/migrate*` | **Yes** |
| **W2** | Claude Code | Sonnet | Tools 레이어 | `tools/*.py`, `server.py` | **Yes** |
| **W3** | Claude Code | Sonnet | Utils + Scripts | `utils/*.py`, `scripts/enrich/*`, `scripts/pruning*`, `scripts/hub*`, `scripts/eval/*` | **Yes** |
| **CX** | Codex CLI | - | 테스트 + 코드 리뷰 (태스크 단위) | 없음 | **절대 No** |
| **GM** | Gemini CLI | gemini-3.1-pro | 대규모 분석 + 리포트 (Phase 단위) | 없음 | **절대 No** |

### 왜 이 구성인가

**파일 소유권 분리**: W1/W2/W3가 동시에 작업해도 같은 파일을 건드리지 않음.
- W1 = storage 레이어 (데이터가 어떻게 저장/조회되는가)
- W2 = tools 레이어 (MCP 도구가 어떻게 동작하는가)
- W3 = utils + scripts (보조 유틸리티 + 배치 스크립트)

**CX/GM = 읽기 전용 검증**: Paul이 직접 Warp에서 실행. 코드 수정 절대 불가.

### Phase별 활성 세션

| Phase | 활성 세션 | 비활성 | 병렬 가능 |
|-------|----------|--------|----------|
| 0 | Main, W1 | W2, W3 | 불가 (W1 단독) |
| 1 | Main, W1, W2, W3 | - | **W1+W2+W3 병렬** |
| 2 | Main, W2, W3 | W1 | **W2+W3 병렬** |
| 3 | Main | W1, W2, W3 | CX+GM만 활성 |

---

## 파일 네이밍 규칙

### 설계 문서 (docs/implementation/)

```
0-impl-{주제}.md
```

인덱스/가이드/Phase 문서 모두 `0-impl-` 접두어. 세션 접두어 없음 (ideation과 다름 — 구현 문서는 오케스트레이터만 관리).

### 소스 코드

기존 경로 유지. 세션 접두어 없음.
```
storage/hybrid.py       ← W1이 수정
tools/remember.py       ← W2가 수정
utils/access_control.py ← W3가 수정
```

### 테스트 파일

```
tests/test_{모듈명}.py
```

테스트 파일은 해당 소스 코드를 소유한 세션이 작성.
- W1 → `tests/test_action_log.py`, `tests/test_hybrid.py`
- W2 → `tests/test_remember_v2.py`, `tests/test_recall_v2.py`
- W3 → `tests/test_access_control.py`, `tests/test_validators_integration.py`

---

## 파일 소유권 상세

### W1 (Storage + Foundation)

```
소유:
  config.py
  storage/hybrid.py
  storage/action_log.py          (신규)
  storage/sqlite_store.py        (수정: +log_correction)
  storage/vector_store.py        (수정: +get_node_embedding)
  scripts/migrate_v2_ontology.py (신규)
  tests/test_action_log.py       (신규)
  tests/test_hybrid.py           (신규)
  tests/test_migration.py        (신규)

비접촉:
  tools/*
  utils/*
  server.py
  scripts/enrich/*
```

### W2 (Tools)

```
소유:
  tools/remember.py              (전체 교체)
  tools/recall.py                (전체 교체)
  tools/promote_node.py          (전체 교체, Phase 2)
  tools/analyze_signals.py       (수정, Phase 2)
  server.py                      (수정: +validators 블록)
  ontology/validators.py         (전체 교체)
  tests/test_remember_v2.py      (신규)
  tests/test_recall_v2.py        (신규)
  tests/test_validators_integration.py (신규)

비접촉:
  storage/*
  utils/*
  config.py
  scripts/*
```

### W3 (Utils + Scripts)

```
소유:
  utils/access_control.py        (신규)
  utils/similarity.py            (신규)
  scripts/enrich/node_enricher.py (수정: drift+check_access)
  scripts/hub_monitor.py         (수정: +recommend)
  scripts/pruning.py             (수정: +check_access)
  scripts/daily_enrich.py        (수정: +Phase 6)
  scripts/calibrate_drift.py     (신규)
  scripts/eval/goldset.yaml      (신규)
  scripts/eval/ab_test.py        (신규)
  scripts/sprt_simulate.py       (신규)
  tests/test_access_control.py   (신규)
  tests/test_drift.py            (신규)

비접촉:
  storage/*
  tools/*
  server.py
  config.py
```

---

## Codex / Gemini 사용 가이드

### CX (Codex CLI) — 태스크 단위 검증

**사용 시점**: W1/W2/W3가 태스크 완료할 때마다.

```bash
# 코드 리뷰: 스펙 대비 구현 비교
codex exec "review /c/dev/01_projects/06_mcp-memory/storage/hybrid.py \
  against the spec in /c/dev/01_projects/06_mcp-memory/docs/ideation/b-r3-14-hybrid-final.md. \
  Check: BCM formula, UCB c values, layer eta mapping, edge cases. \
  Output: pass/fail per item." -o cx-review-hybrid.md

# 테스트 실행 + 리포트
codex exec "cd /c/dev/01_projects/06_mcp-memory && \
  python -m pytest tests/test_validators_integration.py -v 2>&1. \
  Report pass/fail with details." -o cx-test-validators.md

# diff 분석 (커밋 전)
codex exec "analyze git diff HEAD for /c/dev/01_projects/06_mcp-memory. \
  Check: import cycles, missing error handling, API breaking changes, \
  security issues." -o cx-diff-check.md

# 의존성 확인
codex exec "check all imports in /c/dev/01_projects/06_mcp-memory/storage/ \
  for circular dependencies. List the import graph." -o cx-imports.md
```

### GM (Gemini CLI) — Phase 단위 분석

**사용 시점**: Phase 완료 시 + 최종 리뷰.

```bash
# Phase 완료 리뷰 (긴 컨텍스트 활용)
gemini -m gemini-3.1-pro-preview \
  "analyze all changed files in /c/dev/01_projects/06_mcp-memory/ since tag v2.0. \
  Generate: dependency graph, breaking changes, test coverage gaps, \
  security concerns. Format as markdown report." \
  -o gm-phase1-review.md

# 스키마 정합성
gemini -m gemini-3.1-pro-preview \
  "compare the actual SQLite schema in /c/dev/01_projects/06_mcp-memory/data/memory.db \
  with the spec in docs/ideation/0-orchestrator-round3-final.md section V. \
  Report discrepancies." \
  -o gm-schema-check.md

# 전체 아키텍처 리포트 (Phase 3)
gemini -m gemini-3.1-pro-preview \
  "read all Python files in /c/dev/01_projects/06_mcp-memory/ (excluding tests/). \
  Generate a comprehensive architecture document: module responsibilities, \
  data flow, error handling patterns, configuration points." \
  -o gm-architecture-final.md
```

### 결과 처리 워크플로우

```
W1/W2/W3 태스크 완료
  → Paul이 CX 실행 (테스트/리뷰)
  → CX 결과를 Main 세션에서 확인
  → 문제 있으면: 해당 W 세션에 수정 지시 (구체적 파일+라인)
  → 문제 없으면: Main이 체크박스 갱신 → 다음 태스크

Phase 완료
  → Paul이 GM 실행 (전체 리뷰)
  → GM 결과를 Main 세션에서 확인
  → 문제 있으면: 해당 W 세션에 수정 지시
  → 문제 없으면: Main이 Phase 완료 선언 → 다음 Phase 프롬프트 배포
```

---

## 트래킹 메커니즘 — compact 후 손실 0 보장

### 3중 추적

```
[Layer 1] Phase 문서 체크박스  ← Main만 갱신 (CX/GM 검증 후)
[Layer 2] 세션 상태 파일       ← 각 세션이 자기 것만 갱신
[Layer 3] Git 커밋 메시지      ← 자동 감사 추적
```

### 세션 Compact 절차

**태스크 완료 시:**
```
1. git commit "[W{n}] {태스크ID}: {설명}"
2. w{n}-state.md 갱신 (last_done → 완료한 태스크, next → 다음 태스크)
```

**태스크 도중 compact 필요 시:**
```
1. git commit "[W{n}] {태스크ID}: WIP ({진행 상황})"
2. w{n}-state.md 갱신 (next → 현재 태스크 유지, note → 어디까지 했는지)
3. /compact
```

### Compact 후 재개

```
1. w{n}-state.md 읽기
2. next 태스크의 Phase 문서(0-impl-phase{N}.md) 읽기
3. note가 있으면 이어서, 없으면 처음부터 작업 시작
```

### Main Phase 전환 절차

```
1. 모든 W 세션 커밋 확인 (git log)
2. CX/GM 검증 전부 PASS 확인
3. Phase 문서 모든 체크박스 갱신
4. impl-index "현재 상태" 갱신
5. 다음 Phase 프롬프트 작성 → 각 W 세션에 전달
```

---

## 안전 규칙

### ideation에서 계승

1. **Phase N 완료 검증 전 Phase N+1 시작 금지**
2. **범용 프롬프트("이어서 진행해라") 금지** — 구체적 태스크 ID + 파일 경로 명시
3. **잘못된 작업 발생 시 /clear** (/compact 아님)

### implementation 추가 규칙

4. **파일 소유권 엄수** — W1은 tools/ 건드리지 않음, W2는 storage/ 건드리지 않음
5. **CX/GM은 절대 코드 수정 안 함** — 읽기/분석/테스트만
6. **커밋은 태스크 단위** — 하나의 태스크 = 하나의 커밋
7. **Phase 0 마이그레이션 전 DB 백업 필수** — `cp data/memory.db data/memory.db.pre-v2.1`

---

## 세션 Compact 지침

### Main (오케스트레이터)

```
이 세션은 mcp-memory v2.1 온톨로지 구현 오케스트레이터다.
docs/implementation/0-impl-index.md를 읽어라.
"현재 상태" 섹션을 확인하고 다음 할 일을 진행하라.
```

### W1 (Storage)

```
이 세션은 mcp-memory v2.1 구현의 W1(Storage) 세션이다.
docs/implementation/0-impl-index.md의 "W1 소유 파일"을 확인하라.
소유 파일만 수정한다. tools/, utils/, server.py 절대 수정 금지.
docs/implementation/0-impl-phase{N}.md에서 W1 태스크를 확인하고 진행하라.
```

### W2 (Tools)

```
이 세션은 mcp-memory v2.1 구현의 W2(Tools) 세션이다.
docs/implementation/0-impl-index.md의 "W2 소유 파일"을 확인하라.
소유 파일만 수정한다. storage/, utils/, config.py 절대 수정 금지.
docs/implementation/0-impl-phase{N}.md에서 W2 태스크를 확인하고 진행하라.
```

### W3 (Utils + Scripts)

```
이 세션은 mcp-memory v2.1 구현의 W3(Utils+Scripts) 세션이다.
docs/implementation/0-impl-index.md의 "W3 소유 파일"을 확인하라.
소유 파일만 수정한다. storage/, tools/, server.py, config.py 절대 수정 금지.
docs/implementation/0-impl-phase{N}.md에서 W3 태스크를 확인하고 진행하라.
```

---

## 설계 문서 목록

| # | 파일 | 내용 | 상태 |
|---|------|------|------|
| 1 | `0-impl-index.md` | 전체 인덱스 + 세션 구성 + compact 지침 | **완료** |
| 2 | `0-impl-ontology-guide.md` | 온톨로지 비기술자 설명 (10개 섹션) | **완료** |
| 3 | `0-impl-phase0.md` | Phase 0: Foundation (W1:3, W2:3, W3:1, CX:3, GM:1) | **완료** |
| 4 | `0-impl-phase1.md` | Phase 1: Core Replacement (W1:7, W2:4, W3:6, CX:6, GM:1) | **완료** |
| 5 | `0-impl-phase2.md` | Phase 2: Advanced Features (W1:1, W2:2, W3:3, CX:4, GM:1) | **완료** |
| 6 | `0-impl-phase3.md` | Phase 3: Validation & Tuning (W3:3, CX:5, GM:2) | **완료** |
| 7 | `w1-state.md` | W1 세션 상태 (compact 복구용) | **완료** |
| 8 | `w2-state.md` | W2 세션 상태 (compact 복구용) | **완료** |
| 9 | `w3-state.md` | W3 세션 상태 (compact 복구용) | **완료** |

---

## ideation 참조

구현 스펙은 `docs/ideation/` 13개 Round 3 파일에 있다:

| 세션 | 파일 | 핵심 스펙 |
|------|------|----------|
| A-16 | a-r3-16-migrate-script.md | 마이그레이션 9단계 스크립트 |
| A-17 | a-r3-17-actionlog-record.md | action_log.record() + 6개 삽입지점 |
| A-18 | a-r3-18-remember-final.md | remember() 4함수 분리 + F3 방화벽 + 테스트 12개 |
| B-14 | b-r3-14-hybrid-final.md | hybrid.py BCM+UCB 전체 교체 |
| B-15 | b-r3-15-recall-final.md | recall.py mode+패치전환 |
| B-16 | b-r3-16-graph-optimization.md | 그래프 캐싱 + SQL-only UCB |
| C-10 | c-r3-10-goldset-draft.md | 골드셋 25쿼리 |
| C-11 | c-r3-11-promotion-final.md | promote 3-gate 파이프라인 |
| C-12 | c-r3-12-sprt-validation.md | SPRT 수학 검증 |
| D-11 | d-r3-11-validators-final.md | validators type_defs 전환 |
| D-12 | d-r3-12-drift-final.md | drift 탐지 + summary 이상치 |
| D-13 | d-r3-13-access-control.md | access_control 3계층 |
| D-14 | d-r3-14-pruning-integration.md | daily_enrich Phase 6 |

29개 확정 결정: `docs/ideation/0-orchestrator-round3-final.md` 섹션 XII.

---

## 현재 상태 (compact 후 이 섹션을 가장 먼저 확인)

**현재: Phase 3 완료. v2.1 구현 완료.**

Phase 0 완료 (2026-03-05):
- [x] P0-W1-01~03: config.py + migrate 스크립트 + DB 마이그레이션
- [x] P0-W2-01~03: validators.py + server.py + 테스트 13/13
- [x] P0-W3-01: goldset.yaml 25쿼리 초안
- [x] P0-CX-01~03: 전부 PASS
- [x] P0-GM-01: PASS

Phase 1 완료 (2026-03-06):
- [x] W1: 7/7 (action_log, hybrid, sqlite_store, vector_store, TTL, 테스트2)
- [x] W2: 4/4 (remember, recall, 테스트2) + stats→meta 수정
- [x] W3: 6/6 (access_control, similarity, enricher drift/access, 테스트2)
- [x] CX: 6/6 PASS (cx-p1-*.md 6개 리포트)
- [x] GM: PASS (cx-p1-review.md — Phase 1 범위 이슈 없음, High 3건은 Phase 2 범위)

Phase 2 완료 (2026-03-06):
- [x] W1: 1/1 (hybrid +_sprt_check)
- [x] W2: 2/2 (promote 3-gate, analyze_signals)
- [x] W3: 3/3 (hub_monitor, pruning, daily_enrich Phase 6) + archived_at 수정
- [x] CX: 4/4 PASS
- [x] GM: PASS (Gemini 6/6 파일 전부 PASS)

Phase 3 완료 (2026-03-06):
- [x] W3: 3/3 (ab_test, sprt_simulate, calibrate_drift)
- [x] CX: 5/5 PASS (NDCG baseline, SPRT sim, drift cal, 117/117 tests, diff analysis)
- [x] GM: 2/2 PASS (아키텍처 리포트, 스키마 정합성)
- 결정: RRF k=30 유지, SPRT 파라미터 유지, DRIFT_THRESHOLD=0.5 유지
- 기록: NDCG@5=0.057 baseline (goldset 튜닝 대상)

v2.1 구현 완료 (2026-03-06). 마무리 체크리스트 진행 중.
