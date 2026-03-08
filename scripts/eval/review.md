# Goldset Relevant IDs 리뷰
> 각 쿼리별로 현재 gold(G)와 새 후보를 비교.
> **pick**: relevant_ids에 넣을 노드를 골라주세요.
> **현재 gold가 맞으면 그대로, 아니면 새 후보에서 교체.**

---

## q051: git diff 결과를 보고 영향받는 테스트만 골라 최소 테스트셋을 만드는 절차는 뭐였지?
**기대 타입**: Workflow | **난이도**: easy | **notes**: Workflow L1 — 변경 파일 기반 최소 테스트셋 생성 절차

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 1413 | Principle | 3 | gold | git diff 검사로 버그·보안·타입·논리 이슈만 보고하는 코드리뷰 지침 |
| G | 378 | Principle | 3 | gold | AI 설계의 3가지 핵심 원칙: 기선 최소화, 오프로딩, 계층적 위임 |
| G | 181 | Principle | 3 | gold | 컨텍스트를 통화로 보고 토큰 비용 최적화하는 오케스트레이션 설계 원칙 |
| g | 1370 | Principle | 3 | also | 지식 추출 전 전체 맥락 파악과 추출 후 자체 검증을 통한 정확성 확보 원칙 |
| g | 167 | ? | ? | also |  |

### Type-Filtered 새 후보 (10개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 56 | Workflow | 1 | vec:Workflow | Obsidian diff 생성 및 메타 블록 추가 워크플로우 |
| ? | 109 | Workflow | ? | vec:Workflow |  |
| ? | 110 | Workflow | ? | vec:Workflow |  |
| ? | 112 | Workflow | ? | vec:Workflow |  |
| ? | 119 | Workflow | 1 | vec:Workflow | Obsidian 상태 추적 및 Git 로그 확인 워크플로우 |
| ? | 122 | Workflow | 1 | vec:Workflow | 구현 완료 후 테스트 범위 결정 워크플로우 |
| ? | 126 | Workflow | 1 | vec:Workflow | Worktree 환경에서 독립적인 작업을 시작하기 위한 실행 조건 정의 |
| ? | 138 | Workflow | 1 | vec:Workflow | GitHub INBOX에서 TODO로 항목 이동하는 일일 동기화 워크플로우 |
| ? | 4142 | Workflow | 1 | vec:Workflow | multi-source 파이프라인 구현 플랜(Phase1 YouTube → Phase5 GitHub Actions), 총 11개 태스크 |
| ? | 4236 | Workflow | 1 | vec:Workflow | 주제를 여러 독립 세션으로 나누고 오케스트레이터가 결과를 읽어 통합 보고서와 다음 심화 프롬프트를 만드는 멀티세션 아이디에이션 워크플로우다. 이 과정을 라운드 단위로 반복해 연결점과 충돌을 체계적으로 정리한다. |

### 기타 후보 (상위 5개 / 전체 50개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 71 | Insight | 2 | fts | FTS5 트라이그램 토크나이저는 3자 이상만 매칭하므로 2글자 한글 검색은 벡터검색으로 보완 |
| ? | 73 | Preference | 1 | fts | Paul의 작업 선호는 PowerShell에서 직접 실행하고 데이터 흐름을 시각적으로 파악하는 쪽에 가깝다. 표보다는 대시보드와 그래프 기반 표현을 더 선호한다. |
| ? | 86 | Principle | ? | hybrid |  |
| ? | 121 | Skill | 1 | fts | 변경 파일의 최소 테스트셋 추출 능력 |
| ? | 123 | Workflow | 2 | fts | 변경 파일로부터 영향 범위를 추적해 최소 테스트셋을 도출하는 절차다. diff 추출, import/export 분석, 테스트 매핑 후 JSON으로 결과를 출력한다. |

---

## q052: 배포 전에 TypeScript 에러, console.log, localhost 하드코딩, git status를 점검하는 배포 체인은 어떻게 되어 있지?
**기대 타입**: Workflow | **난이도**: medium | **notes**: Workflow L1 — 배포 자동화 체크리스트

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 1413 | Principle | 3 | gold | git diff 검사로 버그·보안·타입·논리 이슈만 보고하는 코드리뷰 지침 |
| G | 1526 | Principle | 3 | gold | 버그·보안·성능·가독성 중심의 코드/시스템 검증 체크리스트 |
| G | 4035 | Principle | 3 | gold | Git 작업 및 로컬 규칙 가이드라인: 브랜치에서만 커밋, 공유 컨텍스트 확인, 절대 경로 금지 |
| g | 1668 | Principle | 3 | also | 포트폴리오 기술 스택 기준: package.json 확인, 기존으로 해결 우선, 프로젝트 스타일 준수 |
| g | 1325 | Principle | 3 | also | 에이전트 팀 구현 시 데이터 수집-보존, 시간대 표준화, 도구 설치 가이드 원칙 |

### Type-Filtered 새 후보 (10개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 109 | Workflow | ? | vec:Workflow |  |
| ? | 112 | Workflow | ? | vec:Workflow |  |
| ? | 118 | Workflow | 1 | vec:Workflow | 프로젝트 시작 전 현재 상태를 파악하는 선행 작업 프로세스 |
| ? | 119 | Workflow | 1 | vec:Workflow | Obsidian 상태 추적 및 Git 로그 확인 워크플로우 |
| ? | 126 | Workflow | 1 | vec:Workflow | Worktree 환경에서 독립적인 작업을 시작하기 위한 실행 조건 정의 |
| ? | 134 | Workflow | 1 | vec:Workflow | Claude와 Opus 기반 다단계 워크플로우: 구현→배포→검증→디스패치→아카이브→세션전환 |
| ? | 138 | Workflow | 1 | vec:Workflow | GitHub INBOX에서 TODO로 항목 이동하는 일일 동기화 워크플로우 |
| ? | 153 | Workflow | 1 | vec:Workflow | Obsidian-Claude 통합 워크플로우: 구현→배포→검증→디스패치→압축의 6단계 자동화 파이프라인 |
| ? | 171 | Workflow | 1 | vec:Workflow | Obsidian 워크플로우 자동화 파이프라인 개선 및 메모리 관리 최적화 |
| ? | 4142 | Workflow | 1 | vec:Workflow | multi-source 파이프라인 구현 플랜(Phase1 YouTube → Phase5 GitHub Actions), 총 11개 태스크 |

### 기타 후보 (상위 5개 / 전체 49개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 180 | SystemVersion | 1 | fts | 스킬 수를 14개에서 9개로 줄이면서 중복 기능을 정리하고 호출 비용을 낮춘 최적화 단계다. disable-model-invocation 전면 적용과 명령어 정비를 통해 토큰 사용량도 절감했다. |
| ? | 183 | SystemVersion | 1 | fts | orchestration 프로젝트 v업데이트: 체인 중간결과 오프로딩, pre/post compact hooks, 세션 목표 표시 추가 |
| ? | 184 | SystemVersion | 1 | fts | orchestration 프로젝트 시스템 버전 업데이트: 토큰 절감과 문서 구조 최적화 |
| ? | 185 | Principle | 3 | fts | 오브시디언 기반 오케스트레이션의 컨텍스트 관리 및 컴팩트 전략 |
| ? | 186 | SystemVersion | 1 | fts | orchestration 시스템 v3.3: CLI 통합, 검증 장벽, 메타데이터 강제화 |

---

## q053: meta-orchestrator는 세션 시작 시 무엇을 읽고 어떤 팀을 활성화할지 어떻게 판단했지?
**기대 타입**: Agent, Workflow | **난이도**: medium | **notes**: Agent/Workflow L1 — 메타 오케스트레이터의 입력과 판단 로직

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 1528 | Principle | 3 | gold | 세션 목표 우선·실패 보존·URL 기반 복원 압축을 포함한 오케스트레이션 규칙 |
| G | 151 | Principle | 3 | gold | 200K 토큰 컨텍스트 효율성을 위한 세션별 목표 관리 및 컴팩트화 전략 |
| G | 132 | Principle | 3 | gold | 200K 토큰 예산 내에서 세션별 목표 관리와 컨텍스트 압축 전략 |
| g | 1302 | Principle | 3 | also | 팀 오케스트레이션의 암묵지: 브랜치 관리, 시간대 규약, 에이전트 스폰 결정권 |
| g | 188 | Principle | 3 | also | Claude 중심 설계: 외부 도구는 검증/추출, LLM별 용도 구분으로 효율성 극대화 |

### Type-Filtered 새 후보 (20개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 91 | Workflow | ? | vec:Workflow |  |
| ? | 109 | Workflow | ? | vec:Workflow |  |
| ? | 118 | Workflow | 1 | vec:Workflow | 프로젝트 시작 전 현재 상태를 파악하는 선행 작업 프로세스 |
| ? | 126 | Workflow | 1 | vec:Workflow | Worktree 환경에서 독립적인 작업을 시작하기 위한 실행 조건 정의 |
| ? | 127 | Workflow | 1 | vec:Workflow | Obsidian 작업 흐름: 매개변수 기반 에이전트 오버라이드 및 컨텍스트 관리 |
| ? | 133 | Agent | 1 | vec:Agent | Claude 모델별 역할 분담: Haiku(상태/요약), Sonnet(탐색/분석), Opus(설계/검증) |
| ? | 134 | Workflow | 1 | vec:Workflow | Claude와 Opus 기반 다단계 워크플로우: 구현→배포→검증→디스패치→아카이브→세션전환 |
| ? | 140 | Agent | 1 | vec:Agent | 정밀 검증 전담 에이전트: diff 리뷰, 포맷 QA, git 히스토리 추적 |
| ? | 141 | Agent | 1 | vec:Agent | 코드 변경사항을 자동 추출·검증·리뷰하는 다목적 에이전트 |
| ? | 144 | Agent | 1 | vec:Agent | Obsidian-Gemini 통합 벌크 데이터 추출 에이전트 |

### 기타 후보 (상위 5개 / 전체 49개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 4 | Question | 0 | fts | 세션 토큰 낭비 문제 식별 및 해결 방안 모색 |
| ? | 9 | Question | 0 | fts | 세션 시작 시 7000-9000 토큰 낭비 원인 분석 및 최적화 전략 |
| ? | 29 | Workflow | 1 | fts | 일일 세션 템플릿: 날짜, 포커스, 로그 기록 구조화 |
| ? | 36 | Framework | 2 | fts | Obsidian 볼트의 계층적 구조 설계: 중앙 MOC 중심의 프로젝트 관리 시스템 |
| ? | 48 | Question | 0 | fts | 세션 토픽 자동감지를 통한 get_context 최적화 방법 |

---

## q054: tech-review-ops, ai-feedback-loop, daily-ops 세 팀을 어떤 역할로 나눴는지 정리한 항목은 뭐였지?
**기대 타입**: Agent | **난이도**: easy | **notes**: Agent L1 — 팀 구조와 역할 분담

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 810 | Identity | 3 | gold | 팀 구조의 리더십 역할, 시냅스 역할, 품질 게이트 메커니즘 정의 |
| G | 404 | Principle | 3 | gold | AI 시스템 설계의 4가지 핵심 원칙: 감소, 문서, 자동화, 단일 진실 공급원 |
| G | 2726 | Principle | 3 | gold | 조건을 설계해 참여자 행동을 유도하고 정성·정량으로 검증하는 경험 설계 원칙 |
| g | 1301 | Principle | 3 | also | 프로젝트 실행 전 3가지 검증 체크리스트: 상태확인, 근거명시, 지시구체성 |
| g | 2712 | Identity | 3 | also | 문제 해결력을 삶의 프로젝트로 삼아 생각을 연결하고 AI로 실행 가능한 다음 행동으로 정리하는 포트폴리오. |

### Type-Filtered 새 후보 (10개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 133 | Agent | 1 | vec:Agent | Claude 모델별 역할 분담: Haiku(상태/요약), Sonnet(탐색/분석), Opus(설계/검증) |
| ? | 140 | Agent | 1 | vec:Agent | 정밀 검증 전담 에이전트: diff 리뷰, 포맷 QA, git 히스토리 추적 |
| ? | 141 | Agent | 1 | vec:Agent | 코드 변경사항을 자동 추출·검증·리뷰하는 다목적 에이전트 |
| ? | 144 | Agent | 1 | vec:Agent | Obsidian-Gemini 통합 벌크 데이터 추출 에이전트 |
| ? | 152 | Agent | ? | vec:Agent |  |
| ? | 156 | Agent | ? | vec:Agent |  |
| ? | 157 | Agent | ? | vec:Agent |  |
| ? | 161 | Agent | ? | vec:Agent |  |
| ? | 197 | Agent | 1 | vec:Agent | 7개 신규 에이전트 추가로 오케스트레이션 시스템 확장 (16→23) |
| ? | 198 | Agent | 1 | vec:Agent | 3개 팀으로 구성된 오케스트레이션 에이전트 시스템 아키텍처 |

### 기타 후보 (상위 5개 / 전체 43개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 42 | Tool | 1 | fts | AI 도구 스택: Claude/GPT/Gemini/Perplexity의 역할 분담 및 접근 방식 |
| ? | 127 | Workflow | 1 | fts | Obsidian 작업 흐름: 매개변수 기반 에이전트 오버라이드 및 컨텍스트 관리 |
| ? | 135 | Principle | 3 | fts | Claude가 설계/결정권자, 외부 도구는 추출만 담당하는 에이전트 역할 분담 원칙 |
| ? | 138 | Workflow | 1 | fts | GitHub INBOX에서 TODO로 항목 이동하는 일일 동기화 워크플로우 |
| ? | 139 | Conversation | 0 | fts | Obsidian 동기화 시스템의 상태 메시지 포맷 정의 |

---

## q055: 할 일 목록을 보고 추가하고 완료 처리하면서 핸드폰 inbox까지 동기화하는 /todo 스킬은 뭐였지?
**기대 타입**: Skill | **난이도**: easy | **notes**: Skill L1 — 명령형 작업 관리 스킬

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 1311 | Principle | 3 | gold | 암묵지: Inbox.md 보존 및 daily-memo 브랜치 관리 원칙 |
| G | 181 | Principle | 3 | gold | 컨텍스트를 통화로 보고 토큰 비용 최적화하는 오케스트레이션 설계 원칙 |
| G | 219 | Principle | 3 | gold | 프로젝트 규칙과 모범 사례를 정의하는 지식 기준점 |
| g | 227 | Principle | 3 | also | Agent 작업 품질 보증을 위한 3단계 표준화 구조 원칙 |
| g | 1313 | Principle | 3 | also | 신규 항목 처리와 미분류 inbox 관리의 기본 원칙 |

### Type-Filtered 새 후보 (10개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 33 | Skill | 1 | vec:Skill | 개인 지식 그래프 관리를 위한 CLI 스킬과 프롬프트 생태계 |
| ? | 44 | Skill | 1 | vec:Skill | Claude 코드 시스템의 8가지 핵심 스킬 세트 및 워크플로우 관리 도구 모음 |
| ? | 55 | Skill | 1 | vec:Skill | Claude Code에서 특정 파일의 변경분만 추출하는 실행 조건 및 기법 |
| ? | 59 | Skill | 1 | vec:Skill | 코드 변경사항 검토 및 품질 관리를 위한 diff/PR 기반 리뷰 스킬 |
| ? | 95 | Skill | ? | vec:Skill |  |
| ? | 106 | Skill | ? | vec:Skill |  |
| ? | 114 | Skill | ? | vec:Skill |  |
| ? | 117 | Skill | 1 | vec:Skill | git 상태와 STATE.md를 파싱하여 1페이지 JSON 요약으로 변환 |
| ? | 125 | Skill | 1 | vec:Skill | Git worktree 설정을 위한 자동화된 오버라이드 파일 생성 기술 |
| ? | 136 | Skill | 1 | vec:Skill | GitHub daily-memo를 로컬 TODO.md와 양방향 동기화하는 스킬 |

### 기타 후보 (상위 5개 / 전체 49개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 22 | Principle | 3 | fts | AI 코딩 도구를 위한 내장 함수 외 추가 규칙 및 관례 정의 |
| ? | 28 | Project | 1 | fts | 6개 프로젝트 포트폴리오: 오케스트레이션, 포트폴리오, 기술리뷰, 일일메모 진행 중 |
| ? | 36 | Framework | 2 | fts | Obsidian 볼트의 계층적 구조 설계: 중앙 MOC 중심의 프로젝트 관리 시스템 |
| ? | 37 | Framework | 2 | fts | Obsidian 볼트의 핵심 추적 구조 및 설정 프레임워크 |
| ? | 56 | Workflow | 1 | fts | Obsidian diff 생성 및 메타 블록 추가 워크플로우 |

---

## q056: 세션 종료 후 daily memo를 동기화하는 실행 스킬이나 스크립트는 뭐였지?
**기대 타입**: Skill, Tool | **난이도**: easy | **notes**: Skill/Tool L1 — 메모 동기화 자동화

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 151 | Principle | 3 | gold | 200K 토큰 컨텍스트 효율성을 위한 세션별 목표 관리 및 컴팩트화 전략 |
| G | 3931 | Principle | 3 | gold | 세션 트랜스크립트(.jsonl) 영구 보존 — 온톨로지 재처리와 빈 recall() 대비 대체검색 보장 |
| G | 752 | Principle | 3 | gold | Claude Auto Memory: 세션 분석 → 임시 저장 → 수동 승격의 3단계 로컬 메모 시스템 |
| g | 132 | Principle | 3 | also | 200K 토큰 예산 내에서 세션별 목표 관리와 컨텍스트 압축 전략 |
| g | 188 | Principle | 3 | also | Claude 중심 설계: 외부 도구는 검증/추출, LLM별 용도 구분으로 효율성 극대화 |

### Type-Filtered 새 후보 (19개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 33 | Skill | 1 | vec:Skill | 개인 지식 그래프 관리를 위한 CLI 스킬과 프롬프트 생태계 |
| ? | 39 | Tool | 1 | vec:Tool | Obsidian Git 플러그인을 통한 10분 간격 자동 커밋/푸시 설정 |
| ? | 42 | Tool | 1 | vec:Tool | AI 도구 스택: Claude/GPT/Gemini/Perplexity의 역할 분담 및 접근 방식 |
| ? | 44 | Skill | 1 | vec:Skill | Claude 코드 시스템의 8가지 핵심 스킬 세트 및 워크플로우 관리 도구 모음 |
| ? | 54 | Skill | 1 | vec:Skill | diff-only: 설명 없이 순수 변경분만 출력하는 기술 |
| ? | 55 | Skill | 1 | vec:Skill | Claude Code에서 특정 파일의 변경분만 추출하는 실행 조건 및 기법 |
| ? | 95 | Skill | ? | vec:Skill |  |
| ? | 101 | Tool | ? | vec:Tool |  |
| ? | 104 | Tool | ? | vec:Tool |  |
| ? | 106 | Skill | ? | vec:Skill |  |

### 기타 후보 (상위 5개 / 전체 40개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 4 | Question | 0 | fts | 세션 토큰 낭비 문제 식별 및 해결 방안 모색 |
| ? | 9 | Question | 0 | fts | 세션 시작 시 7000-9000 토큰 낭비 원인 분석 및 최적화 전략 |
| ? | 29 | Workflow | 1 | fts | 일일 세션 템플릿: 날짜, 포커스, 로그 기록 구조화 |
| ? | 48 | Question | 0 | fts | 세션 토픽 자동감지를 통한 get_context 최적화 방법 |
| ? | 59 | Skill | 1 | fts | 코드 변경사항 검토 및 품질 관리를 위한 diff/PR 기반 리뷰 스킬 |

---

## q057: orchestration 프로젝트 구조와 핵심 경로를 정리한 프로젝트 개요는 뭐였지?
**기대 타입**: Project | **난이도**: easy | **notes**: Project L1 — 프로젝트 구조와 경로 정리

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 227 | Principle | 3 | gold | Agent 작업 품질 보증을 위한 3단계 표준화 구조 원칙 |
| G | 1290 | Identity | 3 | gold | orchestration과 portfolio 프로젝트의 브랜치 구조 및 KST 시간 기준, TODO.md 위치 정의 |
| G | 609 | Principle | 3 | gold | 토큰 효율성을 위한 5가지 핵심 전략: 재읽기 금지, 서브에이전트 활용, 묶음 처리, 경로 제한 |
| g | 1656 | Identity | 3 | also | 문제 해결을 삶의 프로젝트로 삼고 미학·공간·음악을 연결해 AI를 시스템으로 활용하는 정체성 |
| g | 3575 | ? | ? | also |  |

### Type-Filtered 새 후보 (10개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 15 | Project | 1 | vec:Project | 개인 지식그래프 엔진을 위한 4개 프로젝트 저장소 구조 정의 |
| ? | 19 | Project | ? | vec:Project |  |
| ? | 25 | Project | ? | vec:Project |  |
| ? | 28 | Project | 1 | vec:Project | 6개 프로젝트 포트폴리오: 오케스트레이션, 포트폴리오, 기술리뷰, 일일메모 진행 중 |
| ? | 81 | Project | ? | vec:Project |  |
| ? | 90 | Project | ? | vec:Project |  |
| ? | 92 | Project | ? | vec:Project |  |
| ? | 102 | Project | ? | vec:Project |  |
| ? | 165 | Project | 1 | vec:Project | Obsidian 전역 설정 프로젝트 - 모든 파일에 적용되는 루트 레벨 구성 |
| ? | 168 | Project | ? | vec:Project |  |

### 기타 후보 (상위 5개 / 전체 50개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 12 | SystemVersion | 1 | fts | Obsidian 기반 에이전트 시스템 버전 관리 및 메모리 구조 |
| ? | 21 | SystemVersion | 1 | fts | Obsidian-Gemini 시스템 버전 추적 및 메모리 관리 구조 |
| ? | 29 | Workflow | 1 | fts | 일일 세션 템플릿: 날짜, 포커스, 로그 기록 구조화 |
| ? | 30 | Project | 1 | fts | UI 레이아웃 실험 프로젝트: 미니멀/웜톤 디자인 시스템 탐구 |
| ? | 31 | Decision | 1 | fts | 포트폴리오 레이아웃과 tech-review 운영 방향에 관한 4가지 미결정 사항 |

---

## q058: 사용 중인 AI 도구를 역할과 접근 방식까지 나눠서 정리한 내용은 어디 있었지?
**기대 타입**: Tool | **난이도**: medium | **notes**: Tool L1 — 도구 선택 기준과 역할 배치

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 405 | Principle | 3 | gold | AI를 도구가 아닌 팀원으로 보고, 각 모델의 강점에 맞춰 역할을 분담하며 검증을 통해 신뢰를 구축하는 원칙 |
| G | 135 | Principle | 3 | gold | Claude가 설계/결정권자, 외부 도구는 추출만 담당하는 에이전트 역할 분담 원칙 |
| G | 600 | Identity | 3 | gold | 13개 활성화 플러그인으로 구성된 개발 워크플로우 및 설계 도구 모음 |
| g | 148 | Principle | 3 | also | 프로젝트 conductor 구조를 통한 체계적 개발 관리 원칙 |
| g | 84 | ? | ? | also |  |

### Type-Filtered 새 후보 (9개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 39 | Tool | 1 | vec:Tool | Obsidian Git 플러그인을 통한 10분 간격 자동 커밋/푸시 설정 |
| ? | 42 | Tool | 1 | vec:Tool | AI 도구 스택: Claude/GPT/Gemini/Perplexity의 역할 분담 및 접근 방식 |
| ? | 101 | Tool | ? | vec:Tool |  |
| ? | 104 | Tool | ? | vec:Tool |  |
| ? | 116 | Tool | 1 | vec:Tool | Obsidian 플러그인/워크플로우 검증을 위한 JSON 출력 스키마 |
| ? | 194 | Tool | 1 | vec:Tool | Live-context 자동화 도구: 세션 시작 스크립트와 로그 트리밍 시스템 |
| ? | 4155 | Tool | 1 | vec:Tool | YouTube, Twitter 멀티소스 기반 일일 뉴스 수집 파이프라인 완성 |
| ? | 4188 | Tool | 1 | vec:Tool | Gmail MCP 도구의 GCP OAuth 인증 파일 경로 및 자동 생성 규칙 |
| ? | 4277 | Tool | 1 | vec:Tool | Codex CLI fast_mode: stable feature flag, 기본값 true. 별도 --enable 불필요. codex features list로 확인 가능. --f |

### 기타 후보 (상위 5개 / 전체 53개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 13 | Principle | 3 | fts | 불확실한 상황에서는 보류하고 이유를 명시하는 원칙 |
| ? | 14 | Principle | 3 | fts | Git 워크플로우: 명확한 커밋 메시지, force push 금지, STATE.md 자동 동기화 |
| ? | 22 | Principle | 3 | fts | AI 코딩 도구를 위한 내장 함수 외 추가 규칙 및 관례 정의 |
| ? | 27 | Narrative | 0 | fts | 개인 개발 작업공간의 중앙 허브로, 프로젝트 조율과 지식 정리의 기초 |
| ? | 28 | Project | 1 | fts | 6개 프로젝트 포트폴리오: 오케스트레이션, 포트폴리오, 기술리뷰, 일일메모 진행 중 |

---

## q059: 컨텍스트 비대화를 막기 위해 병렬 독립 세션과 index 파일을 쓰는 패턴은 뭐였지?
**기대 타입**: Pattern | **난이도**: medium | **notes**: Pattern L2 — 컨텍스트 관리 패턴

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 222 | Principle | 3 | gold | 200K 토큰 예산 관리: 세션당 목표 설정, 임계값 기반 자동 압축 전략 |
| G | 378 | Principle | 3 | gold | AI 설계의 3가지 핵심 원칙: 기선 최소화, 오프로딩, 계층적 위임 |
| G | 756 | Principle | 3 | gold | 다중 AI 시스템에서 쓰기 권한을 Claude Code에만 부여하여 충돌 방지 및 추적성 확보 |
| g | 276 | Principle | 3 | also | Git 기반 상태 추적과 Claude Code 단일 쓰기 원칙으로 orchestration 시스템 통합 |
| g | 574 | Principle | 3 | also | Git을 진실의 원천으로 삼고 Claude Code만 쓰기, Obsidian은 읽기 전용으로 운영하는 orchestration 시스템 원칙 |

### Type-Filtered 새 후보 (10개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 72 | Pattern | 2 | vec:Pattern | Windows Python에서 한글 출력 시 cp949 인코딩 오류 해결 방법 |
| ? | 3999 | Pattern | 2 | vec:Pattern | mcp-memory의 실제 경로는 /c/dev/01_projects/06_mcp-memory/ — 문서 갱신 필요 |
| ? | 4049 | Pattern | 2 | vec:Pattern | Paul↔Claude 상호작용 기반 의미망 성장 순환: Signal→패턴 승격→Principle→제안→Insight 반복 |
| ? | 4076 | Pattern | 2 | vec:Pattern | 병렬 서브에이전트로 모듈 동시 수정 패턴(2 Sonnet 에이전트 + 메인 세션) 효과 확인 |
| ? | 4092 | Pattern | 2 | vec:Pattern | checkpoint 실행 전 다른 pane의 mcp-memory 작업 여부 확인 필요, DB 동시 쓰기 충돌 가능. |
| ? | 4119 | Signal | 1 | vec:Pattern | 컨텍스트를 각 페인에 1:1로 고정해 여러 컨텍스트를 병렬로 유지하는 워크스페이스 패턴 |
| ? | 4120 | Signal | 1 | vec:Pattern | 마찰 제거 집착: 모든 접근을 단축키로 만들어 생각과 행동 간격을 최소화하는 설계 원칙 |
| ? | 4121 | Signal | 1 | vec:Pattern | 모든 메모에 날짜·시간 자동 삽입해 생각 발생 시점을 기록하는 시간 축 추적 습관 |
| ? | 4235 | Pattern | 2 | vec:Pattern | 컨텍스트 비대화를 막기 위해 독립 세션을 병렬로 운영하고, 각 세션이 한 줄 인덱스 파일을 유지한 뒤 compact 후 index만 읽고 재개하는 패턴이다. 생각을 머릿속이 아니라 파일에 외부화하는 것이 핵심이다. |
| ? | 4280 | Pattern | 2 | vec:Pattern | Sonnet 대규모 구현 위임 패턴: (1) 상세 설계서(코드 diff 포함) 작성 (2) dangerously-skip-permissions + auto 모드 (3) Sonnet |

### 기타 후보 (상위 5개 / 전체 54개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 4 | Question | 0 | fts | 세션 토큰 낭비 문제 식별 및 해결 방안 모색 |
| ? | 9 | Question | 0 | fts | 세션 시작 시 7000-9000 토큰 낭비 원인 분석 및 최적화 전략 |
| ? | 20 | Principle | ? | hybrid |  |
| ? | 29 | Workflow | 1 | fts | 일일 세션 템플릿: 날짜, 포커스, 로그 기록 구조화 |
| ? | 36 | Framework | 2 | fts | Obsidian 볼트의 계층적 구조 설계: 중앙 MOC 중심의 프로젝트 관리 시스템 |

---

## q060: dev 볼트 구조를 계층적으로 설명한 프레임워크 문서는 뭐였지?
**기대 타입**: Framework | **난이도**: medium | **notes**: Framework L2 — 볼트 구조 프레임워크

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 378 | Principle | 3 | gold | AI 설계의 3가지 핵심 원칙: 기선 최소화, 오프로딩, 계층적 위임 |
| G | 35 | Identity | 3 | gold | C:\dev 디렉토리를 Obsidian 볼트로 사용하는 개인 지식 관리 시스템 |
| G | 758 | Principle | 3 | gold | 토큰 효율성을 위해 CLAUDE.md를 계층화하여 매 턴 오버헤드 95% 감소 |
| g | 3367 | Principle | 3 | also | Monet-lab용 타이포그래피 스케일: 폰트, 크기, 웨이트, 트래킹 규격 가이드 |
| g | 164 | ? | ? | also |  |

### Type-Filtered 새 후보 (7개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 36 | Framework | 2 | vec:Framework | Obsidian 볼트의 계층적 구조 설계: 중앙 MOC 중심의 프로젝트 관리 시스템 |
| ? | 37 | Framework | 2 | vec:Framework | Obsidian 볼트의 핵심 추적 구조 및 설정 프레임워크 |
| ? | 38 | Framework | 2 | vec:Framework | 각 프로젝트별 독립적 git 저장소 관리 구조 및 GitHub 연결 현황 |
| ? | 120 | Framework | 2 | vec:Framework | Obsidian 메모 시스템의 상태 조회를 위한 JSON 출력 스키마 |
| ? | 124 | Framework | 2 | vec:Framework | 변경된 파일과 영향받은 테스트를 매핑하는 JSON 출력 스키마 |
| ? | 128 | Framework | 2 | vec:Framework | 작업 맥락을 정의하는 Git worktree 기반 개발 프레임워크 |
| ? | 192 | Framework | 2 | vec:Framework | 4개 팀 + 디스패치 허브 기반 리좀형 조직구조 및 크로스팀 유틸리티 |

### 기타 후보 (상위 5개 / 전체 34개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 12 | SystemVersion | 1 | fts | Obsidian 기반 에이전트 시스템 버전 관리 및 메모리 구조 |
| ? | 15 | Project | 1 | fts | 개인 지식그래프 엔진을 위한 4개 프로젝트 저장소 구조 정의 |
| ? | 21 | SystemVersion | 1 | fts | Obsidian-Gemini 시스템 버전 추적 및 메모리 관리 구조 |
| ? | 28 | Project | 1 | fts | 6개 프로젝트 포트폴리오: 오케스트레이션, 포트폴리오, 기술리뷰, 일일메모 진행 중 |
| ? | 29 | Workflow | 1 | fts | 일일 세션 템플릿: 날짜, 포커스, 로그 기록 구조화 |

---

## q061: portfolio에서 Obsidian 섹션 v4.0을 재작성하며 Hook, Architecture, Problem, Evolution, Lessons 구조로 바꾼 세션 서사는 뭐였지?
**기대 타입**: Narrative | **난이도**: medium | **notes**: Narrative L0 — 작업 맥락과 전개를 담은 세션 서사

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 227 | Principle | 3 | gold | Agent 작업 품질 보증을 위한 3단계 표준화 구조 원칙 |
| G | 188 | Principle | 3 | gold | Claude 중심 설계: 외부 도구는 검증/추출, LLM별 용도 구분으로 효율성 극대화 |
| G | 77 | ? | ? | gold |  |
| g | 2601 | Identity | 3 | also | 마크다운 STATE.md를 공유 통화로 삼아 AI 에이전트 오케스트레이션을 자동화한 시스템 설계 |
| g | 2638 | Insight | 2 | also | Obsidian 섹션 JSX 재구성: 섹션 순서 변경, Impact를 Hook으로 이동하고 중복 제거 |

### Type-Filtered 새 후보 (6개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 27 | Narrative | 0 | vec:Narrative | 개인 개발 작업공간의 중앙 허브로, 프로젝트 조율과 지식 정리의 기초 |
| ? | 52 | Narrative | 0 | vec:Narrative | 개인 지식 그래프를 위한 6개 프로젝트 구조 및 각 프로젝트의 목적 정의 |
| ? | 89 | Narrative | ? | vec:Narrative |  |
| ? | 98 | Narrative | ? | vec:Narrative |  |
| ? | 99 | Narrative | ? | vec:Narrative |  |
| ? | 100 | Narrative | ? | vec:Narrative |  |

### 기타 후보 (상위 5개 / 전체 51개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 4 | Question | 0 | fts | 세션 토큰 낭비 문제 식별 및 해결 방안 모색 |
| ? | 9 | Question | 0 | fts | 세션 시작 시 7000-9000 토큰 낭비 원인 분석 및 최적화 전략 |
| ? | 12 | SystemVersion | 1 | fts | Obsidian 기반 에이전트 시스템 버전 관리 및 메모리 구조 |
| ? | 15 | Project | 1 | fts | 개인 지식그래프 엔진을 위한 4개 프로젝트 저장소 구조 정의 |
| ? | 21 | SystemVersion | 1 | fts | Obsidian-Gemini 시스템 버전 추적 및 메모리 관리 구조 |

---

## q062: 해마와 신피질, 기억 공고화를 온톨로지 레이어와 승격 흐름에 대응시킨 연결은 어떻게 설명됐지?
**기대 타입**: Connection | **난이도**: hard | **notes**: Connection L2 — 뇌과학과 온톨로지 아키텍처 연결

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 4044 | Principle | 3 | gold | 온톨로지 레이어는 위계가 아닌 강도이며, 분석적 인터페이스 관점이다. |
| G | 4166 | Value | 4 | gold | 이질적 도메인의 개념 연결을 통해 새로운 의미 창출하는 AI 시스템 구현 |
| G | 758 | Principle | 3 | gold | 토큰 효율성을 위해 CLAUDE.md를 계층화하여 매 턴 오버헤드 95% 감소 |
| g | 3931 | Principle | 3 | also | 세션 트랜스크립트(.jsonl) 영구 보존 — 온톨로지 재처리와 빈 recall() 대비 대체검색 보장 |
| g | 132 | Principle | 3 | also | 200K 토큰 예산 내에서 세션별 목표 관리와 컨텍스트 압축 전략 |

### Type-Filtered 새 후보 (2개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 4046 | Connection | 2 | vec:Connection | 들뢰즈의 잠재성/현실화 개념이 Signal→Pattern→Principle 흐름과 동형임을 지적. |
| ? | 4209 | Connection | 2 | vec:Connection | 뇌과학의 기억 이론을 mcp-memory의 레이어와 연산에 대응시키는 매핑을 완성했다. 해마와 신피질, 기억 공고화, 수면 리플레이, Hebbian 학습, DMN 등을 시스템 동작과 연결해 확장된 인지 모델로 해석한다. |

### 기타 후보 (상위 5개 / 전체 47개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 38 | Framework | 2 | fts | 각 프로젝트별 독립적 git 저장소 관리 구조 및 GitHub 연결 현황 |
| ? | 70 | Insight | 2 | fts | Datasette 테이블뷰의 한계 극복을 위해 D3+Chart.js 기반 대시보드 필요 |
| ? | 73 | Preference | 1 | fts | Paul의 작업 선호는 PowerShell에서 직접 실행하고 데이터 흐름을 시각적으로 파악하는 쪽에 가깝다. 표보다는 대시보드와 그래프 기반 표현을 더 선호한다. |
| ? | 74 | Principle | ? | hybrid |  |
| ? | 127 | Workflow | 1 | fts | Obsidian 작업 흐름: 매개변수 기반 에이전트 오버라이드 및 컨텍스트 관리 |

---

## q063: IHS 허브 보호 설계에서 레이어별 human review 기준을 어떻게 나눴는지 찾고 싶다
**기대 타입**: Pattern, Framework | **난이도**: hard | **notes**: Pattern/Framework L2 — 허브 보호와 레이어별 검토 규칙

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 1365 | Principle | 3 | gold | tech-review 콘텐츠 품질 향상을 위한 교차 검증 및 구조적 개선 원칙 |
| G | 3849 | Principle | 3 | gold | 얼굴 ROI 기반 정량화와 환경 가중치 결합으로 즉시 실행 가능한 피부 관리 지침 생성 원칙 |
| G | 1289 | Principle | 3 | gold | 검증 원칙: 연관맵 기반 판단, 구체적 파일명 포함, 실행가능한 TODO |
| g | 4044 | Principle | 3 | also | 온톨로지 레이어는 위계가 아닌 강도이며, 분석적 인터페이스 관점이다. |
| g | 1526 | Principle | 3 | also | 버그·보안·성능·가독성 중심의 코드/시스템 검증 체크리스트 |

### Type-Filtered 새 후보 (17개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 36 | Framework | 2 | vec:Framework | Obsidian 볼트의 계층적 구조 설계: 중앙 MOC 중심의 프로젝트 관리 시스템 |
| ? | 37 | Framework | 2 | vec:Framework | Obsidian 볼트의 핵심 추적 구조 및 설정 프레임워크 |
| ? | 38 | Framework | 2 | vec:Framework | 각 프로젝트별 독립적 git 저장소 관리 구조 및 GitHub 연결 현황 |
| ? | 120 | Framework | 2 | vec:Framework | Obsidian 메모 시스템의 상태 조회를 위한 JSON 출력 스키마 |
| ? | 124 | Framework | 2 | vec:Framework | 변경된 파일과 영향받은 테스트를 매핑하는 JSON 출력 스키마 |
| ? | 128 | Framework | 2 | vec:Framework | 작업 맥락을 정의하는 Git worktree 기반 개발 프레임워크 |
| ? | 192 | Framework | 2 | vec:Framework | 4개 팀 + 디스패치 허브 기반 리좀형 조직구조 및 크로스팀 유틸리티 |
| ? | 3999 | Pattern | 2 | vec:Pattern | mcp-memory의 실제 경로는 /c/dev/01_projects/06_mcp-memory/ — 문서 갱신 필요 |
| ? | 4086 | Pattern | 2 | vec:Pattern | Codex CLI: config.toml에 기본 모델·model_reasoning_effort 설정 시 -m 불필요, 오버라이드는 에러 유발 가능. 프로필별 설정 지원 |
| ? | 4092 | Pattern | 2 | vec:Pattern | checkpoint 실행 전 다른 pane의 mcp-memory 작업 여부 확인 필요, DB 동시 쓰기 충돌 가능. |

### 기타 후보 (상위 5개 / 전체 50개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 3 | Decision | 1 | fts | 벡터와 키워드 검색을 결합한 하이브리드 검색 아키텍처 설계 |
| ? | 8 | Principle | 3 | fts | Claude가 설계 권한을 독점하며 외부 CLI는 데이터만 추출 |
| ? | 27 | Narrative | 0 | fts | 개인 개발 작업공간의 중앙 허브로, 프로젝트 조율과 지식 정리의 기초 |
| ? | 28 | Project | 1 | fts | 6개 프로젝트 포트폴리오: 오케스트레이션, 포트폴리오, 기술리뷰, 일일메모 진행 중 |
| ? | 31 | Decision | 1 | fts | 포트폴리오 레이아웃과 tech-review 운영 방향에 관한 4가지 미결정 사항 |

---

## q064: Signal을 Pattern으로 올릴 때 단순 반복 횟수 대신 압축이나 일반화로 판단해야 한다는 논의는 뭐였지?
**기대 타입**: Pattern, Framework | **난이도**: hard | **notes**: Pattern/Framework L2 — 승격 판단 기준과 패턴 인식

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 708 | Principle | 3 | gold | 압축 지시: 의도 보존, 고해상도 토큰화, 암묵적 지식 활용으로 프롬프트 효율화 |
| G | 1349 | Principle | 3 | gold | 에이전트 팀 구현의 핵심: 합의 신뢰, 불일치는 사용자 판단, 자동 반영 금지 |
| G | 404 | Principle | 3 | gold | AI 시스템 설계의 4가지 핵심 원칙: 감소, 문서, 자동화, 단일 진실 공급원 |
| g | 3202 | Principle | 3 | also | 오늘 글로벌 기술 동향 상위 3개만, 발표·게임체인저·엔지니어 관점으로 간결히 전달 |
| g | 2726 | Principle | 3 | also | 조건을 설계해 참여자 행동을 유도하고 정성·정량으로 검증하는 경험 설계 원칙 |

### Type-Filtered 새 후보 (17개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 36 | Framework | 2 | vec:Framework | Obsidian 볼트의 계층적 구조 설계: 중앙 MOC 중심의 프로젝트 관리 시스템 |
| ? | 37 | Framework | 2 | vec:Framework | Obsidian 볼트의 핵심 추적 구조 및 설정 프레임워크 |
| ? | 38 | Framework | 2 | vec:Framework | 각 프로젝트별 독립적 git 저장소 관리 구조 및 GitHub 연결 현황 |
| ? | 72 | Pattern | 2 | vec:Pattern | Windows Python에서 한글 출력 시 cp949 인코딩 오류 해결 방법 |
| ? | 120 | Framework | 2 | vec:Framework | Obsidian 메모 시스템의 상태 조회를 위한 JSON 출력 스키마 |
| ? | 124 | Framework | 2 | vec:Framework | 변경된 파일과 영향받은 테스트를 매핑하는 JSON 출력 스키마 |
| ? | 128 | Framework | 2 | vec:Framework | 작업 맥락을 정의하는 Git worktree 기반 개발 프레임워크 |
| ? | 192 | Framework | 2 | vec:Framework | 4개 팀 + 디스패치 허브 기반 리좀형 조직구조 및 크로스팀 유틸리티 |
| ? | 4049 | Pattern | 2 | vec:Pattern | Paul↔Claude 상호작용 기반 의미망 성장 순환: Signal→패턴 승격→Principle→제안→Insight 반복 |
| ? | 4076 | Pattern | 2 | vec:Pattern | 병렬 서브에이전트로 모듈 동시 수정 패턴(2 Sonnet 에이전트 + 메인 세션) 효과 확인 |

### 기타 후보 (상위 5개 / 전체 48개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 172 | Decision | 1 | fts | Obsidian AUTOCOMPACT 임계값 50%→75%로 상향, 과도한 컴팩트 방지 |
| ? | 185 | Principle | 3 | fts | 오브시디언 기반 오케스트레이션의 컨텍스트 관리 및 컴팩트 전략 |
| ? | 222 | Principle | 3 | fts | 200K 토큰 예산 관리: 세션당 목표 설정, 임계값 기반 자동 압축 전략 |
| ? | 227 | Principle | 3 | hybrid | Agent 작업 품질 보증을 위한 3단계 표준화 구조 원칙 |
| ? | 239 | Narrative | 0 | fts | 2026년 2월-3월 orchestration 프로젝트 세션별 생산성 메트릭 및 병목 분석 |

---

## q065: E14 전체 배치가 100% 실패했던 직접 원인과 거기서 얻은 교훈은 뭐였지?
**기대 타입**: Failure | **난이도**: easy | **notes**: Failure L1 — 배치 실패 원인 분석

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 1301 | Principle | 3 | gold | 프로젝트 실행 전 3가지 검증 체크리스트: 상태확인, 근거명시, 지시구체성 |
| G | 236 | Principle | 3 | gold | 에이전트 성과 평가를 위한 5단계 효과성 척도 기준 |
| G | 35 | Identity | 3 | gold | C:\dev 디렉토리를 Obsidian 볼트로 사용하는 개인 지식 관리 시스템 |
| g | 4173 | Insight | 2 | also | mcp-memory 진단 3건 재검토: 메타데이터 구조 오해, 관계 유형 분류 오류, E14 미실행 근본원인 파악 |
| g | 4067 | Insight | 2 | also | 심층 코드리뷰에서 Section7 외 20개 리스크 발견 — C4-C8 우선(스키마 마이그레이션, 충돌해소, 원자성, ChromaDB 동시성, 신규노드 판별) |

### Type-Filtered 새 후보 (10개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 4110 | Failure | 1 | vec:Failure | 03 How I Build 섹션 라벨 누락 및 Obsidian TOC 항목 없음 버그 발견 후 수정 완료 |
| ? | 4143 | Failure | 1 | vec:Failure | Warp 재시작 시 snapshot-*.md가 비어 세션 복구 불가 — PreCompact hook이 템플릿만 생성하고 Claude로 채워지지 않음 |
| ? | 4149 | Failure | 1 | vec:Failure | Twitter Playwright 스크래핑에서 headless 환경의 셀렉터 미매칭 문제 진단 중 |
| ? | 4150 | Failure | 1 | vec:Failure | GPT null 반환 시 dict.get() 기본값이 무시되는 버그, 방어 코드로 수정 필요 |
| ? | 4172 | Failure | 1 | vec:Failure | 진행바 버그: continue 시 카운터 미업데이트, finally 블록으로 수정 |
| ? | 4212 | Failure | 1 | vec:Failure | relation_extractor에서 re import가 빠져 Anthropic API 응답 파싱이 전면 실패했다. 기본 의존성 누락이 E14 전체 배치 실패로 이어진 대표적 사례다. |
| ? | 4220 | Failure | 1 | vec:Failure | enrichment 결과가 검증 없이 즉시 커밋되면 오염된 임베딩이 검색과 Hebbian 강화에 재투입되어 의미적 피드백 루프를 만든다는 점을 확인했다. 이를 막기 위해 임베딩 유사도 기반 롤백과 correction_log 기록이 필요하다. |
| ? | 4243 | Failure | 1 | vec:Failure | 오케스트레이터 통합 중에 범용 프롬프트를 세션에 보내는 바람에 실제 소스 수정과 커밋이 발생했고, 이를 되돌리는 데 복구 비용이 들었다. 아이디에이션 세션은 반드시 오케스트레이터가 만든 구체 프롬프트로만 제어해야 한다는 실패 사례다. |
| ? | 4245 | Failure | 1 | vec:Failure | 멀티세션 워크플로우에서는 각 라운드 결과를 먼저 통합하고 다음 프롬프트를 생성한 뒤에야 세션에 전달해야 한다. 이 순서를 건너뛰면 단계 혼동으로 사고가 발생한다는 교훈이다. |
| ? | 4105 | ? | ? | vec:Failure |  |

### 기타 후보 (상위 5개 / 전체 42개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 9 | Question | 0 | fts | 세션 시작 시 7000-9000 토큰 낭비 원인 분석 및 최적화 전략 |
| ? | 44 | Skill | 1 | fts | Claude 코드 시스템의 8가지 핵심 스킬 세트 및 워크플로우 관리 도구 모음 |
| ? | 64 | Decision | 1 | fts | MCP Memory 프로젝트를 01_projects/06_mcp-memory로 재구조화 |
| ? | 73 | Preference | 1 | fts | Paul의 작업 선호는 PowerShell에서 직접 실행하고 데이터 흐름을 시각적으로 파악하는 쪽에 가깝다. 표보다는 대시보드와 그래프 기반 표현을 더 선호한다. |
| ? | 119 | Workflow | 1 | fts | Obsidian 상태 추적 및 Git 로그 확인 워크플로우 |

---

## q066: auto-compact 이후 자동 재실행이 안 된다는 실패 사례에서 확인한 한계는 뭐였지?
**기대 타입**: Failure | **난이도**: easy | **notes**: Failure L1 — 자동화 한계 발견

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 282 | Principle | 3 | gold | 200K 컨텍스트 관리 시스템: 42K 기준선에서 150K 자동압축까지의 단계별 임계값 및 오프로딩 전략 |
| G | 927 | Principle | 3 | gold | Obsidian vault 크기 관리를 위한 3단계 compact 임계값 전략 |
| G | 222 | Principle | 3 | gold | 200K 토큰 예산 관리: 세션당 목표 설정, 임계값 기반 자동 압축 전략 |
| g | 760 | Principle | 3 | also | 자동화는 최소한으로: 3가지 필수 hook만 유지, 나머지는 명시적 수동 명령으로 예측 가능성 확보 |
| g | 377 | Principle | 3 | also | LLM 컨텍스트 윈도우를 화폐처럼 관리하는 설계 원칙 |

### Type-Filtered 새 후보 (10개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 214 | Failure | 1 | vec:Failure | Obsidian Git 자동 푸시 간격 설정 미완료 - v2 잔여 작업 |
| ? | 4143 | Failure | 1 | vec:Failure | Warp 재시작 시 snapshot-*.md가 비어 세션 복구 불가 — PreCompact hook이 템플릿만 생성하고 Claude로 채워지지 않음 |
| ? | 4148 | Failure | 1 | vec:Failure | GitHub Actions에서 unstaged changes로 인한 pull --rebase 실패 해결 패턴 |
| ? | 4149 | Failure | 1 | vec:Failure | Twitter Playwright 스크래핑에서 headless 환경의 셀렉터 미매칭 문제 진단 중 |
| ? | 4172 | Failure | 1 | vec:Failure | 진행바 버그: continue 시 카운터 미업데이트, finally 블록으로 수정 |
| ? | 4179 | Failure | 1 | vec:Failure | GitHub Actions에서 git stash pop 실패: 변경사항 없을 때 exit 1 반환, `|| true`로 해결 |
| ? | 4218 | Failure | 1 | vec:Failure | Claude Code의 auto-compact는 컨텍스트 압축만 수행하고 사용자 메시지 없이 자동 재실행되지는 않는다. 따라서 자고 일어나면 완료되는 무인 실행 시나리오는 현재 불가능하다. |
| ? | 4220 | Failure | 1 | vec:Failure | enrichment 결과가 검증 없이 즉시 커밋되면 오염된 임베딩이 검색과 Hebbian 강화에 재투입되어 의미적 피드백 루프를 만든다는 점을 확인했다. 이를 막기 위해 임베딩 유사도 기반 롤백과 correction_log 기록이 필요하다. |
| ? | 4243 | Failure | 1 | vec:Failure | 오케스트레이터 통합 중에 범용 프롬프트를 세션에 보내는 바람에 실제 소스 수정과 커밋이 발생했고, 이를 되돌리는 데 복구 비용이 들었다. 아이디에이션 세션은 반드시 오케스트레이터가 만든 구체 프롬프트로만 제어해야 한다는 실패 사례다. |
| ? | 4279 | Failure | 1 | vec:Failure | FTS 리빌드 누락 실수: inject_synonyms.py로 key_concepts에 한국어 동의어 주입 후 FTS5 인덱스 rebuild를 안 하면 검색에 반영 안 됨. INS |

### 기타 후보 (상위 5개 / 전체 61개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 14 | Principle | 3 | fts | Git 워크플로우: 명확한 커밋 메시지, force push 금지, STATE.md 자동 동기화 |
| ? | 28 | Project | 1 | fts | 6개 프로젝트 포트폴리오: 오케스트레이션, 포트폴리오, 기술리뷰, 일일메모 진행 중 |
| ? | 39 | Tool | 1 | fts | Obsidian Git 플러그인을 통한 10분 간격 자동 커밋/푸시 설정 |
| ? | 43 | Principle | 3 | fts | Claude 중심 지식 그래프 운영의 4가지 핵심 원칙: 단일 진실, 권한 분리, 휘발성/영속성, 자원 효율 |
| ? | 46 | Failure | 1 | fts | FTS5 기본 토크나이저가 한글 처리 실패, 트라이그램으로 전환 |

---

## q067: semantic feedback loop가 어떻게 오염되는지 실제 경로를 검증한 실패 분석은 뭐였지?
**기대 타입**: Failure, Experiment | **난이도**: hard | **notes**: Failure/Experiment L1 — 검색 오염 경로 검증

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 1289 | Principle | 3 | gold | 검증 원칙: 연관맵 기반 판단, 구체적 파일명 포함, 실행가능한 TODO |
| G | 4165 | Philosophy | 4 | gold | 의지 없이 환경·규칙 설계로 체계적 문제해결, 유기적 변경가능성 확보 |
| G | 1334 | Principle | 3 | gold | 3단계 검증 체크리스트(Smart Brevity/내용보존/형식일관성)로 품질관리 |
| g | 1277 | Principle | 3 | also | 에이전트 팀 구현 시 라이브 컨텍스트 검증 및 맥락 위생 원칙 |
| g | 1657 | Principle | 3 | also | 사람의 의지 대신 행동을 유도하는 조건을 설계해 반복을 자동화하는 운영 원리 |

### Type-Filtered 새 후보 (11개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 189 | Experiment | 1 | vec:Experiment | Codex, Gemini, Opus 에이전트 3개월 검증 완료 - 모두 프로덕션 준비 완료 |
| ? | 4090 | Failure | 1 | vec:Failure | GitHub Actions/Vercel 빌드 실패: SYSTEM_ITEMS가 text 전용인데 list 분기(데드코드)로 TS2367/TS2339/TS7006 발생→분기 제거로 해 |
| ? | 4110 | Failure | 1 | vec:Failure | 03 How I Build 섹션 라벨 누락 및 Obsidian TOC 항목 없음 버그 발견 후 수정 완료 |
| ? | 4149 | Failure | 1 | vec:Failure | Twitter Playwright 스크래핑에서 headless 환경의 셀렉터 미매칭 문제 진단 중 |
| ? | 4150 | Failure | 1 | vec:Failure | GPT null 반환 시 dict.get() 기본값이 무시되는 버그, 방어 코드로 수정 필요 |
| ? | 4172 | Failure | 1 | vec:Failure | 진행바 버그: continue 시 카운터 미업데이트, finally 블록으로 수정 |
| ? | 4180 | Failure | 1 | vec:Failure | X.com headless 환경에서 DOM 렌더링 차단, GraphQL API 인터셉트로 전환 필요 |
| ? | 4220 | Failure | 1 | vec:Failure | enrichment 결과가 검증 없이 즉시 커밋되면 오염된 임베딩이 검색과 Hebbian 강화에 재투입되어 의미적 피드백 루프를 만든다는 점을 확인했다. 이를 막기 위해 임베딩 유사도 기반 롤백과 correction_log 기록이 필요하다. |
| ? | 4243 | Failure | 1 | vec:Failure | 오케스트레이터 통합 중에 범용 프롬프트를 세션에 보내는 바람에 실제 소스 수정과 커밋이 발생했고, 이를 되돌리는 데 복구 비용이 들었다. 아이디에이션 세션은 반드시 오케스트레이터가 만든 구체 프롬프트로만 제어해야 한다는 실패 사례다. |
| ? | 4279 | Failure | 1 | vec:Failure | FTS 리빌드 누락 실수: inject_synonyms.py로 key_concepts에 한국어 동의어 주입 후 FTS5 인덱스 rebuild를 안 하면 검색에 반영 안 됨. INS |

### 기타 후보 (상위 5개 / 전체 48개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 9 | Question | 0 | fts | 세션 시작 시 7000-9000 토큰 낭비 원인 분석 및 최적화 전략 |
| ? | 36 | Framework | 2 | fts | Obsidian 볼트의 계층적 구조 설계: 중앙 MOC 중심의 프로젝트 관리 시스템 |
| ? | 42 | Tool | 1 | fts | AI 도구 스택: Claude/GPT/Gemini/Perplexity의 역할 분담 및 접근 방식 |
| ? | 46 | Failure | 1 | fts | FTS5 기본 토크나이저가 한글 처리 실패, 트라이그램으로 전환 |
| ? | 61 | Skill | 1 | fts | 소프트웨어 회귀: 코드 변경으로 인한 기존 기능 파괴 및 호환성 문제 |

---

## q068: v3.3 전체 시스템 e2e 테스트 실험에서 1차와 2차 비교 결과는 어떻게 나왔지?
**기대 타입**: Experiment | **난이도**: medium | **notes**: Experiment L1 — 다단계 E2E 실험 결과

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 406 | Principle | 3 | gold | 7일 반복 개선과 E2E 테스트 기반 실용적 설계 철학 |
| G | 35 | Identity | 3 | gold | C:\dev 디렉토리를 Obsidian 볼트로 사용하는 개인 지식 관리 시스템 |
| G | 879 | Goal | 1 | gold | 24에이전트/14스킬/4팀/6체인/7훅/2CLI 전수 검증 e2e 테스트 플랜 |
| g | 921 | Insight | 2 | also | v3.3 시스템 e2e 테스트 통과: 26개 에이전트 완벽 작동, Opus의 가치는 숨겨진 결함 발견 |
| g | 1012 | Goal | 1 | also | v3.3 시스템 전체 E2E 테스트 및 검증 체인 설계 |

### 기타 후보 (상위 5개 / 전체 41개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 15 | Project | 1 | fts | 개인 지식그래프 엔진을 위한 4개 프로젝트 저장소 구조 정의 |
| ? | 30 | Project | 1 | fts | UI 레이아웃 실험 프로젝트: 미니멀/웜톤 디자인 시스템 탐구 |
| ? | 44 | Skill | 1 | fts | Claude 코드 시스템의 8가지 핵심 스킬 세트 및 워크플로우 관리 도구 모음 |
| ? | 52 | Narrative | 0 | fts | 개인 지식 그래프를 위한 6개 프로젝트 구조 및 각 프로젝트의 목적 정의 |
| ? | 119 | Workflow | 1 | fts | Obsidian 상태 추적 및 Git 로그 확인 워크플로우 |

---

## q069: Subagent-Driven Development로 UI Lab 07부터 10까지 구현한 실험 기록은 뭐였지?
**기대 타입**: Experiment | **난이도**: medium | **notes**: Experiment L1 — 서브에이전트 개발 실험

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 220 | Principle | 3 | gold | 프로젝트별 Git 브랜치 규칙 및 안전한 커밋 관행 |
| G | 222 | Principle | 3 | gold | 200K 토큰 예산 관리: 세션당 목표 설정, 임계값 기반 자동 압축 전략 |
| G | 151 | Principle | 3 | gold | 200K 토큰 컨텍스트 효율성을 위한 세션별 목표 관리 및 컴팩트화 전략 |
| g | 86 | ? | ? | also |  |
| g | 147 | Principle | 3 | also | Gemini 브랜치 기반 워크플로우: main 보호, 컨텍스트 동기화, 검증 후 푸시 |

### Type-Filtered 새 후보 (1개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 189 | Experiment | 1 | vec:Experiment | Codex, Gemini, Opus 에이전트 3개월 검증 완료 - 모두 프로덕션 준비 완료 |

### 기타 후보 (상위 5개 / 전체 53개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 15 | Project | 1 | fts | 개인 지식그래프 엔진을 위한 4개 프로젝트 저장소 구조 정의 |
| ? | 16 | Principle | 3 | fts | 파일 접근 범위와 재읽기 금지, Living Docs 갱신 의무를 정의한 작업 원칙이다. 빌드 산출물과 캐시성 디렉터리를 제외하고 변경 시 STATE.md와 CHANGELOG.md를 반드시 업데이트하도록 요구한다. |
| ? | 22 | Principle | 3 | hybrid | AI 코딩 도구를 위한 내장 함수 외 추가 규칙 및 관례 정의 |
| ? | 29 | Workflow | 1 | fts | 일일 세션 템플릿: 날짜, 포커스, 로그 기록 구조화 |
| ? | 30 | Project | 1 | fts | UI 레이아웃 실험 프로젝트: 미니멀/웜톤 디자인 시스템 탐구 |

---

## q070: 에이전트 수가 23에서 24로 바뀌고 스킬 수가 13에서 11로 조정된 진화 기록을 찾고 싶다
**기대 타입**: Evolution | **난이도**: medium | **notes**: Evolution L1 — 에이전트/스킬 구성 변화

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 2816 | Principle | 3 | gold | 엔터프라이즈는 역할 분리 다중 에이전트와 상위 코디네이터 기반 오케스트레이션·거버넌스가 필수 |
| G | 617 | Principle | 3 | gold | 오케스트레이션 시스템의 동시성 제어 및 에이전트 통신 원칙 |
| G | 3143 | Insight | 2 | gold | AI 에이전트 오케스트레이션이 미들웨어 경쟁력으로 부상 — 멀티에이전트 역량 수요 증가 |
| g | 3221 | Insight | 2 | also | 멀티에이전트 전환 가속으로 에이전트 오케스트레이션 레이어가 핵심 인프라로 부상 |
| g | 3141 | Pattern | 2 | also | Moltbook 환경에서 에이전트 간 위험 지침이 상호 증폭되는 패턴이 OpenClaw 사례로 실증됨 |

### Type-Filtered 새 후보 (2개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 191 | Evolution | 1 | vec:Evolution | orchestration v23→24: doc-syncer 신규 추가, 검증 강화, 9단계 파이프라인으로 확장 |
| ? | 193 | Evolution | 1 | vec:Evolution | 스킬 13개→11개로 정리, /dispatch 신규 추가 및 /morning 통합 강화 |

### 기타 후보 (상위 5개 / 전체 49개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 28 | Project | 1 | fts | 6개 프로젝트 포트폴리오: 오케스트레이션, 포트폴리오, 기술리뷰, 일일메모 진행 중 |
| ? | 33 | Skill | 1 | fts | 개인 지식 그래프 관리를 위한 CLI 스킬과 프롬프트 생태계 |
| ? | 44 | Skill | 1 | fts | Claude 코드 시스템의 8가지 핵심 스킬 세트 및 워크플로우 관리 도구 모음 |
| ? | 59 | Skill | 1 | fts | 코드 변경사항 검토 및 품질 관리를 위한 diff/PR 기반 리뷰 스킬 |
| ? | 136 | Skill | 1 | fts | GitHub daily-memo를 로컬 TODO.md와 양방향 동기화하는 스킬 |

---

## q071: 7일 동안 시스템이 v1.0에서 어떻게 진화했는지 요약한 기록은 뭐였지?
**기대 타입**: Evolution | **난이도**: medium | **notes**: Evolution L1 — 버전 진화 기록

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 43 | Principle | 3 | gold | Claude 중심 지식 그래프 운영의 4가지 핵심 원칙: 단일 진실, 권한 분리, 휘발성/영속성, 자원 효율 |
| G | 406 | Principle | 3 | gold | 7일 반복 개선과 E2E 테스트 기반 실용적 설계 철학 |
| G | 151 | Principle | 3 | gold | 200K 토큰 컨텍스트 효율성을 위한 세션별 목표 관리 및 컴팩트화 전략 |
| g | 3679 | ? | ? | also |  |
| g | 3745 | ? | ? | also |  |

### Type-Filtered 새 후보 (2개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 191 | Evolution | 1 | vec:Evolution | orchestration v23→24: doc-syncer 신규 추가, 검증 강화, 9단계 파이프라인으로 확장 |
| ? | 193 | Evolution | 1 | vec:Evolution | 스킬 13개→11개로 정리, /dispatch 신규 추가 및 /morning 통합 강화 |

### 기타 후보 (상위 5개 / 전체 36개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 29 | Workflow | 1 | fts | 일일 세션 템플릿: 날짜, 포커스, 로그 기록 구조화 |
| ? | 32 | Project | 1 | fts | HOW I AI 프로젝트: 맥락 기반 AI 설계 시스템 v4.0 및 진화 기록 |
| ? | 41 | SystemVersion | 1 | fts | 시스템 버전 관리: v1.0→v2.0 진화, Skills 확장 및 Obsidian Git 통합 |
| ? | 96 | Conversation | 0 | fts | 프로젝트 아카이브 정리: ai-config, monet-lab, portfolio 마이그레이션 기록 |
| ? | 103 | SystemVersion | ? | fts |  |

---

## q072: v2.1 구현 세션을 4개의 Claude Code 세션과 2개의 CLI로 나누기로 한 결정은 뭐였지?
**기대 타입**: Decision | **난이도**: easy | **notes**: Decision L1 — 멀티세션 역할 분담 결정

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 3813 | ? | ? | gold |  |
| G | 2696 | Principle | 3 | gold | v4.0 AI 워크플로우 설계 철학 — 최소화, 검증 우선, 단일 작성자 원칙 |
| G | 1488 | Principle | 3 | gold | LLM 오케스트레이션 원칙: Claude 단일 결정자, 추출형(JSON) 출력, 모델 역할 분담, 컨텍스트 예산 |
| g | 188 | Principle | 3 | also | Claude 중심 설계: 외부 도구는 검증/추출, LLM별 용도 구분으로 효율성 극대화 |
| g | 1579 | Principle | 3 | also | CLI별 컨텍스트 읽기 규칙과 출처 마커, 포트폴리오 브랜치 정책(master 사용) |

### Type-Filtered 새 후보 (10개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 4041 | Decision | 1 | vec:Decision | Claude가 Signal을 Pattern으로 승격하는 판단을 담당하도록 결정(대화 맥락 인지 장점). |
| ? | 4048 | Decision | 1 | vec:Decision | MCP 도구를 7→11개로 확장: analyze_signals, promote_node, get_becoming, inspect 추가; Claude가 5지점에서 의미 판단자 역할 |
| ? | 4062 | Decision | 1 | vec:Decision | Claude가 대화 맥락이 필요한 4개 필드(layer, primary_type, secondary_types, domains)의 실시간 분류 담당으로 확정; 나머지는 GPT가 비 |
| ? | 4088 | Decision | 1 | vec:Decision | claude/portfolio 브랜치에서 P1~P3 구조 변경 완료; PR#5174 검토 후 master 머지 결정 예정 |
| ? | 4154 | Decision | 1 | vec:Decision | GPT 70% / Claude 30% 분배 결정, Codex 배제로 enrichment 작업 최적화 |
| ? | 4226 | Decision | 1 | vec:Decision | 9개 AI의 deep research 결과를 통합해 747줄 분량의 ontology v2 문서를 완성했다. 분산 리서치를 하나의 설계 산출물로 수렴시킨 결정적 기록이다. |
| ? | 4229 | Decision | 1 | vec:Decision | 온톨로지 아이디에이션을 주제별로 4개 독립 세션으로 나누어 병렬적으로 수행하기로 했다. 마지막에는 오케스트레이터 세션이 각 결과를 통합한다. |
| ? | 4248 | Decision | 1 | vec:Decision | v2.1 구현을 위해 메인 오케스트레이터, 기능별 작업 세션, 검증용 CLI까지 포함한 6개 세션 구성을 확정했다. 역할을 명확히 나눠 병렬 구현과 분석을 동시에 돌리는 운영 설계다. |
| ? | 4255 | Decision | 1 | vec:Decision | v2.1에 대한 전면 리뷰가 3개 CLI와 3개 라운드 조합으로 수행되어 58개의 보고서가 생성되었다. 특히 Codex가 스키마 불일치를 치명 이슈로 포착해 교차 검증의 가치를 드러냈다. |
| ? | 4257 | Decision | 1 | vec:Decision | v2.1 리뷰 체계는 3개 CLI, 3개 라운드, 9개 카테고리를 조합한 매트릭스로 설계되었다. 여기에 핵심 E2E 시나리오와 마스터 플랜을 더해 리뷰 범위를 구조화했다. |

### 기타 후보 (상위 5개 / 전체 49개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 1 | Decision | 1 | fts | 외부 메모리를 MCP 서버로 구현하기로 결정 |
| ? | 4 | Question | 0 | fts | 세션 토큰 낭비 문제 식별 및 해결 방안 모색 |
| ? | 7 | Decision | 1 | fts | Orchestration v4.0 출시: Context as Currency 패러다임 도입으로 문맥 기반 가치 체계 구현 |
| ? | 9 | Question | 0 | fts | 세션 시작 시 7000-9000 토큰 낭비 원인 분석 및 최적화 전략 |
| ? | 15 | Project | 1 | fts | 개인 지식그래프 엔진을 위한 4개 프로젝트 저장소 구조 정의 |

---

## q073: 리뷰 아키텍처를 3 CLI x 3 Rounds x 9 Categories로 설계한 결정은 뭐였지?
**기대 타입**: Decision, Framework | **난이도**: medium | **notes**: Decision/Framework L1 — 리뷰 구조 설계 결정

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 849 | Identity | 3 | gold | Claude Opus 4.6이 중앙 의사결정자로 Gemini와 Codex CLI를 조율하는 v3.3 외부 CLI 아키텍처 |
| G | 135 | Principle | 3 | gold | Claude가 설계/결정권자, 외부 도구는 추출만 담당하는 에이전트 역할 분담 원칙 |
| G | 3813 | ? | ? | gold |  |
| g | 590 | Principle | 3 | also | 에이전트 역할별 LLM 모델 선택 기준: Haiku(저비용), Sonnet(중간), Opus(고비용) |
| g | 2696 | Principle | 3 | also | v4.0 AI 워크플로우 설계 철학 — 최소화, 검증 우선, 단일 작성자 원칙 |

### Type-Filtered 새 후보 (17개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 31 | Decision | 1 | vec:Decision | 포트폴리오 레이아웃과 tech-review 운영 방향에 관한 4가지 미결정 사항 |
| ? | 36 | Framework | 2 | vec:Framework | Obsidian 볼트의 계층적 구조 설계: 중앙 MOC 중심의 프로젝트 관리 시스템 |
| ? | 37 | Framework | 2 | vec:Framework | Obsidian 볼트의 핵심 추적 구조 및 설정 프레임워크 |
| ? | 38 | Framework | 2 | vec:Framework | 각 프로젝트별 독립적 git 저장소 관리 구조 및 GitHub 연결 현황 |
| ? | 66 | Decision | 1 | vec:Decision | MCP 메모리 시스템의 4단계 안전망 아키텍처 확정 결정 |
| ? | 93 | Decision | ? | vec:Decision |  |
| ? | 120 | Framework | 2 | vec:Framework | Obsidian 메모 시스템의 상태 조회를 위한 JSON 출력 스키마 |
| ? | 124 | Framework | 2 | vec:Framework | 변경된 파일과 영향받은 테스트를 매핑하는 JSON 출력 스키마 |
| ? | 128 | Framework | 2 | vec:Framework | 작업 맥락을 정의하는 Git worktree 기반 개발 프레임워크 |
| ? | 192 | Framework | 2 | vec:Framework | 4개 팀 + 디스패치 허브 기반 리좀형 조직구조 및 크로스팀 유틸리티 |

### 기타 후보 (상위 5개 / 전체 24개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 1 | Decision | 1 | fts | 외부 메모리를 MCP 서버로 구현하기로 결정 |
| ? | 28 | Project | 1 | fts | 6개 프로젝트 포트폴리오: 오케스트레이션, 포트폴리오, 기술리뷰, 일일메모 진행 중 |
| ? | 58 | Skill | 1 | fts | 보안·회귀·테스트 관점의 체크리스트 기반 코드 리뷰 방법론 |
| ? | 59 | Skill | 1 | fts | 코드 변경사항 검토 및 품질 관리를 위한 diff/PR 기반 리뷰 스킬 |
| ? | 122 | Workflow | 1 | fts | 구현 완료 후 테스트 범위 결정 워크플로우 |

---

## q074: Auto Memory 개선과 Cross-CLI .ctx 정리, Playwright MCP 활성화를 목표로 한 세션 목표는 뭐였지?
**기대 타입**: Goal | **난이도**: easy | **notes**: Goal L1 — 세션 목표 설정

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 132 | Principle | 3 | gold | 200K 토큰 예산 내에서 세션별 목표 관리와 컨텍스트 압축 전략 |
| G | 603 | Principle | 3 | gold | 대체 불가능한 경우만 MCP 서버 추가, 기존 도구 우선 활용 |
| G | 151 | Principle | 3 | gold | 200K 토큰 컨텍스트 효율성을 위한 세션별 목표 관리 및 컴팩트화 전략 |
| g | 222 | Principle | 3 | also | 200K 토큰 예산 관리: 세션당 목표 설정, 임계값 기반 자동 압축 전략 |
| g | 276 | Principle | 3 | also | Git 기반 상태 추적과 Claude Code 단일 쓰기 원칙으로 orchestration 시스템 통합 |

### Type-Filtered 새 후보 (2개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 4045 | Goal | 1 | vec:Goal | 현실의 나를 정밀히 모방하는 팔란티어급 온톨로지 결정체를 만드는 장기 목표 |
| ? | 4231 | Goal | 1 | vec:Goal | 현재 데이터셋으로 BCM, MDL, 베이지안 누적, 드리프트-확산 같은 모델을 직접 실험해보는 것이 목표다. 온톨로지 승격과 학습 메커니즘을 수학적 모델로 검증하려는 탐구 과제다. |

### 기타 후보 (상위 5개 / 전체 36개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 4 | Question | 0 | fts | 세션 토큰 낭비 문제 식별 및 해결 방안 모색 |
| ? | 9 | Question | 0 | fts | 세션 시작 시 7000-9000 토큰 낭비 원인 분석 및 최적화 전략 |
| ? | 29 | Workflow | 1 | fts | 일일 세션 템플릿: 날짜, 포커스, 로그 기록 구조화 |
| ? | 48 | Question | 0 | fts | 세션 토픽 자동감지를 통한 get_context 최적화 방법 |
| ? | 127 | Workflow | 1 | fts | Obsidian 작업 흐름: 매개변수 기반 에이전트 오버라이드 및 컨텍스트 관리 |

---

## q075: 반복 작업이 보이면 바로 단축키나 스크립트로 바꾸려는 습관이 관찰된 신호는 뭐였지?
**기대 타입**: Signal | **난이도**: medium | **notes**: Signal L1 — 마찰 제거와 자동화 집착이 드러난 관찰 신호

### 현재 Gold
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| G | 760 | Principle | 3 | gold | 자동화는 최소한으로: 3가지 필수 hook만 유지, 나머지는 명시적 수동 명령으로 예측 가능성 확보 |
| G | 2714 | Principle | 3 | gold | 환경과 규칙을 설계해 의지에 의존하지 않는 자동화된 사고·실행 구조 |
| G | 3931 | Principle | 3 | gold | 세션 트랜스크립트(.jsonl) 영구 보존 — 온톨로지 재처리와 빈 recall() 대비 대체검색 보장 |
| g | 3576 | ? | ? | also |  |
| g | 3728 | ? | ? | also |  |

### Type-Filtered 새 후보 (1개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 4126 | Signal | 1 | vec:Signal | 체크포인트·Obsidian·daily-memo 등 다중 소스 교차 검증이 온톨로지 신뢰도를 높여 Paul 모델 구축에 유리하다 |

### 기타 후보 (상위 5개 / 전체 58개)
| pick | ID | Type | Layer | Source | Summary |
|------|-----|------|-------|--------|----------|
| ? | 13 | Principle | 3 | fts | 불확실한 상황에서는 보류하고 이유를 명시하는 원칙 |
| ? | 16 | Principle | 3 | fts | 파일 접근 범위와 재읽기 금지, Living Docs 갱신 의무를 정의한 작업 원칙이다. 빌드 산출물과 캐시성 디렉터리를 제외하고 변경 시 STATE.md와 CHANGELOG.md를 반드시 업데이트하도록 요구한다. |
| ? | 27 | Narrative | 0 | fts | 개인 개발 작업공간의 중앙 허브로, 프로젝트 조율과 지식 정리의 기초 |
| ? | 36 | Framework | 2 | fts | Obsidian 볼트의 계층적 구조 설계: 중앙 MOC 중심의 프로젝트 관리 시스템 |
| ? | 37 | Framework | 2 | fts | Obsidian 볼트의 핵심 추적 구조 및 설정 프레임워크 |

---

