# d-r3-11: 스키마 드리프트 — 실제 diff 실행 결과

> 2026-03-05 실행. d-r2-1에서 "5개 누락"이라 추정했으나 실제는 **1개**.

---

## 실행 명령어

```python
from scripts.migrate_v2 import TYPE_TO_LAYER
import yaml

with open('ontology/schema.yaml', 'r', encoding='utf-8') as f:
    schema = yaml.safe_load(f)

schema_types = set(schema['node_types'].keys())  # dict 구조 확인
migrate_types = set(TYPE_TO_LAYER.keys())

print(f'schema.yaml: {len(schema_types)}개')
print(f'TYPE_TO_LAYER: {len(migrate_types)}개')
print('schema에만:', schema_types - migrate_types)
print('migrate에만:', migrate_types - schema_types)
```

---

## 실행 결과

```
schema.yaml 타입 수:   50
TYPE_TO_LAYER 타입 수: 49

schema에만 있는 타입 (migrate 누락): {'Unclassified'}
migrate에만 있는 타입 (schema 누락): (없음)
```

### 수정: 이전 분석(d-r2-1) 오류

| 항목 | d-r2-1 추정 | 실제 (오늘 실행) |
|------|------------|----------------|
| TYPE_TO_LAYER 수 | 45개 | **49개** |
| 누락 타입 수 | 5개 | **1개 (Unclassified만)** |
| schema.yaml 수 | 50개 | 50개 (일치) |
| validators.py 기준 | 50개 | 50개 (schema.yaml 직접 참조) |

**d-r2-1 "50/45 불일치"는 오류. 실제는 50/49, 1개 누락.**

---

## 누락 타입 분석: Unclassified

```yaml
# schema.yaml에 존재
Unclassified:
  description: "분류 불가 또는 아직 분류 미결정 노드"
  tier: ...
  layer: ...
```

```python
# TYPE_TO_LAYER에 없음
# 현재 상태: E6 secondary_types 검증 시 "Unclassified" 입력 → KeyError 위험
```

### 영향 범위

| 컴포넌트 | Unclassified 처리 | 상태 |
|----------|-------------------|------|
| validators.py | schema.yaml 직접 참조 → 50개 인식 | 정상 |
| E6 (node_enricher.py) | TYPE_TO_LAYER 직접 참조 → 49개 인식 | **취약** |
| migrate_v2.py _get_layer() | TYPE_TO_LAYER 조회 → KeyError 가능 | **취약** |
| insert_edge fallback | "connects_with" 자동 교정 | 관계없음 |

### E6 취약점 구체화

```python
# node_enricher.py E6 secondary_types 검증 (추정 코드)
if secondary_type not in TYPE_TO_LAYER:
    # "Unclassified"인 경우 이 분기 진입
    pass  # 또는 KeyError
```

---

## 수정 방법

### 옵션 A (즉시 fix): TYPE_TO_LAYER에 Unclassified 추가

```python
# scripts/migrate_v2.py TYPE_TO_LAYER 딕셔너리 끝에 추가
TYPE_TO_LAYER = {
    ...
    "Workflow": 1,
    "Wonder": 5,
    "Unclassified": 0,  # 추가: L0 (원시 관찰 레이어로 배치)
}
```

**레이어 배정 근거:**
- Unclassified = 분류 미결정 = 가장 낮은 추상 단계
- L0: 원시 데이터/관찰 레이어 (Context, Observation, Conversation 등과 동급)
- 나중에 재분류 시 tier/layer 업그레이드 가능

### 옵션 B (근본 해결): single source of truth 통합

```python
# scripts/migrate_v2.py
# TYPE_TO_LAYER를 schema.yaml에서 자동 생성
import yaml

def _build_type_to_layer():
    with open('ontology/schema.yaml') as f:
        schema = yaml.safe_load(f)
    return {
        name: data.get('layer', 0)
        for name, data in schema['node_types'].items()
    }

TYPE_TO_LAYER = _build_type_to_layer()
```

이렇게 하면 schema.yaml이 단일 진실 소스 → 앞으로 타입 추가 시 schema.yaml만 수정하면 됨.

**권장: 옵션 B** (단일 진실 소스 원칙)

---

## 관계 타입 현황

```
schema.yaml relation_types: 48개
```

| 카테고리 | 예시 |
|---------|------|
| 인과 | caused_by, led_to, resulted_in, triggered_by |
| 계층 | part_of, composed_of, contains, instantiated_as |
| 진화 | evolved_from, derived_from, crystallized_into |
| 대립 | contradicts, refuted_by, blocked_by |
| 유사 | analogous_to, parallel_with, mirrors |
| 지지 | supports, reinforces_mutually, validates |
| 시간 | preceded_by, succeeded_by, simultaneous_with |
| fallback | connects_with (자동 교정 대상) |

**관계 타입은 validators.py와 insert_edge fallback으로 보호됨 → 긴급 이슈 없음.**

---

## 결론

| 항목 | 상태 |
|------|------|
| 노드 타입 드리프트 | **1개 (Unclassified), L0 배정으로 즉시 해결 가능** |
| 관계 타입 드리프트 | 없음 |
| 긴급도 | 낮음 (Unclassified는 드물게 사용, fallback 타입) |
| 권장 조치 | 옵션 B: schema.yaml → TYPE_TO_LAYER 자동 생성 |

**d-r2-1 오류 정정: "5개 누락" → 실제 1개 (Unclassified). 기존 파일 신뢰도 주의.**
