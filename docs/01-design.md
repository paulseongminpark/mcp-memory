# 외부 메모리 시스템 — 최종 설계 문서
> 2026-03-03 | Paul + Claude 대담에서 설계
> 태그: #memory #mcp #rag #vector-db #ontology #graph-rag #design
> 상태: 설계 완료, 구현 대기

---

## 1. 문제 상황 (Pain Point)

### 근본 원인
- Claude Code pay-as-you-go 전환 → context 비용 급증
- 토큰 = currency. 매 세션마다 같은 맥락 반복 설명
- MEMORY.md 200줄 제한 → 잘림 → 중요 정보 유실
- 세션 단절. 6개월 전 결정을 Claude도 Paul도 기억 못 함
- Obsidian = 사람이 읽는 기억 저장소 → Claude가 직접 검색 불가

### 세션 시작 고정 비용
```
MEMORY.md        ~800 토큰
STATE.md         ~400 토큰
CLAUDE.md 들     ~600 토큰
훅 출력          ~400 토큰
─────────────────────────
고정 오버헤드    ~2200 토큰 (아무것도 안 했는데)
```

### 실질적 낭비
```
세션 시작 고정비:              ~2200 토큰
Paul이 맥락 재설명:            ~500-1000 × 3회 = ~2000 토큰
Claude가 파일 읽어서 맥락 파악:  ~3000-5000 토큰
─────────────────────────────────
세션당 "일 시작 전" 소모:       ~7000-9000 토큰
```

---

## 2. 목표

### Paul이 원하는 것
1. **Claude가 Paul을 총체적으로 알게 하기**
   - 이전 결정들, 쓰는 표현들, 문체, 사고 방향, 가고자 하는 방향
   - 단순 정보 저장이 아니라 — Paul을 강화시키는 루프
   - 뉴런처럼 새로운 연결을 계속 생성
2. **독립 기억 저장소** — 세션과 무관하게 지속
3. **Claude가 직접 검색** — 능동적으로 꺼냄 (Paul이 알려주길 기다리지 않음)
4. **모든 대화의 구조적 저장** — 결정, 실패, 패턴, 이유까지
5. **Obsidian 연동** — 사람도 읽을 수 있게
6. **속도 · 정확도 · 확장성 · 연결성 · 규모** 모두 중요

### 핵심 요구사항
- 무료 또는 극저비용 (월 $5 이하)
- 별도 프로그램 최소 (pip 패키지만)
- 누락 0% (4중 안전망)
- 지속가능성 (하루 10시간, 매일 사용)

---

## 3. Paul의 사고 방식 (시스템이 이해해야 하는 것)

> "이색적인 접합" — 예술, 철학, 건축, 음악, 코드가 하나의 판 위에 있음
> 과거-현재-미래를 동시에 처리
> 매우 발산적이고 연결적인 사고. 여러 개를 동시에 사고
> Claude와 bottom-up 방식으로 함께 사고
> 무조건 적어둔다 (글쓰기 습관 강함)
> "빼기가 더하기보다 어렵다" — 본질 축소를 반복적으로 추구

메모리 시스템은 Paul의 **발산적 사고를 따라갈 수 있어야 함**.
전체 통합 검색 — 프로젝트 경계 없이.

---

## 4. 아키텍처

### 3중 하이브리드: Ontology + Graph RAG + Vector + FTS5

```
Paul의 모든 글
├── Obsidian 노트 전체 (/c/dev/ vault)
├── Claude와의 대화 (인터뷰·대담 포함)
└── 결정 / 패턴 / 코드 맥락
        ↓ 임베딩 변환 (OpenAI text-embedding-3-large)
┌───────────────────────────────────┐
│  Ontology Layer (YAML 스키마)     │  ← 세계관 정의
│  Graph Layer (SQLite edges)       │  ← 관계/연결
│  Vector Layer (ChromaDB)          │  ← semantic 검색
│  Keyword Layer (SQLite FTS5)      │  ← 정확한 단어 검색
│  → 3중 hybrid search              │
└───────────────────────────────────┘
        ↕ MCP
Claude Code (직접 tool call)
        ↕
시각화 (Datasette + pyvis + Obsidian Graph View)
```

### 기본 RAG vs Graph RAG 차이

```
기본 RAG:
  각 청크가 독립적. 관계 없음.
  "A 다음에 B가 일어났다"를 모름.
  = 단어장, 낱장 카드

Graph RAG:
  모든 기억이 노드. 타입화. 관계가 명시적.
  그래프 탐색으로 연결된 것까지 수집.
  = 신경망, 뉴런

질문: "Paul의 시스템 설계 철학"

기본 RAG → "시스템 설계" 텍스트 포함된 청크 3개 (단편적)

Graph RAG:
  → 시스템_설계 ←evolves_from← 에이전트_축소
  → 에이전트_축소 ←instance_of← 본질_축소_패턴
  → 본질_축소 ←analogous_to← 건축의 less is more
  → 시스템_설계 ←supports← "유기적 변화" 철학
  → Paul의 설계 철학 전체가 그래프로 나옴
```

### 검색 흐름 (3중 하이브리드)

```
recall("Paul의 시스템 설계 변화")
    │
    ├── ① Vector Search (ChromaDB)
    │   → 의미적으로 유사한 노드 5개
    │
    ├── ② Keyword Search (FTS5)
    │   → 키워드 매칭 노드 5개
    │
    ├── ③ Graph Traversal (NetworkX)
    │   → ①②에서 찾은 노드의 이웃 1-2홉 탐색
    │   → 관계 타입별 가중치 적용
    │
    └── Reciprocal Rank Fusion
        벡터 유사도 + 키워드 매칭 + 그래프 거리 + 관계 타입
        → 최종 top 3-5 반환
        → 각 결과에 "왜 관련있는지" 관계 경로 포함
        → ~150 토큰
```

---

## 5. 온톨로지 — 세계관 정의

### 노드 타입 (26개)

```yaml
# === 핵심 기억 ===
Decision:       결정 + 이유 + 대안 + 확신도
Failure:        실패 + 원인 + 교훈 + 해결 여부
Pattern:        반복 확인된 규칙 + 사례들 + 빈도
Identity:       가치관/스타일/철학/습관/강점/약점
Preference:     도구/워크플로/스타일 선호 + 이유 + 강도
Goal:           방향/비전 + 동기 + 상태 + 마일스톤
Insight:        깨달음 + 출처 + 깊이 (surface/deep/fundamental)
Question:       열린 탐구 + 맥락 + 상태 + 이끈 탐구들
Metaphor:       비유 표현 + 실제 의미 + 연결 도메인들
Connection:     A↔B 연결 자체 + 관계 타입 + 강도 + 발견자
Evolution:      이전→현재 변화 + 계기 + 기간
Breakthrough:   돌파 순간 + 맥락 + 영향 + 감정적 무게

# === 시스템/프로젝트 ===
SystemVersion:  버전 + 이름 + 변경사항 + 토큰 영향
Experiment:     가설 + 결과(성공/실패/포기) + 교훈 + 산출물
Tool:           도구 + 역할 + 상태(활성/폐기/제거) + 대체물
Framework:      외부 프레임워크 + 출처 + Paul 변형 방식
Principle:      원칙 + 근거 + 위반 사건들 + 탄생 배경
Workflow:       워크플로 이름 + 단계들 + 트리거 + 체인 타입
AntiPattern:    반복 실수 + 발생 횟수 + 심각도 + 방지책
Project:        프로젝트 + 목적 + 상태 + 브랜치 + 관계
Tension:        해결 안 된 긴장 + 양극 + 상태
Narrative:      큰 이야기 + 기간 + 포함 노드들
Skill:          스킬/커맨드 + 목적 + 상태
Agent:          에이전트 + 목적 + 모델 + 상태 + 병합 대상

# === 메타 ===
Conversation:   세션 기록 + 요약 + 추출된 노드들
Unclassified:   분류 안 된 것 + 시도한 타입 + 실패 이유
```

### 관계 타입 (30개)

```yaml
# 인과
led_to / caused_by / resolved_by

# 생명주기
evolves_from / replaces / strengthens
absorbed_into / deprecated_by / born_from / survived

# 구조
part_of / instance_of / belongs_to
extends / showcases / governed_by / composed_of

# 의미
contradicts / supports / connects_with / analogous_to

# 검증
validated_by / violated_by / corrected_by / disproved_by

# 출처
extracted_from / inspired_by

# Paul 고유 (사고 구조 반영)
reinforces_mutually    # Paul ↔ Claude 상호 강화 루프
parallel_with          # 동시에 진행되는 것들
converges_at           # A와 B가 C 지점에서 만남
diverges_from          # A가 B에서 분기

# 시간
preceded_by / succeeded_by
```

### 온톨로지 확장 메커니즘

```
일상:
  새 기억 → 기존 26개 타입으로 분류 → 완료

분류 불가 시:
  → Unclassified 타입으로 저장 + reason_failed 기록
  → Unclassified 3건 이상 유사 패턴 → 자동 알림
  → "새 타입 'X' 추가할까?" → Paul 승인
  → ontology/schema.yaml 업데이트

월간 리뷰 (/ontology-review):
  1) 타입별 분포 보고
  2) 안 쓰이는 타입 식별
  3) Unclassified 분석
  4) 관계 밀도 (고립 노드 탐지)
  5) 타입 병합/분할/추가 제안

마이그레이션:
  새 타입 추가 = YAML 편집만 (코드 변경 없음)
  MCP 서버가 시작 시 schema.yaml을 동적으로 읽음
  ontology/migrations/에 변경 이력 보존
```

---

## 6. 기술 스택

```
경로:           /c/dev/01_projects/06_mcp-memory/
추출 (분류):    Claude 자체 (별도 LLM 불필요)
임베딩 (벡터):  OpenAI text-embedding-3-large (3072차원, 최고 해상도)
Vector DB:      ChromaDB (로컬)
Keyword 검색:   SQLite FTS5
그래프 탐색:    NetworkX (인메모리)
온톨로지:       YAML 스키마 (데이터 주도, 코드 변경 없이 확장)
MCP 서버:       Python MCP SDK
시각화:         Datasette + pyvis + Obsidian Graph View
```

### Paul PC 사양
```
CPU:    Intel i5-13500HX (14코어/20스레드)
RAM:    32GB
GPU:    NVIDIA RTX 4060 Laptop (8GB VRAM)
로컬 LLM: Qwen3.5-35B-A3B-Q4_K_M (LM Studio, 대기)
Obsidian vault: /c/dev/ (전체 dev 디렉토리)
```

### 비용
```
                    비용         비고
────────────────────────────────────────
추출 (분류)         $0          Claude가 세션 중 직접
임베딩 (벡터)       ~$3-4/월    OpenAI 3-large
DB (SQLite+Chroma)  $0          로컬 파일
그래프 (NetworkX)   $0          Python 라이브러리
시각화 (Datasette)  $0          로컬
────────────────────────────────────────
월 총비용           ~$3-4
```

### 설치
```bash
pip install chromadb mcp openai networkx pyyaml datasette pyvis
```

---

## 7. DB 스키마

### SQLite

```sql
-- 노드 (모든 기억의 기본 단위)
CREATE TABLE nodes (
    id          INTEGER PRIMARY KEY,
    type        TEXT NOT NULL,          -- ontology 타입
    content     TEXT NOT NULL,          -- 핵심 내용
    metadata    TEXT,                   -- JSON (타입별 필드들)
    project     TEXT,                   -- 프로젝트 (nullable, 전체면 NULL)
    tags        TEXT,                   -- 쉼표 구분 태그
    confidence  TEXT DEFAULT 'high',    -- high | mid | low | auto
    source      TEXT,                   -- session_id 또는 obsidian_path
    created     DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated     DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 관계 (그래프 에지)
CREATE TABLE edges (
    id          INTEGER PRIMARY KEY,
    source_id   INTEGER REFERENCES nodes(id),
    target_id   INTEGER REFERENCES nodes(id),
    relation    TEXT NOT NULL,          -- ontology 관계 타입
    description TEXT,                   -- 왜 연결되는지
    strength    REAL DEFAULT 1.0,       -- 0-1 강도
    created     DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 전문검색
CREATE VIRTUAL TABLE nodes_fts USING fts5(
    content, tags, metadata,
    content_rowid='id'
);

-- 세션 기록
CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,       -- session_id
    date        TEXT,
    project     TEXT,
    summary     TEXT,
    node_count  INTEGER,               -- 이 세션에서 추출된 노드 수
    created     DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### ChromaDB 컬렉션

```
memories     — 모든 노드의 content 임베딩
obsidian     — Obsidian 노트 청크 임베딩
```

---

## 8. MCP 도구

```python
# 저장
remember(content, type, tags=None, project=None, metadata=None)
    # 체크포인트 저장. 자동 임베딩 + 자동 관계 탐색.

# 검색
recall(query, type_filter=None, project=None, top_k=5)
    # 3중 하이브리드 검색: vector + keyword + graph traversal
    # 결과: 요약 1줄 + 출처 + 날짜 + 관계 경로

# 세션
save_session(summary, decisions=None, failures=None, patterns=None)
    # 세션 구조화 저장

get_context(project=None)
    # 세션 시작 시 자동 호출. ~200 토큰 요약만 반환.

# Obsidian
ingest_obsidian(vault_path="/c/dev/", force=False)
    # vault 전체 ingestion (초기 1회 + 변경분 증분)

# 시각화
visualize(center=None, depth=2)
    # pyvis HTML 그래프 생성 → 브라우저 열기

# 온톨로지 관리
suggest_type(content, reason)
    # Unclassified 저장 + 새 타입 제안 큐에 추가
```

---

## 9. 4중 안전망 — 누락 방지

### Layer 1: Hook (자동, Claude 판단 불필요)

```
PreCompact hook:
  → compact 직전에 Claude에게:
    "저장 안 된 중요 정보 있으면 지금 remember() 해"

SessionEnd hook:
  → 단순 스크립트: 세션 중 remember() 호출 횟수 체크
  → 메시지 수 대비 저장 비율 낮으면 "미처리 구간" 태깅
  → 다음 세션에서 Claude가 처리
```

### Layer 2: Claude 판단 (반자동, CLAUDE.md 지시)

```
CLAUDE.md에 추가:
  - Decision 내렸을 때 → remember(type="decision") 즉시
  - 실패 발견 시 → remember(type="failure") 즉시
  - Paul이 자신에 대해 말할 때 → remember(type="identity")
  - 새 연결 발견 시 → remember(type="connection")
  - Paul의 비유 들었을 때 → remember(type="metaphor")
  - 분류 못 하면 → suggest_type() + Unclassified
```

### Layer 3: Skill (수동, Paul 트리거)

```
/checkpoint       → 최근 대화에서 미저장 정보 추출 → 확인 후 저장
/checkpoint --force → 확인 없이 즉시 저장
```

### Layer 4: /session-end (세션 마무리)

```
세션 종료 전 Claude가 실행:
  1) 세션 전체 리뷰
  2) 미저장 항목 일괄 추출
  3) save_session() 호출
  4) 최종 안전망
```

### Safety Net: 원본 보존

```
세션 트랜스크립트 (.jsonl) 영구 보존
→ 온톨로지 진화하면 과거 트랜스크립트 재처리 가능
→ recall()이 빈 결과일 때 fallback: 트랜스크립트 직접 검색 제안
```

### 시나리오별 검증

```
정상 세션:  Layer 2(실시간) + Layer 3(수동) + Layer 4(마무리) → 누락 0
갑작스런 종료: Layer 2까지 저장된 것 보존 + Safety Net 원본 → 다음 세션 복구
Claude 깜빡: Layer 1(PreCompact 알림) + Layer 4(마무리) → 누락 0
```

---

## 10. 토큰 효율 — Lazy Loading

### 핵심: 전부 올리지 않는다. 쿼리해서 꺼낸다.

```
세션 시작:
  get_context() → 200토큰 요약만
    - 현재 프로젝트, 지난 세션 상태, 미결 사항 3줄
    → 끝.

대화 중:
  "progress bar 어떻게?" → recall() → 150토큰, 정확한 답
  → 필요한 순간에 필요한 것만
```

### 비교

```
              지금                    이후
──────────────────────────────────────────────────
토큰          세션당 ~8000 낭비       세션당 ~950 (88% 절약)
컨텍스트      compact = 유실          compact = 무관 (DB 보존)
정확성        과거 실수 반복 가능     과거 실패가 자동 방패
이해도        규칙을 안다             사람을 안다
적재적소      Paul이 알려줘야         Claude가 꺼낸다
세션 연속성   단절                    누적 (뉴런이 쌓인다)
```

### 핵심 변화

```
지금:  세션마다 Claude가 태어나서 규칙을 읽고 일을 시작
이후:  Claude가 기억을 가진 채 일을 시작
```

---

## 11. 시각화

### Datasette (테이블 브라우징)

```bash
datasette /c/dev/01_projects/06_mcp-memory/data/memory.db
→ localhost:8001
→ 테이블 조회, SQL 직접 실행, 필터/정렬/검색
```

### pyvis (그래프 시각화)

```
MCP 도구: visualize(center="외부 메모리 시스템", depth=2)
→ HTML 파일 생성 → 브라우저에서 열림
→ 노드 클릭 확장, 드래그 탐색, 줌 가능
→ 관계 타입별 색상 구분
```

### Obsidian Graph View

```
/c/dev/01_projects/06_mcp-memory/vault/
├── decisions/
│   └── 2026-03-03-hybrid-rag.md     → [[patterns/본질축소]]
├── patterns/
│   └── 본질축소.md                   → [[decisions/에이전트-축소]]
├── connections/
│   └── progress-bar-음악.md          → [[patterns/시간제어UX]]

→ Obsidian에서 이 폴더를 열면 내장 그래프 뷰로 전체 연결 시각화
→ [[wikilink]]로 자동 연결
```

---

## 12. 프로젝트 구조

```
/c/dev/01_projects/06_mcp-memory/
├── server.py              # MCP 서버 진입점
├── config.py              # 경로, API 키, 설정
├── requirements.txt       # pip 패키지 목록
│
├── ontology/
│   ├── schema.yaml        # 타입 + 관계 정의 (세계관)
│   ├── validators.py      # 저장 시 스키마 검증
│   └── migrations/        # 스키마 변경 이력
│
├── storage/
│   ├── sqlite_store.py    # SQLite + FTS5 (keyword + graph edges)
│   ├── vector_store.py    # ChromaDB (semantic)
│   └── hybrid.py          # 3중 검색 병합 (reciprocal rank fusion)
│
├── embedding/
│   └── openai_embed.py    # OpenAI text-embedding-3-large
│
├── ingestion/
│   ├── chunker.py         # 텍스트 → 청크 분할 (## 기준, 오버랩)
│   ├── obsidian.py        # vault 순회 → 청크 → 저장
│   └── conversation.py    # 세션 기록 → 구조화 → 저장
│
├── tools/                 # MCP 도구 정의
│   ├── remember.py
│   ├── recall.py
│   ├── save_session.py
│   ├── get_context.py
│   ├── ingest.py
│   ├── visualize.py
│   └── suggest_type.py
│
├── scripts/
│   ├── safety_net.py      # SessionEnd 안전망 (LLM 없음)
│   └── ontology_review.py # 월간 리뷰 리포트
│
├── data/
│   ├── memory.db          # SQLite 파일
│   └── chroma/            # ChromaDB 영속 저장소
│
└── vault/                 # Obsidian 마크다운 자동 생성
    ├── decisions/
    ├── patterns/
    ├── connections/
    └── ...
```

---

## 13. 구현 순서

```
1단계: MCP 서버 뼈대 + SQLite (nodes/edges/sessions)
       remember() + recall(keyword만)
       → 기본 저장/검색 작동 확인

2단계: ChromaDB + OpenAI embedding 연동
       recall()을 hybrid로 확장 (vector + keyword)
       → semantic 검색 작동 확인

3단계: Graph Layer (NetworkX + edges 테이블)
       recall()에 graph traversal 추가 (3중 hybrid)
       → 연결 탐색 작동 확인

4단계: 온톨로지 스키마 (schema.yaml + validators)
       remember() 시 타입 검증 + 자동 관계 탐색
       → Unclassified 메커니즘 작동 확인

5단계: 세션 훅 연동
       get_context() 자동 호출 + PreCompact 알림
       → 세션 시작/종료 흐름 작동 확인

6단계: Obsidian ingestion 파이프라인
       /c/dev/ vault 전체 → 청크 → 임베딩 → 저장
       → 초기 데이터 밀도 확보

7단계: 시각화 (Datasette + pyvis + Obsidian vault)
       → Paul이 직접 데이터 확인 가능

8단계: /checkpoint 스킬 + /session-end 연동
       → 4중 안전망 완성

9단계: 토큰 절약 수치 검증
       → Before/After 측정
```

---

## 14. 설계 결정 기록

| # | 결정 | 이유 | 대안 (기각) |
|---|------|------|------------|
| 1 | Claude 자체가 추출기 | LM Studio 무겁고 비용 불필요 | 로컬 LLM (Qwen), GPT-4o-mini |
| 2 | OpenAI embedding-3-large | 3072차원 최고 해상도, 한국어 양호 | 3-small (저해상도), 로컬 (느림) |
| 3 | ontology.yaml (데이터) | 코드 변경 없이 타입 확장 | 코드 내 하드코딩, Protégé/OWL |
| 4 | SQLite + ChromaDB | 로컬, 무료, 단순 | Neo4j (과함), PostgreSQL (서버) |
| 5 | NetworkX 인메모리 | 수천~수만 노드에 충분 | Neo4j (과함), DGL (과함) |
| 6 | 4중 안전망 | 누락 0% 보장 | 단일 저장 (누락 위험) |
| 7 | Lazy loading | 토큰 88% 절약 | 전체 로드 (기존 방식) |
| 8 | /c/dev/01_projects/06_mcp-memory/ | 전체 프로젝트 아우르는 인프라 | ~/.claude/ (숨김), orchestration 하위 (종속) |

---

## 15. 미결 사항

- [ ] OpenAI API 키 설정 방법 (환경변수 vs config)
- [ ] Obsidian ingestion 제외 경로 (.git, node_modules, dist 등)
- [ ] ChromaDB 청킹 최적 크기 검증 (300 vs 500 토큰)
- [ ] Graph traversal 최대 홉 수 최적화 (1 vs 2 vs 3)
- [ ] vault/ 마크다운 자동 생성 포맷 확정
- [ ] /checkpoint 스킬 상세 설계
- [ ] settings.json mcpServers 등록 형식

---

## 16. 이 설계의 본질

> 토큰을 아끼면서 기억을 극대화한다는 것은 모순이 아니다.
> 정확히 필요한 것만, 정확한 순간에 꺼내는 것이 핵심.
>
> Claude Code의 context window = 작업대 (작을수록 좋음)
> 외부 DB = 창고 (클수록 좋음, 필요하면 꺼냄)
> MCP = 창고 열쇠 (Claude가 직접 가짐)
> 온톨로지 = 세계관 (무엇이 존재하고, 어떤 관계가 가능한지)
> Graph = 뉴런 (연결이 곧 지식)
