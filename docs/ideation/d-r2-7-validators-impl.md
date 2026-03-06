# D-7: validators.py 연결 — 실제 구현 코드

> 세션 D | 2026-03-05 | Phase 0 Quick Win (30분)
> 오케스트레이터 확정: 즉시 실행

---

## 코드 확인 결과

### 진입점: `server.py` (mcp_server.py 아님)

```python
# server.py L39-47
@mcp.tool()
def remember(
    content: str,
    type: str = "Unclassified",
    tags: str = "",
    project: str = "",
    metadata: dict | None = None,
    confidence: float = 1.0,
    source: str = "claude",
) -> dict:
```

**기존 성공 반환 포맷** (`tools/remember.py` L99-105):
```python
{
    "node_id": node_id,       # int
    "type": type,             # str
    "project": project,       # str
    "auto_edges": auto_edges, # list[dict]
    "message": f"Stored as node #{node_id} with {len(auto_edges)} auto-edge(s)",
}
```

**기존 소프트 에러 포맷** (임베딩 실패 시):
```python
{
    "node_id": node_id,
    "type": type,
    "project": project,
    "auto_edges": [],
    "warning": f"Stored in SQLite but embedding failed: {e}",
    "message": f"Stored as node #{node_id} (embedding failed)",
}
```

### `suggest_closest_type()` 알고리즘

**키워드 매칭 (Levenshtein 아님)**:
```python
# ontology/validators.py L61-79
def suggest_closest_type(content: str) -> str:
    content_lower = content.lower()
    hints = {
        "Decision": ["결정", "decided", "decision", "chose", "선택"],
        "Failure": ["실패", "fail", "error", "버그", "mistake", "실수"],
        "Pattern": ["패턴", "pattern", "반복", "recurring", "규칙"],
        "Identity": ["가치", "철학", "philosophy", "성격", "스타일"],
        # ... (10개 타입)
    }
    for type_name, keywords in hints.items():
        if any(kw in content_lower for kw in keywords):
            return type_name
    return "Unclassified"
```

**주의:** `suggest_closest_type(content)`는 content(본문)를 입력받음.
잘못 입력된 타입명(`"pattern"`)이 아닌 내용("패턴 발견...")으로 추천.
타입명 오류 시 추천은 content 기반 → 더 정확한 추천 가능.

### `insert_edge()` 기존 처리

`sqlite_store.py` L156-183에서 **이미 fallback 있음**:
```python
if relation not in ALL_RELATIONS:
    # correction_log 기록 후 "connects_with"로 대체
    ...
    relation = "connects_with"
```

→ edge relation 검증은 sqlite_store 레벨에서 이미 처리됨.
→ MCP 레벨에서는 node_type 검증만 추가하면 충분.

---

## 구현 코드

### 수정 위치: `server.py` L39 ~ remember() 함수 시작부

```python
# server.py — remember() 함수 수정
# 기존 import 섹션에 추가:
from ontology.validators import validate_node_type, suggest_closest_type

@mcp.tool()
def remember(
    content: str,
    type: str = "Unclassified",
    tags: str = "",
    project: str = "",
    metadata: dict | None = None,
    confidence: float = 1.0,
    source: str = "claude",
) -> dict:
    """
    Store a memory node with automatic embedding and relationship detection.
    ...
    """
    # ── [추가] 타입 검증 ──────────────────────────────────────────────
    valid, msg = validate_node_type(type)
    if not valid:
        # msg가 교정된 타입명을 담고 있으면 자동 교정 (대소문자 불일치)
        # validate_node_type()은 대소문자 무시 매칭 시 (True, "CorrectedName") 반환
        # → 이미 valid=True로 처리되므로 여기는 실제 미지 타입만 옴
        suggestion = suggest_closest_type(content)
        return {
            "node_id": None,
            "type": type,
            "project": project,
            "auto_edges": [],
            "error": f"Unknown node type: '{type}'. {msg}",
            "suggestion": suggestion,
            "message": f"Validation failed: unknown type '{type}'. Suggested: '{suggestion}'",
        }

    # 대소문자 자동 교정: validate_node_type이 (True, "CorrectedName") 반환하는 경우
    if msg:  # msg에 교정된 타입명이 있음
        type = msg  # 교정값으로 대체
    # ── [추가 끝] ──────────────────────────────────────────────────────

    # 기존 로직 그대로 진행...
    from tools.remember import run_remember
    return run_remember(
        content=content, type=type, tags=tags, project=project,
        metadata=metadata, confidence=confidence, source=source,
    )
```

### validate_node_type() 반환값 재확인

```python
# validators.py L35-44
def validate_node_type(node_type: str) -> tuple[bool, str]:
    valid_types = get_valid_node_types()
    if node_type in valid_types:
        return True, ""               # 정확히 일치
    lower_map = {t.lower(): t for t in valid_types}
    if node_type.lower() in lower_map:
        return True, lower_map[node_type.lower()]  # 교정된 타입명 반환
    return False, f"Unknown type '{node_type}'. Valid: {', '.join(valid_types)}"
```

| 입력 | 반환 | 처리 |
|------|------|------|
| `"Pattern"` | `(True, "")` | 그대로 진행 |
| `"pattern"` | `(True, "Pattern")` | `type = "Pattern"` 교정 후 진행 |
| `"FooBar"` | `(False, "Unknown type...")` | 에러 반환 |

### 에러 반환 포맷 (기존 패턴 일치)

```python
# 기존 에러(임베딩 실패)와 동일한 구조 유지:
{
    "node_id": None,          # 저장 안 됨
    "type": type,             # 입력된 타입 (잘못된 것)
    "project": project,
    "auto_edges": [],
    "error": "Unknown node type: 'FooBar'. Valid: ...",
    "suggestion": "Pattern",  # content 기반 추천
    "message": "Validation failed: unknown type 'FooBar'. Suggested: 'Pattern'",
}
```

**`warning` vs `error` 구분:**
- `warning`: 저장은 됐으나 문제 있음 (기존 임베딩 실패 패턴)
- `error`: 저장 자체 안 됨 (신규 — 타입 검증 실패)

### edge relation 검증 (현재 불필요, 이유)

`sqlite_store.insert_edge()` L164-180에서 이미:
```python
if relation not in ALL_RELATIONS:
    # correction_log 기록 + "connects_with" fallback
```
→ 별도 MCP 레벨 검증 불필요. 잘못된 relation은 조용히 교정됨.
→ 원하면 서버 레벨에서도 경고 반환 가능하나 현재는 불필요.

---

## 실행 검증

```bash
# 검증 1: 잘못된 타입
python -c "
import sys; sys.path.insert(0, '.')
from ontology.validators import validate_node_type, suggest_closest_type
print(validate_node_type('FooBar'))           # (False, 'Unknown type...')
print(validate_node_type('pattern'))          # (True, 'Pattern')
print(suggest_closest_type('반복되는 실수'))   # 'AntiPattern'
"

# 검증 2: remember() 호출 후 에러 포맷 확인
# MCP 도구 테스트:
# remember(content="test", type="InvalidType") → error 필드 있어야 함
# remember(content="test", type="pattern") → 자동 교정, node_id 있어야 함
```

---

## 수정 범위 요약

| 파일 | 수정 | 줄 수 |
|------|------|------|
| `server.py` | remember() 앞에 타입 검증 블록 삽입 | +15줄 |
| `server.py` | `from ontology.validators import ...` 추가 | +1줄 |
| 기타 | 없음 | — |

**총 ~16줄 추가. 기존 로직 변경 없음.**
