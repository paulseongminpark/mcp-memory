# 세션 B: 뉴럴 메커니즘 구현 설계

> 생성: 2026-03-05 | 모델: claude-sonnet-4-6 | 세션: 뉴럴 메커니즘 구현 설계
> 참조 파일: `storage/hybrid.py`, `tools/recall.py`, `config.py`
> **코드 수정 없음 — 설계 문서 전용**

---

## 1. BCM vs Oja — 선택: **BCM**

### 결론
Oja는 단순하지만 레이어별 차등 감쇠와 통합이 어렵다.
BCM의 적응형 임계값(ν_θ)은 레이어별로 다르게 설정 가능 → **BCM 선택**.

### 현재 코드 문제
`_hebbian_update()` (`storage/hybrid.py`): `frequency += 1`만. effective_strength 공식에 상한 없음.
DeepSeek 분석: 매일 recall 시 1년 후 1.590× 발산.

### BCM 구현 스케치

```python
# storage/hybrid.py — _hebbian_update() 교체
# 전제: nodes 테이블에 θ_m REAL DEFAULT 0.5, activity_history TEXT 컬럼 추가

LAYER_ETA = {0: 0.02, 1: 0.015, 2: 0.01, 3: 0.005, 4: 0.001, 5: 0.0001}
HISTORY_WINDOW = 20

def _bcm_update(result_ids: list[int], result_scores: list[float], all_edges: list[dict]):
    """BCM 규칙: dw_ij/dt = η · ν_i · (ν_i - ν_θ) · ν_j
    ν_i, ν_j = recall() 결과의 score (0~1 정규화)
    ν_θ      = 노드별 적응형 임계값 (슬라이딩 윈도우 제곱평균으로 갱신)
    η        = 레이어별 학습률 (L5/Value: 거의 고정, L0/Obs: 빠른 변화)
    """
    score_map = dict(zip(result_ids, result_scores))
    id_set = set(result_ids)

    for edge in all_edges:
        src, tgt = edge['source_id'], edge['target_id']
        if src not in id_set or tgt not in id_set:
            continue

        ν_i = score_map[src]
        ν_j = score_map[tgt]

        node = sqlite_store.get_node(src)
        θ_m  = node.get('θ_m') or 0.5
        history = json.loads(node.get('activity_history') or '[]')
        η = LAYER_ETA.get(node.get('layer', 2), 0.01)

        delta_w = η * ν_i * (ν_i - θ_m) * ν_j
        new_freq = max(0.0, edge['frequency'] + delta_w * 10)

        # θ_m 업데이트: 슬라이딩 제곱평균 (BCM 핵심 — runaway 방지)
        history = (history + [ν_i])[-HISTORY_WINDOW:]
        new_θ = sum(h**2 for h in history) / len(history)

        conn.execute("UPDATE edges SET frequency=? WHERE id=?", (new_freq, edge['id']))
        conn.execute("UPDATE nodes SET θ_m=?, activity_history=? WHERE id=?",
                     (new_θ, json.dumps(history), src))
```

### Oja 역할 (제한적)
주기적 pruning 전처리로만 사용 — 노드 출력 edge 총합=1 정규화:
```python
def oja_normalize(source_id: int):
    """Pruning 전처리: 노드 예산 정규화. 기여도 낮은 edge → 삭제 후보."""
    outgoing = get_outgoing_edges(source_id)
    total = sum(e['frequency'] for e in outgoing) or 1
    budget_threshold = 1.0 / (len(outgoing) * 10)
    for e in outgoing:
        norm = e['frequency'] / total
        if norm < budget_threshold:
            mark_for_pruning(e['id'])
        else:
            update_edge_frequency(e['id'], norm)
```

---

## 2. SWR-SO-Spindle 조건부 전이

### 설계 목표
"이 Signal이 Pattern으로 전이될 준비가 되었는가"를 수치로 판단.
현재 "3회 반복이면 Pattern" 규칙 → `swr_readiness()` 교체.

### 전제: recall_log 테이블 추가 필요
```sql
CREATE TABLE recall_log (
    id INTEGER PRIMARY KEY,
    node_id INTEGER,
    source TEXT,     -- 'vector' | 'fts5' | 'graph'
    query_hash TEXT, -- 중복 쿼리 집약
    recalled_at TEXT
);
```
`hybrid_search()` 내부에서 각 결과의 기여 소스를 로그로 기록해야 함.

### 구현 스케치
```python
# tools/promote.py 내 (또는 storage/promotion.py 신규)

PROMOTION_SWR_THRESHOLD = 0.55  # config.py에 추가

def swr_readiness(node_id: int) -> tuple[bool, float]:
    """
    지표 1 — vec_ratio: FTS5→ChromaDB 의존도 전환점 (Gemini 제안)
        vec_ratio > 0.6 → 의미적 연결 우세 → 신피질 전이 준비
    지표 2 — cross_ratio: 이웃 노드가 여러 project에 걸쳐 있는가
        피질간 연결성 proxy (SWR의 "해마-신피질 전송" 대응)
    최종: 0.6 × vec_ratio + 0.4 × cross_ratio > 0.55 → 전이 허용
    """
    log = recall_log.get(node_id)
    fts5_hits = log.count('fts5')
    vec_hits  = log.count('vector')
    total = fts5_hits + vec_hits
    vec_ratio = (vec_hits / total) if total > 0 else 0.0

    edges = sqlite_store.get_edges(node_id)
    neighbor_projects = {
        sqlite_store.get_node(
            e['target_id'] if e['source_id'] == node_id else e['source_id']
        )['project']
        for e in edges
    }
    cross_ratio = len(neighbor_projects) / max(len(edges), 1)

    readiness = 0.6 * vec_ratio + 0.4 * cross_ratio
    return readiness > PROMOTION_SWR_THRESHOLD, round(readiness, 3)
```

---

## 3. UCB c값 동적 조절

### 구현 위치
`storage/hybrid.py` — `traverse()` 교체.
`recall()` 파라미터로 `mode="focus"|"dmn"|"auto"` 노출.

```python
# config.py 추가:
UCB_C_FOCUS = 0.3  # 집중: 강한 연결 우선
UCB_C_AUTO  = 1.0  # 기본 (현재 EXPLORATION_RATE=0.1 교체)
UCB_C_DMN   = 2.5  # DMN: 약한 연결도 탐색 (뇌 DMN 20~30% vs 현재 10%)

def ucb_traverse(graph, seed_ids: list[int],
                 depth: int = 2, c: float = UCB_C_AUTO) -> set[int]:
    """UCB: Score(j) = w_ij + c·√(ln(N_i)/N_j)
    c 높을수록 미탐색 이웃 우선 → DMN 모드 (이색적 접합)
    c 낮을수록 강한 연결 우선 → 집중 모드 (정확한 검색)
    """
    visited = set(seed_ids)
    frontier = set(seed_ids)

    for _ in range(depth):
        candidates: list[tuple[float, int]] = []
        for nid in frontier:
            n_i = graph.nodes[nid].get('visit_count', 1)
            for nbr in graph.neighbors(nid):
                if nbr in visited:
                    continue
                w_ij = graph[nid][nbr].get('weight', 0.1)
                n_j  = graph.nodes[nbr].get('visit_count', 1)
                score = w_ij + c * math.sqrt(math.log(n_i + 1) / (n_j + 1))
                candidates.append((score, nbr))

        candidates.sort(reverse=True)
        next_frontier = {nbr for _, nbr in candidates[:20]}  # 폭발 방지
        visited.update(next_frontier)
        frontier = next_frontier

    return visited

def auto_ucb_c(query: str, mode: str = "auto") -> float:
    """쿼리 단어 수로 자동 모드 결정. 사용자가 명시하면 우선."""
    if mode != "auto":
        return {"focus": UCB_C_FOCUS, "dmn": UCB_C_DMN}.get(mode, UCB_C_AUTO)
    words = query.split()
    if len(words) >= 5:   # 구체적 쿼리 → 집중
        return UCB_C_FOCUS
    if len(words) <= 2:   # 추상적 쿼리 → DMN
        return UCB_C_DMN
    return UCB_C_AUTO
```

**N_i, N_j 추적**: nodes 테이블에 `visit_count INTEGER DEFAULT 0` 컬럼 추가.
`_bcm_update()` 실행 시 함께 갱신.

---

## 4. 패치 전환 (Foraging / Marginal Value Theorem)

### 구현 위치
`tools/recall.py` — `recall()` 후처리 (hybrid_search 호출 직후).

```python
# config.py 추가:
PATCH_SATURATION_THRESHOLD = 0.75  # 75% 이상 동일 project → 포화

def recall(query, type_filter="", project="", top_k=5, mode="auto"):
    results = hybrid_search(query, type_filter=type_filter,
                            project=project, top_k=top_k)

    # Marginal Value Theorem: 수확 체감 → 새 패치로 이동
    if not project and _is_patch_saturated(results):
        dominant = _get_dominant_project(results)
        alt = hybrid_search(query, top_k=top_k, excluded_project=dominant)
        # 원본 상위 절반 + 새 패치 결과 절반
        results = results[:top_k // 2] + alt[:top_k - top_k // 2]
        results.sort(key=lambda r: r['score'], reverse=True)

    return _format(results)

def _is_patch_saturated(results: list[dict]) -> bool:
    if len(results) < 3:
        return False
    projects = [r.get('project', '') for r in results]
    dominant = max(set(projects), key=projects.count)
    return projects.count(dominant) / len(projects) >= PATCH_SATURATION_THRESHOLD

def _get_dominant_project(results: list[dict]) -> str:
    projects = [r.get('project', '') for r in results]
    return max(set(projects), key=projects.count)
```

**`hybrid_search`에 `excluded_project` 파라미터 추가 필요.**
SQL WHERE절: `AND project != ?` 조건 추가.

---

## 5. 맥락 의존적 재공고화 ← 구현 우선순위 1위

### 설계 원칙
Nader(2000): 기억은 인출 시마다 불안정해지고 맥락에 따라 재구성된다.
Bäuml: 재공고화 효과는 원래 학습 맥락의 접근 가능성에 달려 있다.

### 구현 위치
`tools/recall.py` — `recall()` 반환 직전.
edges.description 필드를 JSON 맥락 로그로 재사용 (스키마 변경 최소).

```python
CONTEXT_HISTORY_LIMIT = 5  # config.py 추가: edge당 최근 5개 맥락만 유지

def _record_reconsolidation_context(result_ids: list[int], query: str,
                                     all_edges: list[dict]):
    """활성화된 edge에 사용 맥락 기록.
    예: {"q": "포트폴리오 설계", "t": "2026-03-05T..."}
    이것이 #6 Pruning 맥락 다양성 판단의 데이터 소스가 됨.
    """
    id_set = set(result_ids)
    now = datetime.now(timezone.utc).isoformat()

    for edge in all_edges:
        src, tgt = edge['source_id'], edge['target_id']
        if src not in id_set or tgt not in id_set:
            continue

        try:
            ctx_log = json.loads(edge.get('description') or '[]')
            if not isinstance(ctx_log, list):
                ctx_log = []
        except (json.JSONDecodeError, TypeError):
            ctx_log = []

        ctx_log.append({"q": query[:80], "t": now})
        ctx_log = ctx_log[-CONTEXT_HISTORY_LIMIT:]

        conn.execute(
            "UPDATE edges SET description=? WHERE id=?",
            (json.dumps(ctx_log, ensure_ascii=False), edge['id'])
        )

# recall() 마지막 줄:
# _record_reconsolidation_context([n['id'] for n in result], query, all_edges)
```

---

## 6. Pruning 맥락 의존성 (Bäuml + BSP)

### 설계 원칙
Bäuml (2012, 2015): 망각의 효과는 맥락 의존적. 단순 threshold 삭제 대신
접근 맥락(어떤 쿼리에서 활성화)을 pruning 결정에 포함.
Maastricht (2024): 불필요한 트리플 삭제가 오히려 추천 성능 개선.

```python
# tools/prune.py (신규) 또는 daily_enrich.py 통합

PRUNE_STRENGTH_THRESHOLD = 0.05   # config.py 추가
PRUNE_MIN_CONTEXT_DIVERSITY = 2   # 맥락 2개 이상 → 보존

def should_prune(edge: dict) -> str:
    """Returns: 'keep' | 'archive' | 'delete'

    판단 순서:
    1. 강도(strength) — 충분히 강하면 무조건 keep
    2. 맥락 다양성 — #5에서 기록한 ctx_log 활용
       다양한 맥락에서 활성화된 edge는 강도 낮아도 keep
    3. 티어별 처분 — L3+는 archive, 낮은 티어는 delete
    """
    freq   = edge.get('frequency') or 0
    days   = (now - parse_dt(edge['last_activated'])).days if edge.get('last_activated') else 9999
    strength = freq * math.exp(-0.005 * days)

    if strength > PRUNE_STRENGTH_THRESHOLD:
        return 'keep'

    try:
        ctx_log = json.loads(edge.get('description') or '[]')
        unique_queries = len({c.get('q', '') for c in ctx_log if isinstance(c, dict)})
    except (json.JSONDecodeError, TypeError):
        unique_queries = 0

    if unique_queries >= PRUNE_MIN_CONTEXT_DIVERSITY:
        return 'keep'

    # BSP Probation: 티어별 처분
    src_tier = get_node_tier(edge['source_id'])
    if src_tier == 0:    # L3+ → 아카이브 (30일 후 재평가)
        return 'archive'
    return 'delete'

# edges 테이블에 archived_at TEXT, probation_end TEXT 컬럼 추가
```

---

## 7. Chen의 SA 최적화 (SQL Recursive CTE)

### 현재 vs 제안

| | 현재 | 제안 |
|---|---|---|
| 방식 | Python NetworkX BFS | SQLite Recursive CTE |
| 속도 | 기준 | ~100~500× (Chen 2014) |
| 의존성 | NetworkX in-memory graph | SQLite (이미 존재) |
| 메모리 | `build_graph()` 전체 로드 | DB 직접 쿼리 |

```python
# storage/hybrid.py — traverse() 교체 후보

def traverse_sql(conn, seed_ids: list[int], depth: int = 2) -> set[int]:
    """Chen (2014) DB-optimized spreading activation.
    SQL recursive CTE로 Python BFS 대체.
    build_graph() + NetworkX 호출 완전 제거 가능.
    """
    if not seed_ids:
        return set()

    ph = ','.join('?' * len(seed_ids))
    sql = f"""
    WITH RECURSIVE sa(id, hop) AS (
        -- 초기: seed 노드의 직접 이웃 (양방향)
        SELECT target_id, 1 FROM edges WHERE source_id IN ({ph})
        UNION
        SELECT source_id, 1 FROM edges WHERE target_id IN ({ph})
        UNION ALL
        -- 재귀: depth 제한
        SELECT e.target_id, sa.hop + 1
          FROM edges e JOIN sa ON e.source_id = sa.id WHERE sa.hop < ?
        UNION ALL
        SELECT e.source_id, sa.hop + 1
          FROM edges e JOIN sa ON e.target_id = sa.id WHERE sa.hop < ?
    )
    SELECT DISTINCT id FROM sa WHERE id NOT IN ({ph})
    """
    params = seed_ids + seed_ids + [depth - 1, depth - 1] + seed_ids
    return {row[0] for row in conn.execute(sql, params).fetchall()}
```

**주의**: UCB 탐색(#3)은 edge 가중치 비교가 필요하므로 NetworkX 유지.
`traverse_sql`은 단순 이웃 수집(현재 `traverse()` 역할)에만 적용.

---

## 8. RWR + 놀라움 지수

### 설계 원칙
확산 활성화에서 "예상치 못한" 노드에 보너스 → DMN의 "이색적 접합" 구현.
놀라움 = RWR 점수 / 차수 기반 기대값 - 1 (초과분).

```python
# storage/rwr.py (신규)

def random_walk_with_restart(graph, seed_id: int,
                              alpha: float = 0.15,
                              max_iter: int = 30) -> dict[int, float]:
    """RWR: 각 노드의 최종 활성화 확률.
    alpha = restart 확률 (PageRank damping factor와 동일 개념).
    """
    nodes = list(graph.nodes())
    r = {n: (1.0 if n == seed_id else 0.0) for n in nodes}

    for _ in range(max_iter):
        new_r = {}
        for node in nodes:
            nbrs = list(graph.neighbors(node))
            incoming = sum(
                r[nbr] * graph[nbr][node].get('weight', 1.0) /
                max(sum(graph[nbr][n].get('weight', 1.0)
                        for n in graph.neighbors(nbr)), 1e-9)
                for nbr in nbrs
            )
            new_r[node] = (1 - alpha) * incoming + alpha * (1.0 if node == seed_id else 0.0)
        r = new_r
    return r

def compute_baseline(graph) -> dict[int, float]:
    """차수 기반 기대 활성화 (degree-normalized)."""
    degrees = dict(graph.degree(weight='weight'))
    total = sum(degrees.values()) or 1.0
    return {n: degrees[n] / total for n in graph.nodes()}

def surprise_score(rwr_score: float, baseline_score: float) -> float:
    """놀라움 = RWR가 기대를 얼마나 초과했나. 초과분만 반환."""
    if baseline_score < 1e-9:
        return 0.0
    return max(0.0, rwr_score / baseline_score - 1.0)

# hybrid_search() 통합 (config.py에 RWR_SURPRISE_WEIGHT = 0.1 추가):
# rwr_r    = random_walk_with_restart(graph, seed_ids[0])
# baseline = compute_baseline(graph)
# scores[node_id] += RWR_SURPRISE_WEIGHT * surprise_score(
#     rwr_r.get(node_id, 0), baseline.get(node_id, 0))
```

**성능 주의**: 30K 노드에서 max_iter=30은 느릴 수 있음.
최적화: `scipy.sparse` 행렬 곱 또는 top-K 이웃으로 truncation.

---

## 9. Swing-toward 재연결

### PyTorch 필요? → **불필요. NetworkX로 충분.**
NetworkX `clustering()` O(degree²). 영향받는 4노드 로컬 CC만 계산 → ms 수준.
Maslov-Sneppen 변형: 차수 보존 + 클러스터링 계수 증가하는 swap만 수용.

```python
# storage/graph_ops.py (신규)

def local_clustering_delta(graph, a, b, c, d) -> float:
    """swap (a-b, c-d) → (a-c, b-d) 시 로컬 CC 변화량.
    전체 CC 재계산 대신 영향받는 4노드만 → 속도 대폭 개선.
    """
    affected = {a, b, c, d}
    before = sum(nx.clustering(graph, n) for n in affected)

    graph.remove_edge(a, b); graph.remove_edge(c, d)
    graph.add_edge(a, c);    graph.add_edge(b, d)
    after = sum(nx.clustering(graph, n) for n in affected)

    graph.remove_edge(a, c); graph.remove_edge(b, d)  # 롤백
    graph.add_edge(a, b);    graph.add_edge(c, d)

    return after - before

def swing_toward(graph, n_rounds: int = 200) -> list[tuple]:
    """차수 보존 + 클러스터링 증가. 개선되는 swap만 수용.
    반환: DB에 반영할 edge 변경 목록 [(removed_e1, removed_e2, added_e1, added_e2), ...]
    """
    edges = list(graph.edges())
    applied = []

    for _ in range(n_rounds):
        if len(edges) < 2:
            break
        e1, e2 = random.sample(edges, 2)
        a, b = e1; c, d = e2

        if len({a, b, c, d}) < 4:                        # 자기루프·중복 방지
            continue
        if graph.has_edge(a, c) or graph.has_edge(b, d):  # 멀티엣지 방지
            continue

        if local_clustering_delta(graph, a, b, c, d) >= 0:
            graph.remove_edge(a, b); graph.remove_edge(c, d)
            graph.add_edge(a, c);    graph.add_edge(b, d)
            edges.remove(e1); edges.remove(e2)
            edges += [(a, c), (b, d)]
            applied.append(((a, b), (c, d)))

    return applied

# 실행 시점: daily_enrich.py 마지막 단계
# 반환된 applied 목록으로 SQLite edges 테이블 업데이트
```

---

## DB 스키마 변경 요약

| 테이블 | 추가 컬럼 | 용도 | 관련 메커니즘 |
|---|---|---|---|
| nodes | `θ_m REAL DEFAULT 0.5` | BCM 적응형 임계값 | #1 |
| nodes | `activity_history TEXT` | BCM 이력 (JSON 리스트) | #1 |
| nodes | `visit_count INTEGER DEFAULT 0` | UCB N_j 추적 | #3 |
| edges | `description TEXT` | 재공고화 맥락 로그 (JSON) | #5, #6 |
| edges | `archived_at TEXT` | BSP Probation 시작 시각 | #6 |
| edges | `probation_end TEXT` | 30일 후 재평가 시각 | #6 |
| (신규) | `recall_log` 테이블 | SWR 조건부 전이 판단 | #2 |

---

## 구현 우선순위

| 순위 | 메커니즘 | 이유 |
|---|---|---|
| 1 | 맥락 의존적 재공고화 (#5) | 코드 변경 최소, 즉각 효과, #6의 데이터 소스 |
| 2 | 패치 전환 (#4) | recall() 품질 직접 개선, 스키마 변경 없음 |
| 3 | Chen SA 최적화 (#7) | 성능 bottleneck 제거, 메모리 절약 |
| 4 | UCB c값 (#3) | EXPLORATION_RATE=0.1 고정값 교체 |
| 5 | BCM (#1) | DB 스키마 변경 필요 (nodes 3개 컬럼) |
| 6 | SWR 조건부 전이 (#2) | recall_log 테이블 신규 + 로깅 로직 필요 |
| 7 | RWR + 놀라움 (#8) | 복잡도 높음, scipy.sparse 최적화 필요 |
| 8 | Pruning 맥락 (#6) | #5 완료 후 ctx_log 데이터 쌓이면 가능 |
| 9 | Swing-toward (#9) | daily_enrich.py 통합 마지막 단계 |

---

## 검증 방법

1. **#4 패치 전환**: `recall("포트폴리오")` → 결과 project 분포 확인. 단일 project 지배 해소 여부.
2. **#5 재공고화**: `inspect(edge_id)` → description JSON 확인. 맥락 로그 누적 여부.
3. **#7 Chen SA**: `hybrid_search()` 응답시간 측정. `traverse_sql` vs 현재 BFS 비교.
4. **#3 UCB**: `ucb_traverse(c=2.5)` vs `c=0.3` — 반환 노드의 project 분포 비교.
5. **#1 BCM**: 3개월 후 frequency 분포 히스토그램 → 발산 없이 수렴 여부 확인.
