# 세션 D 인덱스 — 검증 & 허브 보호 & 메트릭스

> compact 후 이 파일만 읽고 이어서 진행한다.
> 규칙: 주제 하나 끝날 때마다 한 줄 요약 추가.

---

## 파일 네이밍 규칙

```
{세션}-r{라운드}-{번호}-{주제}.md
예: d-r3-11-schema-drift.md

- 인덱스 파일(d-index.md)은 라운드 없이 유지
- D 세션 다음 시작: r3-11번부터
- 기존 파일(r2)은 오케스트레이터가 rename 완료
```

---

## 완료 목록

| # | 파일 (rename 후) | 한 줄 요약 | 라운드 |
|---|------|-----------|--------|
| 0 | `d-r2-0-validation-metrics.md` | 전체 통합 요약본 (분할 전 초안) | r2 |
| 1 | `d-r2-1-fatal-weaknesses.md` | E1/E2/E7 미검증 루프 실증 + validators dead code + 스키마 50/45 불일치 | r2 |
| 2 | `d-r2-2-consensus.md` | Hebbian tanh/BCM 정규화 + exp decay 설계 + NDCG 평가 로드맵 + Palantir 리니지 | r2 |
| 3 | `d-r2-3-hub-ihs.md` | hub_monitor.py 구현 (IHS=D+B+NC) + RBAC L4/L5 human-in-the-loop + 주간 스냅샷 | r2 |
| 4 | `d-r2-4-small-world.md` | small_world_audit.py σ 측정 + triadic_suggest.py + Swing-toward rewiring | r2 |
| 5 | `d-r2-5-temporal.md` | activation_log 신규 테이블 + temporal_search() Rewind 모델 + 동적 temporal_relevance | r2 |
| 6 | `d-r2-6-pruning.md` | pruning.py BSP 3단계(탐색→유예30일→아카이브) + Bäuml 맥락 보호 가중치 | r2 |
| 7 | `d-r2-7-validators-impl.md` | server.py remember() 실제 삽입 코드 + 에러 포맷 + suggest_closest_type 키워드 매칭 확인 | r2 |
| 8 | `d-r2-8-drift-detector-impl.md` | E7 L654-668 실제 수정 코드 + get_node_embedding() + cosine_similarity + summary 길이 검증 | r2 |
| 9 | `d-r2-9-hub-monitor-ready.md` | node_id=INTEGER 확인 + hub_snapshots 자동 생성 + 3230노드 5초 예측 + A-10 공존 패턴 | r2 |
| 10 | `d-r2-10-activation-actionlog-merge.md` | action_log 통합(옵션A 권장) + recall뷰 설계 + temporal_search SQL 수정 + 마이그레이션 경로 | r2 |

---

## 오케스트레이터 업데이트 반영

| 결정 | 내용 |
|------|------|
| validators.py 연결 | Phase 0 즉시 실행 확정 (d-7) |
| activation_log | A-9 action_log와 통합 검토 중 (d-10) |
| Hebbian | tanh 제안 철회 → BCM 직행 (B-1 설계 따름, d-2 무효화) |

---

## 핵심 발견 (compact 후 빠른 복기용)

- **server.py** (mcp_server.py 아님): remember()는 L39, tools/remember.py 위임
- **node_id**: INTEGER (TEXT 아님) — hub_monitor.py 쿼리 파라미터 주의
- **get_embedding() 없음**: ChromaDB `collection.get(ids, include=["embeddings"])` 직접 사용
- **suggest_closest_type()**: 키워드 매칭 (Levenshtein 아님), content 본문 입력
- **E7 위치**: L654-668, updates dict 아닌 ChromaDB 직접 upsert
- **hub_snapshots, action_log**: 미존재 → 스크립트 내 자동 생성
- **insert_edge() 이미 fallback**: "connects_with"로 조용히 교정 → MCP 레벨 edge 검증 불필요

---

## 미완료 / 다음 주제 (r3부터)

| 파일명 예정 | 주제 | 비고 |
|------------|------|------|
| `d-r3-11-schema-drift.md` | 스키마 드리프트 5개 누락 타입 실제 diff 실행 | d-r2-1에 명령어만, 실행 미확인 |
| `d-r3-12-bcm-integration.md` | BCM 구현 코드 (B-1 연계) | B 세션 완료 후 D가 통합 |
| `d-r3-13-actionlog-finalize.md` | A-9 action_log 24 타입 확정 후 D-10 완성 | A 세션 결과 대기 |
| `d-r3-14-hub-monitor-run.md` | hub_monitor.py 실제 실행 + 결과 기록 | 코드 준비됨, 실행만 필요 |
