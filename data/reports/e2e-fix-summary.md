# E2E 점검 결과 및 수정 요약

> **Date**: 2026-03-04
> **Scope**: mcp-memory v2.0 enrichment pipeline Step 1-10
> **Method**: 3종 모델 교차 리뷰 (Sonnet + Opus + Codex) → 통합 분석 → 즉시 수정

---

## 1. 3종 리뷰 결과 비교

| | **Sonnet 4.6** | **Opus 4.6** | **Codex (gpt-5.3-codex xhigh)** |
|---|---|---|---|
| **완성도** | 78/100 | B+ | 48/100 |
| **Critical** | 3 | 9 (+C-0) | 8 |
| **Major** | 5 | 7 | 11 |
| **Minor** | 9 | 9 | 7 |
| **단독 발견** | method sig mismatch (C-1) | Phase 4-5 누락 작업, commit 원자성 | init_db v1 문제, CRUD 우회, schema.yaml 불일치 |

### 리포트 파일
- `data/reports/e2e-review-sonnet.md` (396줄)
- `data/reports/e2e-review-opus.md` (306줄)
- `data/reports/e2e-review-codex.md` (185줄)

---

## 2. 3종 공통 Critical

1. `daily_enrich.py` ↔ `graph_analyzer.py` 시그니처 불일치 (Phase 2,4 TypeError 크래시)
2. E7 embedding_text 생성되지만 ChromaDB 재임베딩 미반영
3. 헤비안 학습 / 시간 감쇠 / 유효강도 미구현

---

## 3. 수정 내역 (19개 Fix, 10개 파일)

### Tier 0 — 파이프라인 실행 가능

| Fix | 파일 | 내용 |
|-----|------|------|
| **F-1** | `graph_analyzer.py` | `run_e18/19/21/22_all()`에 `limit: int` 파라미터 추가 |
| **F-2** | `node_enricher.py` | E7 `_apply()`에서 `vector_store.add()` → ChromaDB 재임베딩 |
| **F-3** | `node_enricher.py` | `_update_node()`에 `self.conn.commit()` 추가 (C6 atomicity) |

### Tier 1 — 핵심 메커니즘

| Fix | 파일 | 내용 |
|-----|------|------|
| **F-4** | `hybrid.py` | `_hebbian_update()` — recall 결과 edge `frequency+1`, `last_activated` 갱신 |
| **F-6** | `migrate_v2.py` | `tier`, `maturity`, `observation_count` 3개 컬럼 추가 |
| **F-7** | `config.py` | `Principle→[Belief, Philosophy, Value]` 승격 경로 + PROMOTE_LAYER |
| **F-8** | `daily_enrich.py` | Phase 4에 `ga.run_e24_all()` 호출 추가 |
| **F-9** | `graph_analyzer.py` | `_insert_edge`에 `direction`, `reason`, `base_strength` 저장 |

### Tier 2 — 설계-구현 정합성

| Fix | 파일 | 내용 |
|-----|------|------|
| **F-12** | `e06_secondary_types.yaml` + `node_enricher.py` | 프롬프트에 45개 타입 목록 + 코드 allowlist 필터 |
| **F-13** | `e19_missing_links.yaml` + `graph_analyzer.py` | model_tier `bulk→deep`, E19 모델 변경 |
| **F-14** | `relation_extractor.py` | dry_run sentinel `-1` 카운트 방지 |
| **F-15** | `remember.py` | provisional flag `True(bool)→"true"(str)` 통일 |
| **F-20** | `graph_analyzer.py` | E19 관계 목록 20→48개 전체 전달 |
| **F-21** | `graph_analyzer.py` | E25 `all_types` 15→45개 전체 전달 |

### Tier 3 — 코드 위생

| Fix | 파일 | 내용 |
|-----|------|------|
| **F-18** | `daily_enrich.py` | `_last_inserted` → `re.stats["e13_new_edges"]` |
| **F-23** | `daily_enrich.py` | `total or 1` division by zero 방어 |
| **F-24** | `get_becoming.py` | 도메인 필터 substring→JSON 파싱 정확 매칭 |
| **F-25** | `relation_extractor.py` | f-string SQL에 `_ALLOWED_CLUSTER_FIELDS` guard |

---

## 4. 미수정 (v2.1 Defer)

| 항목 | 이유 |
|------|------|
| F-5: 시간 감쇠 스크립트 | 별도 daily decay 스크립트 필요 — 규모 큼 |
| F-10: init_db v2 컬럼 | sqlite_store.py 구조 변경 필요 — migrate_v2 선행 실행으로 대체 |
| F-11: schema.yaml v2 갱신 | 45개 타입 반영 — 별도 세션 |
| F-16: relate/connect MCP 도구 | 신규 파일 — 별도 구현 세션 |
| F-17: remember() docstring 갱신 | Minor |
| F-19: phase_limit 변수 | Minor — 사용 or 제거 결정 필요 |
| F-22: 프롬프트 언어 통일 | 정책 결정 필요 |

---

## 5. 검증

- **구문 검증**: 10개 파일 `ast.parse()` 전부 PASS
- **기능 검증**: F-1~F-25 개별 assert 전부 PASS
- **통합 검증**: 실제 DB 대상 import + 메서드 시그니처 + 소스 검사 PASS

---

## 6. 교훈

1. **복수 모델 교차 검증이 단일 모델보다 커버리지 높음** — 각 모델이 다른 시각으로 다른 문제 발견
2. **Codex CLI 모델명 주의** — config.toml 기본값 사용, `-m` 오버라이드 회피
3. **enrichment pipeline의 "마지막 1마일"** — 메서드 존재 ≠ 오케스트레이션 연결. 시그니처 정합성과 데이터 영속성이 핵심
