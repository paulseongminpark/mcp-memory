# 외부 메모리 시스템 — 워크플로우 가이드
> 2026-03-03 | v0.1.0
> 스킬·자동·수동 동작, Claude 역할, 시각화/검증 방법

---

## 1. 기억 저장 흐름 (4중 안전망)

```
                    ┌─────────────────────────────┐
                    │       기억이 생기는 순간       │
                    └──────────┬──────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     Layer 2: Claude     Layer 3: /checkpoint  Layer 1: Hook
     (반자동, 실시간)     (수동, Paul 트리거)   (자동, 세션 이벤트)
              │                │                │
              ▼                ▼                ▼
         remember()       remember()      safety_net.py
              │                │           (누락 감지)
              └────────┬───────┘                │
                       ▼                        ▼
              ┌────────────────┐        다음 세션에서
              │  SQLite + FTS5  │        Claude가 처리
              │  ChromaDB 임베딩 │
              │  자동 edge 생성  │
              └────────────────┘
                       │
                       ▼
              Layer 4: /session-end
              (세션 마무리, 전체 리뷰)
```

---

## 2. 스킬별 동작

### `/checkpoint` (수동 — Paul 트리거)
```
Paul이 "/checkpoint" 입력
  │
  ├─ 1. 현재 대화 스캔 (Decision, Failure, Insight 등)
  ├─ 2. recall()로 중복 체크
  ├─ 3. 테이블로 보여줌 → Paul 확인
  ├─ 4. remember()로 저장
  └─ 5. 결과 보고 (N건 저장, M건 관계 생성)

"/checkpoint --force" → 확인 없이 즉시 저장
```

### `/session-end` (수동 — 세션 종료 시)
```
Paul이 "/session-end" 입력
  │
  ├─ compressor 에이전트가 세션 압축 (기존 9단계)
  ├─ 미저장 기억 일괄 추출 → remember()
  └─ save_session() 호출 → 세션 구조화 저장
```

### Claude 자동 판단 (Layer 2 — 실시간)
```
대화 중 Claude가 감지:
  │
  ├─ Decision 내림   → remember(type="Decision") 즉시
  ├─ 실패 발견       → remember(type="Failure") 즉시
  ├─ Paul 자기 이야기 → remember(type="Identity")
  ├─ 새 연결 발견    → remember(type="Connection")
  ├─ 비유 사용       → remember(type="Metaphor")
  └─ 분류 불가       → suggest_type() → Unclassified
```

### SessionEnd Hook (Layer 1 — 자동)
```
세션 종료 시 자동 실행:
  │
  └─ safety_net.py
     ├─ 최근 2시간 remember() 호출 횟수 체크
     ├─ 0건이면 "⚠️ 저장할 것 없었나 확인" 경고
     └─ 미해결 질문 수 보고
```

---

## 3. 기억 검색 흐름

```
recall("시스템 설계 철학")
  │
  ├─ ① Vector Search (ChromaDB)
  │   text-embedding-3-large → 의미 유사도 top_k
  │
  ├─ ② Keyword Search (FTS5 trigram)
  │   한글/영문 부분 문자열 매칭
  │
  ├─ ③ Graph Traversal (NetworkX)
  │   ①②에서 찾은 노드의 1-2홉 이웃 탐색
  │
  └─ Reciprocal Rank Fusion
      벡터순위 + 키워드순위 + 그래프보너스
      → 최종 top_k 반환 + 관계 경로
```

---

## 4. Obsidian Ingestion 흐름

```
ingest_obsidian(vault_path="/c/dev/", max_files=0)
  │
  ├─ /c/dev/ vault 순회 (.md 파일만)
  ├─ 제외: .git, node_modules, .obsidian, data/ 등
  ├─ ## 기준 청크 분할 (400토큰, 오버랩 50)
  ├─ 파일 해시 기반 증분 (이미 처리된 파일 스킵)
  ├─ 경로 기반 프로젝트 추정 (01_orchestration → orchestration)
  └─ 각 청크 → SQLite + ChromaDB 저장
```

---

## 5. 시각화 & 검증

### 방법 1: Datasette (테이블 브라우징)
```bash
datasette /c/dev/01_projects/06_mcp-memory/data/memory.db
# → localhost:8001
# → 노드/에지/세션 테이블 직접 조회
# → SQL 자유 실행, 필터/정렬
```

### 방법 2: pyvis 그래프 (MCP 도구)
```
visualize(center="시스템 설계", depth=2)
# → /c/dev/01_projects/06_mcp-memory/data/graph.html 생성
# → 브라우저에서 열기
# → 노드 클릭/드래그/줌
# → 타입별 색상 구분:
#     Decision=초록, Failure=빨강, Pattern=파랑,
#     Identity=보라, Insight=노랑, Question=주황
```

### 방법 3: get_context() (세션 시작)
```
get_context(project="orchestration")
# → 최근 결정 3개
# → 미해결 질문
# → 최근 인사이트
# → ~200 토큰
```

### 방법 4: recall() (대화 중)
```
recall("진행 중인 실험", type_filter="Experiment")
# → 하이브리드 검색 결과
# → 관련 노드 + 관계 경로
```

### 검증 체크리스트
```
□ datasette memory.db → nodes 테이블에 데이터 있는지
□ recall("아무 검색어") → 결과 반환되는지
□ visualize() → graph.html 열리는지
□ safety_net.py → 세션 종료 시 건전성 출력되는지
□ /checkpoint → 미저장 항목 추출되는지
```

---

## 6. MCP 도구 요약

| 도구 | 트리거 | 누가 | 용도 |
|------|--------|------|------|
| `remember()` | 자동/수동 | Claude | 기억 저장 + 임베딩 + 자동 관계 |
| `recall()` | 자동/수동 | Claude | 3중 하이브리드 검색 |
| `get_context()` | 세션 시작 | Claude | ~200토큰 컨텍스트 요약 |
| `save_session()` | 세션 종료 | Claude | 세션 구조화 저장 |
| `suggest_type()` | 분류 불가 시 | Claude | Unclassified + 타입 제안 |
| `ingest_obsidian()` | 수동 | Paul/Claude | Vault 전체 ingestion |
| `visualize()` | 수동 | Paul/Claude | 그래프 HTML 생성 |

---

## 7. 온톨로지 타입 참조

### 노드 26종
**핵심**: Decision, Failure, Pattern, Identity, Preference, Goal, Insight, Question, Metaphor, Connection, Evolution, Breakthrough
**시스템**: SystemVersion, Experiment, Tool, Framework, Principle, Workflow, AntiPattern, Project, Tension, Narrative, Skill, Agent
**메타**: Conversation, Unclassified

### 관계 33종
**인과**: led_to, caused_by, resolved_by
**생명주기**: evolves_from, replaces, strengthens, absorbed_into, deprecated_by, born_from, survived
**구조**: part_of, instance_of, belongs_to, extends, showcases, governed_by, composed_of
**의미**: contradicts, supports, connects_with, analogous_to
**검증**: validated_by, violated_by, corrected_by, disproved_by
**출처**: extracted_from, inspired_by
**Paul 고유**: reinforces_mutually, parallel_with, converges_at, diverges_from
**시간**: preceded_by, succeeded_by

---

## 8. 오케스트레이션 연동

### SessionStart → 외부 메모리 컨텍스트 자동 로드
```
session-start.sh
  └─ session_context.py 호출
     ├─ 최근 Decision 3개
     ├─ 미해결 Question 3개
     ├─ 최근 Failure 2개
     └─ 최근 Insight 2개
     → 세션 시작 브리핑에 포함 (~200토큰)
```

### compressor (세션 종료) → save_session()
```
compressor 10단계:
  1~9. 기존 아카이브 (session-summary, LOG, STATE 등)
  10. save_session() 데이터 전달 → lead agent가 MCP 호출
      → 세션 요약/결정/미결을 외부 메모리에 구조화 저장
```

### orch-state → query_memory.py
```
orch-state 수집 단계:
  ├─ git log + git status (기존)
  ├─ STATE.md (기존)
  └─ query_memory.py (신규)
     ├─ "최근 결정" --type Decision
     └─ "막힌 것 실패" --type Failure
     → 과거 세션의 결정/실패 패턴 참조
```

### CLI 래퍼 스크립트 (에이전트용)
에이전트는 MCP 도구 직접 호출 불가 → Bash로 CLI 래퍼 호출:
```bash
# 메모리 검색
python3 /c/dev/01_projects/06_mcp-memory/scripts/query_memory.py "검색어"
python3 /c/dev/01_projects/06_mcp-memory/scripts/query_memory.py "검색어" --type Decision --top_k 3

# 세션 컨텍스트 (session-start.sh가 자동 호출)
python3 /c/dev/01_projects/06_mcp-memory/scripts/session_context.py
python3 /c/dev/01_projects/06_mcp-memory/scripts/session_context.py orchestration
```

---

## 9. 파일 구조

```
/c/dev/01_projects/06_mcp-memory/
├── docs/
│   ├── 01-design.md         # 설계 문서 (원본)
│   └── 02-workflow.md        # 이 문서
├── server.py                 # MCP 진입점 (7 tools)
├── config.py                 # 설정
├── ontology/
│   ├── schema.yaml           # 26 types + 33 relations
│   └── validators.py         # 타입 검증 + 추천
├── storage/
│   ├── sqlite_store.py       # SQLite + FTS5(trigram)
│   ├── vector_store.py       # ChromaDB
│   └── hybrid.py             # RRF 3중 검색
├── embedding/
│   └── openai_embed.py       # text-embedding-3-large
├── graph/
│   └── traversal.py          # NetworkX
├── ingestion/
│   ├── chunker.py            # 마크다운 → 청크
│   └── obsidian.py           # Vault 순회 + 증분
├── tools/                    # MCP 도구 7개
├── scripts/
│   ├── safety_net.py         # SessionEnd 건전성 체크
│   ├── session_context.py    # SessionStart 메모리 컨텍스트
│   ├── query_memory.py       # 에이전트용 검색 CLI
│   ├── ontology_review.py    # 온톨로지 건강 리포트
│   └── dashboard.py          # 대시보드 HTML 생성
└── data/                     # .gitignore (자동 생성)
    ├── memory.db
    ├── chroma/
    └── graph.html
```
