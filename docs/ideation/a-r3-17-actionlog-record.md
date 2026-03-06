# A-17: action_log.record() 구현 + 6개 삽입지점 실제 코드

> Round 3 최종 심화 | A-9, A-12 기반
> 목표: action_log.record() 단일 함수 + 6개 코드 삽입지점의 정확한 diff
> 파일: `storage/action_log.py` (신규)

---

## record() 구현

```python
"""storage/action_log.py — 시스템 활동 로깅 (A-9/A-12 확정)."""

import json
from datetime import datetime, timezone

from storage import sqlite_store


# A-9 확정: 25개 action_type
ACTION_TAXONOMY = {
    # remember
    "node_created":     "remember()로 노드 생성",
    "node_classified":  "classify()에서 타입 결정",
    "edge_auto":        "link()에서 자동 edge 생성",
    # recall
    "recall":           "recall() 검색 실행 (요약)",
    "node_activated":   "recall 결과로 반환된 개별 노드의 활성화 기록",
    # promote
    "node_promoted":    "promote_node()에서 타입 승격",
    "edge_realized":    "promote_node()에서 realized_as edge 생성",
    # edge
    "edge_created":     "insert_edge()에서 수동/자동 edge 생성",
    "edge_corrected":   "insert_edge()에서 relation 교정",
    # learning
    "hebbian_update":   "_hebbian_update()에서 frequency+1",
    "bcm_update":       "_bcm_update()에서 strength 조정",
    "reconsolidation":  "description에 맥락 추가",
    # enrichment
    "enrichment_start": "enrichment 배치 시작",
    "enrichment_done":  "enrichment 개별 노드 완료",
    "enrichment_fail":  "enrichment 개별 노드 실패",
    # ontology
    "type_deprecated":  "온톨로지 타입 deprecated",
    "type_migrated":    "온톨로지 타입 마이그레이션",
    "relation_corrected": "잘못된 관계 교정",
    # admin
    "session_start":    "세션 시작",
    "session_end":      "세션 종료",
    "config_changed":   "설정 변경",
    "migration":        "DB 마이그레이션 실행",
    # archive
    "node_archived":    "노드 아카이브",
    "node_reactivated": "아카이브 노드 재활성화",
    "edge_archived":    "edge 아카이브",
}


def record(
    action_type: str,
    actor: str = "system",
    session_id: str | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    params: str | None = None,
    result: str | None = None,
    context: str | None = None,
    model: str | None = None,
    duration_ms: int | None = None,
    token_cost: int | None = None,
    conn: "sqlite3.Connection | None" = None,
) -> int | None:
    """action_log에 1행 기록.

    Args:
        action_type: ACTION_TAXONOMY 키 중 하나.
        actor: "claude" | "system" | "enrichment" | "migration" | "paul"
        session_id: 현재 세션 ID (있으면).
        target_type: "node" | "edge" | "session" | "config" (있으면).
        target_id: 대상의 ID (있으면).
        params: JSON 문자열. 입력 파라미터.
        result: JSON 문자열. 실행 결과.
        context: 자유 텍스트. 추가 맥락.
        model: LLM 모델명 (enrichment 시).
        duration_ms: 실행 시간 ms.
        token_cost: 토큰 사용량.
        conn: 외부 트랜잭션에 참여할 때 전달. None이면 자체 conn 생성.

    Returns:
        삽입된 action_log.id (실패 시 None — 로깅 실패가 주 기능을 중단시키지 않음).
    """
    now = datetime.now(timezone.utc).isoformat()
    own_conn = conn is None

    try:
        if own_conn:
            conn = sqlite_store._connect()

        cur = conn.execute(
            """INSERT INTO action_log
               (actor, session_id, action_type, target_type, target_id,
                params, result, context, model, duration_ms, token_cost, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                actor, session_id, action_type, target_type, target_id,
                params or "{}", result or "{}", context, model,
                duration_ms, token_cost, now,
            ),
        )
        log_id = cur.lastrowid

        if own_conn:
            conn.commit()
        return log_id

    except Exception:
        # 로깅 실패는 주 기능에 영향을 주지 않는다
        return None
    finally:
        if own_conn and conn:
            conn.close()
```

---

## 6개 삽입지점 — 실제 diff

### 1. remember() — `tools/remember.py`

**삽입 위치**: L49 (insert_node 직후) + L96 (insert_edge 직후)

```python
# tools/remember.py — 수정 후 전체

"""remember() — 기억을 저장하고 자동으로 관계를 생성한다."""

import json
from config import SIMILARITY_THRESHOLD, PROMOTE_LAYER, infer_relation
from ontology.validators import validate_node_type, suggest_closest_type
from storage import sqlite_store, vector_store
from storage import action_log                          # <-- 추가


def remember(
    content: str,
    type: str = "Unclassified",
    tags: str = "",
    project: str = "",
    metadata: dict | None = None,
    confidence: float = 1.0,
    source: str = "claude",
) -> dict:
    # 0. 온톨로지 타입 검증
    valid, correction = validate_node_type(type)
    original_type = type
    if not valid:
        suggested = suggest_closest_type(content)
        type = suggested
    elif correction:
        type = correction

    # 0.5 provisional embedding 플래그
    metadata = dict(metadata) if metadata else {}
    metadata["embedding_provisional"] = "true"

    # 0.6 자동 tier/layer 배정
    layer = PROMOTE_LAYER.get(type)
    if layer is not None and layer >= 3:
        tier = 0
    elif layer == 2:
        tier = 2
    else:
        tier = 2

    # 1. SQLite에 노드 저장
    node_id = sqlite_store.insert_node(
        type=type, content=content, metadata=metadata,
        project=project, tags=tags, confidence=confidence,
        source=source, layer=layer, tier=tier,
    )

    # -- action_log: node_created                        # <-- 추가
    action_log.record(                                   # <-- 추가
        action_type="node_created",                      # <-- 추가
        actor="claude",                                  # <-- 추가
        target_type="node",                              # <-- 추가
        target_id=node_id,                               # <-- 추가
        params=json.dumps({                              # <-- 추가
            "original_type": original_type,              # <-- 추가
            "resolved_type": type,                       # <-- 추가
            "layer": layer,                              # <-- 추가
            "tier": tier,                                # <-- 추가
            "project": project,                          # <-- 추가
            "source": source,                            # <-- 추가
        }),                                              # <-- 추가
    )                                                    # <-- 추가

    # 2. ChromaDB에 임베딩 저장
    vec_meta = {"type": type, "project": project, "tags": tags, "embedding_provisional": "true"}
    try:
        vector_store.add(node_id, content, vec_meta)
    except Exception as e:
        return {
            "node_id": node_id, "type": type, "project": project,
            "auto_edges": [],
            "warning": f"Stored in SQLite but embedding failed: {e}",
            "message": f"Stored as node #{node_id} (embedding failed)",
        }

    # 3. 유사 노드 검색 → 자동 edge 생성
    auto_edges = []
    try:
        similar = vector_store.search(content, top_k=5)
    except Exception:
        similar = []
    for sim_id, distance, _ in similar:
        if sim_id == node_id:
            continue
        if distance > SIMILARITY_THRESHOLD:
            continue
        sim_node = sqlite_store.get_node(sim_id)
        if not sim_node:
            continue
        relation = infer_relation(
            src_type=type, src_layer=layer,
            tgt_type=sim_node.get("type", ""), tgt_layer=sim_node.get("layer"),
            src_project=project, tgt_project=sim_node.get("project", ""),
        )
        strength = max(0.0, 1.0 - distance)
        edge_id = sqlite_store.insert_edge(
            source_id=node_id, target_id=sim_id,
            relation=relation,
            description=f"auto: similarity={1.0 - distance:.2f}",
            strength=strength,
        )
        auto_edges.append({
            "edge_id": edge_id, "target_id": sim_id,
            "relation": relation, "strength": round(strength, 2),
        })

        # -- action_log: edge_auto                       # <-- 추가
        action_log.record(                               # <-- 추가
            action_type="edge_auto",                     # <-- 추가
            actor="claude",                              # <-- 추가
            target_type="edge",                          # <-- 추가
            target_id=edge_id,                           # <-- 추가
            params=json.dumps({                          # <-- 추가
                "source_id": node_id,                    # <-- 추가
                "target_id": sim_id,                     # <-- 추가
                "relation": relation,                    # <-- 추가
                "strength": round(strength, 2),          # <-- 추가
            }),                                          # <-- 추가
        )                                                # <-- 추가

    return {
        "node_id": node_id, "type": type, "project": project,
        "auto_edges": auto_edges,
        "message": f"Stored as node #{node_id} with {len(auto_edges)} auto-edge(s)",
    }
```

---

### 2. recall() — `tools/recall.py`

**삽입 위치**: L14 (hybrid_search 직후)

```python
# tools/recall.py — 수정 부분 (L1-17)

"""recall() — 3중 하이브리드 검색으로 기억을 검색한다."""

import json                                              # <-- 추가
from storage.hybrid import hybrid_search
from storage import sqlite_store
from storage import action_log                           # <-- 추가
from config import DEFAULT_TOP_K


def recall(
    query: str,
    type_filter: str = "",
    project: str = "",
    top_k: int = DEFAULT_TOP_K,
) -> dict:
    results = hybrid_search(query, type_filter=type_filter, project=project, top_k=top_k)

    # -- action_log: recall 요약                          # <-- 추가
    top_ids = [r["id"] for r in results[:10]]            # <-- 추가
    action_log.record(                                   # <-- 추가
        action_type="recall",                            # <-- 추가
        actor="claude",                                  # <-- 추가
        params=json.dumps({                              # <-- 추가
            "query": query[:200],                        # <-- 추가
            "type_filter": type_filter,                  # <-- 추가
            "project": project,                          # <-- 추가
            "top_k": top_k,                              # <-- 추가
            "result_count": len(results),                # <-- 추가
            "top_ids": top_ids,                          # <-- 추가
        }),                                              # <-- 추가
        result=json.dumps({                              # <-- 추가
            "count": len(results),                       # <-- 추가
            "top_scores": [                              # <-- 추가
                round(r.get("score", 0), 4)              # <-- 추가
                for r in results[:5]                     # <-- 추가
            ],                                           # <-- 추가
        }),                                              # <-- 추가
    )                                                    # <-- 추가

    if not results:
        return {"results": [], "message": "No memories found."}

    # ... 나머지 포매팅 동일 ...
```

**node_activated 기록**: `storage/hybrid.py` L116 이후에 삽입 (아래 #5 참조)

---

### 3. promote_node() — `tools/promote_node.py`

**삽입 위치**: L76 (conn.commit() 직전)

```python
# tools/promote_node.py — 수정 부분 (L1-5 import 추가 + L76 근처)

"""promote_node() — 타입 승격 실행 + realized_as edge + 이력 보존."""

import json
from datetime import datetime, timezone

from config import VALID_PROMOTIONS, PROMOTE_LAYER
from storage import sqlite_store
from storage import action_log                           # <-- 추가


def promote_node(
    node_id: int,
    target_type: str,
    reason: str = "",
    related_ids: list[int] | None = None,
) -> dict:
    node = sqlite_store.get_node(node_id)
    if not node:
        return {"error": f"Node #{node_id} not found.", "message": "Promotion failed."}

    current_type = node["type"]
    valid_targets = VALID_PROMOTIONS.get(current_type, [])
    if target_type not in valid_targets:
        return {
            "error": f"Invalid promotion: {current_type} → {target_type}",
            "valid_targets": valid_targets,
            "message": f"Cannot promote {current_type} to {target_type}. Valid: {valid_targets}",
        }

    now = datetime.now(timezone.utc).isoformat()

    # 승격 이력
    metadata = json.loads(node.get("metadata") or "{}")
    history = metadata.get("promotion_history", [])
    history.append({"from": current_type, "to": target_type, "reason": reason, "promoted_at": now})
    metadata["promotion_history"] = history
    metadata.pop("embedding_provisional", None)

    new_layer = PROMOTE_LAYER.get(target_type, node.get("layer"))
    conn = sqlite_store._connect()
    conn.execute(
        """UPDATE nodes SET type = ?, layer = ?, metadata = ?, updated_at = ?
           WHERE id = ?""",
        (target_type, new_layer, json.dumps(metadata, ensure_ascii=False), now, node_id),
    )

    edge_ids = []
    for rid in (related_ids or []):
        if rid == node_id:
            continue
        try:
            cur = conn.execute(
                """INSERT INTO edges (source_id, target_id, relation, description, strength, created_at)
                   VALUES (?, ?, 'realized_as', ?, 1.0, ?)""",
                (rid, node_id, f"{current_type}→{target_type}: {reason}", now),
            )
            edge_ids.append(cur.lastrowid)
        except Exception:
            pass

    # -- action_log: node_promoted (conn 공유)            # <-- 추가
    action_log.record(                                   # <-- 추가
        action_type="node_promoted",                     # <-- 추가
        actor="claude",                                  # <-- 추가
        target_type="node",                              # <-- 추가
        target_id=node_id,                               # <-- 추가
        params=json.dumps({                              # <-- 추가
            "from_type": current_type,                   # <-- 추가
            "to_type": target_type,                      # <-- 추가
            "from_layer": node.get("layer"),             # <-- 추가
            "to_layer": new_layer,                       # <-- 추가
            "reason": reason,                            # <-- 추가
            "related_ids": related_ids or [],            # <-- 추가
            "edge_ids": edge_ids,                        # <-- 추가
        }),                                              # <-- 추가
        conn=conn,                                       # <-- 추가 (같은 트랜잭션)
    )                                                    # <-- 추가

    conn.commit()
    conn.close()

    return {
        "node_id": node_id, "previous_type": current_type,
        "new_type": target_type, "new_layer": new_layer,
        "realized_as_edges": edge_ids, "promotion_count": len(history),
        "message": f"Promoted #{node_id}: {current_type} → {target_type} (L{new_layer})",
    }
```

---

### 4. insert_edge() — `storage/sqlite_store.py`

**삽입 위치**: L181 (conn.commit() 직전)

```python
# storage/sqlite_store.py — insert_edge() 수정 부분

def insert_edge(
    source_id: int,
    target_id: int,
    relation: str,
    description: str = "",
    strength: float = 1.0,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    original_relation = relation
    if relation not in ALL_RELATIONS:
        relation = "connects_with"
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO edges (source_id, target_id, relation, description, strength, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (source_id, target_id, relation, description, strength, now),
    )
    edge_id = cur.lastrowid
    if original_relation != relation:
        conn.execute(
            """INSERT INTO correction_log (node_id, edge_id, field, old_value, new_value, reason, corrected_by, created_at)
               VALUES (?, ?, 'relation', ?, ?, 'relation not in ALL_RELATIONS', 'system', ?)""",
            (source_id, edge_id, original_relation, relation, now),
        )

        # -- action_log: edge_corrected                  # <-- 추가
        from storage import action_log                   # <-- 추가 (순환 import 방지)
        action_log.record(                               # <-- 추가
            action_type="edge_corrected",                # <-- 추가
            actor="system",                              # <-- 추가
            target_type="edge",                          # <-- 추가
            target_id=edge_id,                           # <-- 추가
            params=json.dumps({                          # <-- 추가
                "source_id": source_id,                  # <-- 추가
                "target_id": target_id,                  # <-- 추가
                "original": original_relation,           # <-- 추가
                "corrected": relation,                   # <-- 추가
            }),                                          # <-- 추가
            conn=conn,                                   # <-- 추가
        )                                                # <-- 추가

    conn.commit()
    conn.close()
    return edge_id
```

**주의**: `insert_edge()`에 `edge_created` 로깅은 **추가하지 않는다**.
이유: remember()의 link()에서 이미 `edge_auto`로 기록하고, enrichment는 `enrichment_done`으로 기록한다.
insert_edge()에 `edge_created`를 넣으면 모든 edge가 이중 기록된다.
교정(`edge_corrected`)만 기록하는 것이 올바르다.

---

### 5. _hebbian_update / _bcm_update — `storage/hybrid.py`

**삽입 위치**: L116 (return result 직전)

```python
# storage/hybrid.py — _hebbian_update 내부 + hybrid_search 끝

import json                                              # <-- 추가 (파일 상단)
from storage import action_log                           # <-- 추가

def _hebbian_update(result_ids: list[int], all_edges: list[dict],
                    query: str = ""):
    """헤비안 학습 + 재공고화 맥락 기록 (B-10 통합)."""
    if not result_ids:
        return
    id_set = set(result_ids)
    now = datetime.now(timezone.utc).isoformat()

    activated_edges = [
        e for e in all_edges
        if e.get("source_id") in id_set and e.get("target_id") in id_set
    ]
    if not activated_edges:
        return

    conn = None
    try:
        conn = sqlite_store._connect()
        for edge in activated_edges:
            eid = edge.get("id")

            # 1. 헤비안: frequency +1
            conn.execute(
                "UPDATE edges SET frequency = COALESCE(frequency, 0) + 1, "
                "last_activated = ? WHERE id = ?",
                (now, eid),
            )

            # 2. 재공고화: description에 맥락 추가 (B-10)
            if query:
                raw = edge.get("description") or ""
                try:
                    ctx_log = json.loads(raw) if raw else []
                    if not isinstance(ctx_log, list):
                        ctx_log = []
                except (json.JSONDecodeError, ValueError):
                    ctx_log = []
                ctx_log.append({"q": query[:80], "t": now})
                from config import CONTEXT_HISTORY_LIMIT
                ctx_log = ctx_log[-CONTEXT_HISTORY_LIMIT:]
                conn.execute(
                    "UPDATE edges SET description = ? WHERE id = ?",
                    (json.dumps(ctx_log, ensure_ascii=False), eid),
                )

        # -- action_log: hebbian_update (같은 conn)      # <-- 추가
        action_log.record(                               # <-- 추가
            action_type="hebbian_update",                # <-- 추가
            actor="system",                              # <-- 추가
            params=json.dumps({                          # <-- 추가
                "result_count": len(result_ids),         # <-- 추가
                "activated_edges": len(activated_edges), # <-- 추가
                "query": query[:80] if query else "",    # <-- 추가
            }),                                          # <-- 추가
            conn=conn,                                   # <-- 추가
        )                                                # <-- 추가

        conn.commit()
    except Exception:
        pass
    finally:
        if conn:
            conn.close()


# hybrid_search() L116-117 수정:

    # 6. 헤비안 학습 + 재공고화
    _hebbian_update([n["id"] for n in result], all_edges, query=query)

    # 7. 개별 노드 활성화 기록 (A-12 D-5 통합)         # <-- 추가
    _log_recall_activations(result, query)               # <-- 추가

    return result


def _log_recall_activations(results: list[dict], query: str,
                             session_id: str | None = None):
    """recall 결과 개별 노드 활성화를 action_log에 기록 (A-12)."""
    now = datetime.now(timezone.utc).isoformat()
    for rank, node in enumerate(results[:10], 1):
        action_log.record(
            action_type="node_activated",
            actor="system",
            session_id=session_id,
            target_type="node",
            target_id=node["id"],
            params=json.dumps({
                "context_query": query[:200],
                "activation_score": round(node.get("score", 0), 4),
                "activation_rank": rank,
                "channel": "hybrid",
                "node_type": node.get("type", ""),
                "node_layer": node.get("layer"),
            }),
        )
```

---

### 6. enrichment — `scripts/enrich/node_enricher.py`

**삽입 위치**: enrichment 완료/실패 시점

```python
# scripts/enrich/node_enricher.py — 삽입지점 (개념적 위치)
# 실제 enrichment 코드는 LLM 호출 후 DB 업데이트 루프 안에 위치

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from storage import action_log                           # <-- 추가

# ... 기존 enrichment 루프 내부 ...

def enrich_single_node(node_id: int, node: dict, conn) -> bool:
    """개별 노드 enrichment (기존 코드 래퍼 예시)."""
    import time, json
    start = time.monotonic()

    try:
        # ... 기존 LLM 호출 + DB 업데이트 로직 ...
        elapsed_ms = int((time.monotonic() - start) * 1000)

        # -- action_log: enrichment_done                 # <-- 추가
        action_log.record(                               # <-- 추가
            action_type="enrichment_done",               # <-- 추가
            actor="enrichment",                          # <-- 추가
            target_type="node",                          # <-- 추가
            target_id=node_id,                           # <-- 추가
            params=json.dumps({                          # <-- 추가
                "type": node.get("type", ""),            # <-- 추가
                "layer": node.get("layer"),              # <-- 추가
            }),                                          # <-- 추가
            model="claude-haiku-4-5-20251001",           # <-- 추가 (실제 모델)
            duration_ms=elapsed_ms,                      # <-- 추가
            conn=conn,                                   # <-- 추가
        )                                                # <-- 추가
        return True

    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)

        # -- action_log: enrichment_fail                 # <-- 추가
        action_log.record(                               # <-- 추가
            action_type="enrichment_fail",               # <-- 추가
            actor="enrichment",                          # <-- 추가
            target_type="node",                          # <-- 추가
            target_id=node_id,                           # <-- 추가
            result=json.dumps({"error": str(e)[:200]}),  # <-- 추가
            duration_ms=elapsed_ms,                      # <-- 추가
            conn=conn,                                   # <-- 추가
        )                                                # <-- 추가
        return False
```

---

## 순환 import 방지 전략

| import 위치 | 이유 |
|---|---|
| `tools/remember.py` 상단 | tools → storage 방향. 순환 없음. |
| `tools/recall.py` 상단 | 동일. |
| `tools/promote_node.py` 상단 | 동일. |
| `storage/sqlite_store.py` 함수 내부 | storage → storage 순환 방지. `from storage import action_log`를 함수 내부에서. |
| `storage/hybrid.py` 상단 | hybrid → action_log 방향. action_log → sqlite_store만 참조하므로 순환 없음. |
| `scripts/enrich/node_enricher.py` | sys.path.insert 후 import. 독립 스크립트. |

---

## storage/action_log.py 파일 위치

```
storage/
├── __init__.py          # action_log import 추가
├── action_log.py        # 신규
├── hybrid.py
├── sqlite_store.py
└── vector_store.py
```

`storage/__init__.py` 수정:
```python
# 기존 import들...
from storage import action_log  # <-- 추가
```

---

## 검증 쿼리

```sql
-- 마이그레이션 후 action_log 동작 확인
SELECT action_type, COUNT(*) as cnt
FROM action_log
GROUP BY action_type
ORDER BY cnt DESC;

-- 세션별 에너지 (Q7)
SELECT
    session_id,
    SUM(CASE WHEN action_type IN ('node_created', 'edge_auto', 'edge_created')
             THEN 1 ELSE 0 END) AS generative,
    SUM(CASE WHEN action_type IN ('hebbian_update', 'bcm_update', 'reconsolidation')
             THEN 1 ELSE 0 END) AS consolidation,
    SUM(CASE WHEN action_type = 'recall' THEN 1 ELSE 0 END) AS exploratory
FROM action_log
WHERE session_id IS NOT NULL
GROUP BY session_id;
```
