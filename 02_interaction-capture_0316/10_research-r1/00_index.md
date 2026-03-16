<!-- phase: research-r1 | status: 🔄 | updated: 2026-03-16T18:00 -->

# Research R1 — 현재 수집 경로 코드 분석

## 목표
현재 인터랙션 수집 경로 3개의 정확한 동작을 코드 레벨에서 분석하고, 갭을 정량화한다.

## 분석 대상
1. **auto_remember.py** — PostToolUse hook. FILE_TYPE_MAP/BASH_SIGNAL_MAP 매핑
2. **checkpoint skill** — 수동 호출. Layer A(미저장 기억) + Layer B(Paul 관찰)
3. **compressor/session-end** — 세션 종료 시 Step 5 Learn

## 핵심 질문
- 각 경로가 포착하는 인터랙션 차원은?
- 포착하지 못하는 차원은? (갭)
- Claude Code hook이 접근할 수 있는 데이터는 정확히 무엇인가?
- remember() 호출의 토큰 비용은?

## 산출물
- 01_collection-path-analysis.md — 경로별 코드 분석 + 갭 매트릭스
