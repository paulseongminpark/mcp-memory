# Cross Validation — PDR

## 교차 검증 매트릭스

| 검증 축 | 소스 A | 소스 B | 결과 |
|---|---|---|---|
| API 호환 | SKILL.md remember() | mcp-memory tools/remember.py | ✅ 일치 |
| API 호환 | SKILL.md recall() | mcp-memory tools/recall.py | ✅ 수정 후 일치 |
| 경로 일치 | SKILL.md Step 6 | phase-rules.json G6 | ✅ 일치 |
| 경로 일치 | phase-rules.json G6 | validate_output.py G6 | ✅ 일치 |
| 카운트 | phase-rules.json summary | 실제 규칙 수 | ✅ 수정 후 일치 |
| 전파 | phase-rules.json | pipeline-rules.md | ✅ 자동 전파 확인 |
| source 고유 | pdr | checkpoint/hook/save_session | ✅ 충돌 없음 |
