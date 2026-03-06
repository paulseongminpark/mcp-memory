# A-18: remember() 3함수 분리 완성 코드 — 방화벽 F3 + action_log 통합

> Round 3 최종 심화 | A-14 + A-10(방화벽) + A-17(action_log) 통합
> 목표: classify/store/link + F3 가드 + action_log.record() 모두 포함한 최종 코드
> 원칙: 외부 API(MCP tool) 100% 하위호환, 내부만 변경

---

## 최종 코드: `tools/remember.py`

```python
"""remember() — 기억을 저장하고 자동으로 관계를 생성한다.

v2.0: classify/store/link 3함수 분리 (A-14)
    + 방화벽 F3: L4/L5 자동 edge 금지 (A-10)
    + action_log 기록 (A-17)
외부 API(MCP tool remember) 100% 하위호환.
"""

import json
from dataclasses import dataclass

from config import SIMILARITY_THRESHOLD, PROMOTE_LAYER, infer_relation
from ontology.validators import validate_node_type, suggest_closest_type
from storage import sqlite_store, vector_store
from storage import action_log


# ─── 분류 결과 ──────────────────────────────────────────────

@dataclass
class ClassificationResult:
    """classify()의 반환값. DB 접촉 없는 순수 데이터."""
    type: str
    layer: int | None
    tier: int
    metadata: dict
    original_type: str  # 교정 전 원본 타입 (action_log용)


# ─── 방화벽 규칙 ────────────────────────────────────────────

# A-10 F3: L4/L5 노드에 자동 edge 생성 금지 (하드코딩)
FIREWALL_PROTECTED_LAYERS = {4, 5}


# ─── classify() — 순수 분류, DB 접촉 없음 ───────────────────

def classify(
    content: str,
    type: str = "Unclassified",
    metadata: dict | None = None,
) -> ClassificationResult:
    """온톨로지 검증 + tier/layer 배정. DB 접촉 없음.

    Returns:
        ClassificationResult — 분류 결과 (type, layer, tier, metadata, original_type)
    """
    original_type = type

    # 온톨로지 타입 검증
    valid, correction = validate_node_type(type)
    if not valid:
        suggested = suggest_closest_type(content)
        type = suggested
    elif correction:
        type = correction  # 대소문자 교정

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
        original_type=original_type,
    )


# ─── store() — 순수 저장 ────────────────────────────────────

def store(
    content: str,
    cls: ClassificationResult,
    tags: str = "",
    project: str = "",
    confidence: float = 1.0,
    source: str = "claude",
) -> dict:
    """SQLite + ChromaDB에 노드 저장.

    Returns:
        {"node_id": int, "type": str, "project": str}
        ChromaDB 실패 시 "warning" 키 포함
    """
    # SQLite
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

    # action_log: node_created
    action_log.record(
        action_type="node_created",
        actor="claude",
        target_type="node",
        target_id=node_id,
        params=json.dumps({
            "original_type": cls.original_type,
            "resolved_type": cls.type,
            "layer": cls.layer,
            "tier": cls.tier,
            "project": project,
            "source": source,
        }),
    )

    # ChromaDB (provisional)
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


# ─── link() — 자동 edge 생성 + 방화벽 F3 ────────────────────

def link(
    node_id: int,
    content: str,
    type: str,
    layer: int | None,
    project: str = "",
) -> list[dict]:
    """유사 노드 검색 → 자동 edge 생성.

    방화벽 F3: L4/L5 노드에 대한 자동 edge 생성을 차단한다.
    - 새 노드가 L4/L5면: 자동 edge 전부 차단 (수동 link만 허용)
    - 유사 노드가 L4/L5면: 해당 edge만 차단
    """
    # F3-a: 새 노드 자체가 L4/L5이면 자동 edge 전체 차단
    if layer is not None and layer in FIREWALL_PROTECTED_LAYERS:
        return []

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

        # F3-b: 유사 노드가 L4/L5이면 해당 edge 차단
        sim_layer = sim_node.get("layer")
        if sim_layer is not None and sim_layer in FIREWALL_PROTECTED_LAYERS:
            continue

        # 규칙 기반 relation 추론
        relation = infer_relation(
            src_type=type,
            src_layer=layer,
            tgt_type=sim_node.get("type", ""),
            tgt_layer=sim_layer,
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

        # action_log: edge_auto
        action_log.record(
            action_type="edge_auto",
            actor="claude",
            target_type="edge",
            target_id=edge_id,
            params=json.dumps({
                "source_id": node_id,
                "target_id": sim_id,
                "relation": relation,
                "strength": round(strength, 2),
            }),
        )

    return auto_edges


# ─── remember() — 최상위 API (하위호환 유지) ────────────────

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

    기존 MCP API 100% 호환. 내부적으로 classify → store → link 파이프라인.

    Args:
        content: 기억할 내용
        type: 온톨로지 타입 (default: Unclassified)
        tags: 태그 (쉼표 구분)
        project: 프로젝트명
        metadata: 추가 메타데이터
        confidence: 확신도 0.0-1.0
        source: 생성 주체

    Returns:
        {"node_id", "type", "project", "auto_edges", "message"}
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

    # 3. ChromaDB 실패 시 edge 생성 스킵
    if "warning" in store_result:
        return {
            "node_id": node_id,
            "type": cls.type,
            "project": project,
            "auto_edges": [],
            "warning": store_result["warning"],
            "message": f"Stored as node #{node_id} (embedding failed)",
        }

    # 4. 자동 edge 생성 (방화벽 F3 적용)
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

| 항목 | v1 (현재) | v2 (이 설계) |
|------|-----------|-------------|
| 파일 | tools/remember.py (105줄) | tools/remember.py (~195줄) |
| 함수 | remember() 1개 | classify() + store() + link() + remember() 4개 |
| 클래스 | 없음 | ClassificationResult (dataclass) |
| 방화벽 | 없음 | F3: L4/L5 자동 edge 차단 |
| 로깅 | 없음 | action_log.record() 2지점 (node_created, edge_auto) |
| 외부 API | remember(content, type, ...) → dict | **동일** (하위호환 100%) |
| import 추가 | 0 | json, dataclasses.dataclass, storage.action_log |

---

## 방화벽 F3 상세

### 규칙

```
F3-a: 새 노드.layer ∈ {4, 5} → link() 전체 스킵 (auto_edges = [])
F3-b: 유사 노드.layer ∈ {4, 5} → 해당 edge만 스킵 (continue)
```

### 보호 대상 (현재 DB)

```
L4: Value(2), Philosophy(2), Belief(1) — 5개 노드
L5: Axiom(1) — 1개 노드
총 6개 노드 (전부 orphan, edge 0)
```

### 예시

```python
# Case 1: Value 노드 저장 → 자동 edge 0개
remember("효율성을 극단적으로 추구하는 가치", type="Value")
# → link() 진입 시 layer=4 → F3-a 발동 → auto_edges=[]

# Case 2: Observation 저장인데 유사 노드가 Axiom
remember("모든 도구는 단순해야 한다", type="Observation")
# → link()에서 Axiom 유사 노드 발견 → F3-b 발동 → 해당 edge만 스킵

# Case 3: 일반 노드 간 edge → F3 미관여
remember("새 프로젝트 시작", type="Project")
# → 정상 작동, L4/L5가 아니므로 F3 통과
```

### F3가 차단하지 않는 것

```
- promote_node()에서 생성하는 realized_as edge (수동이므로 허용)
- enrichment에서 생성하는 edge (향후 F4에서 별도 제어)
- 명시적 insert_edge() 호출 (수동이므로 허용)
```

---

## API 하위호환 테스트 시나리오 (A-14 확장)

```python
# tests/test_remember_v2.py

from tools.remember import remember, classify, store, link, ClassificationResult


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
    assert result["type"] != "NonExistentType"


def test_chromadb_failure_graceful():
    """ChromaDB 실패 시 SQLite 노드는 생성되고 warning 반환."""
    # vector_store.add를 mock으로 Exception 발생
    result = remember("테스트", type="Observation")
    assert "node_id" in result
    if "warning" in result:
        assert result["auto_edges"] == []


def test_classify_no_db():
    """classify()가 DB 없이 동작하는지."""
    cls = classify("시스템 설계 원칙", type="Principle")
    assert cls.type == "Principle"
    assert cls.layer == 3
    assert cls.tier == 0
    assert cls.original_type == "Principle"


def test_classify_type_correction():
    """classify()가 deprecated 타입을 교정하는지."""
    cls = classify("경험 법칙", type="Heuristic")
    # Heuristic → deprecated → suggest_closest_type() 결과
    assert cls.type != "Heuristic"
    assert cls.original_type == "Heuristic"


def test_store_independent():
    """store()가 classify 결과만으로 동작하는지."""
    cls = ClassificationResult(
        type="Pattern", layer=2, tier=2,
        metadata={}, original_type="Pattern",
    )
    result = store("패턴 인식", cls, project="mcp-memory")
    assert "node_id" in result


def test_link_independent():
    """link()가 node_id만으로 동작하는지."""
    edges = link(node_id=9999, content="테스트", type="Observation", layer=0)
    assert isinstance(edges, list)


def test_firewall_f3a_l4_no_auto_edges():
    """F3-a: L4 노드는 자동 edge 0개."""
    edges = link(node_id=9999, content="핵심 가치", type="Value", layer=4)
    assert edges == []


def test_firewall_f3a_l5_no_auto_edges():
    """F3-a: L5 노드는 자동 edge 0개."""
    edges = link(node_id=9999, content="근본 공리", type="Axiom", layer=5)
    assert edges == []


def test_firewall_f3b_skips_l4_target():
    """F3-b: 유사 노드가 L4이면 해당 edge 스킵."""
    # vector_store.search mock이 L4 노드를 반환하도록 설정
    # → link()가 해당 노드에 edge를 생성하지 않아야 함
    pass  # mock 기반 테스트


def test_return_format_identical():
    """반환 형태가 기존과 동일한지."""
    result = remember("동일성 테스트", type="Insight")
    required_keys = {"node_id", "type", "project", "auto_edges", "message"}
    assert required_keys.issubset(set(result.keys()))


def test_action_log_recorded():
    """remember() 후 action_log에 node_created 기록 확인."""
    from storage import sqlite_store
    result = remember("action_log 테스트", type="Observation")
    conn = sqlite_store._connect()
    log = conn.execute(
        "SELECT * FROM action_log WHERE target_id = ? AND action_type = 'node_created'",
        (result["node_id"],),
    ).fetchone()
    conn.close()
    assert log is not None
```

---

## 구현 체크리스트

```
Phase 0 마이그레이션 후:
[ ] ClassificationResult dataclass 추가
[ ] classify() 함수 분리
[ ] store() 함수 분리 + action_log.record("node_created")
[ ] link() 함수 분리 + F3 가드 + action_log.record("edge_auto")
[ ] remember() 재조립 (classify→store→link)
[ ] 하위호환 테스트 12개 작성+통과
[ ] mcp_server.py 변경 불필요 확인
```

---

## classify/store/link 독립 사용 시나리오

### enrichment에서 재분류

```python
# scripts/enrich/node_enricher.py 내부
from tools.remember import classify

def reclassify_node(node_id: int, content: str, current_type: str):
    cls = classify(content, type=current_type)
    if cls.type != current_type:
        # 타입 변경 → correction_log + action_log
        ...
```

### 외부 시스템에서 store만

```python
# 향후 Obsidian 인제스트 등
from tools.remember import classify, store

cls = classify(content, type="Observation")
result = store(content, cls, project="obsidian", source="obsidian-ingest")
# link()는 별도 호출하거나 스킵 가능
```

### 테스트에서 classify만

```python
# 온톨로지 검증 테스트
cls = classify("이것은 패턴이다", type="InvalidType")
assert cls.type != "InvalidType"
assert cls.original_type == "InvalidType"
```
