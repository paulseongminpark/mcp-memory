# T2-C-04 — Scripts Layer Architecture Review

> **Round**: 2 (Architecture)
> **Reviewer**: rv-c2 (Claude Opus)
> **Scope**: scripts/*.py (19 files), scripts/enrich/*.py (5 files), scripts/eval/*.py (1 file) — 총 25 파일, ~6,500 LOC
> **Key Question**: "이것이 잘 설계되었는가?"
> **Focus**: Script-library boundary, code reuse with main code, CLI interface design, idempotency

---

## Executive Summary

Scripts 레이어는 25개 파일(~6,500 LOC)로 enrichment 파이프라인, 마이그레이션, 모니터링, 시뮬레이션을 담당한다. **enrich/ 서브모듈 3개(node_enricher, graph_analyzer, relation_extractor)가 전체의 44%**를 차지하며, 이 3개 파일에서 `_call_json()` API 호출 로직이 완전 복사-붙여넣기 되어 있다. 또한 pruning 로직이 daily_enrich.py와 pruning.py에 중복되고, DB_PATH가 3개 스크립트에서 config.py 대신 하드코딩되어 있다. CLI 인터페이스는 dry-run 기본값이 스크립트마다 반대이다.

**발견 사항**: HIGH 2 / MEDIUM 5 / LOW 3 / INFO 3

---

## Findings

### H-01: `_call_json()` Triplicated — 2,900 LOC에 걸친 API 호출 중복

**Severity**: HIGH
**Files**: enrich/node_enricher.py, enrich/graph_analyzer.py, enrich/relation_extractor.py

세 파일 모두 거의 동일한 `_call_json()` 메서드를 포함한다:

```python
# 3개 파일에서 반복되는 패턴:
def _call_json(self, model, system_prompt, user_prompt):
    # 1. API provider 분기 (Anthropic vs OpenAI)
    # 2. 재시도 로직 (MAX_RETRIES, exponential backoff)
    # 3. 429 Rate Limit 처리 (parse_retry_after)
    # 4. JSON 응답 파싱
    # 5. 토큰 예산 차감 (TokenBudget.record)
    # 6. BudgetExhausted 예외 던지기
```

| File | LOC | `_call_json()` 추정 LOC |
|------|-----|----------------------|
| node_enricher.py | 806 | ~60 |
| graph_analyzer.py | 1,019 | ~60 |
| relation_extractor.py | 1,067 | ~60 |

추가로 진행바/ETA 계산, ThreadPoolExecutor 패턴도 중복된다.

**문제점**:
1. API provider 분기 로직 수정 시 3개 파일 동시 수정 필요
2. 재시도 정책 불일치 가능 (한 파일만 수정 시)
3. 전체 enrich/ 서브모듈이 2,892 LOC — `_call_json` 중복 없이 ~2,700 LOC 가능

**권장**: `enrich/api_client.py` 공통 모듈 추출:
```python
class EnrichmentAPIClient:
    def call_json(self, model, system, user) -> dict: ...
    def call_json_batch(self, items, workers) -> list: ...
```

---

### H-02: Pruning Logic Duplicated — daily_enrich.py vs pruning.py

**Severity**: HIGH
**Files**: daily_enrich.py (648줄), pruning.py (196줄)

daily_enrich.py의 `phase6_pruning()` 내부 함수와 pruning.py의 stage 함수가 거의 동일:

| daily_enrich.py | pruning.py | 차이 |
|-----------------|------------|------|
| `_run_edge_pruning()` | `stage1_identify_candidates()` | SQL 동일, 출력 형식만 다름 |
| `_run_node_stage2()` | `stage2_mark_candidates()` | actor 하드코딩 vs 파라미터 |
| `_run_node_stage3()` | `stage3_archive_expired()` | 동일 로직 |

**문제점**:
1. pruning 기준(quality_score < 0.3, observation_count < 2, 90일 등) 수정 시 두 파일 동시 수정 필요
2. daily_enrich의 actor가 `'system:daily_enrich'`로 하드코딩, pruning.py는 `--actor` CLI 파라미터 — 불일치

**권장**: pruning.py를 library로 유지하고, daily_enrich.py phase6에서 `from scripts.pruning import stage2_mark_candidates` 형태로 import.

---

### M-01: DB_PATH Hardcoding — config.py 우회 3건

**Severity**: MEDIUM
**Files**: safety_net.py, export_to_obsidian.py, calibrate_drift.py

```python
# safety_net.py
DB_PATH = Path(__file__).parent.parent / "data" / "memory.db"

# export_to_obsidian.py
# 하드코딩된 절대 경로 (C:/dev/...)

# calibrate_drift.py
DB_PATH = ROOT / "data" / "memory.db"  # config 미참조
```

config.py에 `DB_PATH`가 이미 정의되어 있지만 3개 스크립트가 독립적으로 경로를 계산한다.

**문제점**: DB 위치 변경 시 config.py + 3개 스크립트 동시 수정 필요.
**권장**: `from config import DB_PATH` 통일.

---

### M-02: Inconsistent Dry-Run Defaults

**Severity**: MEDIUM
**Files**: daily_enrich.py, pruning.py, hub_monitor.py

| Script | Default Behavior | Flag to Change |
|--------|-----------------|---------------|
| daily_enrich.py | 실행 | `--dry-run` to skip |
| pruning.py | dry-run | `--execute` to run |
| hub_monitor.py | 출력만 | `--snapshot` to write |
| calibrate_drift.py | 실행 | `--dry-run` to skip |

**문제점**: 사용자가 스크립트별로 "기본이 안전인지 위험인지" 기억해야 한다. pruning은 기본 안전, daily_enrich은 기본 실행.

**권장**: 모든 데이터 변경 스크립트는 **기본 dry-run** 통일. `--execute` 또는 `--commit` 플래그로 실제 실행.

---

### M-03: Script-Library Boundary Blur — enrich/ 모듈

**Severity**: MEDIUM
**Files**: enrich/node_enricher.py, enrich/graph_analyzer.py, enrich/relation_extractor.py

이 3개 파일은 `scripts/` 디렉토리에 위치하지만 실제로는 **라이브러리 모듈**이다:
- daily_enrich.py가 import하여 사용
- server.py에서도 dashboard.py를 import
- 독립 실행 불가 (CLI 없음)

```
scripts/
├── daily_enrich.py        ← 진짜 스크립트 (CLI, __main__)
├── pruning.py             ← 진짜 스크립트 (CLI, __main__)
├── enrich/
│   ├── node_enricher.py   ← 라이브러리 (클래스, import용)
│   ├── graph_analyzer.py  ← 라이브러리 (클래스, import용)
│   └── relation_extractor.py ← 라이브러리 (클래스, import용)
```

**문제점**: scripts/ 디렉토리의 의미가 "실행 가능한 스크립트"인데, enrich/는 라이브러리.
**영향**: 코드 탐색 시 혼란, import 경로가 `scripts.enrich.node_enricher`로 불자연스러움.
**권장**: enrich/를 프로젝트 루트의 별도 모듈(예: `enrichment/`)로 이동하거나, 현재 위치 유지 시 README에 boundary 문서화.

---

### M-04: serve_dashboard.py Duplicates dashboard.py Logic

**Severity**: MEDIUM
**Files**: serve_dashboard.py (140줄), dashboard.py (351줄)

serve_dashboard.py가 dashboard.py의 데이터 조회 로직을 **그대로 복사**하여 `_get_fresh_html()` 함수를 구현한다.

```python
# serve_dashboard.py — dashboard.py 로직 복제
def _get_fresh_html():
    # 100+ 줄의 SQL 쿼리 + HTML 생성 — dashboard.py와 동일
```

**문제점**: dashboard 쿼리/표현 수정 시 두 파일 동시 수정 필요.
**권장**: `dashboard.generate_dashboard()`를 호출하거나, 공통 데이터 함수를 분리.

---

### M-05: migrate_v2_ontology.py CLI 부재 + 하드코딩 데이터

**Severity**: MEDIUM
**File**: migrate_v2_ontology.py (638줄)

1. **CLI 없음**: `--dry-run`, `--check` 옵션 없이 바로 실행. migrate_v2.py는 3-mode CLI를 제공하는 것과 대조적.
2. **하드코딩 데이터**: ACTIVE_TYPES(31개), DEPRECATED_TYPES(19개), RELATION_DEFS(49개)가 파일 내부에 리터럴로 정의. schema.yaml이나 config.py와 동기화 없음.

```python
# migrate_v2_ontology.py 내부
ACTIVE_TYPES = [
    "Observation", "Evidence", "Trigger", ...  # 31개 하드코딩
]
DEPRECATED_TYPES = {
    "Fact": "Evidence", "Habit": "Ritual", ...  # 19개 하드코딩
}
```

**문제점**: schema.yaml에 타입 추가/제거 시 이 파일도 수정 필요 — T2-C-03 H-01(Triple Source of Truth)과 동일 문제의 4번째 소스.

---

### L-01: Connection Cleanup — finally 블록 부재

**Severity**: LOW
**Files**: dashboard.py, ontology_review.py, hub_monitor.py

```python
# dashboard.py — finally 없음
conn = sqlite3.connect(DB_PATH)
# ... 300줄의 로직 ...
conn.close()  # 예외 시 도달 못 함
```

**대조**: export_to_obsidian.py, calibrate_drift.py는 `try-finally` 사용 — 올바른 패턴.
**권장**: `with contextlib.closing(sqlite3.connect(...)) as conn:` 패턴 통일.

---

### L-02: No CLI for Several Scripts

**Severity**: LOW
**Files**: safety_net.py, export_to_obsidian.py, ontology_review.py, migrate_v2_ontology.py

4개 스크립트가 argparse 없이 `if __name__` 직접 실행만 지원한다. 특히 migrate_v2_ontology.py는 데이터 변경 스크립트인데 `--dry-run` 옵션이 없어 위험.

---

### L-03: sprt_simulate.py — SPRT 로직 자체 구현

**Severity**: LOW
**File**: sprt_simulate.py (205줄)

SPRT LLR 계산 로직을 자체 구현한다. hybrid.py의 SPRT 로직과 공식은 동일하지만 코드는 독립적.

```python
# sprt_simulate.py — 자체 SPRT
A = math.log((1 - beta) / alpha)
B = math.log(beta / (1 - alpha))
```

**완화**: 시뮬레이션 전용 스크립트이므로 런타임 코드와 독립성이 오히려 장점.
**권장**: config.py의 SPRT_ALPHA, SPRT_BETA 등을 import하여 기본값으로 사용.

---

### I-01: Idempotency — Generally Well Designed (Positive)

**Severity**: INFO (Positive Finding)

대부분의 스크립트가 멱등성을 잘 유지한다:

| Pattern | Scripts | Mechanism |
|---------|---------|-----------|
| State-based filter | daily_enrich, pruning | `WHERE status='active'`, `enriched_at IS NULL` |
| File overwrite | dashboard, export_to_obsidian, ontology_review | 매번 새로 생성 |
| Pure read | session_context, safety_net, ab_test | DB 변경 없음 |
| Pure function | sprt_simulate | 부작용 없음 |
| Column existence check | migrate_v2 | `add_column()` → 이미 있으면 skip |

---

### I-02: migrate_v2.py — Best Practice CLI Design (Positive)

**Severity**: INFO (Positive Finding)

migrate_v2.py는 3-mode CLI + 백업 + 롤백을 제공한다:

```
--dry-run    : 변경 없이 상태 확인
--check      : 마이그레이션 필요 여부만 진단
(default)    : 백업 → 마이그레이션 → 롤백 가능
```

각 step이 독립적이고 멱등적이며, `backup_db()` + `conn.rollback()` + `finally: conn.close()` 구조가 완비. 다른 데이터 변경 스크립트의 모범 사례.

---

### I-03: enrich/ Module Decomposition (Positive)

**Severity**: INFO (Positive Finding)

enrichment 로직을 4개 모듈로 분리한 구조는 우수하다:

| Module | Responsibility | LOC |
|--------|---------------|-----|
| token_counter.py | 예산 관리 + Rate limiting | 279 |
| prompt_loader.py | YAML 프롬프트 로딩 | 63 |
| node_enricher.py | E1-E12 개별 노드 enrichment | 806 |
| graph_analyzer.py | E18-E25 그래프 레벨 분석 | 1,019 |
| relation_extractor.py | E13-E17 관계 추출/정제 | 1,067 |

`TokenBudget`과 `PromptLoader`가 공유 유틸로 잘 분리되어 있고, `BudgetExhausted` 예외를 통한 파이프라인 중단이 일관적이다.

---

## Script Inventory

| Script | LOC | Type | CLI | Reuses Library | Idempotent |
|--------|-----|------|-----|---------------|------------|
| enrich/relation_extractor.py | 1,067 | Library | - | config, token_counter | N/A |
| enrich/graph_analyzer.py | 1,019 | Library | - | config, token_counter | N/A |
| enrich/node_enricher.py | 806 | Library | - | config, sqlite_store, vector_store, access_control, similarity | N/A |
| daily_enrich.py | 648 | Script | argparse | enrich/*, config, action_log, access_control | Yes |
| migrate_v2_ontology.py | 638 | Script | None | config | Partial |
| migrate_v2.py | 422 | Script | argparse (3-mode) | config | Yes |
| dashboard.py | 351 | Library+Script | None | config | Yes |
| enrich/token_counter.py | 279 | Library | - | - | N/A |
| ab_test.py | 242 | Script | argparse | hybrid_search | Yes |
| sprt_simulate.py | 205 | Script | argparse | - | Yes |
| pruning.py | 196 | Script | argparse | config, access_control | Yes |
| hub_monitor.py | 179 | Script | argparse | config, access_control | Yes |
| export_to_obsidian.py | 178 | Script | None | - (hardcoded) | Yes |
| session_context.py | 156 | Script | sys.argv | config | Yes |
| calibrate_drift.py | 149 | Script | argparse | similarity, embed (lazy) | Yes |
| serve_dashboard.py | 140 | Script+Server | argparse | dashboard (duplicated) | Yes |
| ontology_review.py | 125 | Script | None | config, validators | Yes |
| enrich/prompt_loader.py | 63 | Library | - | - | N/A |
| safety_net.py | 58 | Script | None | - (hardcoded) | Yes |

---

## Summary Table

| ID | Severity | Category | Finding | Files |
|----|----------|----------|---------|-------|
| H-01 | HIGH | Code Reuse | `_call_json()` 3중 복사 (API 호출 + 재시도 + 예산) | node_enricher, graph_analyzer, relation_extractor |
| H-02 | HIGH | Code Reuse | pruning stage2/3 로직 daily_enrich vs pruning 중복 | daily_enrich, pruning |
| M-01 | MEDIUM | Config | DB_PATH 하드코딩 3건 (config.py 우회) | safety_net, export_to_obsidian, calibrate_drift |
| M-02 | MEDIUM | CLI | dry-run 기본값 불일치 (실행 vs 안전) | daily_enrich, pruning |
| M-03 | MEDIUM | Boundary | enrich/ = 라이브러리인데 scripts/ 안에 위치 | enrich/*.py |
| M-04 | MEDIUM | Code Reuse | serve_dashboard.py가 dashboard.py 로직 복제 | serve_dashboard, dashboard |
| M-05 | MEDIUM | CLI | migrate_v2_ontology.py CLI 없음 + 타입 하드코딩 | migrate_v2_ontology |
| L-01 | LOW | Error | finally 블록 없는 DB 연결 정리 | dashboard, ontology_review, hub_monitor |
| L-02 | LOW | CLI | 4개 스크립트 argparse 부재 | safety_net, export, ontology_review, migrate_onto |
| L-03 | LOW | Code Reuse | sprt_simulate SPRT 로직 자체 구현 (config 미참조) | sprt_simulate |
| I-01 | INFO | Positive | 멱등성 전반적으로 우수 (state-based filter) | 전체 |
| I-02 | INFO | Positive | migrate_v2.py 3-mode CLI + 백업/롤백 모범 사례 | migrate_v2 |
| I-03 | INFO | Positive | enrich/ 모듈 분리 (TokenBudget, PromptLoader 공유) | enrich/*.py |

---

## Cross-Reference with Previous Reports

| Previous Finding | T2-C-04 Overlap |
|-----------------|-----------------|
| T2-C-01 H-01 Connection Management | L-01 동일 패턴 — scripts에서도 finally 없는 conn.close() |
| T2-C-02 H-01 Private API `_connect()` | daily_enrich, hub_monitor 등도 자체 `_connect()` 또는 `sqlite3.connect()` 직접 사용 |
| T2-C-02 H-02 `_get_total_recall_count()` 중복 | H-01과 동일 패턴 — 코드 복사-붙여넣기 문화 |
| T2-C-03 H-01 Triple Source of Truth | M-05에서 4번째 소스 발견 (migrate_v2_ontology 하드코딩) |

---

## Top 3 Architecture Recommendations

1. **`enrich/api_client.py` 공통 모듈 추출** — `_call_json()`, 재시도 로직, 429 처리, 진행바를 단일 모듈로. node_enricher, graph_analyzer, relation_extractor가 이를 상속/조합. H-01 해결. 예상 감소: ~180 LOC.

2. **pruning.py를 daily_enrich phase6의 소스로 통일** — daily_enrich.py가 pruning.py 함수를 import. actor 파라미터화. H-02 해결.

3. **CLI 표준화** — 모든 데이터 변경 스크립트에 `--dry-run` 기본, `--execute` 플래그 통일. migrate_v2.py의 3-mode 패턴을 표준으로. M-02, M-05, L-02 해결.
