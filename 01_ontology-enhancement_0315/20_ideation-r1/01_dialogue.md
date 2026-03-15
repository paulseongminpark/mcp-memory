# Ideation R1 — 설계 대화

## 1. Gate 1 Fix: Source 태깅

### 설계안 (Option A — minimal)

**변경 흐름:**
```
hybrid_search() (storage/hybrid.py)
  → RRF 합산 시 각 node_id별 source set 추적
  → 반환 dict에 "_sources": ["vector", "fts5", "graph", "typed_vector"] 추가

recall() (tools/recall.py)
  → _log_recall_results()에 sources 전달
  → INSERT에 sources 컬럼 추가 (JSON text)

swr_readiness() (tools/promote_node.py)
  → SQL 수정: sources 컬럼 파싱 → vec_ratio 계산
  → source IS NULL인 기존 행 제외

DB migration
  → ALTER TABLE recall_log ADD COLUMN sources TEXT DEFAULT NULL
```

**hybrid_search() 변경 상세:**
```python
# line 517 부근, RRF 합산에 source 추적 추가
source_map: dict[int, set[str]] = defaultdict(set)

for rank, (node_id, distance, _) in enumerate(vec_results, 1):
    scores[node_id] += 1.0 / (RRF_K + rank)
    source_map[node_id].add("vector")

for rank, (node_id, _, _) in enumerate(fts_results, 1):
    scores[node_id] += 1.0 / (RRF_K + rank)
    source_map[node_id].add("fts5")

for node_id in graph_neighbors:
    scores[node_id] += GRAPH_BONUS
    source_map[node_id].add("graph")

for hint_type, t_results in typed_vec_by_type.items():
    ...
    source_map[node_id].add("typed_vector")

# 반환 시 태깅
node["_sources"] = sorted(source_map.get(node_id, set()))
```

**swr_readiness() 수정:**
```python
# 기존: SELECT source, COUNT(*) FROM recall_log ... (source 컬럼 없어서 실패)
# 신규:
rows = conn.execute(
    "SELECT sources FROM recall_log WHERE node_id=? AND sources IS NOT NULL",
    (node_id,),
).fetchall()
vec_hits = sum(1 for r in rows if '"vector"' in (r[0] or ""))
fts_hits = sum(1 for r in rows if '"fts5"' in (r[0] or ""))
total = vec_hits + fts_hits
vec_ratio = (vec_hits / total) if total > 0 else 0.0
```

### 리스크
- `_sources` 언더스코어 prefix → 기존 소비자 코드 영향 없음
- 기존 2,899 recall_log 행은 sources=NULL → 점진적 축적으로 자연 해결

---

## 2. Signal 고갈 해결

### 옵션 분석

| 옵션 | 장점 | 단점 |
|---|---|---|
| A. Gate 1 fix만 | 정상 경로 복구 | 시간 필요 (수백 회 recall 후) |
| B. 일회성 배치 승격 | 즉시 bootstrap | Gate 우회 = 품질 보증 없음 |
| C. threshold 완화 | cross_ratio만으로 통과 | 기준 약화 |

**권장: A + B 병행**
- Gate 1 fix (A)로 장기 정상화
- 적격 Observation 일괄 승격 (B) — 기준: `frequency ≥ 3 AND observation_count ≥ 2`
- 스크립트 1회 실행, skip_gates=True + reason="bootstrap-batch"

---

## 3. Deprecated 코드 정리 (확정)

**config.py TYPE_CHANNEL_WEIGHTS:**
- 제거: Connection, Evolution, Agent, Skill, Workflow
- 유지: Pattern(1.0), Decision(1.0), Signal(0.8), Failure(0.8), Experiment(0.8), Narrative(0.8), Goal(0.8), Project(0.7), Framework(0.6), Tool(0.5)

**config.py TYPE_KEYWORDS:**
- 제거: Workflow, Agent, Skill, Evolution, Connection
- 유지: Failure, Experiment, Decision, Signal, Goal, Pattern, Framework, Project, Narrative, Tool
- 추가: Identity, Observation, Question, Insight, Principle (현재 누락)

**config.py LAYER_IMPORTANCE:**
- 제거: 4: 0.8, 5: 1.0
- v3 최대 layer = 3

**validators.py suggest_closest_type():**
- 제거: AntiPattern, Workflow
- 추가: Identity, Narrative, Question, Signal

---

## 4. Gate 2 재캘리브레이션

**문제**: Beta(1,10) prior는 total_queries=401 규모에서 수학적으로 통과 불가.
최고 visit_count=58인데 통과에 206+ 필요.

**결정**: Bayesian 제거 → visit_count 직접 threshold
```python
# 기존: p_real = (1+k) / (11+n) > 0.5 → 불가능
# 신규: node.visit_count >= 10
```
현재 visit_count > 10: 60개 노드 → 합리적 후보군.
nodes.frequency 컬럼은 deprecated 처리 (visit_count로 대체).

---

## 5. RELATION_RULES 확장 (17→50+)

**문제**: 225개 타입 쌍 중 17개만 규칙 존재 (7.6%). 나머지는 layer fallback.
fallback-probable edges: 2,872/7,249 (39.6%).

**방향**: config.py RELATION_RULES에 타입 쌍 추가. LLM 비용 0.

추가 후보 (예시):
```python
# 인과 확장
("Failure", "Pattern"): "led_to",      # 실패에서 패턴 발견
("Experiment", "Pattern"): "led_to",   # 실험에서 패턴 확인
("Experiment", "Decision"): "led_to",  # 실험 결과로 결정
("Goal", "Experiment"): "led_to",      # 목표가 실험 유발
("Goal", "Decision"): "led_to",        # 목표가 결정 유발

# 구조 확장
("Framework", "Tool"): "contains",     # 프레임워크가 도구 포함
("Project", "Framework"): "governed_by", # 프로젝트는 프레임워크에 의해
("Project", "Decision"): "contains",   # 프로젝트가 결정 포함
("Goal", "Project"): "governs",        # 목표가 프로젝트 방향 결정

# 의미 확장
("Insight", "Decision"): "led_to",     # 통찰이 결정으로
("Pattern", "Decision"): "governs",    # 패턴이 결정 가이드
("Principle", "Decision"): "governs",  # 원칙이 결정 가이드
("Identity", "Goal"): "governs",       # 정체성이 목표 설정
("Identity", "Decision"): "governs",   # 정체성이 결정 가이드
("Narrative", "Pattern"): "exemplifies", # 서사가 패턴 예시
("Narrative", "Failure"): "exemplifies", # 서사가 실패 예시

# 질문 확장
("Question", "Experiment"): "led_to",  # 질문이 실험 유발
("Question", "Goal"): "led_to",        # 질문이 목표 설정
("Failure", "Question"): "led_to",     # 실패가 질문 유발

# Signal 경로 확장
("Observation", "Question"): "led_to", # 관찰이 질문 유발
("Observation", "Experiment"): "triggered_by", # 관찰이 실험 촉발
("Signal", "Experiment"): "led_to",    # 신호가 실험 유발
("Signal", "Decision"): "led_to",      # 신호가 결정 유발
```

**Cross-project 규칙**: infer_relation()에 cross-project 전용 로직 추가
```python
# 다른 프로젝트 간 같은 타입 → mirrors (기존: parallel_with)
# 다른 프로젝트 간 다른 타입 → transfers_to 또는 influenced_by
```

---

## 6. Cross-project 연결 강화

**문제**: cross-project edges = 8.5% (445/5,229). 지식 사일로.

**수단**:
- RELATION_RULES에 cross-project 규칙 추가 (안건 5와 통합)
- infer_relation()에서 다른 프로젝트 간 관계 시 더 구체적인 타입 선택
- 같은 타입+다른 프로젝트 → `mirrors` (현재: `parallel_with`)

---

## 최종 결정 사항

### 방향
"개별 버그 수리"가 아닌 **"자기 성장 루프 전체 관통 + 관계 품질 강화"**

### 구현 항목 (이번 파이프라인)

| # | 항목 | 파일 | 난이도 |
|---|---|---|---|
| 1 | Deprecated 정리 | config.py, validators.py | 낮 |
| 2 | Gate 2 → visit_count threshold | promote_node.py | 낮 |
| 3 | Gate 1 threshold 완화 (0.55→0.25) | promote_node.py | 낮 |
| 4 | recall_log source 인프라 | hybrid.py, recall.py, DB migration | 중 |
| 5 | RELATION_RULES 확장 (17→40+) | config.py | 중 |
| 6 | Cross-project 관계 로직 | config.py (infer_relation) | 중 |

### 향후 (별도 파이프라인)
- 유령 노드 782개 해결 (enrichment 재실행)
- Edge strength 재캘리브레이션 (BCM 튜닝)
- Tiny 노드 408개 정리 (삭제/병합 정책)
- 기존 fallback edge 2,872개 LLM 재분류

### Success Criteria

| 지표 | before | target |
|---|---|---|
| promote 성공 건수 | 1 | ≥ 10 |
| Signal 노드 수 | 4 | ≥ 15 |
| RELATION_RULES 커버리지 | 17/225 (7.6%) | 40+/225 (18%+) |
| cross-project edge 비율 | 8.5% | 측정 (baseline) |
| NDCG@5 | 현재치 | ≥ 현재치 |
| tests | 169 PASS | 전부 PASS |
