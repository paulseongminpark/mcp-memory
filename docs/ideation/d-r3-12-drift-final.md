# D-r3-12: _detect_semantic_drift() 완성 코드 설계

> 세션 D | Round 3 | 2026-03-05
> D-8 기반 최종 통합: node_enricher.py + utils/similarity.py + calibrate_drift.py + E1 summary 검증

---

## 개요

| 파일 | 변경 | 용도 |
|------|------|------|
| `utils/similarity.py` | 신규 | cosine_similarity() |
| `storage/vector_store.py` | +1 함수 | get_node_embedding() |
| `node_enricher.py` | E7 블록 교체 | drift 탐지 포함 |
| `node_enricher.py` | +2 함수 | summary 길이 검증 |
| `node_enricher.py` | E1 처리 후 | 길이 검증 삽입 |
| `config.py` | +2 상수 | DRIFT_THRESHOLD, SUMMARY_LENGTH_MULTIPLIER |
| `scripts/calibrate_drift.py` | 신규 | threshold 기준선 측정 |

---

## 1. utils/similarity.py (신규 파일)

```python
# utils/similarity.py
"""
벡터 유사도 계산 유틸리티.
외부 의존성: numpy (optional — 없으면 순수 Python fallback)
"""

from __future__ import annotations

try:
    import numpy as np

    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """
        두 벡터의 코사인 유사도 [-1.0, 1.0].
        동일 벡터 → 1.0 / 직교 → 0.0 / 반대 → -1.0

        Args:
            vec_a, vec_b: 동일 차원의 float 리스트
        Returns:
            0.0 if either vector is zero or mismatched length
        """
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        a = np.array(vec_a, dtype=np.float64)
        b = np.array(vec_b, dtype=np.float64)
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / denom) if denom > 0 else 0.0

except ImportError:
    import math

    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:  # type: ignore[misc]
        """numpy 없을 때 순수 Python fallback."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(x * x for x in vec_a))
        norm_b = math.sqrt(sum(x * x for x in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)
```

---

## 2. storage/vector_store.py — get_node_embedding() 추가

```python
# storage/vector_store.py 에 추가 (기존 함수들 뒤에 삽입)

def get_node_embedding(node_id: int) -> list[float] | None:
    """
    ChromaDB에서 node_id의 현재 임베딩 벡터 반환.
    노드가 없거나 임베딩이 없으면 None.

    주의: node_id는 INTEGER (str로 변환해서 ChromaDB에 전달).
    """
    try:
        coll = _get_collection()
        result = coll.get(
            ids=[str(node_id)],
            include=["embeddings"],
        )
        embeddings = result.get("embeddings")
        if embeddings and len(embeddings) > 0 and embeddings[0]:
            return list(embeddings[0])
    except Exception:
        pass
    return None
```

---

## 3. config.py — 상수 추가

```python
# config.py에 추가

# Semantic Drift Detection (E7)
DRIFT_THRESHOLD: float = 0.5
# cosine similarity 하한. 이 값 미만이면 drift로 간주하여 ChromaDB 업데이트 차단.
# 기준: OpenAI text-embedding-3 동일 텍스트 재실행 안정성 ~0.999.
#       실질적 drift(환각)는 0.3-0.7 범위. 0.5는 보수적 설정.
# calibrate_drift.py로 조정 가능.

# Summary Length Validation (E1)
SUMMARY_LENGTH_MULTIPLIER: float = 2.0
# 같은 타입 최근 100개 summary의 중앙값 대비 배율.
# 초과 시 summary_length_validator가 교정 log 기록 후 기존 summary 유지.
SUMMARY_LENGTH_MIN_SAMPLE: int = 5
# 비교 샘플이 이 수 미만이면 검증 skip.
```

---

## 4. node_enricher.py — 헬퍼 함수 추가

```python
# node_enricher.py — 클래스 외부 또는 NodeEnricher 내부에 추가

def _get_summary_median_length(node_type: str, conn) -> float | None:
    """
    같은 타입의 최근 SUMMARY_LENGTH_MIN_SAMPLE개 이상 summary 길이 중앙값.
    샘플 부족 시 None 반환 → 검증 skip.
    """
    from config import SUMMARY_LENGTH_MIN_SAMPLE
    import statistics

    rows = conn.execute(
        "SELECT LENGTH(summary) AS len FROM nodes "
        "WHERE type = ? AND summary IS NOT NULL "
        "  AND status = 'active' AND enriched_at IS NOT NULL "
        "ORDER BY enriched_at DESC LIMIT 100",
        (node_type,),
    ).fetchall()

    if len(rows) < SUMMARY_LENGTH_MIN_SAMPLE:
        return None
    return statistics.median(r[0] for r in rows)


def _validate_summary_length(
    new_summary: str,
    node_type: str,
    conn,
) -> tuple[bool, str | None]:
    """
    새 summary가 길이 이상치인지 검증.

    Returns:
        (True, None)      — 정상
        (False, reason)   — 이상치 (reason에 상세 정보)
    """
    from config import SUMMARY_LENGTH_MULTIPLIER

    median_len = _get_summary_median_length(node_type, conn)
    if median_len is None:
        return True, None  # 샘플 부족 → 패스

    limit = SUMMARY_LENGTH_MULTIPLIER * median_len
    if len(new_summary) > limit:
        return False, (
            f"length_anomaly: {len(new_summary)} chars > "
            f"{SUMMARY_LENGTH_MULTIPLIER}x median {median_len:.0f}"
        )
    return True, None
```

---

## 5. node_enricher.py — E7 블록 교체 (L654-668)

```python
# node_enricher.py L654-668 교체 — E7 블록 (원본: 13줄 → 40줄)

elif tid == "E7":
    if result and not self.dry_run:
        try:
            from storage import vector_store, sqlite_store
            from storage.vector_store import get_node_embedding
            from utils.similarity import cosine_similarity
            from config import DRIFT_THRESHOLD

            node_id = node.get("id")

            # ── Semantic Drift 탐지 ─────────────────────────────────────
            old_embedding = get_node_embedding(node_id)
            drift_detected = False

            if old_embedding:
                # 새 embedding_text(result)로 임베딩 미리 계산
                from storage.embedding import openai_embed
                new_embedding = openai_embed(result)
                similarity = cosine_similarity(old_embedding, new_embedding)

                if similarity < DRIFT_THRESHOLD:
                    drift_detected = True
                    sqlite_store.log_correction(
                        node_id=node_id,
                        field="embedding_text",
                        old_value="<preserved>",
                        new_value=result[:200],
                        reason=(
                            f"semantic_drift: cosine_sim={similarity:.4f} "
                            f"< threshold={DRIFT_THRESHOLD}"
                        ),
                        corrected_by="auto_drift_detector",
                    )

            # ── 드리프트 없을 때만 ChromaDB 업데이트 ────────────────────
            if not drift_detected:
                vec_meta = {
                    "type": node.get("type", ""),
                    "project": node.get("project", ""),
                    "tags": node.get("tags", ""),
                    "embedding_provisional": "false",
                }
                vector_store.add(node_id, result, vec_meta)

        except Exception:
            pass  # ChromaDB/임베딩 실패해도 enrichment 중단하지 않음
```

---

## 6. node_enricher.py — E1 처리 후 summary 길이 검증 삽입

```python
# node_enricher.py — enrich_node_combined() 내 E1 처리 블록 (L354 근방)
# 기존: updates["summary"] = results["E1"]
# 교체:

if "E1" in results and results["E1"]:
    new_summary = results["E1"]
    ok, reason = _validate_summary_length(
        new_summary=new_summary,
        node_type=node.get("type", "Unclassified"),
        conn=conn,
    )
    if ok:
        updates["summary"] = new_summary
    else:
        # 이상치 summary: correction_log 기록 + 기존 summary 유지
        from storage import sqlite_store
        sqlite_store.log_correction(
            node_id=node.get("id"),
            field="summary",
            old_value=(node.get("summary") or "")[:200],
            new_value=new_summary[:200],
            reason=reason,
            corrected_by="summary_length_validator",
        )
        # updates["summary"] 미설정 → 기존 summary 유지됨
```

---

## 7. scripts/calibrate_drift.py (실행 가능 전체 코드)

```python
#!/usr/bin/env python3
"""
scripts/calibrate_drift.py — DRIFT_THRESHOLD 기준선 측정

사용법:
  python scripts/calibrate_drift.py            # 기본 50개 샘플
  python scripts/calibrate_drift.py --n 100    # 100개 샘플 (API 비용 주의)
  python scripts/calibrate_drift.py --dry-run  # DB 접근만, API 미호출

목적:
  같은 content에 OpenAI 임베딩을 2번 생성 → cosine_similarity 측정.
  → DRIFT_THRESHOLD = mean - 2*stdev (자연 변동의 2sigma 아래)
  OpenAI text-embedding-3: 동일 텍스트 재실행 안정성 ~0.999
  실질적 drift 감지 범위: 0.3-0.7

비용: sample_size당 OpenAI API 2회 호출.
      50개 × $0.00002/1K tokens ≈ $0.01 (무시 가능)
"""

from __future__ import annotations

import argparse
import sqlite3
import statistics
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "data" / "memory.db"


def measure_embedding_stability(
    sample_size: int = 50,
    dry_run: bool = False,
) -> dict:
    """
    활성 노드 sample_size개를 랜덤 선택.
    summary (또는 content) 텍스트로 임베딩 2회 생성 → cosine_similarity 측정.

    Returns:
        {
          "mean_stability": float,      # 평균 유사도 (이상적으로 ~0.999)
          "stdev": float,               # 표준편차
          "suggested_threshold": float, # mean - 2*stdev
          "current_threshold": float,   # config.py 현재값
          "n_sampled": int,
          "min_sim": float,
          "max_sim": float,
        }
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    nodes = conn.execute(
        "SELECT id, content, summary FROM nodes "
        "WHERE status='active' AND summary IS NOT NULL "
        "ORDER BY RANDOM() LIMIT ?",
        (sample_size,),
    ).fetchall()

    if not nodes:
        conn.close()
        return {"error": "No active nodes with summary found."}

    print(f"샘플 {len(nodes)}개 선택됨.")

    if dry_run:
        conn.close()
        print("[DRY-RUN] API 호출 건너뜀. 실제 측정 없음.")
        return {
            "dry_run": True,
            "n_sampled": len(nodes),
            "note": "dry-run: 실제 임베딩 미생성",
        }

    from storage.vector_store import get_node_embedding
    from storage.embedding import openai_embed
    from utils.similarity import cosine_similarity

    similarities = []
    errors = 0

    for i, node in enumerate(nodes):
        text = node["summary"] or node["content"]
        if not text:
            continue

        try:
            # 같은 텍스트로 임베딩 2번 생성 (자연 변동 측정)
            emb1 = openai_embed(text)
            emb2 = openai_embed(text)
            sim = cosine_similarity(emb1, emb2)
            similarities.append(sim)
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  임베딩 오류 (node {node['id']}): {e}")

        if (i + 1) % 10 == 0:
            print(f"  진행: {i + 1}/{len(nodes)}")

    conn.close()

    if not similarities:
        return {"error": "임베딩 생성 실패. API 키 확인 필요."}

    from config import DRIFT_THRESHOLD

    mean = statistics.mean(similarities)
    stdev = statistics.stdev(similarities) if len(similarities) > 1 else 0.0
    suggested = mean - 2 * stdev

    result = {
        "mean_stability": round(mean, 6),
        "stdev": round(stdev, 6),
        "suggested_threshold": round(suggested, 6),
        "current_threshold": DRIFT_THRESHOLD,
        "n_sampled": len(similarities),
        "n_errors": errors,
        "min_sim": round(min(similarities), 6),
        "max_sim": round(max(similarities), 6),
    }
    return result


def print_report(result: dict):
    print("\n=== Drift Threshold Calibration Report ===")
    for k, v in result.items():
        print(f"  {k}: {v}")

    if "suggested_threshold" in result and "current_threshold" in result:
        suggested = result["suggested_threshold"]
        current = result["current_threshold"]
        if suggested > current:
            print(f"\n  권장: DRIFT_THRESHOLD를 {current} → {suggested:.3f}로 올릴 것")
        elif suggested < current - 0.1:
            print(f"\n  권장: DRIFT_THRESHOLD를 {current} → {suggested:.3f}로 낮출 것")
        else:
            print(f"\n  현재 threshold({current}) 적절함.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drift threshold calibration")
    parser.add_argument("--n", type=int, default=50, help="샘플 수 (기본 50)")
    parser.add_argument("--dry-run", action="store_true", help="DB 접근만, API 미호출")
    args = parser.parse_args()

    result = measure_embedding_stability(sample_size=args.n, dry_run=args.dry_run)
    print_report(result)
```

---

## 8. sqlite_store.log_correction() — 미존재 시 추가

```python
# storage/sqlite_store.py — log_correction() 헬퍼 (없으면 추가)
# correction_log 테이블 스키마 가정:
#   (id, node_id, edge_id, field, old_value, new_value, reason, corrected_by, event_type, created_at)

def log_correction(
    node_id: int | None = None,
    edge_id: int | None = None,
    field: str = "",
    old_value: str = "",
    new_value: str = "",
    reason: str = "",
    corrected_by: str = "system",
    event_type: str = "correction",
) -> None:
    """correction_log 기록. 실패해도 main flow 중단 안 함."""
    try:
        conn = _connect()
        conn.execute(
            "INSERT INTO correction_log "
            "(node_id, edge_id, field, old_value, new_value, reason, corrected_by, event_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (node_id, edge_id, field, old_value, new_value, reason, corrected_by, event_type),
        )
        conn.commit()
    except Exception:
        pass
```

---

## 9. 구현 파일 최종 요약

| 파일 | 변경 내용 | 위험도 |
|------|---------|--------|
| `utils/similarity.py` | 신규 (numpy/fallback 겸용) | 낮음 |
| `storage/vector_store.py` | `get_node_embedding()` 추가 | 낮음 |
| `config.py` | `DRIFT_THRESHOLD=0.5`, `SUMMARY_LENGTH_MULTIPLIER=2.0` | 낮음 |
| `node_enricher.py` | E7 블록 교체 (~40줄) | 중간 |
| `node_enricher.py` | `_get_summary_median_length()` + `_validate_summary_length()` 추가 | 낮음 |
| `node_enricher.py` | E1 처리 후 길이 검증 삽입 (~10줄) | 낮음 |
| `storage/sqlite_store.py` | `log_correction()` 추가 (없을 경우) | 낮음 |
| `scripts/calibrate_drift.py` | 신규 (측정 도구) | 없음 |

---

## 10. 실행 검증 순서

```bash
# 1. similarity 모듈 단위 테스트
python -c "
from utils.similarity import cosine_similarity
print(cosine_similarity([1,0,0], [1,0,0]))  # 1.0
print(cosine_similarity([1,0,0], [0,1,0]))  # 0.0
print(cosine_similarity([1,0], [1]))         # 0.0 (mismatched)
"

# 2. get_node_embedding 확인
python -c "
import sys; sys.path.insert(0, '.')
from storage.vector_store import get_node_embedding
emb = get_node_embedding(1)
print('dim:', len(emb) if emb else 'None')
"

# 3. calibrate_drift dry-run
python scripts/calibrate_drift.py --dry-run

# 4. calibrate_drift 실제 측정 (소규모)
python scripts/calibrate_drift.py --n 10

# 5. summary 길이 검증 SQL 확인
python -c "
import sqlite3
conn = sqlite3.connect('data/memory.db')
rows = conn.execute(
    'SELECT type, COUNT(*), AVG(LENGTH(summary)) FROM nodes '
    'WHERE summary IS NOT NULL AND status=\"active\" GROUP BY type'
).fetchall()
for r in rows: print(r)
"
```
