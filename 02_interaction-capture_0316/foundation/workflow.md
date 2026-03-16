# Workflow — Interaction Capture

## PDR 실행 흐름

```
1. 트리거 감지 (compact 직전 or DONE gate)
2. 대화 역순회 — 첫 턴부터 현재까지
3. 차원 1~8 순차 스캔:
   a. 해당 차원 관찰 추출
   b. 각 관찰마다 recall(top_k=3) 중복 체크
   c. 신규 → remember() 저장
   d. 유사 → edge 연결 또는 Signal 승격 제안
   e. 동일 → 스킵
4. PDR 리포트 생성 (02_pdr-report.md)
5. G6 체크 통과 → DONE 마킹 가능
```

## 기존 경로 통합

```
세션 시작 ─────────────────────────────────── 세션 종료
  │                                              │
  ├─ auto_remember (연속, 도구 이벤트)           │
  ├─ /checkpoint (수동, 중간 관찰)               │
  ├─ /pdr (compact 직전, 전수 스캔) ◄── NEW     │
  └─ /session-end (5단계 아카이브) ──────────────┘

Pipeline DONE:
  └─ /pdr (G6, 최종 회고 + 이전 PDR recall 통합)
```
