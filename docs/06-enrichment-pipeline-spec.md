# mcp-memory — 4-Model Enrichment Pipeline 상세 스펙

> **Status**: 설계 확정 (2026-03-04)
> **Author**: Paul + Claude (Opus 4.6)
> **의존**: 05-full-architecture-blueprint.md (Part 12에서 참조)
> **목적**: OpenAI Data Sharing 무료 토큰을 90% 활용하여 의미망을 매일 자동으로 성장시키는 파이프라인

---

## 1. 토큰 예산

### 1.1 OpenAI Data Sharing Program

Paul의 계정 상태 (2026-03-04 확인):
- **Enrolled**: "You're enrolled for complimentary daily tokens"
- **Data sharing**: Enabled for all projects
- **Credit balance**: ~$9 (비상금)
- **Tier**: 1-2 (개인 개발자)
- **리셋**: 매일 00:00 UTC (KST 09:00)

### 1.2 일일 토큰 한도

```
대형 모델 풀: 250,000 tokens/day
  사용 가능: gpt-5.2, gpt-5.1, gpt-5.1-codex, gpt-5,
             gpt-5-codex, gpt-5-chat-latest, gpt-4.1,
             gpt-4o, o1, o3

소형 모델 풀: 2,500,000 tokens/day
  사용 가능: gpt-5.1-codex-mini, gpt-5-mini, gpt-5-nano,
             gpt-4.1-mini, gpt-4.1-nano, gpt-4o-mini,
             o1-mini, o3-mini, o4-mini, codex-mini-latest
```

### 1.3 90% 예산 배분

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  소형 풀 (한도 2,500K → 목표 2,250K = 90%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  gpt-5-mini    │ Phase 1: 대량 enrichment      │ 1,800K
  o3-mini       │ Phase 2: 배치 추론            │   450K
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  대형 풀 (한도 250K → 목표 225K = 90%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  gpt-5.2       │ Phase 4: 심층 생성            │  100K
  o3            │ Phase 5: 깊은 추론            │   75K
  gpt-4.1       │ Phase 3: 정밀 검증            │   50K
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  + Codex CLI   │ Phase 6: 코드/프롬프트/온톨로지 검증 │ 별도
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 1.4 o3/o3-mini 추론 토큰 주의사항

o3 계열 모델은 내부 chain-of-thought 추론 토큰을 소비한다.
표면상 500 토큰 출력이지만 내부적으로 3,000-5,000 토큰 사용 가능.

```
o3 (대형): 표면 토큰의 3-5x → 75K 예산으로 실질 15-25회 호출
o3-mini (소형): 표면 토큰의 2-3x → 450K 예산으로 실질 150-200회 호출
```

token_counter에서 `usage.completion_tokens_details.reasoning_tokens`를 반드시 추적해야 함.

---

## 2. 4-Model 역할 배분

### 2.1 모델별 최적 작업

| 모델 | 풀 | 강점 | 배정 작업 |
|------|---|------|----------|
| **gpt-5-mini** | 소형 | 속도+비용 효율, 충분한 품질 | 대량 enrichment: summary, tags, facets, 관계 추출, embedding, 중복 탐지 |
| **o3-mini** | 소형 | 논리적 추론 (배치) | 모순 탐지, Assemblage 발견, 시간 체인 추론, edge 방향 추론 |
| **gpt-4.1** | 대형 | 안정성, 검증됨 | confidence < 0.5 재분류, 레이어 검증 |
| **gpt-5.2** | 대형 | 최상급 생성 능력 | L4-L5 분류, 성장 내러티브, 지식 공백 분석, 크로스도메인 해석 |
| **o3** | 대형 | 깊은 추론 (최상급) | 온톨로지 메타 검증, 이색적 접합 최종 판단, 승격 논증 |
| **Codex CLI** | 별도 | 코드 분석/생성 | 프롬프트 품질 검증, 파이프라인 코드 리뷰, 온톨로지 일관성 체크 |

### 2.2 왜 이 배분인가

**gpt-5-mini가 대량 작업을 맡는 이유:**
- 2.5M 풀에서 가장 최신 + 가장 높은 품질
- summary, tags 등은 "생성" 작업 → 추론 모델보다 생성 모델이 적합
- 배치 처리에서 속도 우위

**o3-mini가 배치 추론을 맡는 이유:**
- "이 두 노드가 모순인가?" = 논리적 판단 → 추론 모델이 우위
- Assemblage는 이질적 요소의 관계를 분석하는 추론 작업
- 시간 체인은 인과 순서 추론

**o3가 최종 판단을 맡는 이유:**
- 온톨로지 자체의 논리적 일관성 = 가장 어려운 추론
- "이색적 접합인가 우연인가" = 깊은 판단 필요
- Signal→Pattern 승격 논증 = 증거 기반 추론

**gpt-5.2가 심층 생성을 맡는 이유:**
- L4-L5 (Belief, Philosophy, Value, Axiom) = 추상 개념 이해 필요
- 성장 내러티브 = 서사 생성 능력 최상
- 지식 공백의 "왜" = 맥락적 이해 + 설명 생성

---

## 3. 25개 Enrichment 작업 상세

### 3.1 노드 단위 작업 (12개)

#### E1. summary 생성
```
입력: node.content (전문)
출력: 1줄 요약 (max 100자)
모델: gpt-5-mini
프롬프트: "다음 텍스트의 핵심을 1줄로 요약하라. 100자 이내."
용도: recall() 결과 표시, 대시보드 미리보기, embedding 품질 향상
저장: nodes.summary (신규 컬럼)
```

#### E2. key_concepts 추출
```
입력: node.content
출력: 핵심 개념 3-5개 (JSON array)
모델: gpt-5-mini
프롬프트: "다음 텍스트에서 핵심 개념 3-5개를 추출하라. 각 개념은 1-3단어."
용도: FTS5 검색 확장, 클러스터링 기반, 관계 추출 보조
저장: nodes.key_concepts (신규 컬럼, JSON)
```

#### E3. tags 확장
```
입력: node.content + 기존 tags
출력: 추가 태그 3-5개
모델: gpt-5-mini
프롬프트: "기존 태그를 참고하되 중복 없이 추가 태그 3-5개 생성. 검색에 유용한 것 위주."
용도: FTS5 검색 대폭 강화
저장: nodes.tags (기존 컬럼에 append)
```

#### E4. facets 매핑
```
입력: node.content + node.source + node.project
출력: Paul의 차원 1-3개
모델: gpt-5-mini (규칙 기반 1차 + GPT 보정)
가능 값: philosopher, developer, designer, writer, system-architect,
         researcher, aesthetician, educator, strategist
프롬프트: "이 텍스트가 Paul의 어떤 측면을 반영하는가?"
저장: nodes.facets (신규 컬럼, JSON array)
규칙 기반 우선:
  source에 ".claude/skills/" → ["developer"]
  content에 "미학|들뢰즈|철학|존재론" → ["philosopher"]
  content에 "포트폴리오|디자인|UI|UX" → ["designer"]
  content에 "에세이|글쓰기|서사" → ["writer"]
  나머지 → GPT 판단
```

#### E5. domains 감지
```
입력: node.content + node.project + node.source
출력: 관련 도메인 1-3개
모델: gpt-5-mini (규칙 기반 1차 + GPT 보정)
가능 값: orchestration, portfolio, tech-review, monet-lab,
         daily-memo, mcp-memory, philosophy, literature, art, general
프롬프트: "이 내용이 어떤 도메인에 관련되는가? 복수 가능."
저장: nodes.domains (신규 컬럼, JSON array)
규칙 기반 우선:
  project 필드가 있으면 해당 도메인 + GPT가 추가 도메인 감지
  예: project=orchestration이지만 content에 "포트폴리오" 언급
      → domains: ["orchestration", "portfolio"]  ← 크로스도메인!
```

#### E6. secondary_types 배정
```
입력: node.content + node.type (primary)
출력: 보조 타입 0-2개
모델: gpt-4.1 (대형 풀, 정확도 중요)
프롬프트: "이 노드의 주타입은 {type}이다. 보조 타입이 있다면? (최대 2개)
  보조 타입은 주타입과 다른 각도에서 이 내용을 설명하는 타입이어야 한다.
  없으면 빈 배열."
저장: nodes.secondary_types (신규 컬럼, JSON array)
```

#### E7. embedding_text 최적화
```
입력: summary + key_concepts + tags + facets + domains
출력: 임베딩용 최적화 텍스트 (150-200자)
모델: gpt-5-mini
프롬프트: "다음 요약, 개념, 태그를 결합하여 의미 검색에 최적화된
  자연스러운 텍스트를 생성하라. 150-200자."
용도: ChromaDB 재임베딩 → 벡터 검색 품질 대폭 향상
저장: 별도 저장 안 함, ChromaDB의 document 필드를 업데이트
작동: embedding_text → OpenAI embedding-3-large → ChromaDB upsert
```

#### E8. quality_score 산정
```
입력: node.content + node.type
출력: 0.0-1.0 점수 + 근거 1줄
모델: gpt-5-mini
프롬프트: "이 노드의 정보 밀도를 0-1로 평가하라.
  1.0 = 구체적, 실행 가능, 검증 가능
  0.5 = 일반적 서술
  0.0 = 의미 없는 잡음
  점수와 1줄 근거를 반환."
용도: recall() 결과 정렬, tier 자동 판정 보조
저장: nodes.quality_score (신규 컬럼, REAL)
```

#### E9. abstraction_level 산정
```
입력: node.content + node.layer
출력: 0.0-1.0 (레이어 내 추상도)
모델: gpt-5-mini
프롬프트: "Layer {layer} 내에서 이 노드의 추상 수준은?
  0.0 = 매우 구체적 (특정 도구, 특정 날짜)
  1.0 = 매우 추상적 (범용 원칙, 철학적 명제)"
용도: 검색 결과 정렬, 레이어 내 위계 시각화
저장: nodes.abstraction_level (신규 컬럼, REAL)
```

#### E10. temporal_relevance 산정
```
입력: node.content + node.created_at + 현재 날짜
출력: 0.0-1.0 (현재 유효성)
모델: gpt-5-mini
프롬프트: "이 노드가 {today} 기준으로 얼마나 현재 유효한가?
  1.0 = 시간 초월 (원칙, 가치)
  0.5 = 부분 유효 (일부 변경)
  0.0 = 완전 폐기 (구버전 설정)"
용도: recall() 시간 감쇠 보조, 오래된 정보 자동 필터
저장: nodes.temporal_relevance (신규 컬럼, REAL)
```

#### E11. actionability 산정
```
입력: node.content + node.type
출력: 0.0-1.0 (실행 가능성)
모델: gpt-5-mini
프롬프트: "이 노드가 즉시 실행 가능한 내용을 담고 있는가?
  1.0 = 바로 실행 가능 (코드, 명령어, 구체 지시)
  0.5 = 방향은 있지만 구체화 필요
  0.0 = 관찰/성찰만 (실행과 무관)"
용도: Decision/Plan 우선순위, 대시보드 필터
저장: nodes.actionability (신규 컬럼, REAL)
```

#### E12. layer 검증
```
입력: node.content + node.type + node.layer (기존)
출력: 확인된 layer + confidence + 교정 사유 (변경 시)
모델: gpt-4.1 (대형 풀, 정확도 중요)
프롬프트: "이 노드의 현재 레이어는 {layer}이다. 맞는가?
  L0=원시경험, L1=행위/사건, L2=개념/패턴, L3=원칙/정체성,
  L4=세계관, L5=가치/존재론.
  맞으면 {layer, confidence, changed: false}
  틀리면 {layer: 교정값, confidence, changed: true, reason: '...'}"
저장: nodes.layer 업데이트 (변경 시)
```

### 3.2 Edge 단위 작업 (5개)

#### E13. 크로스도메인 관계 추출
```
입력: 서로 다른 domain의 노드 8개 클러스터
출력: 발견된 관계 0-5개 [{source, target, relation, strength, reason}]
모델: gpt-5-mini
프롬프트: "다음 8개 노드는 서로 다른 도메인에 속한다.
  의미적 연결이 있는 쌍을 찾아라.
  관계 타입: {48개 중 크로스도메인 특수 6개 + 의미론적 8개}
  연결이 없으면 빈 배열."
클러스터링 전략:
  - ChromaDB에서 도메인 다른 유사 노드 쌍 추출
  - 같은 facet 다른 domain 노드 쌍
  - 같은 key_concept 다른 domain 노드 쌍
```

#### E14. 동일도메인 관계 정밀화
```
입력: 기존 edge + source/target content
출력: 업그레이드된 relation 타입 + direction + reason
모델: gpt-5-mini
프롬프트: "이 두 노드의 현재 관계는 '{relation}'이다.
  48개 관계 타입 중 더 정확한 것이 있는가?
  방향(upward/downward/horizontal)은?"
대상: relation이 "connects_with" 또는 "supports"인 generic edge
  → 더 구체적인 48개 타입으로 업그레이드
```

#### E15. edge 방향 + 이유 보정
```
입력: edge + source/target content + source/target layer
출력: direction + reason
모델: o3-mini (추론 필요)
프롬프트: "source (Layer {s_layer}, {s_type})와
  target (Layer {t_layer}, {t_type}) 사이의 관계 '{relation}'에서
  방향은? upward(추상화), downward(구체화), horizontal(동등), cross-layer"
```

#### E16. edge strength 보정
```
입력: edge + source/target content
출력: 보정된 base_strength (0.0-1.0)
모델: gpt-5-mini
프롬프트: "이 두 노드의 연결 강도를 0-1로 평가하라.
  1.0 = 불가분한 관계 (A 없이 B 불가)
  0.5 = 관련 있지만 독립적
  0.0 = 우연적 연결"
대상: vector similarity로 자동 생성된 edge (강도가 거리 기반이라 부정확)
```

#### E17. 중복 edge 병합
```
입력: 같은 source-target 쌍의 여러 edge
출력: 병합 결정 (merge/keep-both)
모델: gpt-5-mini
프롬프트: "같은 두 노드 사이에 edge가 {n}개 있다.
  각각: {relations}. 병합해야 하나? 어떤 relation이 가장 정확한가?"
```

### 3.3 그래프 단위 작업 (8개)

#### E18. 클러스터 테마 추출
```
입력: 밀집 연결된 노드 10-15개 클러스터
출력: 공통 테마 1-3줄 + 상위 추상화 제안
모델: gpt-5.2 (대형 풀, 최상급)
프롬프트: "이 {n}개 노드는 밀접하게 연결되어 있다.
  1. 공통 주제는?
  2. 이 클러스터를 하나의 상위 노드로 추상화한다면?
  3. Framework 또는 Mental Model로 만들 수 있는가?"
용도: Framework, Mental Model 타입 노드 자동 발견
```

#### E19. 빠진 연결 탐지
```
입력: 고립 노드 + 같은 domain/facet의 연결된 노드들
출력: 연결 제안 [{target, relation, reason}]
모델: gpt-5-mini
프롬프트: "이 노드(#{id})는 고립되어 있다.
  같은 도메인의 다른 노드들을 보고, 연결 가능한 것을 찾아라."
목표: orphan 0개
```

#### E20. 시간 체인 탐지
```
입력: 같은 project의 시간순 노드들 (최대 20개)
출력: 인과 체인 [{sequence: [ids], chain_type, description}]
모델: o3-mini (추론 필요)
프롬프트: "이 노드들의 시간 순서를 보고 인과 체인을 찾아라.
  예: Decision A → Failure B → Insight C → Decision D
  체인 타입: evolution(진화), failure-recovery(실패-회복),
            spiral(반복심화), divergence(분기)"
용도: Evolution 타입 자동 생성, 대시보드 타임라인
```

#### E21. 모순 탐지
```
입력: 같은 domain의 노드 쌍 (content 유사하지만 다른 주장)
출력: [{pair: [id1, id2], contradiction_type, description}]
모델: o3-mini (논리적 추론)
프롬프트: "이 두 노드가 서로 모순되는가?
  모순 타입: direct(직접 충돌), temporal(시점 차이로 변화),
            contextual(맥락에 따라 다름), paradox(의도적 모순)"
용도: Tension 타입 자동 생성, contradicts 관계 edge 생성
```

#### E22. Assemblage 탐지
```
입력: 하나의 Decision/Breakthrough 노드 + 연결된 모든 노드
출력: Assemblage 여부 + 구성 요소 + 설명
모델: o3-mini (구조 추론)
프롬프트: "이 Decision은 여러 이질적 요소의 조합으로 만들어졌는가?
  어떤 Tool + Failure + Insight + Context가 결합되었는가?
  이 조합이 하나의 '배치(Assemblage)'를 형성하는가?"
용도: assembles 관계 edge 생성, 들뢰즈 배치 개념 구현
```

#### E23. 승격 후보 분석
```
입력: Signal 타입 노드들 + 유사 노드들
출력: [{signal_id, maturity_score, promotion_target, evidence, recommendation}]
모델: o3 (대형 풀, 깊은 추론)
프롬프트: "이 Signal이 Pattern으로 승격할 근거가 충분한가?
  1. 유사한 관찰이 몇 번 반복되었나?
  2. 어떤 도메인에서 반복되었나?
  3. 반복에서 일관된 구조가 보이는가?
  4. 승격 추천 여부 + 근거"
용도: analyze_signals() MCP 도구 내부, Claude 승격 판단 보조
```

#### E24. 병합 후보 탐지
```
입력: ChromaDB distance < 0.15인 노드 쌍
출력: [{pair: [id1, id2], action: merge|keep|differs_in, reason}]
모델: gpt-5-mini
프롬프트: "이 두 노드가 중복인가?
  merge: 하나로 합치기 (완전 중복)
  keep: 둘 다 유지 (보완적)
  differs_in: 유사하지만 핵심 차이 있음 → differs_in edge 생성"
용도: 노이즈 제거 + 차이 추적 edge 자동 생성
```

#### E25. 지식 공백 분석
```
입력: 도메인별 타입 분포 통계 + 전체 온톨로지
출력: [{domain, missing_types, gap_reason, importance, suggestion}]
모델: gpt-5.2 (대형 풀, 맥락 이해)
프롬프트: "이 도메인의 노드 분포를 보라.
  {domain}: {type: count, ...}
  어떤 타입이 비정상적으로 적은가? 왜 적은가?
  1) 실제로 없다 2) 기록하지 않았다 3) 다른 타입으로 분류됨
  어떤 조치가 필요한가?"
용도: 주간 리포트, 다음 대화 방향 제시
```

---

## 4. 분류 파이프라인 상세 (Claude + GPT 협업)

### 4.1 경로 1: 실시간 (remember / /checkpoint)

```
Claude가 대화 맥락 전체를 보유한 상태

Claude 직접 채움 (4개, 맥락 의존):
  ① layer (0-5)
  ② primary_type (45개 중 1개)
  ③ secondary_types (0-2개)
  ④ domains (1-3개)

시스템 자동 채움 (3개, 규칙 기반):
  ⑤ tier = 2 (curated, Paul 승인이므로)
  ⑥ maturity = type별 초기값 테이블
  ⑦ facets = 규칙 기반 매핑 (E4 참조)

GPT 비동기 백필 (6개, daily_enrich.py):
  ⑧ summary (E1)
  ⑨ key_concepts (E2)
  ⑩ embedding_text (E7)
  ⑪ quality_score (E8)
  ⑫ abstraction_level (E9)
  ⑬ temporal_relevance (E10)
  ⑭ actionability (E11)
  ⑮ tags 확장 (E3)
```

### 4.2 경로 2: 배치 (Obsidian 인제스션)

```
Step 1: 규칙 기반 (API 없음, ~60% 커버)
  파일 경로 → layer 추정
  파일 경로 → facets 추정
  project 필드 → domains 1차

Step 2: gpt-5-mini — 레이어 분류 (나머지 40%)
  "이 텍스트는 어떤 레이어? (0~5) + confidence"
  → 6개 중 택1

Step 3: gpt-5-mini — 타입 분류
  "Layer {N}에서 이 텍스트의 primary_type은?
   secondary_types는? confidence는?"
  → 최대 18개 중 택1 + 보조 0-2개

Step 4: gpt-5-mini — 메타데이터 일괄 생성
  summary, key_concepts, tags, domains, embedding_text
  → E1-E5, E7 일괄 실행

Step 5: confidence 기반 에스컬레이션
  confidence ≥ 0.8  → 자동 수락 (tier: 1 = refined)
  confidence 0.5~0.8 → 수락 + 월/목 리뷰 큐 등록
  confidence < 0.5  → 즉시 Claude 검토 큐

Step 6: tier 배정
  규칙 통과 → tier 0 (raw)
  GPT 분류 완료 → tier 1 (refined)
  Claude 검토 완료 → tier 2 (curated)
```

### 4.3 경로 3: recall() 중 수동적 교정

```
Claude가 recall() 결과를 보고 오분류 감지:
  tier 0-1: 자동 교정, correction_log에 기록
  tier 2: Paul에게 확인 후 교정

correction_log 스키마:
  {node_id, old_type, new_type, old_layer, new_layer,
   reason, corrected_by: "claude", timestamp}
```

### 4.4 경로 4: 월/목 정기 감사

```
월요일: 전체 감사
  - correction_log 미처리 건
  - confidence < 0.8 미검토 노드
  - secondary_types 누락 노드
  - facets/domains 누락 노드
  - 주간 지식 공백 보고서 검토

목요일: 빠른 점검
  - confidence < 0.5 미처리
  - recall 중 교정 건만
  - 승격 후보 리뷰

토큰 비용: 월 ~17K, 목 ~8K (대형 풀, 1% 미만)
```

---

## 5. 실행 설계: daily_enrich.py

### 5.1 파일 구조

```
scripts/
├── daily_enrich.py              # 메인 파이프라인 (매일 실행)
├── migrate_v2.py                # 1회성 마이그레이션 (Day 1-3)
├── codex_review.py              # Codex CLI 검증 (매일 실행)
├── enrich/
│   ├── __init__.py
│   ├── token_counter.py         # 토큰 예산 관리 (핵심)
│   ├── node_enricher.py         # E1-E12: 노드 단위 enrichment
│   ├── relation_extractor.py    # E13-E17: edge 단위 enrichment
│   ├── graph_analyzer.py        # E18-E25: 그래프 단위 분석
│   ├── prompts/                 # 프롬프트 템플릿
│   │   ├── summary.txt
│   │   ├── key_concepts.txt
│   │   ├── classify_layer.txt
│   │   ├── classify_type.txt
│   │   ├── cross_domain.txt
│   │   ├── contradiction.txt
│   │   ├── assemblage.txt
│   │   ├── promotion.txt
│   │   └── knowledge_gap.txt
│   └── reports/                 # 결과 리포트 출력 디렉토리
│       └── YYYY-MM-DD.md
```

### 5.2 실행 흐름

```
daily_enrich.py 실행 시:

1. 토큰 카운터 초기화
   TokenBudget(large=225000, small=2250000)

2. Phase 1: 대량 enrichment (gpt-5-mini, 1,800K)
   a. 신규 노드 전체 enrichment (오늘 생성된 것)
   b. 기존 노드 로테이션 개선 (enrichment 필드 빈 것 우선)
   c. 크로스도메인 관계 추출 (새 노드 × 기존 노드)
   d. 동일도메인 관계 정밀화 (generic edge 업그레이드)
   e. 중복 탐지 + 병합 후보
   f. edge 품질 감사 (로테이션)
   g. embedding 최적화 (로테이션)

3. Phase 2: 배치 추론 (o3-mini, 450K)
   a. 모순/긴장 탐지
   b. Assemblage 탐지
   c. 시간 체인 추론
   d. edge 방향 추론

4. Phase 3: 정밀 검증 (gpt-4.1, 50K)
   a. confidence < 0.5 재분류
   b. 레이어 검증 (어제 결과)

5. Phase 4: 심층 생성 (gpt-5.2, 100K)
   a. L4-L5 분류
   b. 성장 내러티브 (Becoming 중인 노드)
   c. 지식 공백 분석
   d. 크로스도메인 연결 해석

6. Phase 5: 깊은 추론 (o3, 75K)
   a. 이색적 접합 최종 판단 (Phase 1 후보 중 top 20)
   b. 승격 판단 논증 (Signal → Pattern)
   c. 온톨로지 메타 검증 (타입 경계, 누락, 일관성)

7. Phase 6: Codex CLI 검증
   a. 프롬프트 품질 검증 (prompts/ 디렉토리)
   b. 파이프라인 코드 리뷰 (daily_enrich.py)
   c. 온톨로지 일관성 체크 (schema.yaml)

8. Phase 7: 리포트 생성
   a. 토큰 사용량 정산 (모델별)
   b. 생성/교정/삭제 통계
   c. 발견 사항 요약
   d. Claude 월/목 감사용 큐 업데이트
   e. → data/reports/YYYY-MM-DD.md 저장
```

### 5.3 token_counter.py 설계

```python
LARGE_MODELS = {"o3", "gpt-5.2", "gpt-5.1", "gpt-4.1", "gpt-4o", "o1"}
SMALL_MODELS = {"o3-mini", "gpt-5-mini", "gpt-5-nano",
                "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o-mini",
                "o4-mini", "o1-mini", "codex-mini-latest"}

class TokenBudget:
    def __init__(self, large_limit=225000, small_limit=2250000):
        self.limits = {"large": large_limit, "small": small_limit}
        self.used = {"large": 0, "small": 0}
        self.log = []  # 모든 호출 기록

    def pool(self, model: str) -> str:
        if model in LARGE_MODELS: return "large"
        if model in SMALL_MODELS: return "small"
        raise ValueError(f"Unknown model: {model}")

    def can_spend(self, model: str, estimated_tokens: int) -> bool:
        p = self.pool(model)
        return (self.used[p] + estimated_tokens) <= self.limits[p]

    def record(self, model: str, usage: dict):
        """API 응답의 usage 객체를 기록"""
        p = self.pool(model)
        total = usage["total_tokens"]
        # o3 계열: reasoning_tokens 포함
        if "completion_tokens_details" in usage:
            reasoning = usage["completion_tokens_details"].get("reasoning_tokens", 0)
            total = usage["prompt_tokens"] + usage["completion_tokens"]  # reasoning 포함됨
        self.used[p] += total
        self.log.append({
            "model": model, "pool": p, "tokens": total,
            "cumulative": self.used[p], "timestamp": datetime.now().isoformat()
        })

    def remaining(self, pool: str) -> int:
        return self.limits[pool] - self.used[pool]

    def utilization(self) -> dict:
        return {
            "large": f"{self.used['large']}/{self.limits['large']} ({self.used['large']/self.limits['large']*100:.1f}%)",
            "small": f"{self.used['small']}/{self.limits['small']} ({self.used['small']/self.limits['small']*100:.1f}%)"
        }
```

### 5.4 codex_review.py 설계

```python
#!/usr/bin/env python3
"""매일 실행 — Codex CLI로 코드/프롬프트/온톨로지 검증"""

REVIEWS = [
    {
        "name": "프롬프트 품질",
        "target": "scripts/enrich/prompts/",
        "prompt": "이 프롬프트들의 정확도를 높이려면? "
                  "엣지 케이스, 모호한 지시, 개선점?"
    },
    {
        "name": "파이프라인 코드",
        "target": "scripts/daily_enrich.py",
        "prompt": "토큰 낭비, 에러 핸들링 빈틈, 배치 최적화 가능 지점?"
    },
    {
        "name": "온톨로지 일관성",
        "target": "ontology/schema.yaml",
        "prompt": "타입 간 경계 모호성, 관계 타입 누락, 논리적 모순?"
    },
    {
        "name": "enrichment 모듈",
        "target": "scripts/enrich/",
        "prompt": "모듈 간 의존성, 에러 전파, 데이터 정합성 문제?"
    }
]
```

---

## 6. 1회성 마이그레이션 계획 (Day 1-3)

### Day 1: 노드 전체 enrichment

```
소형 풀 (2,250K):
  E1 summary: 310 배치 × 3,500 = 1,085K
  E2 key_concepts + E3 tags: 310 배치 × 2,800 = 868K
  E7 embedding_text: 100 배치 × 3,000 = 300K
  합계: 2,253K (90.1%)

대형 풀 (225K):
  E12 layer 검증: 50 배치 × 3,500 = 175K
  E6 secondary_types: 15 배치 × 3,500 = 52K
  합계: 227K (91%)
```

### Day 2: 관계 추출 + 점수

```
소형 풀 (2,250K):
  E13 크로스도메인 관계: 400 클러스터 × 2,200 = 880K
  E14 동일도메인 정밀화: 300 클러스터 × 1,800 = 540K
  E4 facets + E5 domains: 310 배치 × 2,500 = 775K
  E8 quality_score: 20 배치 × 2,800 = 56K
  합계: 2,251K (90%)

대형 풀 (225K):
  E18 클러스터 테마: 30 클러스터 × 3,300 = 99K
  E25 지식 공백: 20 도메인 × 3,000 = 60K
  E23 승격 후보 (o3): 15 Signal × 4,000 = 60K
  합계: 219K (88%)
```

### Day 3: 품질 검증 + 고급 분석

```
소형 풀 (2,250K):
  E16 edge strength 보정: 271 배치 × 2,500 = 678K
  E15 edge 방향 (o3-mini): 200 배치 × 1,500 = 300K
  E21 모순 탐지 (o3-mini): 30 배치 × 3,000 = 90K
  E22 Assemblage (o3-mini): 40 배치 × 3,500 = 140K
  E20 시간 체인 (o3-mini): 150 시퀀스 × 1,500 = 225K
  E9 abstraction + E10 temporal + E11 actionability: 310 배치 × 2,500 = 775K
  합계: 2,208K (88%)

대형 풀 (225K):
  E19 빠진 연결 탐지 (gpt-5.2): 30 배치 × 2,800 = 84K
  이색적 접합 최종 (o3): 20 쌍 × 3,500 = 70K
  병합 후보 심층 (gpt-4.1): 30 쌍 × 2,000 = 60K
  합계: 214K (86%)
```

### Day 3 완료 후 상태

```
전 노드 (3,098개):
  ✓ summary, key_concepts, tags (확장), embedding_text
  ✓ facets, domains, secondary_types
  ✓ quality_score, abstraction_level, temporal_relevance, actionability
  ✓ layer 검증 완료

전 edge (~8,000개):
  ✓ 크로스도메인 ~2,000개 신규
  ✓ relation 타입 정밀화
  ✓ direction + strength 보정

그래프 분석:
  ✓ 클러스터 테마 30개
  ✓ 시간 체인 150개
  ✓ 모순 쌍 ~30개
  ✓ Assemblage ~40개
  ✓ 승격 후보 ~15개
  ✓ 지식 공백 보고서
  ✓ 고립 노드 0개
```

---

## 7. 비판적 점검 — 설계 결함 및 리스크

### 7.1 치명적 (구현 전 반드시 해결)

**C1. o3 추론 토큰 예측 불가**
- 문제: o3는 내부 reasoning_tokens를 예측할 수 없다. 같은 프롬프트도 때에 따라 3x~10x 변동.
- 영향: 75K 예산이 15회 만에 소진될 수도, 25회 가능할 수도.
- 해결:
  - o3 Phase를 마지막에 배치 (다른 Phase 완료 후 남은 예산으로)
  - `max_reasoning_tokens` 파라미터로 제한 (o3 API 지원 시)
  - 첫 3회 호출 후 평균 토큰 계산 → 남은 예산으로 가능한 횟수 동적 조정

**C2. API 응답 실패 시 토큰 낭비**
- 문제: API 호출 실패해도 입력 토큰은 소비된다 (OpenAI 정책).
- 영향: 네트워크 에러, timeout, rate limit → 예산 낭비.
- 해결:
  - 실패 시 재시도 전 토큰 기록
  - 연속 3회 실패 시 해당 Phase 스킵
  - Phase 간 우선순위: Phase 1 > 2 > 3 > 4 > 5 (앞이 더 중요)

**C3. 프롬프트 품질이 전체 파이프라인 품질을 결정**
- 문제: 25개 작업의 프롬프트가 부정확하면 3,098개 노드에 잘못된 메타데이터가 채워짐.
- 영향: 오분류 → 잘못된 edge → 잘못된 recall → 의미망 전체 오염.
- 해결:
  - 50개 노드 표본으로 각 프롬프트 사전 테스트
  - 결과를 Paul이 직접 검토 후 프롬프트 확정
  - Codex CLI가 매일 프롬프트 품질 검증
  - 첫 실행은 --dry-run 모드 (DB 반영 안 함, 결과만 출력)

### 7.2 심각 (초기에 대응 필요)

**S1. 배치 처리 순서 의존성**
- 문제: E7 (embedding_text)는 E1 (summary) + E2 (key_concepts) 완료 후 실행해야 함.
- 영향: 순서 꼬이면 빈 summary로 embedding_text 생성 → 품질 저하.
- 해결: Phase 내 의존성 DAG 정의, 의존성 충족 확인 후 실행.

**S2. 소형 모델 환각(hallucination) 위험**
- 문제: gpt-5-mini가 content에 없는 facets/domains를 생성할 수 있음.
- 영향: "Paul이 작곡가다"처럼 허위 facet이 퍼질 수 있음.
- 해결:
  - facets, domains는 허용 목록(allowlist)으로 제한
  - 자유 생성 필드 (summary, key_concepts)만 열어둠
  - quality_score가 0.3 미만이면 자동 플래그

**S3. 크로스도메인 클러스터링 전략**
- 문제: "어떤 노드 쌍을 비교할 것인가"가 E13의 품질을 결정.
- 영향: 무작위 쌍 → 대부분 관계 없음 → 토큰 낭비.
- 해결: 세 가지 전략 병행
  1. ChromaDB 유사도: 다른 domain인데 distance < 0.3인 쌍
  2. 같은 key_concept: 추출된 개념이 겹치는 다른 domain 노드
  3. 같은 facet: philosopher 태그가 붙은 orchestration + mcp-memory 노드

**S4. Day 1-3 마이그레이션 실패 시 복구**
- 문제: Day 2에서 에러 발생 시 Day 1 결과와의 정합성.
- 해결:
  - 각 E작업별 완료 플래그 (nodes.enrichment_status JSON)
  - 실패 시 해당 작업만 재실행 (멱등성 보장)
  - Day 시작 전 DB 백업 (data/backup/YYYY-MM-DD.db)

### 7.3 추가 발견 — 치명적 (코드 리뷰에서 발견)

**C4. SQLite 스키마 마이그레이션 전략 부재**
- 문제: nodes에 10개+ 신규 컬럼 필요하지만, 현재 `sqlite_store.py`의 `init_db()`에 ALTER TABLE 로직 없음. FTS5 가상 테이블은 ALTER TABLE ADD COLUMN 미지원 → DROP 후 재생성 필요.
- 영향: 기존 3,098개 노드의 FTS 인덱스 재구축 + 데이터 정합성 필수.
- 해결: `migrate_v2.py`에 순차 ALTER TABLE + FTS5 재생성 + 트랜잭션 롤백 로직.

**C5. Enrichment 결과 간 충돌 해소 메커니즘 없음**
- 문제: E4(facets) 규칙 기반 → `["developer"]`, GPT → `["philosopher", "designer"]`. 합집합? GPT 우선? 미정의.
- 문제: E12(layer 검증)에서 layer 변경 시, 이미 실행된 E6(secondary_types)가 기존 layer 기준이라 무효화.
- 해결: 각 작업에 conflict resolution policy 명시.
  facets: `union(rule, gpt)`. layer: `gpt_if_confidence > 0.8 else keep`. secondary_types: layer 변경 시 재실행.

**C6. 파이프라인 중간 크래시 시 부분 기록 (Atomicity)**
- 문제: E1(summary) 완료 후 E2(key_concepts)에서 크래시 → 반쪽짜리 노드.
  다음 실행에서 E7(embedding_text)가 불완전한 입력으로 생성.
- 해결: `nodes.enrichment_status JSON` 컬럼 — `{"E1": "2026-03-04T...", "E2": null}`.
  daily_enrich.py는 이 필드 읽어서 미완료 작업만 재실행.

**C7. ChromaDB 재임베딩 동시성 문제**
- 문제: E7 실행 중 MCP recall()이 동시 서비스되면, 구/신 embedding 혼재.
  "raw content" 기반 벡터와 "optimized embedding_text" 기반 벡터가 공존 → 유사도 왜곡.
- 해결: 1) 새 컬렉션에 재임베딩 후 atomic swap, 또는
  2) KST 09:30 실행 시간대에 MCP 사용 적으므로 경고만 로깅.

**C8. "신규 노드" 판별 기준 미정의**
- 문제: "오늘 생성된 노드"가 UTC인지 KST인지 미정의.
  `enrichment_status` 없으면 "이미 enrichment된 노드"와 구분 불가.
- 해결: `enriched_at TEXT` 컬럼 추가 (NULL = 미처리).
  시간 기준 UTC 통일, 코드에 명시.

### 7.4 추가 발견 — 심각 (코드 리뷰에서 발견)

**S5. recall() / remember()와의 통합 설계 부재**
- 문제: enrichment 필드(quality_score, temporal_relevance)를 recall() 랭킹에 어떻게 반영할지 미정의.
  remember() 저장 시 최초 embedding이 enrichment 후 교체되면 최초 것은 무의미.
- 해결: recall() scoring에 `quality_score * 0.2 + temporal_relevance * 0.1` 가중치 설계 추가.
  remember() 저장 시 "provisional embedding" 플래그.

**S6. 순환 의존: embedding ↔ edge 추출 ↔ graph analysis**
- 문제: E7(embedding) → ChromaDB 유사도 변경 → E13(관계 추출) 변경 → E18(클러스터) 변경 → 다음 실행에서 E7 변경... 순환 피드백 루프.
- 해결: 1-pass 제한. E7 결과는 "다음 실행"의 E13 입력. 수렴 검증은 주 1회.

**S7. config.py에 enrichment 설정 부재**
- 문제: 4개 모델 ID, 토큰 예산, 배치 크기, sleep 시간, dry-run 플래그 등 전부 없음.
- 해결: `config.py`에 `ENRICHMENT_MODELS`, `TOKEN_BUDGETS`, `BATCH_SIZE` 등 추가.

**S8. edges 테이블에 direction/reason/updated_at 컬럼 없음**
- 문제: E15 결과(direction)를 저장할 곳 없음. 관계 변경 이력도 추적 불가.
- 해결: edges에 `direction TEXT, reason TEXT, updated_at TEXT` 추가.

**S9. 4개 모델 Rate Limiting 전략 불충분**
- 문제: 모델별/tier별 RPM/TPM이 다름. 무료 토큰 프로그램이 별도 rate limit 부과 가능.
- 해결: token_counter에 모델별 RPM/TPM 트래킹 + adaptive sleep + 429 retry-after 파싱.

**S10. correction_log 테이블 미정의**
- 문제: 스키마만 정의, SQLite 테이블 생성 없음.
- 해결: `init_db()`에 correction_log 테이블 추가.

**S11. 기존 enrichment/ 모듈과의 관계 불명확**
- 문제: `enrichment/classifier.py`는 gpt-4.1-mini로 실시간 분류. 새 `scripts/enrich/`는 배치. 교체? 공존?
- 해결: 기존 = 실시간 경로(remember), 신규 = 배치 경로(daily_enrich). 역할 분리 명시.

### 7.5 추가 발견 — 운영

**O5. 마이그레이션 Day 1 예산 초과**
- 문제: Day 1 소형 풀 2,253K > 2,250K 한도. Day 2도 2,251K. 90% 목표와 모순.
- 해결: Day 1-3을 4일로 분산, 또는 각 Day를 2,000K(80%)로 보수적 계산.

**O6. OpenAI Batch API 미활용**
- 문제: Batch API로 50% 할인 + 비동기 처리 가능하지만 스펙에서 미고려.
- 해결: Batch API 무료 풀 호환 여부 확인 후, 마이그레이션은 Batch API 전환 검토.

**O7. 프롬프트 25개 유지보수 비용**
- 문제: 온톨로지 변경 시 25개 전부 수정해야. 일부 하드코딩되면 유지보수 지옥.
- 해결: 모든 프롬프트를 prompts/ YAML로 외부화. 변경 시 50개 표본 회귀 테스트.

**O8. temporal_relevance 재계산 주기**
- 문제: 시간 경과에 따라 값이 변해야 하지만 매일 3,098개 재계산 시 토큰 과다.
- 해결: rule-based decay (age_days 기반)를 1차 적용, GPT는 "시간 초월 여부"만 1회 판단.

**O9. remember() 실시간 분류의 토큰이 일일 예산 침식**
- 문제: 기존 classifier.py가 gpt-4.1-mini(소형 풀) 사용. 일일 예산에서 빠져나감.
- 해결: 실시간 분류를 Claude 완전 위임. gpt-4.1-mini는 배치에서만 사용.

**O10. SQLite DB 락 경합**
- 문제: daily_enrich.py 수천 건 UPDATE + MCP 서버 동시 INSERT/SELECT → writer 경합.
- 해결: 배치 UPDATE를 트랜잭션으로 묶어 lock 시간 최소화. 또는 임시 테이블 merge.

**O11. OpenAI Data Sharing 숨은 제약**
- 문제: embedding 호출(text-embedding-3-large)이 무료 풀에서 차감되는지 불명확.
  스펙은 chat completion 토큰만 계산, embedding 토큰 누락.
- 해결: 확인 필요. embedding은 별도 과금 모델 → 무료 풀 미포함 가능성 높음.

---

## 8. 미결 설계 질문 (업데이트)

### 확인 필요 (외부 의존)
1. **o3 reasoning_tokens 제한**: `max_reasoning_tokens` 파라미터 지원 여부
2. **Codex CLI 모델**: 무료 풀 포함 여부
3. **OpenAI Batch API**: 무료 풀 호환 여부
4. **embedding 과금**: text-embedding-3-large가 무료 풀에서 차감되는지
5. **Data Sharing 제약**: 사용처 제한, 모든 엔드포인트 호환 여부

### 설계 결정 필요
6. **프롬프트 테스트**: 50개 표본 선정 기준 — 타입별 균등 + 고난이도 위주 권장
7. **일상 루프 우선순위**: 신규 노드(50K) vs 기존 개선(나머지) — 신규 우선 후 잔여
8. **리포트 형식**: markdown (대시보드 통합은 Phase 4)
9. **DB 백업**: 마이그레이션 기간 매일 + 이후 주 1회
10. **conflict resolution**: facets=union, layer=gpt우선(>0.8), secondary=layer변경시재실행
11. **ChromaDB 재임베딩**: atomic swap vs 순차 upsert (규모상 순차 upsert + 경고 로깅)
12. **마이그레이션 일수**: 3일(85%) vs 4일(안전, 각 80%)

---

## 9. 구현 순서 (새 세션 시작점)

### 전제 조건
비판적 점검에서 발견한 가장 시급한 3가지가 해결되지 않으면 daily_enrich.py 첫 실행 자체가 불가능:
- **C4**: SQLite 스키마 마이그레이션 전략 부재
- **C6**: 파이프라인 중간 크래시 시 부분 기록 (Atomicity)
- **C8**: "신규 노드" 판별 기준 미정의

### Step 1: migrate_v2.py (C4, C8, S8, S10 해결)
```
해결하는 리스크: C4(스키마), C8(신규노드판별), S8(edges컬럼), S10(correction_log)

작업:
  a. nodes 테이블 ALTER TABLE — 10개+ 신규 컬럼 추가
     summary, key_concepts, facets, domains, secondary_types,
     quality_score, abstraction_level, temporal_relevance,
     actionability, enrichment_status(JSON), enriched_at(TEXT)
  b. edges 테이블 ALTER TABLE — direction, reason, updated_at 추가
  c. correction_log 테이블 CREATE
  d. FTS5 가상 테이블 DROP + 재생성 (summary, key_concepts 포함)
  e. 기존 3,098개 노드에 layer 필드 부여 (type→layer 매핑 테이블)
  f. 기존 edge에 frequency=0, decay_rate=0.005 기본값
  g. DB 백업 (data/backup/) 로직
  h. 트랜잭션 경계 + 롤백 로직
```

### Step 2: config.py enrichment 설정 추가 (S7 해결)
```
해결하는 리스크: S7(config 부재)

작업:
  a. ENRICHMENT_MODELS: 4개 모델 ID
  b. TOKEN_BUDGETS: 대형/소형 풀 한도
  c. BATCH_SIZE: 기본 10
  d. BATCH_SLEEP: 기본 0.3초
  e. DRY_RUN: False (테스트 시 True)
  f. REPORT_DIR: data/reports/
  g. BACKUP_DIR: data/backup/
  h. FACETS_ALLOWLIST: 허용된 facet 목록
  i. DOMAINS_ALLOWLIST: 허용된 domain 목록
```

### Step 3: scripts/enrich/token_counter.py (C1, S9 해결)
```
해결하는 리스크: C1(o3 토큰 예측 불가), S9(rate limiting)

작업:
  a. TokenBudget 클래스 (대형/소형 풀 분리 추적)
  b. 모델별 RPM/TPM 트래킹
  c. o3 reasoning_tokens 별도 추적
  d. can_spend() / record() / remaining() / utilization()
  e. 429 retry-after 파싱 + adaptive sleep
  f. 90% 한도 도달 시 자동 중단
  g. 일일 사용량 JSON 로그 (data/reports/token_log/)
```

### Step 4: scripts/enrich/node_enricher.py (E1-E12)
```
해결하는 리스크: C5(충돌 해소), C6(atomicity), S2(환각 방지)

작업:
  a. E1-E5: summary, key_concepts, tags, facets, domains 생성
  b. E6: secondary_types 배정
  c. E7: embedding_text 최적화
  d. E8-E11: quality/abstraction/temporal/actionability 점수
  e. E12: layer 검증
  f. conflict resolution policy 구현
  g. enrichment_status 업데이트 로직
  h. allowlist 검증 (facets, domains)
  i. --dry-run 모드
```

### Step 5: scripts/enrich/relation_extractor.py (E13-E17)
```
해결하는 리스크: S3(클러스터링 전략), S6(순환 의존)

작업:
  a. E13: 크로스도메인 관계 추출 (3가지 클러스터링 전략)
  b. E14: 동일도메인 관계 정밀화
  c. E15: edge 방향 + 이유
  d. E16: strength 보정
  e. E17: 중복 edge 병합
  f. 1-pass 제한 (순환 방지)
```

### Step 6: scripts/enrich/graph_analyzer.py (E18-E25)
```
작업:
  a. E18: 클러스터 테마 추출
  b. E19: 빠진 연결 탐지
  c. E20: 시간 체인 탐지
  d. E21: 모순 탐지
  e. E22: Assemblage 탐지
  f. E23: 승격 후보 분석
  g. E24: 병합 후보 탐지
  h. E25: 지식 공백 분석
```

### Step 7: scripts/daily_enrich.py (메인 파이프라인)
```
해결하는 리스크: C2(API 실패), C7(ChromaDB 동시성), O10(DB 락)

작업:
  a. Phase 1-7 순차 실행 오케스트레이션
  b. Phase 간 우선순위 (1 > 2 > 3 > 4 > 5)
  c. 연속 3회 실패 시 Phase 스킵
  d. DB 트랜잭션 배치 처리 (락 최소화)
  e. 리포트 생성 (data/reports/YYYY-MM-DD.md)
  f. --budget-large / --budget-small CLI 옵션
```

### Step 8: scripts/codex_review.py
```
작업:
  a. 프롬프트 품질 검증
  b. 파이프라인 코드 리뷰
  c. 온톨로지 일관성 체크
  d. enrichment 모듈 의존성 검사
```

### Step 9: 프롬프트 템플릿 + 50개 표본 테스트
```
해결하는 리스크: C3(프롬프트 품질)

작업:
  a. scripts/enrich/prompts/ 디렉토리에 25개 프롬프트 외부화
  b. 50개 표본 선정 (타입별 균등 + 고난이도)
  c. --dry-run으로 결과 출력
  d. Paul 검토 후 프롬프트 확정
```

### Step 10: MCP 도구 통합 (S5 해결)
```
작업:
  a. recall() scoring에 enrichment 필드 가중치 반영
  b. remember()에 provisional embedding 플래그
  c. 신규 4개 MCP 도구: analyze_signals, promote_node, get_becoming, inspect
```
