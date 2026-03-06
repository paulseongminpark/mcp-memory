# 심화 5: type_defs + relation_defs 실제 마이그레이션 SQL

> A-1(Palantir) + A-4(버전관리) + A-11(빼기 데이터) 기반
> 현재 DB: 3,230 nodes (31개 활성 타입), 6,020 edges (48개 정의 관계)

---

## Step 1: 메타 테이블 생성

```sql
-- sqlite_store.py init_db() 또는 별도 마이그레이션 스크립트에서 실행

-- 타입 정의 메타 테이블
CREATE TABLE IF NOT EXISTS type_defs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    layer INTEGER NOT NULL,
    super_type TEXT,
    description TEXT,
    status TEXT DEFAULT 'active',      -- active | deprecated | archived
    rank TEXT DEFAULT 'normal',        -- normal | preferred | deprecated
    deprecated_reason TEXT,
    replaced_by TEXT,
    deprecated_at TEXT,
    version INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 관계 정의 메타 테이블
CREATE TABLE IF NOT EXISTS relation_defs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT,                      -- causal, structural, semantic 등
    direction_constraint TEXT,          -- upward | downward | horizontal | any
    layer_constraint TEXT,              -- cross-layer | same-layer | any
    reverse_of TEXT,                    -- 역방향 관계명 (있으면)
    status TEXT DEFAULT 'active',
    rank TEXT DEFAULT 'normal',
    deprecated_reason TEXT,
    replaced_by TEXT,
    deprecated_at TEXT,
    version INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 온톨로지 스냅샷 (분기별)
CREATE TABLE IF NOT EXISTS ontology_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_tag TEXT UNIQUE NOT NULL,
    type_defs_json TEXT,
    relation_defs_json TEXT,
    change_summary TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_type_defs_status ON type_defs(status);
CREATE INDEX IF NOT EXISTS idx_type_defs_super ON type_defs(super_type);
CREATE INDEX IF NOT EXISTS idx_relation_defs_status ON relation_defs(status);
CREATE INDEX IF NOT EXISTS idx_relation_defs_category ON relation_defs(category);
```

---

## Step 2: 31개 활성 타입 INSERT (schema.yaml + PROMOTE_LAYER 기반)

```sql
-- 타임스탬프 변수 (실행 시 Python에서 주입)
-- now = datetime.now(timezone.utc).isoformat()

INSERT INTO type_defs (name, layer, super_type, description, status, rank, created_at, updated_at) VALUES
-- Tier A (100+ 노드, 핵심 13개)
('Workflow',       1, 'System',     '반복적 작업 흐름/프로세스',         'active', 'preferred', '{now}', '{now}'),
('Insight',        2, 'Concept',    '관찰에서 도출된 통찰',              'active', 'preferred', '{now}', '{now}'),
('Principle',      3, 'Identity',   '행동/판단의 기준이 되는 원칙',      'active', 'preferred', '{now}', '{now}'),
('Decision',       1, 'Action',     '선택과 그 근거',                   'active', 'preferred', '{now}', '{now}'),
('Narrative',      0, 'Experience', '경험의 서사적 기록',                'active', 'normal',    '{now}', '{now}'),
('Tool',           1, 'System',     '사용하는 도구/소프트웨어',          'active', 'normal',    '{now}', '{now}'),
('Framework',      2, 'Concept',    '체계적 사고/분석 틀',              'active', 'preferred', '{now}', '{now}'),
('Skill',          1, 'System',     '습득한 기술/능력',                 'active', 'normal',    '{now}', '{now}'),
('Project',        1, 'System',     '진행 중인 프로젝트',               'active', 'normal',    '{now}', '{now}'),
('Goal',           1, 'System',     '달성하고자 하는 목표',             'active', 'normal',    '{now}', '{now}'),
('Agent',          1, 'System',     'AI 에이전트/자동화 구성요소',       'active', 'normal',    '{now}', '{now}'),
('Pattern',        2, 'Concept',    '반복적으로 관찰되는 구조',          'active', 'preferred', '{now}', '{now}'),
('SystemVersion',  1, 'System',     '시스템/도구의 버전 기록',           'active', 'normal',    '{now}', '{now}'),

-- Tier B (10-100 노드, 보조 11개)
('Conversation',   0, 'Experience', '대화/세션 맥락 기록',              'active', 'normal',    '{now}', '{now}'),
('Failure',        1, 'Action',     '실패와 그 원인',                   'active', 'normal',    '{now}', '{now}'),
('Experiment',     1, 'Action',     '실험과 결과',                      'active', 'normal',    '{now}', '{now}'),
('Breakthrough',   1, 'Action',     '돌파구/중요한 발견',               'active', 'normal',    '{now}', '{now}'),
('Identity',       3, 'Identity',   '정체성 관련 기록',                 'active', 'normal',    '{now}', '{now}'),
('Unclassified',   NULL, NULL,      '미분류 노드 (메타)',               'active', 'normal',    '{now}', '{now}'),
('Evolution',      1, 'Action',     '시간에 따른 변화 기록',             'active', 'normal',    '{now}', '{now}'),
('Connection',     2, 'Concept',    '개념 간 연결/접합',                'active', 'normal',    '{now}', '{now}'),
('Tension',        2, 'Concept',    '상충하는 관점/긴장',               'active', 'normal',    '{now}', '{now}'),
('Question',       1, 'Signal',     '탐구해야 할 질문',                 'active', 'normal',    '{now}', '{now}'),
('Observation',    0, 'Experience', '관찰/원시 데이터',                 'active', 'normal',    '{now}', '{now}'),

-- Tier C (1-10 노드, 소수 7개 — L4/L5 포함)
('Preference',     0, 'Experience', '선호/취향',                        'active', 'normal',    '{now}', '{now}'),
('Signal',         1, 'Signal',     '아직 패턴이 안 된 관찰 신호',      'active', 'normal',    '{now}', '{now}'),
('AntiPattern',    1, 'Signal',     '피해야 할 반복 패턴',              'active', 'normal',    '{now}', '{now}'),
('Value',          4, 'Worldview',  '핵심 가치관',                      'active', 'preferred', '{now}', '{now}'),
('Philosophy',     4, 'Worldview',  '세계관/철학적 입장',               'active', 'preferred', '{now}', '{now}'),
('Belief',         4, 'Worldview',  '핵심 믿음',                        'active', 'preferred', '{now}', '{now}'),
('Axiom',          5, 'Axiom',      '근본 공리/자명한 전제',             'active', 'preferred', '{now}', '{now}');
```

---

## Step 3: 19개 미사용 타입 deprecated INSERT (A-11 replaced_by 매핑)

```sql
INSERT INTO type_defs (name, layer, super_type, description, status, rank, deprecated_reason, replaced_by, deprecated_at, created_at, updated_at) VALUES
-- L0
('Evidence',      0, 'Experience', '근거/증거',               'deprecated', 'deprecated', 'No instances since creation', 'Observation',   '{now}', '{now}', '{now}'),
('Trigger',       0, 'Experience', '트리거/촉발 요인',         'deprecated', 'deprecated', 'No instances since creation', 'Signal',        '{now}', '{now}', '{now}'),
('Context',       0, 'Experience', '맥락 정보',               'deprecated', 'deprecated', 'No instances since creation', 'Conversation',  '{now}', '{now}', '{now}'),

-- L1
('Plan',          1, 'System',     '계획/실행 방안',           'deprecated', 'deprecated', 'No instances since creation', 'Goal',          '{now}', '{now}', '{now}'),
('Ritual',        1, 'System',     '반복적 의식/루틴',         'deprecated', 'deprecated', 'No instances since creation', 'Workflow',      '{now}', '{now}', '{now}'),
('Constraint',    1, 'System',     '제약 조건',               'deprecated', 'deprecated', 'No instances since creation', 'Principle',     '{now}', '{now}', '{now}'),
('Assumption',    1, 'Action',     '가정/전제',               'deprecated', 'deprecated', 'No instances since creation', 'Belief',        '{now}', '{now}', '{now}'),

-- L2
('Heuristic',     2, 'Concept',    '경험 법칙',               'deprecated', 'deprecated', 'No instances since creation', 'Pattern',       '{now}', '{now}', '{now}'),
('Trade-off',     2, 'Concept',    '트레이드오프',             'deprecated', 'deprecated', 'No instances since creation', 'Tension',       '{now}', '{now}', '{now}'),
('Metaphor',      2, 'Concept',    '비유/은유',               'deprecated', 'deprecated', 'No instances since creation', 'Connection',    '{now}', '{now}', '{now}'),
('Concept',       2, 'Concept',    '일반 개념',               'deprecated', 'deprecated', 'No instances since creation', 'Insight',       '{now}', '{now}', '{now}'),

-- L3
('Boundary',      3, 'Identity',   '경계/한계',               'deprecated', 'deprecated', 'No instances since creation', 'Principle',     '{now}', '{now}', '{now}'),
('Vision',        3, 'Identity',   '비전/지향점',             'deprecated', 'deprecated', 'No instances since creation', 'Goal',          '{now}', '{now}', '{now}'),
('Paradox',       3, 'Identity',   '역설/모순',               'deprecated', 'deprecated', 'No instances since creation', 'Tension',       '{now}', '{now}', '{now}'),
('Commitment',    3, 'Identity',   '약속/헌신',               'deprecated', 'deprecated', 'No instances since creation', 'Decision',      '{now}', '{now}', '{now}'),

-- L4
('Mental Model',  4, 'Worldview',  '멘탈 모델',               'deprecated', 'deprecated', 'No instances since creation', 'Framework',     '{now}', '{now}', '{now}'),
('Lens',          4, 'Worldview',  '관점/시각',               'deprecated', 'deprecated', 'No instances since creation', 'Framework',     '{now}', '{now}', '{now}'),

-- L5
('Wonder',        5, 'Axiom',      '경이/경탄',               'deprecated', 'deprecated', 'No instances since creation', 'Question',      '{now}', '{now}', '{now}'),
('Aporia',        5, 'Axiom',      '아포리아/해결 불가',       'deprecated', 'deprecated', 'No instances since creation', 'Question',      '{now}', '{now}', '{now}');
```

---

## Step 4: 48개 관계 INSERT (config.py RELATION_TYPES 기반)

```sql
INSERT INTO relation_defs (name, category, direction_constraint, layer_constraint, reverse_of, status, rank, created_at, updated_at) VALUES
-- causal (8개)
('caused_by',       'causal',       'any',        'any',         'resulted_in',    'active', 'normal',    '{now}', '{now}'),
('led_to',          'causal',       'any',        'any',         'triggered_by',   'active', 'preferred', '{now}', '{now}'),
('triggered_by',    'causal',       'any',        'any',         'led_to',         'active', 'normal',    '{now}', '{now}'),
('resulted_in',     'causal',       'any',        'any',         'caused_by',      'active', 'normal',    '{now}', '{now}'),
('resolved_by',     'causal',       'any',        'any',         NULL,             'active', 'normal',    '{now}', '{now}'),
('prevented_by',    'causal',       'any',        'any',         NULL,             'active', 'normal',    '{now}', '{now}'),
('enabled_by',      'causal',       'any',        'any',         NULL,             'active', 'preferred', '{now}', '{now}'),
('blocked_by',      'causal',       'any',        'any',         NULL,             'active', 'normal',    '{now}', '{now}'),

-- structural (8개)
('part_of',          'structural',  'any',        'any',         'contains',       'active', 'preferred', '{now}', '{now}'),
('composed_of',      'structural',  'any',        'any',         NULL,             'active', 'normal',    '{now}', '{now}'),
('extends',          'structural',  'any',        'any',         'derived_from',   'active', 'normal',    '{now}', '{now}'),
('governed_by',      'structural',  'downward',   'any',         'governs',        'active', 'normal',    '{now}', '{now}'),
('instantiated_as',  'structural',  'downward',   'cross-layer', NULL,             'active', 'preferred', '{now}', '{now}'),
('expressed_as',     'structural',  'downward',   'cross-layer', NULL,             'active', 'preferred', '{now}', '{now}'),
('contains',         'structural',  'any',        'any',         'part_of',        'active', 'normal',    '{now}', '{now}'),
('derived_from',     'structural',  'any',        'any',         'extends',        'active', 'normal',    '{now}', '{now}'),

-- layer_movement (6개)
('realized_as',        'layer_movement', 'upward',   'cross-layer', 'abstracted_from', 'active', 'normal',    '{now}', '{now}'),
('crystallized_into',  'layer_movement', 'upward',   'cross-layer', NULL,              'active', 'preferred', '{now}', '{now}'),
('abstracted_from',    'layer_movement', 'downward', 'cross-layer', 'realized_as',     'active', 'normal',    '{now}', '{now}'),
('generalizes_to',     'layer_movement', 'upward',   'cross-layer', NULL,              'active', 'preferred', '{now}', '{now}'),
('constrains',         'layer_movement', 'any',      'any',         NULL,              'active', 'normal',    '{now}', '{now}'),
('generates',          'layer_movement', 'any',      'any',         NULL,              'active', 'normal',    '{now}', '{now}'),

-- diff_tracking (4개)
('differs_in',     'diff_tracking', 'horizontal', 'same-layer', NULL,             'active', 'normal',    '{now}', '{now}'),
('variation_of',   'diff_tracking', 'horizontal', 'same-layer', NULL,             'active', 'normal',    '{now}', '{now}'),
('evolved_from',   'diff_tracking', 'any',        'any',        'succeeded_by',   'active', 'normal',    '{now}', '{now}'),
('succeeded_by',   'diff_tracking', 'any',        'any',        'evolved_from',   'active', 'normal',    '{now}', '{now}'),

-- semantic (8개)
('supports',              'semantic', 'any',        'any', 'contradicts',   'active', 'preferred', '{now}', '{now}'),
('contradicts',           'semantic', 'any',        'any', 'supports',      'active', 'normal',    '{now}', '{now}'),
('analogous_to',          'semantic', 'horizontal', 'any', NULL,            'active', 'normal',    '{now}', '{now}'),
('parallel_with',         'semantic', 'horizontal', 'any', NULL,            'active', 'normal',    '{now}', '{now}'),
('reinforces_mutually',   'semantic', 'horizontal', 'any', NULL,            'active', 'normal',    '{now}', '{now}'),
('connects_with',         'semantic', 'any',        'any', NULL,            'active', 'normal',    '{now}', '{now}'),
('inspired_by',           'semantic', 'any',        'any', NULL,            'active', 'normal',    '{now}', '{now}'),
('exemplifies',           'semantic', 'any',        'any', NULL,            'active', 'normal',    '{now}', '{now}'),

-- perspective (4개)
('viewed_through',  'perspective', 'any', 'any', NULL, 'deprecated', 'deprecated', '{now}', '{now}'),
('interpreted_as',  'perspective', 'any', 'any', NULL, 'deprecated', 'deprecated', '{now}', '{now}'),
('questions',       'perspective', 'any', 'any', NULL, 'active',     'normal',     '{now}', '{now}'),
('validates',       'perspective', 'any', 'any', NULL, 'active',     'normal',     '{now}', '{now}'),

-- temporal (4개)
('preceded_by',        'temporal', 'any', 'any', NULL, 'active', 'normal', '{now}', '{now}'),
('simultaneous_with',  'temporal', 'any', 'any', NULL, 'active', 'normal', '{now}', '{now}'),
('born_from',          'temporal', 'any', 'any', NULL, 'active', 'normal', '{now}', '{now}'),
('assembles',          'temporal', 'any', 'any', NULL, 'active', 'normal', '{now}', '{now}'),

-- cross_domain (6개)
('transfers_to',    'cross_domain', 'any', 'any', NULL, 'active', 'normal', '{now}', '{now}'),
('mirrors',         'cross_domain', 'any', 'any', NULL, 'active', 'normal', '{now}', '{now}'),
('influenced_by',   'cross_domain', 'any', 'any', NULL, 'active', 'normal', '{now}', '{now}'),
('showcases',       'cross_domain', 'any', 'any', NULL, 'active', 'normal', '{now}', '{now}'),
('correlated_with', 'cross_domain', 'any', 'any', NULL, 'active', 'normal', '{now}', '{now}'),
('refuted_by',      'cross_domain', 'any', 'any', NULL, 'active', 'normal', '{now}', '{now}');
```

### Step 4b: governs 추가 (A-11 결론: 역방향으로 정당)

```sql
-- governs: governed_by의 역방향. DB에 32개 edge 존재. ALL_RELATIONS에 추가 정당.
INSERT INTO relation_defs (name, category, direction_constraint, layer_constraint, reverse_of, status, rank, created_at, updated_at)
VALUES ('governs', 'structural', 'upward', 'any', 'governed_by', 'active', 'normal', '{now}', '{now}');
```

---

## Step 5: 6개 잘못된 관계 교정 SQL (A-11 기반)

```sql
-- governs(32) → ALL_RELATIONS에 추가 (Step 4b에서 처리). 기존 edge는 유지.

-- strengthens(9) → supports
UPDATE edges SET relation = 'supports'
WHERE relation = 'strengthens';
INSERT INTO correction_log (edge_id, field, old_value, new_value, reason, corrected_by, created_at)
SELECT id, 'relation', 'strengthens', 'supports',
       'A-11: invalid relation corrected', 'migration', datetime('now')
FROM edges WHERE relation = 'strengthens';  -- UPDATE 전에 실행하거나, 별도 스크립트에서 순서 보장

-- validated_by(3) → validates
UPDATE edges SET relation = 'validates'
WHERE relation = 'validated_by';

-- extracted_from(2) → derived_from
UPDATE edges SET relation = 'derived_from'
WHERE relation = 'extracted_from';

-- instance_of(2) → instantiated_as
UPDATE edges SET relation = 'instantiated_as'
WHERE relation = 'instance_of';

-- evolves_from(4) → evolved_from
UPDATE edges SET relation = 'evolved_from'
WHERE relation = 'evolves_from';
```

### Python 마이그레이션 스크립트 (correction_log 포함)

```python
# scripts/migrate_ontology.py

RELATION_CORRECTIONS = {
    "strengthens":    "supports",
    "validated_by":   "validates",
    "extracted_from": "derived_from",
    "instance_of":    "instantiated_as",
    "evolves_from":   "evolved_from",
}

def correct_invalid_relations(conn):
    """A-11 기반 잘못된 관계 6개 교정."""
    now = datetime.now(timezone.utc).isoformat()
    total = 0

    for old_rel, new_rel in RELATION_CORRECTIONS.items():
        # 대상 edge 조회
        edges = conn.execute(
            "SELECT id FROM edges WHERE relation = ?", (old_rel,)
        ).fetchall()

        if not edges:
            continue

        # correction_log 기록 (UPDATE 전)
        for edge in edges:
            conn.execute(
                """INSERT INTO correction_log
                   (edge_id, field, old_value, new_value, reason, corrected_by, created_at)
                   VALUES (?, 'relation', ?, ?, 'A-11: invalid relation corrected', 'migration', ?)""",
                (edge["id"], old_rel, new_rel, now)
            )

        # 일괄 UPDATE
        count = conn.execute(
            "UPDATE edges SET relation = ? WHERE relation = ?",
            (new_rel, old_rel)
        ).rowcount
        total += count
        print(f"  {old_rel} -> {new_rel}: {count} edges corrected")

    conn.commit()
    return total
```

---

## Step 6: 미사용 관계 2개 deprecated 처리

```sql
-- interpreted_as, viewed_through: 사용 0, deprecated
-- (Step 4에서 이미 deprecated로 INSERT됨)
-- questions: 유보 (Question 타입과 자연스러운 쌍)

-- deprecated 관계 정의 업데이트 (설명 추가)
UPDATE relation_defs
SET deprecated_reason = 'No instances since creation. Perspective category unused.',
    deprecated_at = datetime('now')
WHERE name IN ('interpreted_as', 'viewed_through')
  AND status = 'deprecated';
```

---

## Step 7: 초기 스냅샷 생성

```sql
INSERT INTO ontology_snapshots (version_tag, type_defs_json, relation_defs_json, change_summary, created_at)
VALUES (
    'v2.0-initial',
    (SELECT json_group_array(json_object(
        'name', name, 'layer', layer, 'super_type', super_type,
        'status', status, 'rank', rank, 'replaced_by', replaced_by
    )) FROM type_defs),
    (SELECT json_group_array(json_object(
        'name', name, 'category', category, 'status', status,
        'rank', rank, 'reverse_of', reverse_of
    )) FROM relation_defs),
    'Initial migration: 31 active + 19 deprecated types, 49 active + 2 deprecated relations, 6 invalid relation corrections',
    datetime('now')
);
```

---

## validators.py 연동 — type_defs 테이블 기반으로 전환

```python
# ontology/validators.py — 수정 방향

def get_valid_node_types() -> set[str]:
    """type_defs 테이블에서 활성 타입 조회. schema.yaml 대체."""
    conn = sqlite_store._connect()
    rows = conn.execute(
        "SELECT name FROM type_defs WHERE status = 'active'"
    ).fetchall()
    conn.close()
    return {r["name"] for r in rows}

def validate_node_type(type_name: str) -> tuple[bool, str | None]:
    """type_defs 기반 검증. deprecated 타입이면 replaced_by 반환."""
    conn = sqlite_store._connect()
    row = conn.execute(
        "SELECT name, status, replaced_by FROM type_defs WHERE name = ?",
        (type_name,)
    ).fetchone()
    conn.close()

    if not row:
        return False, None
    if row["status"] == "deprecated":
        return False, row["replaced_by"]  # deprecated → 대체 타입 제안
    # 대소문자 교정
    if row["name"] != type_name:
        return True, row["name"]
    return True, None

def validate_relation(relation: str) -> tuple[bool, str | None]:
    """relation_defs 기반 검증."""
    conn = sqlite_store._connect()
    row = conn.execute(
        "SELECT name, status, replaced_by FROM relation_defs WHERE name = ?",
        (relation,)
    ).fetchone()
    conn.close()

    if not row:
        return False, None
    if row["status"] == "deprecated":
        return False, row["replaced_by"]
    return True, None
```

---

## 마이그레이션 실행 순서

```
1. type_defs + relation_defs + ontology_snapshots 테이블 생성
2. 31개 활성 타입 INSERT
3. 19개 미사용 타입 deprecated INSERT
4. 48+1개 관계 INSERT (governs 포함)
5. 6개 잘못된 관계 교정 (correction_log 기록)
6. 미사용 관계 deprecated 업데이트
7. 초기 스냅샷 v2.0-initial 생성
8. validators.py를 type_defs/relation_defs 기반으로 전환
9. config.py ALL_RELATIONS에 'governs' 추가

되돌리기: type_defs/relation_defs DROP으로 즉시 복원.
기존 nodes/edges 테이블은 변경하지 않음.
```
