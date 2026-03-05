# Q4. 온톨로지 버전 관리 — SNOMED/GO/Wikidata 패턴

## 현재 상태

**버전 관리 0.** 타입/관계 변경 시:
- `schema.yaml` 직접 수정
- `config.py`의 `RELATION_TYPES` 직접 수정
- 기존 노드/엣지 orphan 가능
- 변경 이력 없음

`correction_log`는 **인스턴스 수정 이력**이지 **스키마 변경 이력**이 아니다.

## 우리에게 맞는 패턴: Wikidata + Gene Ontology 하이브리드

- SNOMED CT: 의료용으로 과도하게 엄격
- Schema.org: 너무 느슨
- **Wikidata 3-rank**: normal -> preferred -> deprecated (+ reason)
- **Gene Ontology**: replaced_by 태그 + 대량 Obsolete 전략

## type_defs + 버전 스냅샷

```sql
CREATE TABLE type_defs (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    layer INTEGER NOT NULL,
    super_type TEXT,
    description TEXT,
    status TEXT DEFAULT 'active',     -- active | deprecated | archived
    rank TEXT DEFAULT 'normal',       -- normal | preferred | deprecated
    deprecated_reason TEXT,
    replaced_by TEXT,
    deprecated_at TEXT,
    version INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT,
    UNIQUE(name, version)
);

CREATE TABLE ontology_snapshots (
    id INTEGER PRIMARY KEY,
    version_tag TEXT UNIQUE NOT NULL,
    type_defs_json TEXT,
    relation_defs_json TEXT,
    change_summary TEXT,
    created_at TEXT
);
```

## deprecation 워크플로우

```python
def deprecate_type(type_name: str, reason: str, replaced_by: str = None):
    """타입 deprecated 처리. 관련 노드는 유지."""
    # 1. type_defs.status = 'deprecated'
    # 2. deprecated_reason, replaced_by 기록
    # 3. 관련 노드에 metadata.deprecated_type_warning = True
    # 4. validators.py가 deprecated 타입 새 노드 시 경고
    # 5. correction_log에 스키마 변경 기록

def migrate_type(from_type: str, to_type: str, dry_run: bool = True):
    """deprecated 타입 노드를 새 타입으로 마이그레이션."""
    # dry_run이면 결과만 보고
```

## 관계 타입 정리 로드맵

현재 48개 -> 목표: 활성 12-15개 + deprecated 나머지

```
Phase 1: 사용 빈도 분석 (SELECT relation, COUNT(*) FROM edges GROUP BY relation)
Phase 2: 사용 0 관계 -> deprecated
Phase 3: 유사 관계 병합 (supports + reinforces_mutually -> supports)
Phase 4: super-category만 UI 노출 (causal 3, structural 3, semantic 3, layer 3 = ~12개)
```

## 버전 스냅샷 트리거

- **자동**: type_defs/relation_defs status 변경 시
- **수동**: `ontology_review()` 도구
- **분기**: 3개월마다 전체 스냅샷
- Git으로도 추적 가능 (schema.yaml 히스토리와 보완)
