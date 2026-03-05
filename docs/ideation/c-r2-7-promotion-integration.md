# 세션 C — PyTorch #7: 승격 모델 통합 흐름

> 2026-03-05 | Q2 심화 — recall() → analyze_signals() → promote_node() 실제 코드 삽입점

---

## 3단계 통합 흐름

```
recall() 호출
    │
    ├─ hybrid_search() 실행
    │       │
    │       └─ _hebbian_update() → [NEW] SPRT 즉시 감지
    │               signal이 "promote" 반환 시 → nodes.promotion_candidate = True 플래그
    │
    └─ 결과 반환

daily_enrich.py 또는 analyze_signals() 호출 (자동/수동)
    │
    ├─ 기존: 클러스터 maturity 계산
    │
    └─ [NEW] Bayesian P(real) 스캔
            P > 0.5이고 promotion_candidate = True → 승격 후보 목록

promote_node() 호출 (사용자 또는 auto)
    │
    ├─ [NEW] SWR readiness 게이트 (B-2)
    │       not ready → 즉시 반환
    │
    ├─ [NEW] MDL 압축 검증
    │       compressed > individual → 반환 (승격 거부)
    │
    └─ 기존 승격 로직 실행
```

---

## 삽입점 1: storage/hybrid.py — SPRT 즉시 감지

`_hebbian_update()` 직후, `hybrid_search()` 반환 전에 삽입.

```python
# storage/hybrid.py 추가

import json, math

def _sprt_check(node: dict, score: float, conn) -> bool:
    """recall score 추가 후 SPRT 판단. "promote" 신호 시 True 반환."""
    if node.get("type") not in ("Signal",):
        return False

    # score_history 갱신
    history = json.loads(node.get("score_history") or "[]")
    history = (history + [round(score, 4)])[-50:]  # 최대 50개 유지
    conn.execute("UPDATE nodes SET score_history=? WHERE id=?",
                 (json.dumps(history), node["id"]))

    # SPRT 계산
    if len(history) < 5:  # 최소 5개 관찰 필요
        return False

    A = math.log(0.8 / 0.05)    # 승격 임계 (β=0.2, α=0.05)
    B = math.log(0.2 / 0.95)    # 기각 임계
    p1, p0 = 0.7, 0.3

    cumulative = 0.0
    for obs in history:
        log_lr = math.log(p1/p0) if obs > 0.5 else math.log((1-p1)/(1-p0))
        cumulative += log_lr
        if cumulative >= A:
            return True   # "promote" 신호
        if cumulative <= B:
            return False  # "reject"
    return False


# hybrid_search() 내부 — result 구성 직후, return 전:
# (현재 _hebbian_update 호출 다음 줄에 추가)
conn = sqlite_store._connect()
for node in result:
    if node.get("type") == "Signal":
        score = node.get("score", 0.0)
        if _sprt_check(node, score, conn):
            conn.execute(
                "UPDATE nodes SET promotion_candidate=1 WHERE id=?",
                (node["id"],)
            )
conn.commit()
conn.close()
```

---

## 삽입점 2: tools/analyze_signals.py — Bayesian 스캔

`_compute_maturity()` 결과에 Bayesian P(real)을 합산.

```python
# tools/analyze_signals.py 수정

from scipy.stats import beta as beta_dist

def _bayesian_promotion_score(nodes: list[dict], total_queries: int) -> float:
    """클러스터 내 Signal들의 평균 P(real pattern)."""
    if not nodes or total_queries <= 0:
        return 0.0
    probs = []
    for n in nodes:
        k = n.get("frequency") or 0
        n_queries = max(total_queries, k)
        # Prior: Beta(1, 10) — 회의적
        alpha_post = 1 + k
        beta_post = 10 + (n_queries - k)
        probs.append(beta_dist(alpha_post, beta_post).mean())
    return sum(probs) / len(probs)


# analyze_signals() 내부 — _compute_maturity 호출 이후:
# total_queries는 meta 테이블에서 조회

conn2 = sqlite_store._connect()
row = conn2.execute(
    "SELECT value FROM meta WHERE key='total_recall_count'"
).fetchone()
total_queries = int(row[0]) if row else 0
conn2.close()

# 클러스터 결과 구성 시 bayesian_score 추가:
bayesian_p = _bayesian_promotion_score(cluster_nodes, total_queries)
# promotion_candidate 플래그 있는 노드 수
sprt_flagged = sum(
    1 for n in cluster_nodes if n.get("promotion_candidate")
)

results.append({
    "node_ids": cluster_ids,
    "maturity": round(maturity, 2),
    "bayesian_p": round(bayesian_p, 3),   # 추가
    "sprt_flagged": sprt_flagged,         # 추가
    "recommendation": _recommend_v2(maturity, bayesian_p, sprt_flagged),
    ...
})


def _recommend_v2(maturity: float, bayesian_p: float, sprt_flagged: int) -> str:
    """기존 maturity 기반 + Bayesian + SPRT 통합 판단."""
    if maturity > 0.9 and bayesian_p > 0.6:
        return "auto_promote"
    if bayesian_p > 0.5 or sprt_flagged >= 2:
        return "user_review"
    if maturity > 0.6:
        return "user_review"
    return "not_ready"
```

---

## 삽입점 3: tools/promote_node.py — MDL 검증 게이트

`valid_targets` 확인 직후, DB 업데이트 전에 삽입.

```python
# tools/promote_node.py 수정

def _mdl_gate(node: dict, related_nodes: list[dict]) -> tuple[bool, str]:
    """MDL 기준: 승격 후 description length가 줄어드는가.
    LLM 호출 없이 embedding cosine similarity로 근사.
    """
    if not related_nodes or len(related_nodes) < 2:
        return True, "not_enough_signals"   # 데이터 부족 → 통과

    import numpy as np
    from storage import vector_store

    # 각 Signal의 embedding 조회
    coll = vector_store._get_collection()
    ids = [str(n["id"]) for n in related_nodes]
    try:
        result = coll.get(ids=ids, include=["embeddings"])
        embs = result.get("embeddings") or []
    except Exception:
        return True, "embedding_unavailable"

    if len(embs) < 2:
        return True, "embedding_unavailable"

    # pairwise cosine similarity
    vecs = np.array(embs)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs_norm = vecs / (norms + 1e-9)
    sim_matrix = vecs_norm @ vecs_norm.T
    n = len(vecs)
    pairs = [(i, j) for i in range(n) for j in range(i+1, n)]
    avg_sim = sum(sim_matrix[i, j] for i, j in pairs) / len(pairs)

    # avg_sim > 0.75 → 의미적 중복 높음 → Pattern 통합 정당
    if avg_sim > 0.75:
        return True, f"high_similarity={avg_sim:.2f}"
    return False, f"low_similarity={avg_sim:.2f}_mdl_failed"


# promote_node() 내부 삽입점:
# valid_targets 확인 직후

if related_ids:
    related_nodes = [sqlite_store.get_node(rid) for rid in related_ids if rid != node_id]
    related_nodes = [n for n in related_nodes if n]
    mdl_ok, mdl_reason = _mdl_gate(node, related_nodes)
    if not mdl_ok:
        return {
            "status": "mdl_failed",
            "reason": mdl_reason,
            "message": f"MDL gate rejected promotion: {mdl_reason}",
        }
```

---

## DB 마이그레이션 SQL

```sql
-- 1. SPRT용 score_history
ALTER TABLE nodes ADD COLUMN score_history TEXT DEFAULT '[]';

-- 2. SPRT 플래그
ALTER TABLE nodes ADD COLUMN promotion_candidate INTEGER DEFAULT 0;

-- 3. BCM용 (B-1 정본)
ALTER TABLE nodes ADD COLUMN θ_m REAL DEFAULT 0.5;
ALTER TABLE nodes ADD COLUMN activity_history TEXT DEFAULT '[]';

-- 4. 글로벌 카운터 meta 테이블
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '0'
);
INSERT OR IGNORE INTO meta (key, value) VALUES ('total_recall_count', '0');

-- 5. recall_log (B-2 SWR용)
CREATE TABLE IF NOT EXISTS recall_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL,
    source TEXT NOT NULL,       -- 'vector' | 'fts5' | 'graph'
    query_hash TEXT,
    recalled_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_recall_log_node ON recall_log(node_id);
```

---

## total_recall_count 갱신 지점

`tools/recall.py` 내 `hybrid_search()` 호출 직후:

```python
# tools/recall.py 끝 부분에 추가
conn = sqlite_store._connect()
conn.execute(
    "UPDATE meta SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) "
    "WHERE key = 'total_recall_count'"
)
conn.commit()
conn.close()
```

---

## 파일 변경 요약

| 파일 | 변경 | 우선순위 |
|---|---|---|
| `storage/hybrid.py` | `_sprt_check()` + `promotion_candidate` 플래그 | Phase 3 |
| `tools/analyze_signals.py` | `_bayesian_promotion_score()` + `_recommend_v2()` | Phase 3 |
| `tools/promote_node.py` | `_mdl_gate()` | Phase 4 |
| `tools/recall.py` | `total_recall_count` 갱신 | Phase 3 |
| DB migration | 위 SQL 5개 | Phase 2 (선행 필요) |
