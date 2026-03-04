# Checkpoint + SessionStart Ontology 연동 업그레이드
작성: 2026-03-04

## 배경
- checkpoint 스킬이 현재 작업 결과(Decision/Failure) 위주 저장
- Paul 자체에 대한 관찰이 체계적으로 수집되지 않음
- SessionStart가 최근 Decision 위주 로드 → 세션 시작 시 Paul의 패턴/원칙을 모르고 시작

## Ontology 승격 경로 (이미 존재)
```
Observation (L0) → Signal (L1) → Pattern (L2) → Principle (L3) → Belief/Value (L4~L5)
```

## 구현 1: checkpoint 스킬 개선

### 현재
- 작업 결과만 추출 (Decision, Failure, Preference)

### 목표
Layer A + Layer B 동시 추출:

**Layer A — 작업 결과** (기존)
- Decision, Failure, Preference, Tool, Skill → L0~L1

**Layer B — Paul 관찰** (신규)
- 처음 발견된 관찰 → Observation (L0)
- 이번 세션에서 반복 확인 → Signal (L1)
- 이전 세션에서도 봤음 확인 → Pattern (L2) 승격 제안

### 타입 결정 로직
```
recall()로 유사 노드 검색
  → 기존 없음: Observation 저장
  → Signal 있음: Pattern 승격 제안
  → Pattern 있음: 중복 스킵 or 강도 강화
```

## 구현 2: SessionStart 컨텍스트 개선

### 현재
- 최근 Decision 5건 + 미해결 질문 + 최근 실패 위주

### 목표
```
L2 이상 nodes (Pattern/Insight/Principle/Identity/Belief/Value)
  → quality_score 상위 15개
  + 최근 30일 Signal (아직 Pattern 미승격, 관찰 중인 것)
  + 최근 7일 Observation (Paul이 직접 언급한 것)
```

### 이유
- 타입 고정 필터(Pattern/Identity/Principle) → 놓치는 것 많음
- Layer + quality_score 기반이 더 범용적
- Signal 포함 → 아직 굳어지지 않은 관찰도 세션에 주입

## 다중 소스 확장 (장기)
현재 수집 소스:
- analyze_conv.py (대화 분석 파이프라인)

추가할 소스:
- checkpoint (실시간 세션 중 관찰) ← 이번 업그레이드
- Obsidian vault 노트
- daily-memo 브랜치 내용

소스가 많을수록 교차 검증 → 신뢰도 높은 ontology 구축

## 파일 위치
- checkpoint 스킬: C:/Users/pauls/.claude/skills/checkpoint/
- SessionStart hook: C:/dev/01_projects/01_orchestration/ (hooks 관련)
- 외부 메모리: C:/dev/01_projects/06_mcp-memory/
