# L1 Search Improvement — 3-Layer Type-Aware Search

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** L1 노드(Workflow/Tool/Agent/Failure 등) 검색 정확도를 개선하여 corrected goldset 기준 NDCG@5 0.60→0.75+ 달성

**Architecture:** 3개 레이어를 순차 적용 — (1) 임베딩에 타입 태그 추가로 벡터 공간 분리, (2) 쿼리 키워드 기반 타입 부스트, (3) 결과 타입 다양성 보장. 각 레이어는 독립적으로 on/off 가능.

**Tech Stack:** Python, ChromaDB, OpenAI text-embedding-3-large, SQLite FTS5

**Baseline:**
- Corrected goldset NDCG@5: 0.44 (전체 75q) / 0.60 (q051-q075 25q)
- Original goldset NDCG@5: 0.57 (전체 75q, 순환 참조 포함)

---

### Task 1: Goldset 교정 적용

**Files:**
- Modify: `scripts/eval/goldset.yaml`
- Reference: `scripts/eval/goldset_corrected.yaml` (이미 생성됨)

**Step 1: 교정된 goldset을 메인으로 교체**

```bash
cp scripts/eval/goldset.yaml scripts/eval/goldset_v2.0_backup.yaml
cp scripts/eval/goldset_corrected.yaml scripts/eval/goldset.yaml
```

**Step 2: 버전 헤더 확인**

goldset.yaml 상단이 `version: '2.1'`이고 `correction_note`가 포함되어 있는지 확인.

**Step 3: Baseline NDCG 측정**

```bash
PYTHONIOENCODING=utf-8 python scripts/eval/ab_test.py --k 18 --top-k 10
```

Expected: NDCG@5 ≈ 0.44 (교정된 goldset 기준 baseline)

**Step 4: Commit**

```bash
git add scripts/eval/goldset.yaml scripts/eval/goldset_v2.0_backup.yaml
git commit -m "[mcp-memory] goldset v2.1: L1 relevant_ids 타입 교정 (순환 참조 제거)"
```

---

### Task 2: Layer C — 타입 태그 재임베딩

**Files:**
- Modify: `scripts/pipeline/reembed.py:17-35` (build_embed_text 함수)

**Step 1: build_embed_text에 타입 태그 추가**

`scripts/pipeline/reembed.py`의 `build_embed_text` 함수를 수정:

```python
def build_embed_text(node: dict) -> str:
    """노드에서 임베딩용 텍스트 생성. 타입 태그 포함."""
    parts = []
    # 타입 태그를 첫 줄에 추가
    node_type = node.get("type", "")
    if node_type:
        parts.append(f"[{node_type}]")
    if node.get("summary"):
        parts.append(node["summary"])
    if node.get("key_concepts"):
        kc = node["key_concepts"]
        if kc.startswith("["):
            import json
            try:
                kc = ", ".join(json.loads(kc))
            except Exception:
                pass
        parts.append(kc)
    content = node.get("content", "")
    if content:
        parts.append(content[:200])
    return "\n".join(parts)
```

**Step 2: 재임베딩 실행**

```bash
PYTHONIOENCODING=utf-8 python scripts/pipeline/reembed.py
```

Expected: 2859 nodes 재임베딩 완료, 0 errors.
시간: ~3-5분 (OpenAI API batch, text-embedding-3-large)

**Step 3: NDCG 측정 (Layer C 효과)**

```bash
PYTHONIOENCODING=utf-8 python scripts/eval/ab_test.py --k 18 --top-k 10
```

Expected: NDCG@5 > 0.44 (baseline 대비 개선)

**Step 4: Commit**

```bash
git add scripts/pipeline/reembed.py
git commit -m "[mcp-memory] Layer C: 타입 태그 재임베딩 ([Type] prefix)"
```

---

### Task 3: Layer A — 키워드 기반 타입 부스트

**Files:**
- Modify: `config.py` (TYPE_KEYWORDS 상수 추가)
- Modify: `storage/hybrid.py:445-480` (스코어 계산에 type_boost 추가)
- Create: `tests/test_type_boost.py`

**Step 1: config.py에 TYPE_KEYWORDS 추가**

config.py 하단에 추가:

```python
# ── Type-aware search boost ──────────────────────────────────
TYPE_BOOST = 0.03  # 타입 매칭 시 추가 점수

TYPE_KEYWORDS: dict[str, list[str]] = {
    "Workflow": ["워크플로우", "절차", "단계", "파이프라인", "프로세스", "체인", "실행 순서"],
    "Tool": ["도구", "툴", "CLI", "스크립트", "명령어", "플러그인"],
    "Agent": ["에이전트", "팀", "역할", "봇", "자동화 에이전트"],
    "Skill": ["스킬", "명령", "/", "슬래시"],
    "Failure": ["실패", "에러", "버그", "오류", "장애", "문제"],
    "Experiment": ["실험", "테스트", "검증", "비교", "시도"],
    "Decision": ["결정", "선택", "결단", "판단", "확정"],
    "Evolution": ["진화", "변경", "업데이트", "버전", "발전", "개선"],
    "Signal": ["신호", "관찰", "습관", "패턴 관찰", "징후"],
    "Goal": ["목표", "계획", "방향", "비전"],
    "Pattern": ["패턴", "반복", "규칙", "관례"],
    "Framework": ["프레임워크", "구조", "아키텍처", "설계", "스키마"],
    "Project": ["프로젝트", "레포", "저장소"],
    "Connection": ["연결", "관계", "대응", "매핑"],
    "Narrative": ["서사", "맥락", "이야기", "세션 기록"],
}
```

**Step 2: 테스트 작성**

`tests/test_type_boost.py`:

```python
"""Type boost 키워드 감지 테스트."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import TYPE_KEYWORDS, TYPE_BOOST


def detect_type_hints(query: str) -> dict[str, float]:
    """쿼리에서 타입 힌트 감지 → {type: boost_score}."""
    hints = {}
    for node_type, keywords in TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in query:
                hints[node_type] = TYPE_BOOST
                break
    return hints


def test_workflow_detection():
    hints = detect_type_hints("워크플로우 자동화 절차")
    assert "Workflow" in hints


def test_failure_detection():
    hints = detect_type_hints("E14 배치 실패 원인")
    assert "Failure" in hints


def test_no_false_positive():
    hints = detect_type_hints("컨텍스트를 통화로 보는 원칙")
    assert "Workflow" not in hints
    assert "Failure" not in hints


def test_multiple_types():
    hints = detect_type_hints("에이전트 팀 구조 설계 프레임워크")
    assert "Agent" in hints
    assert "Framework" in hints
```

**Step 3: 테스트 실행 (실패 확인)**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests/test_type_boost.py -v
```

Expected: PASS (TYPE_KEYWORDS가 config.py에 이미 추가되었으므로 통과해야 함)

**Step 4: hybrid.py에 type boost 적용**

`storage/hybrid.py` 라인 445 근처, 기존 스코어 계산 루프 내부에 추가.

기존 코드 (L462-475):
```python
    qs = node.get("quality_score") or 0.0
    tr = node.get("temporal_relevance") or 0.0
    enrichment_bonus = (
        qs * ENRICHMENT_QUALITY_WEIGHT + tr * ENRICHMENT_TEMPORAL_WEIGHT
    )
    tier = node.get("tier", 2)
    tier_bonus = {0: 0.15, 1: 0.05, 2: 0.0}.get(tier, 0.0)
    node["score"] = scores[node_id] + enrichment_bonus + tier_bonus
    candidates.append(node)
```

변경 후:
```python
    qs = node.get("quality_score") or 0.0
    tr = node.get("temporal_relevance") or 0.0
    enrichment_bonus = (
        qs * ENRICHMENT_QUALITY_WEIGHT + tr * ENRICHMENT_TEMPORAL_WEIGHT
    )
    tier = node.get("tier", 2)
    tier_bonus = {0: 0.15, 1: 0.05, 2: 0.0}.get(tier, 0.0)
    # Layer A: type keyword boost
    type_boost = _type_hints.get(node.get("type", ""), 0.0)
    node["score"] = scores[node_id] + enrichment_bonus + tier_bonus + type_boost
    candidates.append(node)
```

`_type_hints`는 hybrid_search() 함수 상단에서 계산:
```python
def hybrid_search(query, type_filter="", project="", excluded_project="", top_k=DEFAULT_TOP_K, mode="auto"):
    # Layer A: detect type hints from query
    _type_hints = _detect_type_hints(query)
    ...
```

`_detect_type_hints` 함수를 hybrid.py 상단에 추가:
```python
from config import TYPE_KEYWORDS, TYPE_BOOST

def _detect_type_hints(query: str) -> dict[str, float]:
    """쿼리에서 타입 키워드 감지 → {type: boost}."""
    hints: dict[str, float] = {}
    for node_type, keywords in TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in query:
                hints[node_type] = TYPE_BOOST
                break
    return hints
```

**Step 5: 기존 테스트 통과 확인**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests/ -x -q
```

Expected: 153+ tests PASS

**Step 6: NDCG 측정 (Layer C + A 효과)**

```bash
PYTHONIOENCODING=utf-8 python scripts/eval/ab_test.py --k 18 --top-k 10
```

**Step 7: Commit**

```bash
git add config.py storage/hybrid.py tests/test_type_boost.py
git commit -m "[mcp-memory] Layer A: 키워드 기반 타입 부스트 (TYPE_BOOST=0.03)"
```

---

### Task 4: Layer D — 타입 다양성 보장

**Files:**
- Modify: `storage/hybrid.py:477-480` (결과 반환 직전에 diversity 적용)
- Create: `tests/test_type_diversity.py`

**Step 1: 테스트 작성**

`tests/test_type_diversity.py`:

```python
"""Type diversity re-ranking 테스트."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _apply_type_diversity(candidates: list[dict], top_k: int, max_same_type_ratio: float = 0.6) -> list[dict]:
    """타입 다양성 보장 re-ranking."""
    if len(candidates) <= top_k:
        return candidates

    top = candidates[:top_k]
    rest = candidates[top_k:]

    # 상위 결과의 타입 분포 확인
    type_counts: dict[str, int] = {}
    for c in top:
        t = c.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    max_allowed = max(1, int(top_k * max_same_type_ratio))

    # 초과 타입 교체
    for dominant_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        if count <= max_allowed:
            continue
        excess = count - max_allowed
        # top에서 dominant_type의 최하위 항목을 제거
        for _ in range(excess):
            for i in range(len(top) - 1, -1, -1):
                if top[i].get("type") == dominant_type:
                    removed = top.pop(i)
                    rest.insert(0, removed)
                    break
            # rest에서 다른 타입의 최상위 항목을 추가
            for j, r in enumerate(rest):
                if r.get("type") != dominant_type:
                    top.append(rest.pop(j))
                    break

    top.sort(key=lambda n: n.get("score", 0), reverse=True)
    return top[:top_k]


def test_diversity_breaks_monopoly():
    candidates = [
        {"id": i, "type": "Principle", "score": 1.0 - i * 0.01}
        for i in range(8)
    ] + [
        {"id": 100, "type": "Workflow", "score": 0.5},
        {"id": 101, "type": "Failure", "score": 0.4},
    ]
    result = _apply_type_diversity(candidates, top_k=5)
    types = [r["type"] for r in result]
    assert types.count("Principle") <= 3  # 60% of 5


def test_diversity_preserves_good_results():
    candidates = [
        {"id": 1, "type": "Principle", "score": 1.0},
        {"id": 2, "type": "Workflow", "score": 0.9},
        {"id": 3, "type": "Failure", "score": 0.8},
        {"id": 4, "type": "Pattern", "score": 0.7},
        {"id": 5, "type": "Tool", "score": 0.6},
    ]
    result = _apply_type_diversity(candidates, top_k=5)
    assert len(result) == 5
    # 이미 다양하므로 변경 없음
    assert result[0]["id"] == 1


def test_diversity_no_change_when_diverse():
    candidates = [
        {"id": i, "type": f"Type{i}", "score": 1.0 - i * 0.1}
        for i in range(10)
    ]
    result = _apply_type_diversity(candidates, top_k=5)
    assert [r["id"] for r in result] == [0, 1, 2, 3, 4]
```

**Step 2: 테스트 실행 (통과 확인 — 함수가 테스트 파일에 정의됨)**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests/test_type_diversity.py -v
```

**Step 3: hybrid.py에 diversity 적용**

`storage/hybrid.py`에 `_apply_type_diversity` 함수 추가하고, 라인 477-480을 수정:

기존:
```python
candidates.sort(key=lambda n: n["score"], reverse=True)
result = candidates[:top_k]
return result
```

변경:
```python
candidates.sort(key=lambda n: n["score"], reverse=True)
result = _apply_type_diversity(candidates, top_k)
return result
```

**Step 4: 전체 테스트 실행**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests/ -x -q
```

Expected: 155+ tests PASS (기존 153 + type_boost 4 + type_diversity 3)

**Step 5: NDCG 측정 (Layer C + A + D 효과)**

```bash
PYTHONIOENCODING=utf-8 python scripts/eval/ab_test.py --k 18 --top-k 10
```

Expected: NDCG@5 > 0.50 (corrected goldset 기준)

**Step 6: Commit**

```bash
git add storage/hybrid.py tests/test_type_diversity.py
git commit -m "[mcp-memory] Layer D: 타입 다양성 보장 (max_same_type_ratio=0.6)"
```

---

### Task 5: 검증 및 Living Docs

**Files:**
- Modify: `STATE.md`
- Modify: `CHANGELOG.md`
- Reference: `HOME.md` (dev-vault root)

**Step 1: 전체 검증 실행**

```bash
PYTHONIOENCODING=utf-8 python scripts/eval/verify.py
PYTHONIOENCODING=utf-8 python -m pytest tests/ -x -q
```

**Step 2: 최종 NDCG 비교 (before/after)**

```bash
# 교정된 goldset 기준
PYTHONIOENCODING=utf-8 python scripts/eval/ab_test.py --k 18 --top-k 10
```

기대 결과:
- NDCG@5: 0.44 → 0.55+ (corrected goldset, 전체 75q)
- q051-q075 NDCG@5: 0.60 → 0.75+

**Step 3: STATE.md 업데이트**

- Version: v2.2.0
- NDCG 점수 갱신
- v2.2.0 Changes 섹션 추가 (3-Layer type-aware search)

**Step 4: CHANGELOG.md 업데이트**

v2.2.0 항목 추가:
- Layer C: 타입 태그 재임베딩
- Layer A: 키워드 기반 타입 부스트
- Layer D: 타입 다양성 보장
- Goldset v2.1: L1 relevant_ids 교정

**Step 5: HOME.md 업데이트**

mcp-memory 행 갱신

**Step 6: Commit + Push**

```bash
git add STATE.md CHANGELOG.md
git commit -m "[mcp-memory] v2.2.0: 3-Layer type-aware search"
```

dev-vault:
```bash
cd /c/dev && git add HOME.md && git commit -m "[dev-vault] HOME.md — mcp-memory v2.2.0 반영"
```

---

## 성공 기준

| 메트릭 | Before (corrected) | Target | Method |
|--------|-------------------|--------|--------|
| 전체 NDCG@5 | 0.44 | ≥0.55 | Layer C+A+D |
| q051-q075 NDCG@5 | 0.60 | ≥0.75 | Layer C+A+D |
| Tests | 153 | ≥158 | +type_boost +diversity |
| Verification | 41 PASS | ≥41 PASS | 기존 유지 |

## 실행 순서

```
Task 1: Goldset 교정 적용 (3분)
Task 2: Layer C 재임베딩 (5분)
Task 3: Layer A 타입 부스트 (10분)
Task 4: Layer D 다양성 보장 (10분)
Task 5: 검증 + Living Docs (5분)
```
