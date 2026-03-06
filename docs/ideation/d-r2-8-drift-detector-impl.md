# D-8: _detect_semantic_drift() — E7 방어 완성

> 세션 D | 2026-03-05
> node_enricher.py 실제 코드 기반 구현

---

## 코드 확인 결과

### E7 처리 정확한 위치 (`node_enricher.py`)

```
L239-247: e7_embedding_text() — LLM API 호출, 최대 250자 반환
L654-668: _apply() 메서드 내 E7 블록 — ChromaDB 직접 쓰기
```

**L654-668 실제 코드:**
```python
elif tid == "E7":
    # ChromaDB 재임베딩 (S5/C7 해결)
    if result and not self.dry_run:
        try:
            from storage import vector_store
            node_id = node.get("id")
            vec_meta = {
                "type": node.get("type", ""),
                "project": node.get("project", ""),
                "tags": node.get("tags", ""),
                "embedding_provisional": "false",
            }
            vector_store.add(node_id, result, vec_meta)   # ← ChromaDB upsert
        except Exception:
            pass  # 실패해도 무시
```

**핵심 발견:**
- E7은 `updates` dict에 넣지 않음 → `_update_node()` 경유 없음
- 즉시 `vector_store.add()` 호출 → ChromaDB upsert
- 실패 시 `pass` (무음 실패) → 현재 방어선 없음
- E7은 BULK_TASKS에 포함 안 됨 → `enrich_node_combined()` 아닌 별도 태스크로 실행

### `vector_store.py` 분석

```python
# storage/vector_store.py
def add(node_id: int, content: str, metadata: dict | None = None) -> None:
    # L26~36: ChromaDB upsert
    coll.upsert(
        ids=[str(node_id)],
        embeddings=[vector],    # OpenAI embed_text(content) 결과
        documents=[content],
        metadatas=[meta],
    )

def search(query: str, top_k: int = 5, where: dict | None = None) -> list[tuple[int, float, dict]]:
    # L39~56: query로 유사 노드 검색
```

**`get_embedding(node_id)` 없음** → ChromaDB collection.get() 직접 사용 필요:
```python
# ChromaDB SDK: collection.get(ids, include=["embeddings"])
# vector_store.py에는 없으나 collection 객체에 직접 접근 가능
```

---

## cosine_similarity 구현

### ChromaDB에서 기존 임베딩 가져오기

```python
# storage/vector_store.py 에 추가할 헬퍼 함수
def get_node_embedding(node_id: int) -> list[float] | None:
    """
    ChromaDB에서 node_id의 현재 임베딩 벡터 반환.
    없으면 None.
    """
    try:
        coll = _get_collection()          # 기존 _get_collection() 함수 활용
        result = coll.get(
            ids=[str(node_id)],
            include=["embeddings"],
        )
        if result["embeddings"] and result["embeddings"][0]:
            return result["embeddings"][0]
    except Exception:
        pass
    return None
```

### cosine_similarity 구현

```python
# utils/similarity.py (신규) 또는 node_enricher.py 내 헬퍼

import math

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    두 벡터의 코사인 유사도 [-1, 1].
    동일 벡터 → 1.0 / 직교 → 0.0 / 반대 → -1.0
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)
```

**numpy 사용 가능 시 (성능 우선):**
```python
import numpy as np

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a = np.array(vec_a)
    b = np.array(vec_b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0
```

---

## `_detect_semantic_drift()` 전체 구현

### 삽입 위치: `node_enricher.py` L654-668 수정

```python
# node_enricher.py L654-668 수정 (E7 블록 전체 교체)

elif tid == "E7":
    if result and not self.dry_run:
        try:
            from storage import vector_store
            from storage.vector_store import get_node_embedding  # 신규 헬퍼
            from utils.similarity import cosine_similarity       # 신규 유틸

            node_id = node.get("id")

            # ── Semantic Drift 탐지 ─────────────────────────────────
            drift_detected = False
            old_embedding = get_node_embedding(node_id)

            if old_embedding:
                # 새 텍스트의 임베딩 미리 계산
                from storage.embedding import openai_embed
                new_embedding = openai_embed(result)
                similarity = cosine_similarity(old_embedding, new_embedding)

                if similarity < DRIFT_THRESHOLD:  # 기본값 0.5
                    drift_detected = True
                    # correction_log에 기록
                    from storage import sqlite_store
                    sqlite_store.log_correction(
                        node_id=node_id,
                        field="embedding_text",
                        old_value="<preserved>",
                        new_value=result[:200],  # 너무 길면 자름
                        reason=f"semantic_drift: cosine_sim={similarity:.4f} < {DRIFT_THRESHOLD}",
                        corrected_by="auto_drift_detector",
                    )

            # ── 드리프트 없으면 ChromaDB 업데이트 ──────────────────
            if not drift_detected:
                vec_meta = {
                    "type": node.get("type", ""),
                    "project": node.get("project", ""),
                    "tags": node.get("tags", ""),
                    "embedding_provisional": "false",
                }
                vector_store.add(node_id, result, vec_meta)
            # ── [끝] ─────────────────────────────────────────────────

        except Exception as e:
            pass  # ChromaDB 실패해도 enrichment 중단하지 않음 (기존 동작 유지)
```

### DRIFT_THRESHOLD 위치

```python
# config.py에 추가
DRIFT_THRESHOLD: float = 0.5  # cosine similarity 하한 (실험값)
```

---

## DRIFT_THRESHOLD=0.5 적절성 — 기준선 측정 방법

### 현재 enrichment 데이터로 기준선 측정 SQL

```sql
-- summary 길이 분포 (타입별)
SELECT
    type,
    COUNT(*) AS n,
    AVG(LENGTH(summary)) AS avg_len,
    MIN(LENGTH(summary)) AS min_len,
    MAX(LENGTH(summary)) AS max_len,
    -- 중앙값 근사 (SQLite에 PERCENTILE 없으므로)
    GROUP_CONCAT(LENGTH(summary)) AS all_lens
FROM nodes
WHERE summary IS NOT NULL AND status='active'
GROUP BY type
ORDER BY n DESC
LIMIT 20;
```

```python
# scripts/calibrate_drift.py — 기준선 측정 스크립트
"""
enrichment이 완료된 노드들에서 embedding_text를 2회 enrichment한다고 가정하고
같은 content에 대해 embedding similarity를 측정, DRIFT_THRESHOLD 보정.
"""
import sqlite3
from pathlib import Path
from storage.vector_store import get_node_embedding
from storage.embedding import openai_embed
from utils.similarity import cosine_similarity

def measure_stability(conn, sample_size: int = 50) -> dict:
    """
    같은 노드의 임베딩을 2번 생성해서 자연적 변동폭 측정.
    DRIFT_THRESHOLD는 이 변동폭 평균의 2σ 아래로 설정.
    """
    nodes = conn.execute(
        "SELECT id, content, summary FROM nodes "
        "WHERE status='active' AND summary IS NOT NULL "
        "ORDER BY RANDOM() LIMIT ?",
        (sample_size,)
    ).fetchall()

    similarities = []
    for node_id, content, summary in nodes:
        # 같은 텍스트로 임베딩 2번 생성 (OpenAI API 호출이므로 비용 주의)
        emb1 = openai_embed(summary)
        emb2 = openai_embed(summary)
        sim = cosine_similarity(emb1, emb2)
        similarities.append(sim)

    import statistics
    mean = statistics.mean(similarities)
    stdev = statistics.stdev(similarities)

    return {
        "mean_stability": mean,
        "stdev": stdev,
        "suggested_threshold": mean - 2 * stdev,  # 자연 변동의 2σ 아래
        "current_threshold": 0.5,
        "n_sampled": len(similarities),
    }
```

**예상 결과:** OpenAI text-embedding-3 모델은 동일 텍스트에 대해 거의 동일한 벡터를 반환하므로 자연 안정성은 ~0.999. 실질적인 drift(환각)는 0.3~0.7 범위에서 감지됨. 따라서 **0.5는 보수적으로 적절**.

---

## summary 길이 검증

### historical_summaries 수집 SQL

```sql
-- 같은 타입 노드의 최근 100개 summary 길이
SELECT LENGTH(summary) AS len
FROM nodes
WHERE type = ?           -- 검증 대상 노드의 타입
  AND summary IS NOT NULL
  AND status = 'active'
  AND enriched_at IS NOT NULL
ORDER BY enriched_at DESC
LIMIT 100;
```

### 구현

```python
# node_enricher.py 내 헬퍼 함수 추가

def _get_summary_median_length(node_type: str, conn) -> float | None:
    """같은 타입의 최근 100개 summary 길이 중앙값"""
    rows = conn.execute(
        "SELECT LENGTH(summary) FROM nodes "
        "WHERE type=? AND summary IS NOT NULL AND status='active' "
        "ORDER BY enriched_at DESC LIMIT 100",
        (node_type,)
    ).fetchall()
    if len(rows) < 5:  # 샘플 부족 시 검증 skip
        return None
    import statistics
    return statistics.median(r[0] for r in rows)


def _validate_summary_length(
    new_summary: str,
    node_type: str,
    conn,
    multiplier: float = 2.0,  # 중앙값의 2배 초과 시 flag
) -> tuple[bool, str | None]:
    median_len = _get_summary_median_length(node_type, conn)
    if median_len is None:
        return True, None  # 샘플 부족: 패스
    if len(new_summary) > multiplier * median_len:
        return False, f"length_anomaly: {len(new_summary)} > {multiplier}×{median_len:.0f}"
    return True, None
```

**E1(summary) 처리에 삽입 (L354-358 근방):**
```python
# enrich_node_combined() 내 E1 처리 후
if "E1" in results:
    new_summary = results["E1"]
    ok, reason = _validate_summary_length(new_summary, node.get("type", ""), conn)
    if ok:
        updates["summary"] = new_summary
    else:
        # correction_log 기록 + 기존 summary 유지
        sqlite_store.log_correction(
            node_id=node_id, field="summary",
            old_value=node.get("summary", ""), new_value=new_summary,
            reason=reason, corrected_by="summary_length_validator"
        )
```

---

## correction_log 확장 (필요 시)

`sqlite_store.py`에 `log_correction()` 헬퍼가 있는지 확인 필요.
없으면:

```python
# storage/sqlite_store.py 에 추가
def log_correction(
    node_id: int,
    field: str,
    old_value: str,
    new_value: str,
    reason: str,
    corrected_by: str,
    edge_id: int | None = None,
):
    conn.execute(
        "INSERT INTO correction_log "
        "(node_id, edge_id, field, old_value, new_value, reason, corrected_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (node_id, edge_id, field, old_value, new_value, reason, corrected_by)
    )
    conn.commit()
```

---

## 구현 파일 요약

| 파일 | 변경 내용 |
|------|---------|
| `storage/vector_store.py` | `get_node_embedding(node_id: int)` 추가 |
| `utils/similarity.py` | `cosine_similarity()` 신규 |
| `node_enricher.py` L654-668 | E7 블록 교체 (drift 탐지 포함) |
| `node_enricher.py` | `_validate_summary_length()` 추가 |
| `node_enricher.py` L354-358 | E1 처리 후 길이 검증 삽입 |
| `config.py` | `DRIFT_THRESHOLD = 0.5` 추가 |
