# Handoff — Interaction Capture

## 즉시 사용 가능
- `/pdr` — 스킬 등록 완료, 즉시 호출 가능
- G6 gate — 다음 파이프라인 DONE부터 자동 적용

## 향후 개선 (blocking 아님)
1. **Checkpoint Layer B 차원 태그 추가** — /checkpoint에서도 PDR 태그 체계 사용하면 중복 감지 정확도 향상
2. **Observation 분포 모니터링** — PDR 도입 후 Observation 비율 추적
3. **Signal 자동 승격** — PDR 반복 관찰 → Signal 승격 자동화 (현재 수동 제안)
4. **recall() source_filter 추가** — mcp-memory에 source 기반 필터 파라미터 추가하면 PDR 노드 조회 정확도 향상

## 주의사항
- /pdr은 compact 직전에 실행 (토큰 여유 필요 ~14K)
- DONE 모드에서는 이전 PDR recall 통합 포함
- 첫 실행 시 중복 체크할 기존 PDR 노드 없음 (정상)
