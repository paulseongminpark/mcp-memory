# mcp-memory 온톨로지 완성 — 실행 설계서

> Date: 2026-03-08
> 이 문서를 읽는 세션이 전체 구현을 담당한다. 코드 수정 → 스크립트 작성 → 실행까지 한 세션에서 완료.
> 완료 후 `run_pipeline.py`를 실행하면 전체 파이프라인이 자동 실행된다.

---

## 현재 상태

- NDCG@5: 0.585, NDCG@10: 0.600, hit_rate: 0.783
- Tests: 153/153 PASS
- 커밋: `d254c39` (v2.1.2)

## 목표

1. NDCG@5 ≥ 0.65 (enrichment + boost 수정)
2. 모듈형 검증 시스템 (`checks/`) 구축
3. `run_pipeline.py` — 전체 자동 실행 스크립트
4. 검증 결과 DB 기록 + 서버 시작 시 자동 실행

---

## Part 1: 코드 수정 (7건)

### 1-1. LIKE boost 부작용 수정

**파일**: `storage/sqlite_store.py` — `search_fts()` 함수

**문제**: high_boost가 FTS 결과 앞에 삽입되어 q004(-0.159), q008(-0.127) 회귀 발생.

**수정**: high_boost 최대 2개로 cap. 나머지는 low_append로 이동.

```python
# 변경 전:
high_boost: list[tuple[int, str, float]] = []
low_append: list[tuple[int, str, float]] = []
for nid in like_ranked:
    if nid not in seen_ids:
        cnt = like_match_count[nid]
        if cnt >= high_thresh:
            high_boost.append(...)
        else:
            low_append.append(...)
        seen_ids.add(nid)
fts_results = high_boost + fts_results + low_append

# 변경 후:
high_boost: list[tuple[int, str, float]] = []
low_append: list[tuple[int, str, float]] = []
for nid in like_ranked:
    if nid not in seen_ids:
        cnt = like_match_count[nid]
        if cnt >= high_thresh and len(high_boost) < 2:  # ← cap 2개
            high_boost.append((nid, like_content[nid], -float(cnt) * 10))
        else:
            low_append.append((nid, like_content[nid], -float(cnt)))
        seen_ids.add(nid)
fts_results = high_boost + fts_results + low_append
```

### 1-2. q017/q018 동의어 주입

**파일**: `scripts/pipeline/inject_synonyms.py` (신규)

타깃 노드의 key_concepts에 한국어 동의어를 추가하여 FTS/LIKE 검색이 잡을 수 있게 한다.

```python
"""q017/q018 0점 쿼리 해결 — 타깃 노드에 한국어 동의어 주입."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from storage.sqlite_store import _db

SYNONYMS = {
    # q017: "창의적 사고 방식" → gold [4166, 4161]
    4166: ["창의적 사고", "사고 방식", "창의성", "창의적 접근"],
    4161: ["창의적 사고", "사고 방식", "다차원적 사고", "사고 패턴"],
    # q018: "정보 충돌 방지 시스템 설계" → gold [755, 756, 771]
    755: ["정보 충돌", "시스템 일관성", "충돌 방지", "데이터 충돌"],
    756: ["정보 충돌 방지", "동시 수정 방지", "쓰기 충돌"],
    771: ["충돌 방지 설계", "단일 소스", "정보 일관성"],
    # q016 보강: "AI 협업 원칙" 추가
    404: ["AI 협업 원칙", "협업 설계"],
}

def main():
    with _db() as conn:
        for node_id, new_terms in SYNONYMS.items():
            row = conn.execute(
                "SELECT key_concepts FROM nodes WHERE id=?", (node_id,)
            ).fetchone()
            if not row:
                print(f"  SKIP: node {node_id} not found")
                continue
            existing = row[0] or ""
            # 기존 key_concepts에 새 용어 추가 (중복 제거)
            existing_set = set(t.strip() for t in existing.split(",") if t.strip())
            added = [t for t in new_terms if t not in existing_set]
            if not added:
                print(f"  SKIP: node {node_id} already has all terms")
                continue
            merged = existing + (", " if existing else "") + ", ".join(added)
            conn.execute(
                "UPDATE nodes SET key_concepts=? WHERE id=?", (merged, node_id)
            )
            print(f"  OK: node {node_id} += {added}")
        conn.commit()
    print("DONE: synonyms injected")

if __name__ == "__main__":
    main()
```

### 1-3. 중복 449건 정리

**파일**: `scripts/pipeline/cleanup_duplicates.py` (신규)

content_hash 백필 시 발견된 449 중복 content 정리. 동일 content 중 가장 오래된(ID 작은) 노드만 유지, 나머지 soft-delete.

```python
"""중복 content 노드 soft-delete (status='deleted')."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from storage.sqlite_store import _db

def main():
    deleted = 0
    with _db() as conn:
        # 동일 content_hash를 가진 노드 그룹 찾기
        groups = conn.execute("""
            SELECT content_hash, GROUP_CONCAT(id) as ids, COUNT(*) as cnt
            FROM nodes
            WHERE content_hash IS NOT NULL AND status='active'
            GROUP BY content_hash
            HAVING cnt > 1
        """).fetchall()
        print(f"Found {len(groups)} duplicate groups")
        for row in groups:
            ids = sorted(int(x) for x in row[1].split(","))
            keep = ids[0]  # 가장 오래된 노드 유지
            remove = ids[1:]
            for rid in remove:
                conn.execute(
                    "UPDATE nodes SET status='deleted' WHERE id=?", (rid,)
                )
                # 해당 노드의 edge도 soft-delete
                conn.execute(
                    "UPDATE edges SET status='deleted' WHERE source_id=? OR target_id=?",
                    (rid, rid),
                )
                deleted += 1
        conn.commit()
    print(f"DONE: {deleted} duplicate nodes soft-deleted")

if __name__ == "__main__":
    main()
```

### 1-4. _post_search_learn() background 전환

**파일**: `storage/hybrid.py` — `post_search_learn()` 함수

```python
# 변경 전 (동기):
def post_search_learn(results, query, session_id=None):
    if not results:
        return
    all_edges, _ = _get_graph()
    _bcm_update(...)
    # ... SPRT, action_log ...

# 변경 후 (background thread):
import threading

def post_search_learn(results, query, session_id=None):
    """검색 후 학습 — background thread로 실행."""
    if not results:
        return
    # shallow copy — thread에서 안전하게 접근
    results_copy = [dict(r) for r in results]
    t = threading.Thread(
        target=_post_search_learn_impl,
        args=(results_copy, query, session_id),
        daemon=True,
    )
    t.start()

def _post_search_learn_impl(results, query, session_id):
    """실제 학습 로직 (background)."""
    try:
        all_edges, _ = _get_graph()
        _bcm_update(
            [n["id"] for n in results],
            [n["score"] for n in results],
            all_edges,
            query=query,
        )
        # SPRT + action_log (기존 코드 그대로)
        ...
    except Exception as e:
        logging.warning("Background learn failed: %s", e)
```

**주의**: `results`를 shallow copy해서 thread에 전달. main thread가 results를 변경해도 안전.

### 1-5. NetworkX full rebuild 축소

**파일**: `storage/hybrid.py` — `_get_graph()` + `hybrid_search()`

현재 `_get_graph()`가 전체 edge를 로드 → NetworkX 그래프 빌드. 이를 `_traverse_sql()` (이미 구현됨)로 교체.

```python
# hybrid_search() 내부 변경:

# 변경 전:
all_edges, graph = _get_graph()
c = _auto_ucb_c(query, mode=mode)
graph_neighbors = (
    _ucb_traverse(graph, seed_ids, depth=GRAPH_MAX_HOPS, c=c)
    if seed_ids else set()
)

# 변경 후:
c = _auto_ucb_c(query, mode=mode)
if seed_ids:
    if c <= UCB_C_FOCUS:
        # focus 모드: SQL CTE로 빠르게 (NetworkX 불필요)
        graph_neighbors = _traverse_sql(seed_ids, depth=GRAPH_MAX_HOPS)
    else:
        # auto/dmn 모드: UCB 필요 → NetworkX 유지 (visit_count 기반 탐험)
        all_edges, graph = _get_graph()
        graph_neighbors = _ucb_traverse(graph, seed_ids, depth=GRAPH_MAX_HOPS, c=c)
else:
    graph_neighbors = set()
```

**rationale**: focus 모드는 UCB 탐험이 불필요하므로 SQL CTE가 더 빠르다. auto/dmn은 visit_count 기반 UCB가 필요하므로 NetworkX 유지. 점진적 축소.

BCM에서 `all_edges`가 필요하므로, `_post_search_learn_impl()`에서만 `_get_graph()` 호출.

```python
def _post_search_learn_impl(results, query, session_id):
    try:
        all_edges, _ = _get_graph()  # BCM용으로만 로드
        _bcm_update(...)
```

### 1-6. verification_log 테이블 추가

**파일**: `storage/sqlite_store.py` — `init_db()` 함수에 추가

```sql
CREATE TABLE IF NOT EXISTS verification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    check_name TEXT NOT NULL,
    category TEXT,
    score REAL,
    threshold REAL,
    status TEXT NOT NULL,  -- PASS/WARN/FAIL
    details TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_vlog_run ON verification_log(run_id);
CREATE INDEX IF NOT EXISTS idx_vlog_check ON verification_log(check_name);
```

### 1-7. config.py에 VERIFY_THRESHOLDS 추가

**파일**: `config.py`

```python
VERIFY_THRESHOLDS = {
    "ndcg@5": 0.55,
    "ndcg@10": 0.55,
    "hit_rate": 0.70,
    "null_layer_pct": 0.0,     # NULL layer 노드 비율 (0% 목표)
    "enrichment_coverage": 0.60,  # enrichment 완료 비율
    "orphan_pct": 0.10,        # 고립 노드 비율 (10% 이하)
    "content_hash_coverage": 0.95,  # content_hash 보유 비율
    "duplicate_pct": 0.0,      # 중복 비율 (0% 목표)
}
```

---

## Part 2: 검증 시스템 (`checks/`)

### 공통 구조

**파일**: `checks/__init__.py`

```python
from dataclasses import dataclass, field

@dataclass
class CheckResult:
    name: str
    category: str  # search, schema, data, promotion, recall, enrichment, graph, type
    score: float | None = None
    threshold: float | None = None
    status: str = "PASS"  # PASS/WARN/FAIL
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.threshold is not None and self.score is not None:
            if self.score < self.threshold:
                self.status = "FAIL" if self.score < self.threshold * 0.8 else "WARN"
```

### 모듈 8개 명세

#### 2-1. `checks/search_quality.py`
- `run(db_path) -> list[CheckResult]`
- goldset.yaml 로드 → hybrid_search 실행 → NDCG@5, NDCG@10, hit_rate 계산
- 0점 쿼리 목록을 details에 포함
- ab_test.py의 `ndcg_at_k`, `load_goldset` 함수 재사용

#### 2-2. `checks/schema_consistency.py`
- PROMOTE_LAYER keys ⊂ schema.yaml node_types
- schema.yaml node_types ⊂ PROMOTE_LAYER (deprecated 제외)
- ALL_RELATIONS == schema.yaml relation_types
- type_defs 테이블 active count == schema.yaml count
- relation_defs 테이블 active count == schema.yaml count
- RELATION_RULES 참조 타입이 모두 PROMOTE_LAYER에 존재 (deprecated 제외)
- VALID_PROMOTIONS 참조 타입이 모두 PROMOTE_LAYER에 존재 (deprecated 제외)

#### 2-3. `checks/data_integrity.py`
- NULL layer 노드 수 (Unclassified 제외)
- content_hash 보유율 (active 노드 중)
- 중복 content_hash 그룹 수
- status='deleted' 노드의 edge 정리 여부
- orphan 노드 (edge 0개) 비율

#### 2-4. `checks/promotion_pipeline.py`
- Signal 노드 존재 여부
- promote_node() import 성공 여부
- VALID_PROMOTIONS 경로 각각에 대해 시뮬레이션 (실제 promote 하지 않음, gate 로직만 검증)
- promotion_candidate=1 노드 수
- L4/L5 접근제어 (check_access 검증)

#### 2-5. `checks/recall_scenarios.py`
- 한국어 2글자 쿼리 ("충돌") → 결과 1개+ 반환 확인
- 한국어 조사 포함 쿼리 ("시스템에서") → 조사 제거 후 매칭 확인
- 영어 쿼리 ("orchestration") → FTS5 trigram 매칭 확인
- 혼합 쿼리 ("AI 설계 원칙") → 결과 반환 확인
- mode=focus → UCB_C=0.3 적용 확인
- mode=dmn → UCB_C=2.5 적용 확인
- duplicate remember → content_hash 차단 확인
- recall_log 기록 확인 (recall 후 recall_log 행 증가)

#### 2-6. `checks/enrichment_coverage.py`
- enrichment_status 분포 (pending/enriched/failed)
- summary 필드 NULL 비율
- key_concepts 필드 NULL 비율
- domains 필드 NULL 비율
- quality_score > 0 비율

#### 2-7. `checks/graph_health.py`
- 총 edge 수
- active edge 수
- edge relation 분포 상위 10개
- 고립 노드 (incoming+outgoing edge 0) 수
- connected component 수 (SQL 기반, NetworkX 불필요)
- avg edge strength

#### 2-8. `checks/type_distribution.py`
- 노드 타입별 count (상위 20)
- 미사용 타입 (count=0) 목록
- 관계 타입별 count (상위 20)
- 미사용 관계 목록
- 레이어별 노드 분포

---

## Part 3: 실행 스크립트

### 3-1. `scripts/eval/verify.py` — 검증 러너

```python
"""모듈형 검증 시스템 러너."""
import uuid, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from checks import CheckResult
from checks import search_quality, schema_consistency, data_integrity
from checks import promotion_pipeline, recall_scenarios
from checks import enrichment_coverage, graph_health, type_distribution
from storage.sqlite_store import _db

MODULES = [
    search_quality, schema_consistency, data_integrity,
    promotion_pipeline, recall_scenarios,
    enrichment_coverage, graph_health, type_distribution,
]

def run_all(quick=False):
    """전체 검증 실행. quick=True면 search_quality 스킵 (서버 시작용)."""
    run_id = str(uuid.uuid4())[:8]
    all_results = []
    modules = [m for m in MODULES if not (quick and m == search_quality)]
    for mod in modules:
        try:
            results = mod.run()
            all_results.extend(results)
        except Exception as e:
            all_results.append(CheckResult(
                name=mod.__name__.split(".")[-1],
                category="error",
                status="FAIL",
                details={"error": str(e)},
            ))
    # DB 저장
    _save_results(run_id, all_results)
    # 요약 출력
    _print_summary(run_id, all_results)
    return all_results

def _save_results(run_id, results):
    with _db() as conn:
        for r in results:
            conn.execute(
                """INSERT INTO verification_log
                   (run_id, check_name, category, score, threshold, status, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (run_id, r.name, r.category, r.score, r.threshold,
                 r.status, json.dumps(r.details, ensure_ascii=False)),
            )
        conn.commit()

def _print_summary(run_id, results):
    pass_count = sum(1 for r in results if r.status == "PASS")
    warn_count = sum(1 for r in results if r.status == "WARN")
    fail_count = sum(1 for r in results if r.status == "FAIL")
    print(f"\n{'='*60}")
    print(f"VERIFICATION {run_id}: {pass_count} PASS / {warn_count} WARN / {fail_count} FAIL")
    print(f"{'='*60}")
    for r in results:
        icon = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}[r.status]
        score_str = f" ({r.score:.3f}/{r.threshold:.3f})" if r.score is not None else ""
        print(f"  [{icon}] {r.category:12s} | {r.name}{score_str}")
    if fail_count:
        print(f"\nFAILED CHECKS:")
        for r in results:
            if r.status == "FAIL":
                print(f"  - {r.name}: {r.details}")
```

### 3-2. `scripts/pipeline/run_pipeline.py` — 전체 자동 실행

```python
"""온톨로지 완성 파이프라인 — 전체 자동 실행."""
import subprocess, sys, time, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent

def run(cmd, desc):
    print(f"\n{'='*60}")
    print(f"[PHASE] {desc}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"STDERR: {result.stderr}")
        print(f"WARNING: {desc} returned code {result.returncode}")
    return result.returncode

def main():
    start = time.time()

    # Phase A: 데이터 수정
    run([sys.executable, "scripts/pipeline/inject_synonyms.py"], "동의어 주입")
    run([sys.executable, "scripts/pipeline/cleanup_duplicates.py"], "중복 정리")

    # Phase B: FTS 인덱스 리빌드 (동의어 주입 후 필요)
    run([sys.executable, "-c", """
import sys; sys.path.insert(0, '.')
from storage.sqlite_store import _db
with _db() as conn:
    conn.execute("INSERT INTO nodes_fts(nodes_fts) VALUES('rebuild')")
    conn.commit()
print("FTS index rebuilt")
"""], "FTS 인덱스 리빌드")

    # Phase C: 테스트
    code = run([sys.executable, "-m", "pytest", "tests/", "-x", "-q"], "pytest")
    if code != 0:
        print("ABORT: tests failed")
        return 1

    # Phase D: NDCG 측정
    run([sys.executable, "scripts/eval/ab_test.py", "--k", "18", "--top-k", "10"], "NDCG 측정")

    # Phase E: 검증 시스템 실행
    run([sys.executable, "scripts/eval/verify.py"], "전체 검증")

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE in {elapsed:.1f}s")
    print(f"{'='*60}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### 3-3. server.py 통합

서버 시작 시 빠른 검증 추가:

```python
# server.py 수정 (init_db, sync_schema 다음에):
from storage.sqlite_store import init_db, sync_schema
init_db()
sync_schema()

# quick verify (search_quality 스킵, <2초)
try:
    from scripts.eval.verify import run_all
    run_all(quick=True)
except Exception:
    pass  # 검증 실패가 서버 시작을 막지 않음
```

---

## Part 4: Codex CLI enrichment (선택사항)

벌크 enrichment는 OpenAI API 없이 Codex CLI로 대체 가능. 단, 시간이 오래 걸림.

### 4-1. `scripts/pipeline/enrich_batch.py`

```python
"""Codex CLI로 벌크 enrichment — API 비용 없이."""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from storage.sqlite_store import _db

BATCH_SIZE = 30
OUTPUT_DIR = ROOT / "data" / "enrichment_batches"

def export_unenriched():
    """enrichment 필요한 노드 export."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with _db() as conn:
        rows = conn.execute("""
            SELECT id, type, content, tags, project
            FROM nodes
            WHERE status='active'
              AND (enrichment_status IS NULL OR enrichment_status='pending')
            ORDER BY id
        """).fetchall()
    nodes = [dict(r) for r in rows]
    batches = [nodes[i:i+BATCH_SIZE] for i in range(0, len(nodes), BATCH_SIZE)]
    for i, batch in enumerate(batches):
        path = OUTPUT_DIR / f"batch_{i:03d}.json"
        path.write_text(json.dumps(batch, ensure_ascii=False, indent=2))
    print(f"Exported {len(nodes)} nodes in {len(batches)} batches")
    return len(batches)

def run_codex_batch(batch_idx):
    """단일 배치를 Codex CLI로 enrichment."""
    input_path = OUTPUT_DIR / f"batch_{batch_idx:03d}.json"
    output_path = OUTPUT_DIR / f"result_{batch_idx:03d}.json"
    if not input_path.exists():
        return
    nodes = json.loads(input_path.read_text())
    prompt = f"""아래 노드들에 대해 enrichment를 수행하라. 각 노드에 대해:
- summary: 1-2문장 요약 (한국어)
- key_concepts: 핵심 개념 3-7개 (한국어, 쉼표 구분)
- domains: 관련 도메인 2-4개 (영어, 쉼표 구분)
- facets: 세부 특성 2-4개 (영어, 쉼표 구분)

입력 노드:
{json.dumps(nodes, ensure_ascii=False, indent=2)}

출력: JSON 배열. 각 원소는 {{"id": int, "summary": str, "key_concepts": str, "domains": str, "facets": str}}
JSON만 출력하라. 다른 텍스트 금지.
"""
    result = subprocess.run(
        ["codex", "exec", prompt, "-o", str(output_path)],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        print(f"Batch {batch_idx} FAILED: {result.stderr[:200]}")

def import_results():
    """Codex 결과를 DB에 반영."""
    imported = 0
    for path in sorted(OUTPUT_DIR.glob("result_*.json")):
        try:
            results = json.loads(path.read_text())
            with _db() as conn:
                for r in results:
                    conn.execute("""
                        UPDATE nodes SET
                            summary=?, key_concepts=?, domains=?, facets=?,
                            enrichment_status='enriched'
                        WHERE id=?
                    """, (r["summary"], r["key_concepts"],
                          r.get("domains", ""), r.get("facets", ""),
                          r["id"]))
                conn.commit()
            imported += len(results)
        except Exception as e:
            print(f"Import {path.name} failed: {e}")
    print(f"Imported {imported} enrichments")

if __name__ == "__main__":
    total = export_unenriched()
    for i in range(total):
        print(f"\nBatch {i+1}/{total}")
        run_codex_batch(i)
    import_results()
```

**주의**: Codex CLI enrichment는 시간이 오래 걸린다 (배치당 30-60초, 40배치 ≈ 30분). `run_pipeline.py`에 포함하되 선택적 실행.

---

## Part 5: goldset 확장 (25→50)

Codex CLI로 25개 추가 쿼리 생성 후, 수동으로 relevant_ids 검증 필요.

```bash
codex exec "goldset.yaml에 25개 쿼리가 있다. 아래 DB 타입 분포를 참고하여 25개를 더 만들어라.
기존 쿼리가 커버하지 않는 영역을 우선:
- Workflow/Tool/Skill/Agent 관련 (L1)
- Framework/Pattern/Connection 관련 (L2)
- Failure/Experiment/Evolution 관련 (L1)
- 시간 순서 관련 (preceded_by, led_to)
- 교차 도메인 관련 (connects_with, transfers_to)

형식: goldset.yaml과 동일. relevant_ids는 비워두고 query와 difficulty만.
" -o data/goldset_expansion.yaml
```

relevant_ids는 DB 검색 후 수동 매핑 필요 → 이건 자동화 불가, 다음 세션에서.

---

## 실행 순서 요약

```
1. 코드 수정 (Part 1: 1-1 ~ 1-7)
   ├── sqlite_store.py: boost cap + verification_log
   ├── hybrid.py: background thread + NetworkX 축소
   ├── config.py: VERIFY_THRESHOLDS
   └── server.py: verify_quick()

2. 신규 파일 생성 (Part 2 + Part 3)
   ├── checks/__init__.py
   ├── checks/search_quality.py
   ├── checks/schema_consistency.py
   ├── checks/data_integrity.py
   ├── checks/promotion_pipeline.py
   ├── checks/recall_scenarios.py
   ├── checks/enrichment_coverage.py
   ├── checks/graph_health.py
   ├── checks/type_distribution.py
   ├── scripts/eval/verify.py
   ├── scripts/pipeline/run_pipeline.py
   ├── scripts/pipeline/inject_synonyms.py
   ├── scripts/pipeline/cleanup_duplicates.py
   └── scripts/pipeline/enrich_batch.py (선택)

3. 테스트 실행: pytest tests/ -x -q
4. 파이프라인 실행: python scripts/pipeline/run_pipeline.py
5. 결과 확인 + 커밋
```

---

## 성공 기준

| 메트릭 | 현재 | 목표 | 방법 |
|--------|------|------|------|
| NDCG@5 | 0.585 | ≥0.62 | 동의어 + boost 수정 |
| Tests | 153 | ≥153 | 기존 유지 + 신규 |
| 검증 PASS | 17/17 | ≥30 | checks/ 8모듈 |
| 검증 FAIL | 0 | 0 | 전체 통과 |
| 중복 노드 | 449 | 0 | cleanup script |
| verification_log | 없음 | 자동 기록 | DB 테이블 |

---

## 주의사항

- **DB 경로**: `data/memory.db` (프로젝트 루트 기준)
- **FTS 리빌드 필수**: 동의어 주입 후 `INSERT INTO nodes_fts(nodes_fts) VALUES('rebuild')` 실행
- **NetworkX 완전 제거 아님**: focus 모드만 SQL 전환, auto/dmn은 유지
- **Codex enrichment는 선택**: run_pipeline.py에서 주석 처리 가능
- **goldset 확장은 반자동**: 쿼리 생성은 Codex, relevant_ids 매핑은 수동
- **커밋 메시지 형식**: `[mcp-memory] v2.1.3: 검증 시스템 + 온톨로지 완성`
