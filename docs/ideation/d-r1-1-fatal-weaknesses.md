# D-1: 치명적 약점 3가지 재검증

> 세션 D | 2026-03-05 | 코드 읽기 기반 실증 분석

---

## 1-A. 의미적 피드백 루프 — 실제 경로 추적

### 코드 경로 (`node_enricher.py`)

```
_call_llm()
  ├─ E1(summary)       ← 검증 없음. raw LLM output → _update_node() → commit
  ├─ E2(key_concepts)  ← 검증 없음. raw LLM output → _update_node() → commit
  ├─ E3(tags)          ← 검증 없음. raw LLM output → _update_node() → commit
  └─ E7(embedding_text)
       ↓ 오염된 summary 기반 새 임베딩 텍스트 생성
       → vector_store.update()       # ChromaDB 오염 벡터 삽입
       → hybrid_search() 벡터 채널  # 오염 노드 상위 노출
       → _hebbian_update()           # 오염 엣지 frequency+1, strength↑
       → 다음 enrichment 세션 컨텍스트로 재사용
       → 루프 완성
```

### 현재 방어선

| 타겟 | 방어 | 수준 |
|------|------|------|
| E4/E5 (facets, domains) | allowlist 필터 | ✅ OK |
| E8-E11 (float scores) | `max(0, min(1, ...))` | ✅ OK |
| E12 (layer 변경) | confidence > 0.8 조건부 | ⚠️ 부분적 |
| **E1, E2, E3, E7** | **없음** | ❌ 취약 |

### 탐지 메커니즘 설계

```python
# 추가 위치: node_enricher.py, enrich_node_combined() 내 E7 처리 후

DRIFT_THRESHOLD = 0.5  # config로 이동 필요

def _detect_semantic_drift(node_id: str, old_embedding: list, new_embedding_text: str) -> bool:
    """
    반환값: True = 업데이트 거부 (drift 탐지)
    """
    new_emb = vector_store.embed(new_embedding_text)
    similarity = cosine_similarity(old_embedding, new_emb)
    if similarity < DRIFT_THRESHOLD:
        sqlite_store.log_correction(
            node_id=node_id,
            field="embedding_text",
            old_value="<preserved>",
            new_value=new_embedding_text,
            reason=f"semantic_drift: cosine_sim={similarity:.3f} < {DRIFT_THRESHOLD}",
            corrected_by="auto_drift_detector"
        )
        return True
    return False

def _validate_summary_length(new_summary: str, historical_summaries: list) -> tuple[bool, str | None]:
    """
    역사적 중앙값의 2배 초과 시 flag.
    historical_summaries: 같은 타입 노드의 최근 summary 리스트
    """
    if not historical_summaries:
        return True, None
    median_len = statistics.median(len(s) for s in historical_summaries)
    if len(new_summary) > 2 * median_len:
        return False, f"length_anomaly: {len(new_summary)} > 2×{median_len:.0f}"
    return True, None
```

**correction_log 확장 필요 필드:**
```sql
-- correction_log에 추가 컬럼
ALTER TABLE correction_log ADD COLUMN event_type TEXT;       -- 'semantic_drift' | 'length_anomaly'
ALTER TABLE correction_log ADD COLUMN similarity_score REAL; -- 코사인 유사도
ALTER TABLE correction_log ADD COLUMN auto_rollback INTEGER; -- 0/1
```

**호출 순서 (E7 처리 시):**
```python
# enrich_node_combined() 내
if "embedding_text" in updates:
    old_emb = vector_store.get_embedding(node_id)  # 기존 임베딩
    if old_emb and _detect_semantic_drift(node_id, old_emb, updates["embedding_text"]):
        del updates["embedding_text"]  # 오염된 업데이트 제거
        # ChromaDB 재임베딩 건너뜀
```

---

## 1-B. 스키마 드리프트 — 수치 확인

### 소스별 타입 수 불일치

| 소스 | 타입 수 | 경로 |
|------|---------|------|
| `ontology/schema.yaml` | **50개** | Unclassified 포함 |
| `scripts/migrate_v2.py` TYPE_TO_LAYER | **45개** | 5개 누락 |
| `ontology/validators.py` 기준 | **50개** | schema.yaml 읽음 |
| E6 secondary_types 검증 기준 | **45개** | TYPE_TO_LAYER 직접 참조 |

### 5개 누락 타입 확인 (실행 필요)

```bash
python -c "
from scripts.migrate_v2 import TYPE_TO_LAYER
import yaml
with open('ontology/schema.yaml') as f:
    schema = yaml.safe_load(f)
schema_types = {t['name'] for t in schema['node_types']}
migrate_types = set(TYPE_TO_LAYER.keys())
print('schema.yaml에만 (누락):', schema_types - migrate_types)
print('migrate에만 (추가):', migrate_types - schema_types)
"
```

### init_db() 구조 문제

```
현재:
  init_db() → CREATE TABLE IF NOT EXISTS (v1 스키마만)
  migrate_v2.py → ALTER TABLE ADD COLUMN (v2 컬럼 추가)
  → 두 스크립트를 별도 실행해야 함. 문서화 없음.

신규 설치 시:
  init_db() 실행 → layer, tier, quality_score 등 컬럼 없음
  → MCP 서버 시작 즉시 에러

해결 (storage/sqlite_store.py):
  def init_db():
      _create_base_schema()       # 기존 CREATE TABLE IF NOT EXISTS
      _apply_v2_migrations()      # ALTER TABLE ADD COLUMN IF NOT EXISTS (멱등)
      _rebuild_fts_if_needed()    # FTS5 재구축
```

```python
# _apply_v2_migrations() 구현 설계
def _apply_v2_migrations(conn):
    """멱등적 v2 컬럼 추가 (이미 있으면 건너뜀)"""
    v2_node_columns = [
        ("layer", "INTEGER DEFAULT 0"),
        ("summary", "TEXT"),
        ("key_concepts", "TEXT"),
        ("facets", "TEXT"),
        ("domains", "TEXT"),
        ("secondary_types", "TEXT"),
        ("quality_score", "REAL DEFAULT 0.0"),
        ("abstraction_level", "REAL DEFAULT 0.0"),
        ("temporal_relevance", "REAL DEFAULT 0.5"),
        ("actionability", "REAL DEFAULT 0.0"),
        ("enrichment_status", "TEXT DEFAULT '{}'"),
        ("enriched_at", "DATETIME"),
        ("tier", "INTEGER DEFAULT 2"),
        ("maturity", "TEXT DEFAULT 'raw'"),
        ("observation_count", "INTEGER DEFAULT 0"),
    ]
    existing = {row[1] for row in conn.execute("PRAGMA table_info(nodes)")}
    for col_name, col_def in v2_node_columns:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE nodes ADD COLUMN {col_name} {col_def}")
    conn.commit()
```

---

## 1-C. validators.py Dead Code 확인

### 호출 경로 추적

```
mcp_server.py → remember()
  → sqlite_store.insert_node()     ← validators.py 임포트/호출 없음
  → vector_store.add()
  → NO TYPE VALIDATION

mcp_server.py → insert_edge() 또는 _create_edge_if_needed()
  → sqlite_store.insert_edge()     ← validators.py 임포트/호출 없음
  → NO RELATION VALIDATION

node_enricher.py E6 secondary_types
  → scripts.migrate_v2.TYPE_TO_LAYER 직접 참조 (45개 기준)
  → validators.py 미사용
```

**결론:** `ontology/validators.py`는 완성된 코드이지만 **어떤 파이프라인에서도 호출되지 않음**.

### 연결 설계 (Quick Win — 30분)

```python
# mcp_server.py remember() 함수 수정
from ontology.validators import validate_node_type, validate_relation_type, suggest_closest_type

def remember(content: str, type: str = "Unclassified", ...):
    # 타입 검증 추가
    valid, msg = validate_node_type(type)
    if not valid:
        suggestion = suggest_closest_type(type)
        return {
            "status": "error",
            "error": f"Unknown node type: '{type}'. {msg}",
            "suggestion": suggestion,
        }
    # 기존 로직 계속...

def _create_edge(source_id, target_id, relation, ...):
    # 관계 타입 검증 추가
    valid, msg = validate_relation_type(relation)
    if not valid:
        return {
            "status": "error",
            "error": f"Unknown relation type: '{relation}'. {msg}",
        }
    # 기존 로직 계속...
```

---

## 요약

| 약점 | 실재 여부 | 즉시 조치 |
|------|----------|---------|
| 의미적 피드백 루프 | ✅ E1/E2/E7 경로 실증 | `_detect_semantic_drift()` + summary 길이 검증 |
| 스키마 드리프트 | ✅ 50 vs 45 타입 불일치 | `_apply_v2_migrations()` 통합 |
| validators.py 미호출 | ✅ Dead code 확인 | `remember()` / `insert_edge()` 진입점 연결 |
