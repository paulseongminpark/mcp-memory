# c-r3-12: scripts/ 디렉토리 구조 완성

> Round 3에서 생성된 파일 목록 및 사용 순서

## 신규 생성 파일

```
scripts/
├── migrate_phase2.py          # DB 컬럼 추가 (먼저 실행)
├── eval/
│   ├── ab_test.py             # RRF k=60 vs k=30 A/B 테스트
│   └── goldset.yaml           # 평가 쿼리셋 (Paul 라벨링 필요)
└── link_detector/
    └── train_predict.py       # Missing link 탐지 (sklearn LR)
```

## 실행 순서

```bash
# 1. DB migration (Phase 2 선행 필수)
python scripts/migrate_phase2.py

# 2. Missing link 탐지 (임베딩 필요)
python scripts/link_detector/train_predict.py --top-k 20
# → data/reports/missing_links.json

# 3. A/B 테스트 (골드셋 라벨링 후)
# goldset.yaml을 Paul이 채운 다음:
python scripts/eval/ab_test.py --goldset scripts/eval/goldset.yaml
# → data/reports/ab_test_result.json
```

## 의존성

| 파일 | 의존 |
|---|---|
| migrate_phase2.py | sqlite3 (stdlib) |
| ab_test.py | yaml, config, storage.hybrid |
| train_predict.py | numpy, sklearn, chromadb, config |

## goldset.yaml 라벨링 안내

- 현재 3개 예시 쿼리 포함 (q001~q003)
- Paul이 tier=0 노드 기반으로 20~50개 추가 필요
- tier=0 노드 조회: `SELECT id, type, content FROM nodes WHERE tier=0 ORDER BY quality_score DESC LIMIT 50;`
- 쿼리 형식: 자연어 검색 문장, relevant_ids에 반드시 있어야 할 node_id

## 완료 판정 기준

- [ ] migrate_phase2.py dry-run 통과
- [ ] goldset.yaml 20개 이상 쿼리 (Paul 라벨링)
- [ ] ab_test.py 실행 → NDCG@5, MRR 수치 확보
- [ ] train_predict.py top-20 출력 → Paul 검토
