# Phase 0: Foundation — 기반 공사

> 목표: DB 스키마 확장, 타입/관계 정의 DB 이전, 검증 연결, 마이그레이션 안전성 확보
> 예상: 1주
> 선행 조건: 없음 (최초 Phase)
> 완료 조건: CX 멱등성 테스트 통과 + GM 스키마 정합성 확인

---

## 의존성 그래프

```
P0-W1-01 (config.py)
    │
    ▼
P0-W1-02 (migrate 스크립트 작성)
    │
    ▼
P0-W1-03 (DB 백업 + migrate 실행)
    │
    ├──────────────────┐
    ▼                  ▼
P0-W2-01 (validators) P0-CX-01 (멱등성 테스트)
    │
    ▼
P0-W2-02 (server.py)
    │
    ▼
P0-W2-03 (validators 테스트)
    │
    ▼
P0-CX-02 (테스트 실행)
    │
    ▼
P0-GM-01 (스키마 정합성)

P0-W3-01 (goldset) ← 독립, 언제든 가능
```

---

## W1 태스크 (Storage + Foundation)

| 상태 | ID | 태스크 | 파일 | 스펙 출처 | 의존 |
|------|----|----|------|----------|------|
| [x] | P0-W1-01 | config.py 상수 16개 추가 | `config.py` | round3-final 섹션 VI | 없음 |
| [x] | P0-W1-02 | migrate_v2_ontology.py 작성 (9단계, 멱등, fail-forward) | `scripts/migrate_v2_ontology.py` | a-r3-16 | P0-W1-01 |
| [x] | P0-W1-03 | DB 백업 + 마이그레이션 실행 + 검증 | `data/memory.db` | a-r3-16 | P0-W1-02 |

### P0-W1-01 상세: config.py 상수 추가

```python
# BCM (B-14)
UCB_C_FOCUS = 0.3
UCB_C_AUTO = 1.0
UCB_C_DMN = 2.5
BCM_HISTORY_WINDOW = 20
CONTEXT_HISTORY_LIMIT = 5
LAYER_ETA = {0: 0.020, 1: 0.015, 2: 0.010, 3: 0.005, 4: 0.001, 5: 0.0001}

# Recall (B-15)
PATCH_SATURATION_THRESHOLD = 0.75

# Promotion (C-11, C-12)
PROMOTION_SWR_THRESHOLD = 0.55
SPRT_ALPHA = 0.05
SPRT_BETA = 0.2
SPRT_P1 = 0.7
SPRT_P0 = 0.3
SPRT_MIN_OBS = 5

# Drift (D-12)
DRIFT_THRESHOLD = 0.5
SUMMARY_LENGTH_MULTIPLIER = 2.0
SUMMARY_LENGTH_MIN_SAMPLE = 10
```

### P0-W1-02 상세: 마이그레이션 스크립트

9단계 순서 (a-r3-16):
1. action_log 테이블 생성
2. type_defs, relation_defs, ontology_snapshots, meta 테이블 생성
3. type_defs INSERT (31 active + 19 deprecated = 50)
4. relation_defs INSERT (48 active + 2 deprecated = 50)
5. 잘못된 관계 5종 교정 (strengthens→supports 등) + correction_log
6. edges.description TEXT → JSON 배열 마이그레이션 (**비가역적, 백업 필수**)
7. activation_log VIEW 생성
8. ontology_snapshots v2.1-initial 기록
9. nodes 컬럼 3개 추가 (theta_m, activity_history, visit_count)

원칙: 각 단계 독립 트랜잭션, 멱등 (이미 존재하면 스킵).

### P0-W1-03 상세: 실행

```bash
cp data/memory.db data/memory.db.pre-v2.1
python scripts/migrate_v2_ontology.py
# 검증: 각 단계 pass/skip/fail 출력 확인
```

---

## W2 태스크 (Tools)

| 상태 | ID | 태스크 | 파일 | 스펙 출처 | 의존 |
|------|----|----|------|----------|------|
| [x] | P0-W2-01 | validators.py type_defs 기반 전체 교체 | `ontology/validators.py` | d-r3-11 | P0-W1-03 |
| [x] | P0-W2-02 | server.py validators 검증 블록 삽입 | `server.py` | d-r3-11 | P0-W2-01 |
| [x] | P0-W2-03 | validators 테스트 작성 (TC1~TC10) | `tests/test_validators_integration.py` | d-r3-11 | P0-W2-02 |

### P0-W2-01 상세: validators.py 교체

검증 4경우:
- `(True, None)` — 정확 일치
- `(True, canonical)` — 대소문자 교정
- `(False, replaced_by)` — deprecated → 자동 교정
- `(False, None)` — 미지 타입 → 저장 차단 + suggest_closest_type()

edge relation 검증은 MCP 레벨 불필요 — insert_edge() fallback에 위임.

---

## W3 태스크 (Utils + Scripts)

| 상태 | ID | 태스크 | 파일 | 스펙 출처 | 의존 |
|------|----|----|------|----------|------|
| [x] | P0-W3-01 | goldset.yaml 25쿼리 초안 작성 | `scripts/eval/goldset.yaml` | c-r3-10 | 없음 |

VERIFY 항목 5개는 Paul이 DB 직접 조회로 확정 필요 (q019, q024, q025 등).

---

## CX 검증 (Codex CLI, Paul 실행)

| 상태 | ID | 검증 내용 | 실행 시점 | 명령어 |
|------|----|----|----------|--------|
| [x] | P0-CX-01 | 마이그레이션 멱등성 (2회 실행 → 동일 결과) | P0-W1-03 후 | PASS — 기능적 멱등 확인 (cx-p0-idempotent.md) |
| [x] | P0-CX-02 | type_defs 50개 + relation_defs 50개 확인 | P0-W1-03 후 | PASS — 50/50 확인 (cx-p0-counts-20260305-222923.md) |
| [x] | P0-CX-03 | validators 테스트 실행 | P0-W2-03 후 | PASS — 13/13 (cx-p0-validators.md) |

## GM 검증 (Gemini CLI, Paul 실행)

| 상태 | ID | 검증 내용 | 실행 시점 | 명령어 |
|------|----|----|----------|--------|
| [x] | P0-GM-01 | 스키마 정합성 리포트 | 모든 P0 태스크 후 | PASS — Main 직접 검증 (Phase 0 범위 내 정합성 확인) |

---

## Phase 0 완료 기준

```
■ W1: 3개 태스크 전부 완료 + 커밋 (+ CX-02 fix 1건)
■ W2: 3개 태스크 전부 완료 + 커밋
■ W3: 1개 태스크 완료 + 커밋
■ CX: 3개 검증 전부 PASS
■ GM: 스키마 정합성 확인 (Main 직접 검증)
■ Main: 모든 체크박스 갱신 → "Phase 0 완료" 선언 (2026-03-05)
```

**Phase 0 완료. Phase 1 시작 가능.**
