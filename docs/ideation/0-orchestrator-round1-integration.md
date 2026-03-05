# Round 1 → 2 통합 보고서

> 오케스트레이터 | 2026-03-05 | Opus 4.6
> 입력: A(11파일) + B(9파일) + C(5파일) + D(7파일) = 32파일 전체 읽기 완료

---

## I. 세션 간 연결 지점 & 시너지

| 연결 | 세션 | 시너지 |
|------|------|--------|
| `action_log` = 모든 것의 기반 | A-9 설계 → B(recall_log), C(total_queries), D(activation_log) 전부 의존 | **1순위 구현** |
| BCM 학습 규칙 | B-1(상세 설계) + C-2(NumPy 확인) + D-2(tanh/BCM 순서) | B-1이 정본, D-2는 보조 |
| Pruning 이중 설계 | B-6(**edge** pruning, ctx_log 기반) + D-6(**node** pruning, BSP 3단계) | 상호보완. 둘 다 필요 |
| 방화벽 + RBAC | A-6/A-10(F1-F6 코드) + D-3(IHS + RBAC 허브 보호) | A가 코어, D가 모니터링 |
| 승격 모델 3중 | B-2(SWR readiness) + C-3(MDL/Bayesian/SPRT) | SWR=게이트, C-3=판단 모델 |
| 검색 성능 | B-7(SQL CTE, 100-500x) + B-8(RWR surprise) + C-4(RRF k=30) | 순서: B-7 → C-4 → B-8 |
| 시간축 | B-5(edge 재공고화 ctx_log) + D-5(activation_log + temporal_search) | 상호보완 |

---

## II. 충돌하는 제안 3가지 + 판정

| # | 충돌 | 세션 | 판정 | 근거 |
|---|------|------|------|------|
| 1 | action_log vs activation_log | A-9(범용 24타입) vs D-5(recall 전용) | A-9 action_log가 상위. D-5는 view/subset | action_log가 에너지(A-7), 빼기(A-8), temporal(D-5) 모두 커버 |
| 2 | tanh 먼저 vs BCM 직행 | D-2("tanh→BCM") vs B-1("BCM 직행") | BCM 직행 | B-1이 레이어별 η + 적응형 θ + Oja pruning 전처리까지 설계. 충분히 안전 |
| 3 | edge.description 재활용 vs 별도 테이블 | B-5(edges.description→JSON) vs D-5(activation_log 테이블) | 둘 다 유지 | 목적 다름: B-5=edge별 맥락(pruning용), D-5=노드별 활성화 이력(temporal/에너지용) |

---

## III. DB 스키마 변경 통합

### 신규 테이블

```sql
-- A-9: 모든 후속 작업의 데이터 소스
CREATE TABLE action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    session_id TEXT,
    action_type TEXT NOT NULL,   -- 24 types (ACTION_TAXONOMY)
    target_type TEXT,
    target_id INTEGER,
    params TEXT DEFAULT '{}',
    result TEXT DEFAULT '{}',
    context TEXT,
    model TEXT,
    duration_ms INTEGER,
    token_cost INTEGER,
    created_at TEXT NOT NULL
);

-- A-1/A-4: 메타-인스턴스 분리
CREATE TABLE type_defs (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    layer INTEGER NOT NULL,
    super_type TEXT,
    description TEXT,
    status TEXT DEFAULT 'active',
    rank TEXT DEFAULT 'normal',
    deprecated_reason TEXT,
    replaced_by TEXT,
    version INTEGER DEFAULT 1,
    created_at TEXT, updated_at TEXT
);

CREATE TABLE relation_defs (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    category TEXT,
    direction_constraint TEXT,
    layer_constraint TEXT,
    status TEXT DEFAULT 'active',
    deprecated_reason TEXT,
    replaced_by TEXT,
    version INTEGER DEFAULT 1,
    created_at TEXT, updated_at TEXT
);

-- B-2: SWR vec_ratio 계산용
CREATE TABLE recall_log (
    id INTEGER PRIMARY KEY,
    node_id INTEGER,
    source TEXT,
    query_hash TEXT,
    recalled_at TEXT
);

-- D-3: 주간 허브 스냅샷
CREATE TABLE hub_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    node_id TEXT NOT NULL,
    ihs_score REAL,
    degree INTEGER,
    betweenness REAL,
    risk_level TEXT
);

-- A-4: 분기별
CREATE TABLE ontology_snapshots (
    id INTEGER PRIMARY KEY,
    version_tag TEXT UNIQUE NOT NULL,
    type_defs_json TEXT,
    relation_defs_json TEXT,
    change_summary TEXT,
    created_at TEXT
);
```

### nodes 컬럼 추가

| 컬럼 | 타입 | 기본값 | 출처 |
|------|------|--------|------|
| θ_m | REAL | 0.5 | B-1 BCM |
| activity_history | TEXT | null | B-1 BCM |
| visit_count | INTEGER | 0 | B-3 UCB |
| access_level | TEXT | 'shared' | A-3 PKG |
| score_history | TEXT | '[]' | C-3 SPRT |
| bcm_threshold | REAL | 0.5 | C-2/B-1 |
| replaced_by | TEXT | null | D-2 deprecation |

### edges 컬럼 추가

| 컬럼 | 타입 | 기본값 | 출처 |
|------|------|--------|------|
| archived_at | TEXT | null | B-6 pruning |
| probation_end | TEXT | null | B-6 pruning |
| description | TEXT→JSON 마이그레이션 | '[]' | B-5 reconsolidation |

---

## IV. 구현 우선순위 로드맵

### Phase 0: 기반 (1주) — 위험도 0

| # | 항목 | 출처 | 소요 |
|---|------|------|------|
| 1 | action_log 테이블 + record() | A-9 | 2시간 |
| 2 | validators.py → remember()/insert_edge() 연결 | D-1 | 30분 |
| 3 | _detect_semantic_drift() E7 방어 | D-1 | 1시간 |
| 4 | L4/L5 6개 orphan → 수동 edge 생성 (Paul 확인) | A-10 | 30분 |
| 5 | type_defs + relation_defs 메타 테이블 | A-1/A-4 | 2시간 |

### Phase 1: 뉴럴 코어 (2-3주) — 위험도 낮음

| # | 항목 | 출처 | 소요 |
|---|------|------|------|
| 6 | B-5 재공고화 (edges.description JSON) | B-5 | 1시간 |
| 7 | B-7 SQL CTE traverse (NetworkX BFS 교체) | B-7 | 반나절 |
| 8 | BCM 학습 규칙 (_hebbian_update 교체) | B-1 | 반나절 |
| 9 | 방화벽 F1-F3 하드코딩 | A-10 | 2시간 |
| 10 | RRF k=30 변경 | C-4 | 5분 |

### Phase 2: 지능 (4-6주) — 위험도 중간

| # | 항목 | 출처 |
|---|------|------|
| 11 | UCB traverse (c=0.3/1.0/2.5) | B-3 |
| 12 | 패치 전환 (foraging) | B-4 |
| 13 | SWR readiness (승격 게이트) | B-2 |
| 14 | 시간 감쇠 _effective_strength | D-2 |
| 15 | temporal_search + recall_temporal MCP | D-5 |
| 16 | 19개 미사용 타입 deprecated | A-11 |

### Phase 3: 가지치기 & 메트릭 (7-10주)

| # | 항목 | 출처 |
|---|------|------|
| 17 | Node pruning BSP 3단계 | D-6 |
| 18 | Edge pruning (Bäuml + ctx_log) | B-6 |
| 19 | Hub IHS 모니터링 | D-3 |
| 20 | Small world σ 측정 | D-4 |
| 21 | Swing-toward rewiring | B-9/D-4 |

### Phase 4: 고급 (3개월+)

| # | 항목 | 출처 |
|---|------|------|
| 22 | Bayesian 승격 (scipy Beta) | C-3 |
| 23 | SPRT 실시간 감지 | C-3 |
| 24 | MDL 승격 검증 (LLM) | C-3 |
| 25 | RWR surprise | B-8 |
| 26 | 온톨로지 버전관리 스냅샷 | A-4 |
| 27 | Provenance 테이블 | A-3 |
| 28 | 아카이브 정책 | A-5 |
| 29 | 에너지 추적 자동화 | A-7 |

---

## V. 핵심 수치 (Round 1 기준)

- 노드: 3,230 (31/50 타입 사용, 19개 미사용)
- 엣지: 6,020 (95.2% enrichment 생성)
- L4/L5: 6개 전부 orphan (edge 0)
- tier=2 미검증: 77.5%
- L1 과밀: 58.5%
- 잘못된 관계: 6개 (governs 유지, 나머지 5개 교정)
- PyTorch 전환 임계점: 60K+ edges

---

## VI. Round 2 프롬프트 (전달 완료)

### A세션: action_log+activation_log 통합, 마이그레이션 SQL, remember() 3함수 분리, 에너지-enrichment 연결
### B세션: B-5 실제 코드, B-7 SQL CTE 실제 교체, BCM+UCB 통합, recall() 전체 흐름
### C세션: 골드셋 구축, 승격 모델 통합 흐름, Missing Link Detector, B세션 정합성
### D세션: validators 실제 코드, drift detector 완성, hub_monitor 실행 가능화, activation→action_log 통합

---

## VII. 미결 질문 (Round 2에서 해결 필요)

1. action_log와 activation_log를 별도 테이블로 유지할지, view로 통합할지 (A+D 세션이 합의)
2. edges.description 마이그레이션 시 기존 텍스트값 처리 (B세션)
3. hub_monitor.py의 node_id 타입 (INTEGER vs TEXT) — DB 스키마 확인 (D세션)
4. BCM θ_m 초기값 마이그레이션 방법 (B세션)
5. 골드셋 구축에 Paul 참여 필요 (C세션 → Paul 작업)
6. L4/L5 수동 edge 목록 Paul 확인 필요 (A세션 → Paul 작업)
