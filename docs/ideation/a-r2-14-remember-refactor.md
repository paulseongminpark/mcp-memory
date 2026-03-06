# 심화 6: remember() 3함수 분리 — 실제 코드

> A-1(Palantir) 기반. tools/remember.py 105줄 → classify/store/link 분리
> 원칙: 외부 API(MCP tool) 불변, 내부 구조만 변경

---

## 현재 코드 분석 (tools/remember.py)

```
Line  1-6:   imports
Line  8-16:  remember() 시그니처
Line 17-23:  [CLASSIFY] 온톨로지 타입 검증 + 교정
Line 25-28:  [CLASSIFY] provisional embedding 플래그
Line 29-37:  [CLASSIFY] 자동 tier/layer 배정
Line 38-49:  [STORE]    SQLite insert_node + ChromaDB add
Line 50-64:  [STORE]    ChromaDB 실패 시 graceful return
Line 66-97:  [LINK]     유사 노드 검색 → 자동 edge 생성
Line 99-105: return
```

분리 지점이 명확하다: 17-37 = classify, 38-64 = store, 66-97 = link.

---

## 분리된 코드

### classify() — 순수 분류, DB 접촉 없음

```python
"""remember() — 기억을 저장하고 자동으로 관계를 생성한다."""

from dataclasses import dataclass

from config import SIMILARITY_THRESHOLD, PROMOTE_LAYER, infer_relation
from ontology.validators import validate_node_type, suggest_closest_type
from storage import sqlite_store, vector_store


@dataclass
class ClassificationResult:
    type: str
    layer: int | None
    tier: int
    metadata: dict


def classify(
    content: str,
    type: str = "Unclassified",
    metadata: dict | None = None,
) -> ClassificationResult:
    """순수 분류. DB 접촉 없음. 온톨로지 검증 + tier/layer 배정."""
    # 온톨로지 타입 검증
    valid, correction = validate_node_type(type)
    if not valid:
        suggested = suggest_closest_type(content)
        type = suggested
    elif correction:
        type = correction

    # provisional embedding 플래그
    metadata = dict(metadata) if metadata else {}
    metadata["embedding_provisional"] = "true"

    # 자동 tier/layer 배정
    layer = PROMOTE_LAYER.get(type)
    if layer is not None and layer >= 3:
        tier = 0  # core
    elif layer == 2:
        tier = 2  # auto (enrichment 후 승격)
    else:
        tier = 2  # auto

    return ClassificationResult(
        type=type,
        layer=layer,
        tier=tier,
        metadata=metadata,
    )
```

### store() — 순수 저장, 분류 결정을 받아서 저장만

```python
def store(
    content: str,
    cls: ClassificationResult,
    tags: str = "",
    project: str = "",
    confidence: float = 1.0,
    source: str = "claude",
) -> dict:
    """순수 저장. 분류 결정을 받아서 SQLite + ChromaDB에 저장.

    Returns:
        {"node_id": int, "type": str, "project": str}
        ChromaDB 실패 시 warning 포함
    """
    # SQLite에 노드 저장
    node_id = sqlite_store.insert_node(
        type=cls.type,
        content=content,
        metadata=cls.metadata,
        project=project,
        tags=tags,
        confidence=confidence,
        source=source,
        layer=cls.layer,
        tier=cls.tier,
    )

    # ChromaDB에 임베딩 저장 (provisional)
    vec_meta = {
        "type": cls.type,
        "project": project,
        "tags": tags,
        "embedding_provisional": "true",
    }
    try:
        vector_store.add(node_id, content, vec_meta)
    except Exception as e:
        return {
            "node_id": node_id,
            "type": cls.type,
            "project": project,
            "warning": f"Stored in SQLite but embedding failed: {e}",
        }

    return {
        "node_id": node_id,
        "type": cls.type,
        "project": project,
    }
```

### link() — 자동 edge 생성, 저장 완료된 노드에 대해 실행

```python
def link(
    node_id: int,
    content: str,
    type: str,
    layer: int | None,
    project: str = "",
) -> list[dict]:
    """자동 edge 생성. 저장 완료된 노드에 대해 유사 노드 검색 → edge 생성.

    Returns:
        [{"edge_id": int, "target_id": int, "relation": str, "strength": float}, ...]
    """
    auto_edges = []
    try:
        similar = vector_store.search(content, top_k=5)
    except Exception:
        return auto_edges

    for sim_id, distance, _ in similar:
        if sim_id == node_id:
            continue
        if distance > SIMILARITY_THRESHOLD:
            continue
        sim_node = sqlite_store.get_node(sim_id)
        if not sim_node:
            continue
        # 규칙 기반 relation 추론
        relation = infer_relation(
            src_type=type,
            src_layer=layer,
            tgt_type=sim_node.get("type", ""),
            tgt_layer=sim_node.get("layer"),
            src_project=project,
            tgt_project=sim_node.get("project", ""),
        )
        strength = max(0.0, 1.0 - distance)
        edge_id = sqlite_store.insert_edge(
            source_id=node_id,
            target_id=sim_id,
            relation=relation,
            description=f"auto: similarity={1.0 - distance:.2f}",
            strength=strength,
        )
        auto_edges.append({
            "edge_id": edge_id,
            "target_id": sim_id,
            "relation": relation,
            "strength": round(strength, 2),
        })

    return auto_edges
```

### remember() — 최상위 API (하위 호환 유지)

```python
def remember(
    content: str,
    type: str = "Unclassified",
    tags: str = "",
    project: str = "",
    metadata: dict | None = None,
    confidence: float = 1.0,
    source: str = "claude",
) -> dict:
    """기억을 저장하고 자동으로 관계를 생성한다.

    기존 API 100% 호환. 내부적으로 classify → store → link 파이프라인 실행.
    """
    # 1. 분류
    cls = classify(content, type=type, metadata=metadata)

    # 2. 저장
    store_result = store(
        content, cls,
        tags=tags, project=project,
        confidence=confidence, source=source,
    )
    node_id = store_result["node_id"]

    # 3. 저장 실패 (ChromaDB 오류) 시 edge 생성 스킵
    if "warning" in store_result:
        return {
            "node_id": node_id,
            "type": cls.type,
            "project": project,
            "auto_edges": [],
            "warning": store_result["warning"],
            "message": f"Stored as node #{node_id} (embedding failed)",
        }

    # 4. 자동 edge 생성
    auto_edges = link(
        node_id, content,
        type=cls.type, layer=cls.layer, project=project,
    )

    return {
        "node_id": node_id,
        "type": cls.type,
        "project": project,
        "auto_edges": auto_edges,
        "message": f"Stored as node #{node_id} with {len(auto_edges)} auto-edge(s)",
    }
```

---

## 변경 요약

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| 파일 | tools/remember.py (105줄) | tools/remember.py (~140줄) |
| 함수 | remember() 1개 | classify() + store() + link() + remember() 4개 |
| 외부 API | remember(content, type, ...) | **동일** (하위 호환) |
| import 추가 | 없음 | `dataclasses.dataclass` |
| 새 클래스 | 없음 | `ClassificationResult` |

### 변경하지 않는 것

- `remember()`의 시그니처와 반환 형태: 동일
- `mcp_server.py`의 remember 도구 등록: 변경 불필요
- `insert_node()`, `insert_edge()`, `vector_store.add()`: 변경 불필요
- `validate_node_type()`, `suggest_closest_type()`, `infer_relation()`: 변경 불필요

---

## 이점: 온톨로지 진화 시나리오

### 시나리오 1: 새 타입 추가

```python
# 변경 전: remember.py + schema.yaml + validators.py + config.py 전부 수정
# 변경 후: type_defs에 INSERT + classify() 규칙 추가 (1곳)
```

### 시나리오 2: enrichment에서 재분류

```python
# 변경 전: enrichment가 직접 SQL UPDATE
# 변경 후:
def reclassify_node(node_id: int):
    node = sqlite_store.get_node(node_id)
    cls = classify(node["content"], type=node["type"])
    if cls.type != node["type"]:
        # 타입 변경 → correction_log 기록
        ...
```

### 시나리오 3: 방화벽 통합 (A-10)

```python
# link() 내부에 F3 가드 추가
def link(node_id, content, type, layer, project=""):
    for sim_id, distance, _ in similar:
        sim_node = sqlite_store.get_node(sim_id)
        if not sim_node:
            continue
        # F3: L4/L5 자동 edge 금지
        sim_layer = sim_node.get("layer")
        if sim_layer is not None and sim_layer >= 4:
            continue
        ...
```

---

## API 하위호환 테스트 시나리오

```python
# tests/test_remember_compat.py

def test_basic_remember():
    """기본 호출이 동일한 결과를 반환하는지."""
    result = remember("테스트 기억", type="Observation", project="mcp-memory")
    assert "node_id" in result
    assert result["type"] == "Observation"
    assert "auto_edges" in result
    assert "message" in result

def test_invalid_type_correction():
    """잘못된 타입이 교정되는지."""
    result = remember("테스트", type="NonExistentType")
    assert result["type"] != "NonExistentType"  # suggest_closest_type 결과

def test_chromadb_failure_graceful():
    """ChromaDB 실패 시 SQLite 노드는 생성되고 warning 반환."""
    # vector_store.add를 mock으로 Exception 발생
    result = remember("테스트", type="Observation")
    assert "node_id" in result
    assert "warning" in result
    assert result["auto_edges"] == []

def test_classify_independent():
    """classify()가 DB 없이 동작하는지."""
    cls = classify("시스템 설계 원칙", type="Principle")
    assert cls.type == "Principle"
    assert cls.layer == 3
    assert cls.tier == 0

def test_store_independent():
    """store()가 classify 결과만으로 동작하는지."""
    cls = ClassificationResult(type="Pattern", layer=2, tier=2, metadata={})
    result = store("패턴 인식", cls, project="mcp-memory")
    assert "node_id" in result

def test_link_independent():
    """link()가 node_id만으로 동작하는지."""
    edges = link(node_id=9999, content="테스트", type="Observation", layer=0)
    assert isinstance(edges, list)

def test_return_format_identical():
    """반환 형태가 기존과 동일한지."""
    result = remember("동일성 테스트", type="Insight")
    # 기존 반환 키: node_id, type, project, auto_edges, message
    required_keys = {"node_id", "type", "project", "auto_edges", "message"}
    assert required_keys.issubset(set(result.keys()))
```

---

## 구현 체크리스트

```
[ ] ClassificationResult dataclass 추가
[ ] classify() 함수 분리 (remember 17-37줄)
[ ] store() 함수 분리 (remember 38-64줄)
[ ] link() 함수 분리 (remember 66-97줄)
[ ] remember() 재조립 (classify→store→link)
[ ] 하위호환 테스트 7개 작성+통과
[ ] mcp_server.py 변경 불필요 확인
[ ] action_log 기록 삽입 (A-9 계획대로)
```
