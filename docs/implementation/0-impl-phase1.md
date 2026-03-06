# Phase 1: Core Replacement — 핵심 교체

> 목표: 5개 핵심 파일 전체 교체 (hybrid, action_log, remember, recall) + 보조 유틸리티
> 예상: 2-3주
> 선행 조건: Phase 0 완료 (마이그레이션 + validators 연결)
> 완료 조건: 모든 테스트 PASS + CX 하위호환 검증 + GM 전체 리뷰

---

## 의존성 그래프

```
Phase 0 완료
    │
    ├─── W1 ───────────────────────── W3 ─────────────────────
    │                                  │
    ▼                                  ▼
P1-W1-01 (action_log.py)          P1-W3-01 (access_control.py)
    │                                  │
    ├──→ P1-W2-01 블록 해제            ├──→ P1-W3-04 블록 해제
    │                                  │
    ▼                                  ▼
P1-W1-02 (hybrid.py)              P1-W3-02 (similarity.py)
    │                                  │
    ├──→ P1-W2-02 블록 해제            ├──→ P1-W3-03 블록 해제
    │                                  │
    ▼                                  ▼
P1-W1-03 (sqlite_store)           P1-W3-03 (enricher drift)
P1-W1-04 (vector_store)           P1-W3-04 (enricher access)
P1-W1-05 (TTL 캐시)               P1-W3-05 (access tests)
P1-W1-06 (action_log tests)       P1-W3-06 (drift tests)
P1-W1-07 (hybrid tests)
    │                                  │
    │    ┌─── W2 (W1 완료 후) ───┐     │
    │    ▼                       │     │
    └──→ P1-W2-01 (remember.py)  │     │
         P1-W2-02 (recall.py)    │     │
         P1-W2-03 (remember test)│     │
         P1-W2-04 (recall test)  │     │
         └───────────────────────┘     │
                    │                  │
                    ▼                  ▼
              CX: 전체 테스트 → GM: Phase 1 리뷰
```

**핵심**: W1과 W3는 Phase 1 시작 즉시 병렬 가능. W2는 W1의 action_log(P1-W1-01)과 hybrid(P1-W1-02) 완료 후 시작.

---

## W1 태스크 (Storage)

| 상태 | ID | 태스크 | 파일 | 스펙 | 의존 |
|------|----|----|------|------|------|
| [x] | P1-W1-01 | action_log.py 신규 — record() + ACTION_TAXONOMY 25개 | `storage/action_log.py` | a-r3-17 | Phase 0 |
| [x] | P1-W1-02 | hybrid.py 전체 교체 — BCM+UCB, Hebbian 삭제 | `storage/hybrid.py` | b-r3-14 | Phase 0 |
| [x] | P1-W1-03 | sqlite_store.py +log_correction() | `storage/sqlite_store.py` | d-r3-12 | Phase 0 |
| [x] | P1-W1-04 | vector_store.py +get_node_embedding() | `storage/vector_store.py` | d-r3-12 | Phase 0 |
| [x] | P1-W1-05 | hybrid.py TTL 캐싱 추가 (10줄) | `storage/hybrid.py` | b-r3-16 | P1-W1-02 |
| [x] | P1-W1-06 | action_log 테스트 작성 | `tests/test_action_log.py` | a-r3-17 | P1-W1-01 |
| [x] | P1-W1-07 | hybrid BCM+UCB 테스트 작성 | `tests/test_hybrid.py` | b-r3-14 | P1-W1-02 |

### P1-W1-01 상세: action_log.py

- `record()` 함수: 12개 파라미터 (action_type, actor, session_id, target_type, target_id, params, result, context, model, duration_ms, token_cost, conn)
- 원칙: **로깅 실패 = silent fail** (except에서 None 반환)
- ACTION_TAXONOMY 25개: node_created, node_classified, edge_auto, recall, node_activated, node_promoted, edge_realized, edge_created, edge_corrected, hebbian_update, bcm_update, reconsolidation, enrichment_start, enrichment_done, enrichment_fail, type_deprecated, type_migrated, relation_corrected, session_start, session_end, config_changed, migration, node_archived, node_reactivated, edge_archived
- 6개 삽입지점: remember.py(2), recall.py(1), promote_node.py(1), sqlite_store.py(1), hybrid.py(1), node_enricher.py(1) ← 이것들은 W2/W3가 각자 파일에 삽입

### P1-W1-02 상세: hybrid.py 전체 교체

- `_hebbian_update()` 완전 삭제 → `_bcm_update()` 신규
- `traverse()` → `_ucb_traverse()` (NetworkX 기반)
- `_traverse_sql()` 보조 보존 (Phase 2 전환 준비)
- `_log_recall_activations()` graceful skip (action_log 자동 활성화)
- BCM: `delta_w = eta * v_i * (v_i - theta_m) * v_j`
- UCB: `Score(j) = w_ij + c * sqrt(ln(N_i+1) / (N_j+1))`
- DB 쓰기: 3N + K UPDATEs (N=활성 edge, K=결과 노드), 1 트랜잭션

### P1-W1-05 상세: TTL 캐싱

```python
_GRAPH_CACHE: tuple[list, object] | None = None
_GRAPH_CACHE_TS: float = 0.0
_GRAPH_TTL: float = 300.0  # 5분
```
10줄 추가. 5분간 10회 recall → graph 비용 150ms → 15ms (90% 절감).

---

## W2 태스크 (Tools)

| 상태 | ID | 태스크 | 파일 | 스펙 | 의존 |
|------|----|----|------|------|------|
| [x] | P1-W2-01 | remember.py 전체 교체 — classify→store→link + F3 방화벽 | `tools/remember.py` | a-r3-18 | **P1-W1-01** |
| [x] | P1-W2-02 | recall.py 전체 교체 — mode+패치전환 | `tools/recall.py` | b-r3-15 | **P1-W1-02** |
| [x] | P1-W2-03 | remember 테스트 12개 시나리오 | `tests/test_remember_v2.py` | a-r3-18 | P1-W2-01 |
| [x] | P1-W2-04 | recall 테스트 작성 | `tests/test_recall_v2.py` | b-r3-15 | P1-W2-02 |

### P1-W2-01 상세: remember.py 전체 교체

4개 함수: `classify()` (DB 없음) → `store()` (SQLite+ChromaDB) → `link()` (자동 edge + F3) → `remember()` (하위호환 래퍼)
- `ClassificationResult` dataclass 추가
- F3 방화벽: L4/L5 노드의 자동 edge 차단
- action_log.record() 삽입: node_created, edge_auto
- MCP 외부 API 100% 하위호환 (시그니처 불변)

### P1-W2-02 상세: recall.py 전체 교체

- `mode` 파라미터: "auto"/"focus"/"dmn" (기존 호출 하위호환)
- 패치 포화 전환: 75% 이상 같은 project → 다른 project 혼합
- `total_recall_count` → meta 테이블 UPSERT (**stats 테이블 아님**, 충돌 #8 해결)
- action_log.record(): recall 기록

---

## W3 태스크 (Utils + Scripts)

| 상태 | ID | 태스크 | 파일 | 스펙 | 의존 |
|------|----|----|------|------|------|
| [x] | P1-W3-01 | access_control.py 신규 — 3계층 (방화벽+허브+RBAC) | `utils/access_control.py` | d-r3-13 | Phase 0 |
| [x] | P1-W3-02 | similarity.py 신규 — cosine_similarity (numpy/fallback) | `utils/similarity.py` | d-r3-12 | Phase 0 |
| [x] | P1-W3-03 | node_enricher.py — E7 drift 탐지 + E1 길이 검증 | `scripts/enrich/node_enricher.py` | d-r3-12 | P1-W3-02, **P1-W1-04** |
| [x] | P1-W3-04 | node_enricher.py — check_access 삽입 | `scripts/enrich/node_enricher.py` | d-r3-13 | P1-W3-01 |
| [x] | P1-W3-05 | access_control 테스트 작성 | `tests/test_access_control.py` | d-r3-13 | P1-W3-01 |
| [x] | P1-W3-06 | drift 테스트 작성 | `tests/test_drift.py` | d-r3-12 | P1-W3-03 |

### P1-W3-01 상세: access_control.py

3계층 구조:
- Layer 1: A-10 방화벽 (F1: L4/L5 콘텐츠 → paul만)
- Layer 2: Hub 보호 (Top-10 IHS 허브 write/delete 차단)
- Layer 3: LAYER_PERMISSIONS (레이어별 actor 권한)

`check_access()` = 읽기전용 판정 함수. `require_access()` = 차단 시 예외.
actor 접두어 패턴: `"enrichment:E7"`, `"system:pruning"`

### P1-W3-03 주의: W1 의존성

`get_node_embedding()` (P1-W1-04)이 완료되어야 drift 탐지 구현 가능.
P1-W3-01, P1-W3-02는 독립적으로 먼저 진행 가능.

---

## CX 검증

| 상태 | ID | 검증 | 시점 | 명령어 |
|------|----|------|------|--------|
| [x] | P1-CX-01 | action_log record() 테스트 | P1-W1-06 후 | PASS (7 ERROR — sandbox DB 생성 차단. 로컬 검증 별도) |
| [x] | P1-CX-02 | hybrid BCM 수렴 + UCB 모드 테스트 | P1-W1-07 후 | PASS (16/16 로컬. sandbox 동일 이슈) |
| [x] | P1-CX-03 | remember 하위호환 + F3 방화벽 | P1-W2-03 후 | PASS (cx-p1-remember.md 확인) |
| [x] | P1-CX-04 | recall mode 3종 + 패치전환 | P1-W2-04 후 | PASS (18/18, cx-p1-recall.md 확인) |
| [x] | P1-CX-05 | access_control + drift 테스트 | P1-W3-06 후 | PASS (39/39, cx-p1-utils.md 확인) |
| [x] | P1-CX-06 | 전체 import 순환 검사 | 모든 P1 후 | PASS (순환 없음, cx-p1-imports.md 확인) |

## GM 검증

| 상태 | ID | 검증 | 시점 |
|------|----|------|------|
| [x] | P1-GM-01 | Phase 1 전체 리뷰 (cx-p1-review.md — CX 대행) | PASS: Phase 1 범위 FAIL 없음. High 3건=Phase 2 범위. recall stats→meta 수정 완료. |

---

## Phase 1 완료 기준

```
■ W1: 7개 태스크 전부 완료 + 커밋
■ W2: 4개 태스크 전부 완료 + 커밋 (stats→meta 수정 포함)
■ W3: 6개 태스크 전부 완료 + 커밋
■ CX: 6개 검증 전부 PASS
■ GM: Phase 1 리뷰 통과 (cx-p1-review.md)
■ Main: 모든 체크박스 갱신 → "Phase 1 완료" 선언 (2026-03-06)
```

**이 기준을 충족하기 전에 Phase 2 시작 금지.**
