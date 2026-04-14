# 다음 세션: 온톨로지 50-세션 시뮬레이션 실행

## 배경

2026-04-09~10 두 세션에 걸쳐 mcp-memory v5.1 → v7.0 대규모 수리 완료.
인프라(임베딩/저장소/학습/구조)는 전부 수리됨. 남은 것은 **실제 동작 검증**.

50-세션 시뮬레이션을 Remote Trigger로 실행하려 했으나, 
모델 변경(Sonnet→Opus) 시 events(프롬프트)가 유실되어 실행 실패.

## 즉시 할 것

### 1. Remote Trigger 재설정 + 실행

```
Trigger ID: trig_01RDAqJi6sHtvcBS3SmGfHyj
이름: ontology-full-activation
문제: events 배열이 비어있음 (모델 update 시 유실)
```

조치:
1. RemoteTrigger action:"update" 로 프롬프트 재삽입
   - model: claude-opus-4-6
   - events에 아래 "시뮬레이션 프롬프트" 전체 삽입
   - cron: 즉시 실행이면 action:"run" 사용
2. 실행 확인: git log에 `[auto] ontology full activation` 커밋 확인

### 2. 시뮬레이션 프롬프트 (Remote Trigger에 넣을 것)

```
너는 mcp-memory 온톨로지를 "살아있는 신경망"으로 활성화하는 에이전트다. 한국어로 작업한다.
이것은 1회성 대규모 작업이다. 컨텍스트를 최대한 활용해라.

## 환경
pip install sentence-transformers numpy pyyaml python-dotenv 2>/dev/null
.env에 EMBEDDING_PROVIDER=local 설정됨.
DB: data/memory.db (SQLite). 벡터: nodes.embedding BLOB (numpy). 검색: storage/hybrid.py.

## 목표 (전부 달성해야 종료)
1. validated >= 30% (현재 6.4%)
2. NDCG@5 >= 0.40 (현재 0.293)
3. cross-domain edge >= 30% (현재 19.8%)
4. missing embedding = 0 (현재 2)
5. 시뮬레이션 중 100+ 노드 승격
6. 반복 recall 시 edge strength +20% 이상 변화
7. 모든 추상 쿼리에서 3개 이상 프로젝트 혼합 결과

## DB 백업 (필수, 첫 번째 명령)
cp data/memory.db data/backup/memory-$(date +%Y%m%d-%H%M).db

## Step 0: 기준선 측정
- active nodes, validated 수, provisional 수
- active edges, cross-domain edge 수
- edge strength 분포 (mean, std)
- missing embedding 수
- NDCG: PYTHONIOENCODING=utf-8 EMBEDDING_PROVIDER=local python3 scripts/eval/ndcg.py --json

## Step 1: 누락 임베딩 수정
embedding IS NULL인 active 노드에 임베딩 생성+저장.

## Step 2: 50-세션 시뮬레이션

설계 원칙:
- 각 세션에서 실제 파일을 Read로 읽고, 그 내용에서 진짜 통찰을 형성
- remember()에는 실제 발견한 것만. 템플릿/가짜 데이터 절대 금지
- tags에 반드시 'simulation,auto-activation' 포함
- project는 읽은 파일의 실제 프로젝트

### Track A: 아키텍처 정밀 읽기 (세션 1-10)
각 세션: 파일 1-2개를 Read로 전체 읽기 → 통찰 형성 → remember 3-5회 → recall 15회 → 크로스도메인 recall 5회

| 세션 | Read 대상 | remember 타입 |
|------|----------|-------------|
| A1 | docs/01-design.md | Insight, Decision |
| A2 | docs/04-ontology-design-dialogue.md (처음 200줄) | Pattern, Observation |
| A3 | docs/04-ontology-design-dialogue.md (200-400줄) | Insight, Pattern |
| A4 | storage/hybrid.py (처음 300줄) | Pattern, Observation |
| A5 | storage/hybrid.py (300-600줄) | Insight, Decision |
| A6 | tools/remember.py | Pattern, Observation |
| A7 | tools/recall.py + tools/get_context.py | Insight, Pattern |
| A8 | scripts/daily_enrich.py (처음 300줄) | Observation, Pattern |
| A9 | ontology/schema.yaml | Observation, Insight |
| A10 | docs/05-full-architecture-blueprint.md (처음 200줄) | Insight, Principle |

### Track B: 크로스도메인 합성 (세션 11-20)
각 세션: 두 프로젝트의 기존 노드를 recall로 탐색 → 공유 원칙 발견 → Principle/Pattern으로 remember

| 세션 | 도메인 쌍 | recall 쿼리 예시 |
|------|----------|----------------|
| B1 | orchestration + mcp-memory | "시스템 설계 원칙", "아키텍처 결정" |
| B2 | portfolio + mcp-memory | "Paul을 표현하는 것", "자기 외부화" |
| B3 | tech-review + orchestration | "자동화 파이프라인", "데이터 흐름" |
| B4 | monet-lab + portfolio | "UI 실험", "시각적 표현" |
| B5 | documentation-system + mcp-memory | "구조화 원칙", "메타데이터" |
| B6 | orchestration + portfolio + tech-review | "Paul의 설계 철학" (3개 관통) |
| B7 | mcp-memory + context-cascade-system | "토큰 효율", "기억 효율" |
| B8 | epistemic-methods + mcp-memory | "인식론", "지식 구조" |
| B9 | index-system + mcp-memory | "관계 추적", "그래프 구조" |
| B10 | 전체 5개 프로젝트 통합 | "이색적 접합", "다차원 연결" |

### Track C: Paul 사고 패턴 (세션 21-30)
DB에서 기존 노드를 쿼리로 읽고 메타 관찰.

| 세션 | DB 쿼리 | 분석 |
|------|---------|------|
| C1 | source_kind='user' 전체 | Paul 직접 입력의 공통 패턴 |
| C2 | type='Principle' 전체 | 원칙들의 클러스터링 |
| C3 | type='Failure' 상위 20개 | 실패 패턴 추출 |
| C4 | type='Decision' AND visit>5 | 자주 참조되는 결정 |
| C5 | type='Identity' 전체 | Paul의 자기 서술 구조 |
| C6 | visit_count 상위 20개 | 가장 중요한 지식 |
| C7 | type='Pattern' AND quality>0.9 | 고품질 패턴의 특징 |
| C8 | type='Observation' AND visit>3 | 패턴으로 갈 준비된 것 |
| C9 | type='Signal' 전체 | 성장하지 못한 신호들 |
| C10 | 크로스도메인 edge 양쪽 노드 | 이색적 접합 사례 |

### Track D: Hebbian 강화 + 스트레스 (세션 31-40)

| 세션 | 행동 | 목표 |
|------|------|------|
| D1-D3 | 핵심 개념 5개 반복 recall (총 15회씩) | edge +20% |
| D4 | 2글자 한국어 쿼리 30개 | hit_rate 측정 |
| D5 | 영어 쿼리 20개 | 한국어 노드 매칭 |
| D6 | 100자+ 서술형 쿼리 10개 | 의미 검색 품질 |
| D7 | 존재하지 않는 개념 쿼리 10개 | false positive 확인 |
| D8 | 동시 remember 15개 (배치) | 전부 저장+벡터 |
| D9 | recall source 분포 분석 | vector/fts5/graph 균형 |
| D10 | 전체 NDCG 82쿼리 | 중간 측정 |

### Track E: 성장 사이클 완주 (세션 41-50)

| 세션 | 행동 | 검증 |
|------|------|------|
| E1 | 새 Observation 15개 (5개 도메인) | 저장+edge |
| E2 | E1 노드 집중 recall 30회 | Hebbian 강화 |
| E3 | auto_promote --execute | 승격 확인 |
| E4 | 새 Signal 5개 + 반복 recall | Signal→Pattern |
| E5 | auto_promote --execute | 승격 확인 |
| E6 | Pattern recall 반복 | Pattern→Principle |
| E7 | auto_promote --execute | 최종 승격 |
| E8 | Phase 6 dry-run (decay) | 감쇠 대상 |
| E9 | Phase 6 dry-run (pruning) | 가지치기 대상 |
| E10 | 최종 NDCG + 건강 리포트 | 목표 달성 확인 |

## Step 3: 승격 대규모 실행
python3 scripts/auto_promote.py --execute
목표: 100+ 승격. 기준 너무 엄격하면 완화 (visit>=2, edges>=2, quality>=0.7).

## Step 4: 크로스도메인 edge 강화
30% 미만이면 추상 쿼리 50회 집중 recall → co_retrieval edge 자동 생성.

## Step 5: 최종 측정 + 비교표

## Step 6: 보고 + 커밋
STATE.md, CHANGELOG.md 갱신.
git add -A && git commit -m '[auto] ontology full activation' && git push

## 규칙
- remember() type: Observation, Signal, Pattern, Insight, Decision, Failure, Principle
- tags에 항상 'simulation,auto-activation'
- Phase 6 pruning은 dry-run만
- DB 백업 필수
- 컨텍스트 85% 소진 시 Step 5-6 즉시
```

## 현재 DB 상태 (2026-04-10)

| 지표 | 값 |
|------|---|
| Active nodes | 3,199 (원래 5,260) |
| Validated | 205 (6.4%) |
| Provisional | 2,997 (93.6%) |
| Active edges | 5,982 |
| Cross-domain edges | ~19.8% |
| NDCG@5 | 0.293 |
| NDCG@10 | 0.302 |
| hit_rate | 72.0% |
| Embedding | local (multilingual-e5-large 1024d) |
| Storage | SQLite 1-Store (ChromaDB 제거됨) |
| Learning | Hebbian frequency-based (ACTIVE) |
| Growth | auto_promote on SessionEnd (ACTIVE) |
| Decay | daily_enrich Phase 6 (IMPLEMENTED) |
| Pruning | 199 edges pruned (첫 실행 완료) |

## 커밋 히스토리 (이번 수리)
```
4787d29 v7.0 — 1-Store + auto-promote relaxation + config split + enrichment simplification
2e5dcdf v6.0.1 — Edge time decay + pruning + growth cycle hook + tool cleanup
71ae715 v6.0 — Local embedding + Hebbian learning + auto-promote
```

## 파일 위치
- 파이프라인: 06_ontology-repair_0409/
- 진단 보고: 06_ontology-repair_0409/10_diagnose-r1/01_dialogue.md
- auto_promote: scripts/auto_promote.py
- reembed: scripts/reembed_local.py
- 로컬 임베딩: embedding/local_embed.py
- goldset: scripts/eval/goldset_v4.yaml (FROZEN, 82 queries)

## Remote Trigger 실수 기록
- RemoteTrigger update로 model만 바꾸려 했으나, job_config.ccr 전체가 교체되어 events 유실
- 교훈: update 시 events도 반드시 포함하거나, 변경할 필드만 정확히 지정
