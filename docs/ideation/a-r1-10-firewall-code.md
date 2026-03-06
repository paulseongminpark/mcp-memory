# 심화 2: 인지적 방화벽 — 실제 코드 삽입 지점

## 실제 L4/L5 노드 현황 (2026-03-05 DB 진단)

```
L4/L5 총 6개 노드. 전부 orphan (edge 0).

#4161 L4 [Belief]     q=0.92 src=user
  "모든 현상을 다차원으로 해석하는 것이 사고의 본질이다"
#4162 L4 [Philosophy]  q=0.78 src=user
  "기억과 연결이 동시에, 의식하지 않아도 자동으로 일어난다"
#4165 L4 [Philosophy]  q=0.92 src=user
  "의지에 의존하지 않고 환경과 규칙을 설계해서 관찰->분해->구조화->검증"
#4163 L4 [Value]       q=0.95 src=user
  "뇌의 다차원적 연결을 외부화하고 싶다는 욕구. 더, 더, 더!"
#4166 L4 [Value]       q=0.92 src=user
  "이색적 접합 - 서로 다른 도메인의 개념을 연결해서 새로운 의미"
#4164 L5 [Axiom]       q=0.85 src=user
  "'가고 싶은 지점'과 '가야만 하는 지점' - 이 둘의 수렴과 분기 추적"
```

**치명적 발견**: L4/L5에 edge 0개.
- recall() 시 벡터 유사도에만 의존, 그래프 보너스(0.3) 전혀 못 받음
- Paul의 핵심 가치가 시스템에서 **유리(遊離)**
- **방화벽 이전에 수동 edge 구축 필요**

## F1: immutable_core

### _check_firewall() — storage/sqlite_store.py 신규

```python
def _check_firewall(node_id: int, actor: str, operation: str) -> bool:
    conn = _connect()
    row = conn.execute("SELECT layer FROM nodes WHERE id = ?", (node_id,)).fetchone()
    conn.close()
    if not row or row["layer"] is None or row["layer"] < 4:
        return True
    if operation in ("modify_content", "modify_type", "delete"):
        return actor == "paul"
    if operation == "modify_metadata":
        return actor in ("paul", "claude")
    return True
```

### update_node() — storage/sqlite_store.py 신규 (현재 미존재!)

enrichment가 직접 SQL UPDATE하는 것이 방화벽 우회의 근본 원인.

```python
def update_node(node_id: int, updates: dict, actor: str = "system") -> bool:
    content_fields = {"content", "type"}
    if content_fields & set(updates.keys()):
        if not _check_firewall(node_id, actor, "modify_content"):
            raise PermissionError("F1: L4/L5 content requires actor='paul'")
    # UPDATE 실행...
```

## F2: enrichment_restriction

### scripts/enrich/node_enricher.py — enrich_node_combined() 내부

```python
if node.get("layer") is not None and node["layer"] >= 4:
    allowed_fields = {"summary", "key_concepts", "quality_score"}
    updates = {k: v for k, v in updates.items() if k in allowed_fields}
```

## F3: auto_edge_prohibition

### tools/remember.py:72-97

```python
for sim_id, distance, _ in similar:
    # ... 기존 체크 ...
    sim_node = sqlite_store.get_node(sim_id)
    if not sim_node: continue
    sim_layer = sim_node.get("layer")
    if sim_layer is not None and sim_layer >= 4:
        continue  # F3: L4/L5 자동 edge 금지
    # ... edge 생성
```

### scripts/enrich/relation_extractor.py — E13

```python
if target_layer >= 4 or source_layer >= 4:
    continue  # F3: enrichment L4/L5 edge 금지
```

## F4: promotion_human_gate

### tools/promote_node.py

```python
target_layer = PROMOTE_LAYER.get(target_type)
if target_layer is not None and target_layer >= 4:
    if source != "paul":
        return {"error": "F4: L4/L5 promotion requires human confirmation", "action": "blocked"}
```

## F5: decay_immunity

### storage/hybrid.py — _hebbian_update()

```python
for edge in matching_edges:
    source_node = sqlite_store.get_node(edge["source_id"])
    target_node = sqlite_store.get_node(edge["target_id"])
    if any((n.get("layer") or 0) >= 4 for n in [source_node, target_node] if n):
        continue  # F5: L4/L5 decay 면역
    # ... Hebbian 갱신
```

성능 최적화: edge 테이블에 source_layer/target_layer 캐시 컬럼 추가 고려.

## F6: deletion_prohibition

```python
FIREWALL_EXCEPTIONS = {
    "layer_gte_4": "L4/L5 자동 비활성화/아카이브 불가",
    "tier_0_manual": "tier=0 자동 비활성화 시 경고",
}
```

## integrity_check() 구현

```python
# tools/integrity.py
def integrity_check() -> dict:
    conn = sqlite_store._connect()
    l4l5 = conn.execute(
        "SELECT id, type, layer, content, source FROM nodes WHERE layer >= 4 AND status = 'active'"
    ).fetchall()

    results = {"core_count": len(l4l5), "baseline": 6, "violations": []}

    for node in l4l5:
        if node["source"] not in ("user", "paul"):
            results["violations"].append({"rule": "F1", "node_id": node["id"],
                "detail": f"L{node['layer']} created by '{node['source']}'"})

        edges = conn.execute(
            "SELECT * FROM edges WHERE source_id = ? OR target_id = ?",
            (node["id"], node["id"])).fetchall()
        for e in edges:
            if "enrichment" in (e["description"] or "").lower():
                results["violations"].append({"rule": "F3", "edge_id": e["id"]})

    conn.close()
    return results
```

## L4/L5 연결 복구 제안 (Paul 확인 필요)

```
L5 Axiom (#4164: 수렴/분기)
  <- crystallized_into - L4 Value (#4163: 더, 더, 더)
  <- crystallized_into - L4 Value (#4166: 이색적 접합)
  <- governs - L4 Belief (#4161: 다차원 해석)

L4 Value (#4163) -> expressed_as -> L3 Principle (컨텍스트 효율성, 확장된 인지)
L4 Value (#4166) -> expressed_as -> L2 Pattern (DMN), L3 Principle (연결 자동화)
L4 Philosophy (#4162) -> expressed_as -> L3 Principle (Hebbian), L2 Pattern (자동 강화)
L4 Philosophy (#4165) -> expressed_as -> L3 Principle (시스템 설계), L2 Framework (오케스트레이션)
L4 Belief (#4161) -> expressed_as -> L3 Principle (다각도 분석), L2 Pattern (크로스 도메인)
```

이 연결은 F3에 의해 자동 생성 불가. Paul 승인 후 수동 생성.
