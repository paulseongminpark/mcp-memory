# 세션 B: 뉴럴 메커니즘 구현 설계 — 인덱스

> 생성: 2026-03-05 | 모델: claude-sonnet-4-6
> 참조: `docs/2026-03-05-ontology-claude-paul-v2.md` 섹션 2, 7

## 파일 목록

| 파일 | 메커니즘 | 구현 우선순위 | 핵심 변경 위치 |
|---|---|---|---|
| [b-neural-1-bcm-vs-oja.md](b-neural-1-bcm-vs-oja.md) | BCM vs Oja 학습 규칙 | 5 | `storage/hybrid.py` `_hebbian_update()` |
| [b-neural-2-swr-transfer.md](b-neural-2-swr-transfer.md) | SWR-SO-Spindle 조건부 전이 | 6 | `tools/promote.py` |
| [b-neural-3-ucb-c.md](b-neural-3-ucb-c.md) | UCB c값 동적 조절 | 4 | `storage/hybrid.py` `traverse()` |
| [b-neural-4-patch-foraging.md](b-neural-4-patch-foraging.md) | 패치 전환 (Foraging/MVT) | 2 | `tools/recall.py` |
| [b-neural-5-reconsolidation.md](b-neural-5-reconsolidation.md) | 맥락 의존적 재공고화 | **1** | `tools/recall.py` |
| [b-neural-6-pruning.md](b-neural-6-pruning.md) | Pruning 맥락 의존성 (Bäuml) | 8 | `daily_enrich.py` 또는 `tools/prune.py` |
| [b-neural-7-chen-sa.md](b-neural-7-chen-sa.md) | Chen SA 최적화 (SQL CTE) | 3 | `storage/hybrid.py` `traverse_sql()` |
| [b-neural-8-rwr-surprise.md](b-neural-8-rwr-surprise.md) | RWR + 놀라움 지수 | 7 | `storage/rwr.py` (신규) |
| [b-neural-9-swing-toward.md](b-neural-9-swing-toward.md) | Swing-toward 재연결 | 9 | `storage/graph_ops.py` (신규), `daily_enrich.py` |

---

## DB 스키마 변경 전체 요약

| 테이블 | 컬럼 | 타입 | 기본값 | 관련 메커니즘 |
|---|---|---|---|---|
| nodes | `θ_m` | REAL | 0.5 | BCM (#1) |
| nodes | `activity_history` | TEXT | null | BCM (#1) |
| nodes | `visit_count` | INTEGER | 0 | UCB (#3) |
| edges | `description` | TEXT | null | 재공고화 (#5), Pruning (#6) |
| edges | `archived_at` | TEXT | null | Pruning (#6) |
| edges | `probation_end` | TEXT | null | Pruning (#6) |
| (신규) | recall_log 테이블 | — | — | SWR (#2) |

---

## 구현 의존성

```
#5 재공고화 (edge.description 기록)
    └→ #6 Pruning (ctx_log 다양성 판단)

#3 UCB (nodes.visit_count)
    └→ #1 BCM (visit_count 함께 갱신)

#2 SWR (recall_log 테이블)
    ← hybrid_search() 내 소스 로깅 선행 필요

#7 Chen SA (traverse_sql)
    ← edges 인덱스 확인 선행 필요

#8 RWR (build_graph 필요)
    ← #7과 공존 (역할 분리)

#9 Swing-toward
    ← #6 Pruning 이후 실행
```

---

## 통합 파일

전체 내용 단일 파일: [b-neural-mechanisms.md](b-neural-mechanisms.md)
