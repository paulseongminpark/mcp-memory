# 세션 D: 검증 & 허브 보호 & 메트릭스

> 날짜: 2026-03-05 | 담당: Claude Sonnet 4.6 (세션 D)
> 목적: v2 완성 상태에서 치명적 약점 재검증 + 모니터링 체계 설계
> 코드 수정 없음 — 검증 결과와 설계안만

---

## 1. 치명적 약점 재검증 결과

### 1-A. 의미적 피드백 루프 — 실재 확인

**코드 추적 경로 (`node_enricher.py`):**
```
_call_llm()
  E1(summary), E2(key_concepts): 검증 없음 → raw LLM output → DB (L693-700 즉시 commit)
  E7(embedding_text): 오염된 summary 기반 새 임베딩 텍스트 생성
  → vector_store.update()         # ChromaDB 오염 벡터 삽입
  → hybrid_search() 벡터 채널    # 오염 노드 상위 노출
  → _hebbian_update()             # 오염 엣지 frequency+1, strength 상승
  → 다음 enrichment 세션에서 오염 노드 컨텍스트 재사용
  → 루프 완성
```

**현재 방어선 (있는 것):**
| 대상 | 방어 | 수준 |
|------|------|------|
| E4/E5 (facets, domains) | allowlist 필터 | OK |
| E8-E11 (score float) | `max(0, min(1, ...))` | OK |
| E12 (layer 변경) | confidence > 0.8 조건부 | 부분적 |
| **E1, E2, E3, E7** | **없음** | **취약** |

**탐지 메커니즘 설계:**
```python
# scripts/enrich/node_enricher.py 신규 함수
def _detect_semantic_drift(node_id, old_embedding, new_embedding_text):
    """환각 탐지: 임베딩 변화량이 임계치 초과 시 롤백"""
    new_emb = vector_store.embed(new_embedding_text)
    similarity = cosine_similarity(old_embedding, new_emb)
    if similarity < DRIFT_THRESHOLD:  # 권장값: 0.5
        sqlite_store.log_correction(
            node_id=node_id,
            field="embedding_text",
            old_value="<preserved>",
            new_value=new_embedding_text,
            reason=f"semantic_drift: cosine_sim={similarity:.3f}",
            corrected_by="auto_drift_detector"
        )
        return True  # 업데이트 거부
    return False

def _validate_summary(new_summary, historical_median_len):
    """summary 길이가 역사적 중앙값의 2배 초과 시 flag"""
    if len(new_summary) > 2 * historical_median_len:
        return False, "length_anomaly"
    return True, None
```

**correction_log 확장 필요 필드:**
- `event_type`: "semantic_drift" | "length_anomaly" | "type_mismatch"
- `similarity_score`: float
- `auto_rollback`: bool

---

### 1-B. 스키마 드리프트 — 실제 불일치 수치

| 소스 | 타입 수 | 비고 |
|------|---------|------|
| `ontology/schema.yaml` | **50개** | Unclassified 포함 |
| `scripts/migrate_v2.py` TYPE_TO_LAYER | **45개** | 5개 누락 |
| `ontology/validators.py` 기준 | **50개** | schema.yaml 읽음 |
| E6 secondary_types 검증 | **45개** | TYPE_TO_LAYER 직접 참조 |

**구조적 문제:**
```
init_db()      → IF NOT EXISTS 만 있음. v2 컬럼 없음 (layer, tier, etc.)
migrate_v2.py  → v1→v2 전환 (별도 실행 필요)
결론: 새 설치 시 두 스크립트 실행 순서 보장 필요. 자동화/문서화 없음.
```

**해결 설계 (`storage/sqlite_store.py`):**
```python
def init_db():
    _create_base_schema()      # 기존 CREATE TABLE IF NOT EXISTS
    _apply_v2_migrations()     # ALTER TABLE ADD COLUMN IF NOT EXISTS
    _rebuild_fts_if_needed()   # FTS5 재구축
```

**5개 누락 타입 확인 명령:**
```bash
python -c "
from scripts.migrate_v2 import TYPE_TO_LAYER
import yaml
schema = yaml.safe_load(open('ontology/schema.yaml'))
schema_types = {t['name'] for t in schema['node_types']}
migrate_types = set(TYPE_TO_LAYER.keys())
print('schema에만:', schema_types - migrate_types)
"
```

---

### 1-C. validators.py 호출 여부 — Dead Code 확인

**검증 결과:**
```
remember()      → sqlite_store.insert_node() → validators.py 미호출
insert_edge()   → sqlite_store.insert_edge() → validators.py 미호출
node_enricher E6 → scripts.migrate_v2.TYPE_TO_LAYER 직접 참조 (45개 기준)
```

**결론:** `ontology/validators.py` 존재하나 메인 파이프라인 어디서도 호출 안 됨 = **dead code**.

**연결 설계 (Quick Win #1):**
```python
# mcp_server.py remember() 진입점에 추가
from ontology.validators import validate_node_type, validate_relation_type, suggest_closest_type

def remember(content, node_type, ...):
    valid, msg = validate_node_type(node_type)
    if not valid:
        suggested = suggest_closest_type(node_type)
        return {"error": msg, "suggestion": suggested}
    ...

def insert_edge(source_id, target_id, relation, ...):
    valid, msg = validate_relation_type(relation)
    if not valid:
        return {"error": msg}
    ...
```

---

## 2. 5개 합의 지점 해결 방안

### 2-A. Hebbian 불안정 → 정규화

**현재:** `frequency +1` 무한 증가, strength 상한 없음.

**tanh 정규화 (설계):**
```python
# storage/hybrid.py _hebbian_update() 수정안
def _update_edge_strength(edge_id, conn):
    row = conn.execute(
        "SELECT base_strength, frequency FROM edges WHERE id=?", (edge_id,)
    ).fetchone()
    tau = 10  # 실험 필요 (세션 B 연계)
    new_strength = row["base_strength"] * math.tanh(row["frequency"] / tau)
    # tanh → [0, base_strength] 수렴, 발산 방지
    conn.execute(
        "UPDATE edges SET strength=?, frequency=frequency+1 WHERE id=?",
        (new_strength, edge_id)
    )
```

**BCM sliding threshold (대안):**
```python
theta = moving_average([e["strength"]**2 for e in recent_edges])
delta = learning_rate * (strength - theta)  # theta 초과: LTD / 미만: LTP
```

---

### 2-B. 시간 감쇠 — 현재 미구현

**현재:** `decay_rate` 컬럼 존재. 적용 로직 없음 (`hybrid.py` 미구현).

**설계:**
```python
def _apply_decay(edge, current_time):
    if edge["last_activated"]:
        delta_days = (current_time - edge["last_activated"]).days
        return edge["strength"] * math.exp(-edge["decay_rate"] * delta_days)
    return edge["strength"]

# 레이어별 decay_rate 기본값
DECAY_RATE_BY_LAYER = {
    0: 0.010,  # L0 원시: 빠른 감쇠
    1: 0.007,
    2: 0.005,  # L2 패턴: 중간
    3: 0.003,
    4: 0.001,  # L4-5 가치/공리: 거의 영구
    5: 0.001,
}
```

---

### 2-C. 검증 체계 구축 순서

```
Phase 1 (즉시):  validators.py → remember()/insert_edge() 연결
Phase 2 (1주):   골드셋 100개 수동 구축 (query → expected_nodes)
Phase 3 (2주):   NDCG@10 오프라인 평가 스크립트
Phase 4 (1달):   A/B 테스트 (RRF k=60 vs k=30 비교)
```

---

### 2-D. Palantir 참조 우선 차용

| 순위 | Palantir 패턴 | mcp-memory 적용 |
|-----|---------------|----------------|
| 1 | 리니지(Lineage) 추적 | correction_log 확장 (전체 이력 보존) |
| 2 | 메타/인스턴스 분리 | L4-L5(메타) vs L0-L1(인스턴스) 이미 근사 |
| 3 | 버전 스냅샷 | schema.yaml 버전태깅 + 정기 DB 스냅샷 |
| 4 | Deprecation | status='deprecated' + replaced_by 필드 |

---

### 2-E. 하드코딩 파라미터 실험 순서

| 파라미터 | 현재값 | 실험 범위 | 측정 지표 |
|---------|-------|----------|---------|
| RRF_K | 60 | 30, 60, 100 | NDCG@10 |
| ENRICHMENT_QUALITY_WEIGHT | 0.2 | 0.1, 0.2, 0.4 | 사용자 만족도 |
| GRAPH_BONUS | config값 | 0.05, 0.1, 0.2 | recall rate |
| decay_rate | 미구현 | 0.001~0.01 | edge 분포 |
| DRIFT_THRESHOLD (신규) | 없음 | 0.3, 0.5, 0.7 | 환각 탐지율 |

---

## 3. 허브 보호 대시보드 (IHS)

### IHS 계산 (`scripts/hub_monitor.py` 신규)

```python
import networkx as nx
import numpy as np

def calculate_ihs(conn):
    """IHS = Degree Centrality + Betweenness Centrality + Neighborhood Connectivity"""
    edges = conn.execute(
        "SELECT source_id, target_id, strength FROM edges WHERE status='active'"
    ).fetchall()

    G = nx.DiGraph()
    for e in edges:
        G.add_edge(e["source_id"], e["target_id"], weight=e["strength"])

    degree = nx.degree_centrality(G)
    # 노드 수 > 1000 시 샘플링
    if len(G.nodes) > 1000:
        betweenness = nx.betweenness_centrality(G, k=100, normalized=True)
    else:
        betweenness = nx.betweenness_centrality(G, normalized=True)

    max_deg = max(dict(G.degree()).values()) or 1
    nc = {}
    for node in G.nodes():
        neighbors = list(G.neighbors(node))
        nc[node] = np.mean([G.degree(n) for n in neighbors]) / max_deg if neighbors else 0.0

    ihs = {
        node: degree.get(node, 0) + betweenness.get(node, 0) + nc.get(node, 0)
        for node in G.nodes()
    }
    return sorted(ihs.items(), key=lambda x: -x[1])[:10], G


def hub_health_report(conn):
    top10, G = calculate_ihs(conn)
    report = []
    for node_id, ihs_score in top10:
        node = conn.execute(
            "SELECT content, type, layer, tier FROM nodes WHERE id=?", (node_id,)
        ).fetchone()
        sub_hubs = [n for n in G.neighbors(node_id) if G.degree(n) > 5]
        report.append({
            "node_id": node_id,
            "preview": node["content"][:50],
            "ihs": round(ihs_score, 4),
            "degree": G.degree(node_id),
            "layer": node["layer"],
            "sub_hub_count": len(sub_hubs),
            "risk": "HIGH" if not sub_hubs else "LOW",
        })
    return report
```

### RBAC 설계

```python
# 허브 수정 권한 매트릭스
HUB_RBAC = {
    "layer_0_1": {"write": "AI",           "delete": "AI"},
    "layer_2_3": {"write": "AI",           "delete": "HUMAN_REVIEW"},
    "layer_4_5": {"write": "HUMAN_REVIEW", "delete": "HUMAN_REVIEW"},
    "top10_hub": {"write": "HUMAN_REVIEW", "delete": "HUMAN_REVIEW"},
}

def check_hub_permission(node_id, action, top10_ids, conn):
    if node_id in top10_ids:
        return "HUMAN_REVIEW_REQUIRED"
    node = get_node(node_id, conn)
    if node["layer"] in [4, 5]:
        return "HUMAN_REVIEW_REQUIRED"
    return "ALLOWED"
```

### 모니터링 지표

```sql
-- hub_snapshots 테이블 (주간 스냅샷 저장)
CREATE TABLE IF NOT EXISTS hub_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date DATE NOT NULL,
    node_id       TEXT NOT NULL,
    ihs_score     REAL,
    degree        INTEGER,
    betweenness   REAL,
    risk_level    TEXT  -- 'HIGH' | 'LOW'
);
```

**알림 트리거:**
1. Top-10 허브 degree가 전주 대비 20% 이상 감소
2. betweenness > 0.3 인데 sub_hub_count == 0 (단일 허브 위험)
3. 신규 노드가 Top-5 허브와 연결 없이 추가됨 (고립 위험)

---

## 4. 스몰 월드 측정 설계

### 측정 스크립트 (`scripts/small_world_audit.py`)

```python
import networkx as nx
import numpy as np

def measure_small_world(conn):
    edges = load_active_edges(conn)
    G = nx.DiGraph()
    G.add_edges_from([(e["source_id"], e["target_id"]) for e in edges])
    G_u = G.to_undirected()

    # 최대 연결 컴포넌트만
    largest_cc = max(nx.connected_components(G_u), key=len)
    G_sub = G_u.subgraph(largest_cc)

    C = nx.average_clustering(G_sub)

    if len(G_sub) > 500:
        sample = list(G_sub.nodes)[:500]
        L = nx.average_shortest_path_length(G_sub.subgraph(sample))
    else:
        L = nx.average_shortest_path_length(G_sub)

    # Erdős–Rényi 랜덤 그래프 기준값
    n = len(G_sub); m = len(G_sub.edges)
    p = 2*m / (n*(n-1)) if n > 1 else 0.001
    C_r = p
    L_r = np.log(n) / np.log(n*p) if n*p > 1 else float('inf')

    sigma = (C / C_r) / (L / L_r)  # sigma > 1 → Small World

    return {
        "clustering_coeff": C,
        "avg_path_length": L,
        "small_world_sigma": sigma,
        "is_small_world": sigma > 1.0,
        "node_count": n,
        "edge_count": m,
    }
```

### Triadic Closure 탐지 SQL

```sql
-- A→B, B→C 인데 A→C 없는 삼각형 후보
SELECT DISTINCT
    e1.source_id AS A,
    e1.target_id AS B,
    e2.target_id AS C
FROM edges e1
JOIN edges e2 ON e1.target_id = e2.source_id
LEFT JOIN edges e3
    ON e3.source_id = e1.source_id AND e3.target_id = e2.target_id
WHERE e3.id IS NULL
  AND e1.source_id != e2.target_id
  AND e1.strength > 0.5   -- 강한 연결만 (이론 조건)
  AND e2.strength > 0.5
LIMIT 100;
```

### Swing-Toward Rewiring (월 1회 배치)

```python
def swing_toward_rewire(G, target_clustering=0.3, max_iter=1000):
    """
    차수 보존 + 클러스터링 계수 상승
    출처: Journal of Complex Networks
    """
    edges = list(G.edges())
    for _ in range(max_iter):
        if nx.average_clustering(G) >= target_clustering:
            break
        e1, e2 = random.sample(edges, 2)
        A, B = e1; C, D = e2
        if (set(G.neighbors(A)) & set(G.neighbors(C))
                and not G.has_edge(A, C)
                and not G.has_edge(B, D)):
            G.remove_edge(A, B); G.remove_edge(C, D)
            G.add_edge(A, C); G.add_edge(B, D)
    return G
```

---

## 5. 시간축 보완 설계

**현재 보유 필드:** `created_at`, `updated_at`, `last_activated`, `enriched_at`

**부족한 것:**
- 시간 범위 검색 ("2주 전 기억") 불가
- `decay_rate` 컬럼 있으나 `hybrid.py`에서 미적용
- 활성화 이력 단일 필드 → 이력 손실

### activation_log 테이블 (신규)

```sql
CREATE TABLE IF NOT EXISTS activation_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id          TEXT NOT NULL REFERENCES nodes(id),
    session_id       TEXT,
    activated_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    context_query    TEXT,
    activation_score REAL
);
CREATE INDEX idx_actlog_node    ON activation_log(node_id, activated_at);
CREATE INDEX idx_actlog_session ON activation_log(session_id);
```

### temporal_search (Rewind 모델)

```python
def temporal_search(query, since_days=None):
    results = hybrid_search(query)
    if since_days:
        cutoff = datetime.now() - timedelta(days=since_days)
        results = [r for r in results
                   if r["last_activated"] and r["last_activated"] >= cutoff]
    # 최신 활성화일수록 boost
    for r in results:
        if r["last_activated"]:
            days_ago = (datetime.now() - r["last_activated"]).days
            r["score"] *= (1 + 1.0 / (1 + days_ago * 0.1))
    return sorted(results, key=lambda x: -x["score"])
```

### temporal_relevance 동적 계산

```python
def compute_temporal_relevance(node, current_time):
    """정적 저장값 대신 동적 계산"""
    age_days = (current_time - node["created_at"]).days
    base = max(0.0, 1.0 - age_days / 365)          # 1년 선형 감쇠
    if node["last_activated"]:
        recency = (current_time - node["last_activated"]).days
        boost = math.exp(-recency / 30)              # 30일 반감기
        return min(1.0, base + boost * 0.5)
    return base
```

---

## 6. Pruning 구현 설계

### BSP 3단계 (`scripts/pruning.py`)

**Stage 1: 후보 식별**
```sql
SELECT n.id, n.content, n.quality_score, n.observation_count, n.last_activated,
       COUNT(e.id) AS edge_count
FROM nodes n
LEFT JOIN edges e ON (e.source_id = n.id OR e.target_id = n.id)
WHERE n.status = 'active'
  AND n.quality_score < 0.3
  AND (n.observation_count IS NULL OR n.observation_count < 2)
  AND (n.last_activated IS NULL
       OR n.last_activated < datetime('now', '-90 days'))
  AND n.layer IN (0, 1)    -- L2+ (패턴/원칙) 보호
GROUP BY n.id
HAVING edge_count < 3      -- 허브 연결 노드 보호
ORDER BY n.quality_score ASC, n.last_activated ASC;
```

**Stage 2: 유예 30일**
```python
def mark_pruning_candidates(conn, ids):
    conn.execute(
        "UPDATE nodes SET status='pruning_candidate', "
        "updated_at=CURRENT_TIMESTAMP WHERE id IN ({})".format(
            ",".join("?" * len(ids))
        ), ids
    )
    for nid in ids:
        log_correction(nid, "status", "active", "pruning_candidate",
                       reason="BSP Stage 2")
    conn.commit()
```

**Stage 3: 아카이브 (삭제 금지)**
```python
def execute_pruning(conn, dry_run=True):
    expired = conn.execute(
        "SELECT id FROM nodes WHERE status='pruning_candidate'"
        " AND updated_at < datetime('now', '-30 days')"
    ).fetchall()
    if dry_run:
        return [r["id"] for r in expired]   # 미리보기
    conn.execute(
        "UPDATE nodes SET status='archived' WHERE id IN ({})".format(
            ",".join("?" * len(expired))
        ), [r["id"] for r in expired]
    )
    conn.commit()
    return [r["id"] for r in expired]
```

**맥락 의존적 Pruning (Bäuml 기반):**
```python
def contextual_pruning_weight(node, conn, top10_hub_ids):
    """프로젝트 내 밀도 + 허브 연결로 보호"""
    same_proj = conn.execute(
        "SELECT COUNT(*) FROM edges e JOIN nodes n2 ON e.target_id=n2.id"
        " WHERE e.source_id=? AND n2.project=?",
        (node["id"], node["project"])
    ).fetchone()[0]
    if same_proj >= 3:
        return 0.0  # 보호
    if node["id"] in top10_hub_ids:
        return 0.0
    return 1.0
```

---

## 7. 구현 우선순위 로드맵

```
즉시 (Quick Win):
  1. validators.py → remember()/insert_edge() 연결           [30분]
  2. init_db() + _apply_v2_migrations() 통합                  [1시간]

단기 (1주):
  3. _detect_semantic_drift() 구현 (E1/E2/E7 보호)           [2시간]
  4. decay 적용 로직 (exp(-decay_rate*Δt))                   [1시간]
  5. activation_log 테이블 추가                               [30분]

중기 (2주):
  6. hub_monitor.py IHS 대시보드 + hub_snapshots             [3시간]
  7. small_world_audit.py 측정 + 주간 배치                   [2시간]
  8. pruning.py BSP 3단계                                     [3시간]

장기 (1달):
  9. temporal_search() + Rewind 모델                          [4시간]
 10. Triadic Closure 자동 추천 (주간 배치)                   [3시간]
 11. A/B 테스트 프레임워크 (골드셋 + NDCG@10)               [1주]
```

---

## 8. 타 세션 연계 포인트

| 세션 | 연계 주제 |
|------|---------|
| 세션 A | Palantir 리니지 구체화, replaced_by 필드 스키마 |
| 세션 B | Hebbian 정규화 tau 값 실험, BCM threshold 구현 |
| 세션 C | (미확인) |
| 세션 D (본) | 검증 체계, IHS, 스몰 월드, 시간축, Pruning |
