# Q7. 에너지 추적 — 세션 활동 트래킹

## Prigogine의 산일 구조에서 에너지원 = Paul의 세션 활동

시스템이 자기조직화하려면 **에너지 유입**을 측정해야 한다. 현재 이 측정이 없다.

## action_log + 세션 에너지 지표

```python
def calculate_session_energy(session_id: str) -> dict:
    actions = get_actions_by_session(session_id)
    energy = {
        "total_actions": len(actions),
        "creation_energy": count(actions, type='remember'),
        "retrieval_energy": count(actions, type='recall'),
        "organization_energy": count(actions, type='promote'),
        "exploration_energy": count(actions, type='recall', unique_domains=True),
    }
    if energy["creation_energy"] > energy["retrieval_energy"]:
        energy["mode"] = "generative"
    elif energy["exploration_energy"] > energy["retrieval_energy"] * 0.3:
        energy["mode"] = "exploratory"
    else:
        energy["mode"] = "consolidation"
    return energy
```

## session_context.py 확장

```python
def get_context_cli(project=""):
    # 기존 출력 후 추가:
    recent_energy = get_recent_session_energies(limit=5)
    print("=== 세션 에너지 패턴 ===")
    for s in recent_energy:
        print(f"  {s['date']} [{s['mode']}] "
              f"생성:{s['creation']} 인출:{s['retrieval']} 탐색:{s['exploration']}")
    if all(s['mode'] == 'consolidation' for s in recent_energy[-3:]):
        print("  warning: 최근 3세션 공고화 모드 -- 새 경험 주입 권장")
```

## 에너지 기반 자동 정책

```python
def decide_enrichment_focus():
    weekly_energy = get_weekly_energy_summary()
    if weekly_energy["mode"] == "generative":
        return {"focus": "node_enrichment", "batch_size": 50}
    elif weekly_energy["mode"] == "consolidation":
        return {"focus": "edge_enrichment", "batch_size": 30}
    elif weekly_energy["mode"] == "exploratory":
        return {"focus": "graph_enrichment", "batch_size": 20}
```

## 구현 우선순위

1. `action_log` 테이블 추가 (Q1과 동시)
2. remember(), recall(), promote_node()에 기록 추가 (각 3줄)
3. `calculate_session_energy()` 함수 (순수 쿼리, 50줄)
4. session_context.py 에너지 출력 (10줄)

-> 심화: [a-arch-9-action-log-deep.md](a-arch-9-action-log-deep.md)
