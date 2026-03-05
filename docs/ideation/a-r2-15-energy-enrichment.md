# 심화 7: 에너지 추적 → enrichment 정책 자동화

> A-7(에너지 추적) + A-9(action_log) → daily_enrich.py 실제 연동
> 핵심: calculate_session_energy() → decide_enrichment_focus() → phase별 배치 크기 조절

---

## 현재 daily_enrich.py 구조

```
main()
  ├── Phase 1: bulk (gpt-5-mini) — E1-E5,E7-E11,E13-E14,E16-E17
  ├── Phase 2: reasoning (o3-mini) — E15,E20-E22
  ├── Phase 3: verify (gpt-4.1) — E6,E12
  ├── Phase 4: deep (gpt-5.2) — E18,E19,E24,E25
  ├── Phase 5: judge (o3) — E23
  └── Phase 7: report
```

**현재 문제**: 배치 크기와 Phase 우선순위가 **하드코딩**. 세션 활동 패턴에 무관하게 동일한 양을 처리한다.

---

## 에너지 → enrichment 연결 모델

### Prigogine 산일 구조 해석

```
에너지 모드           → 시스템이 필요로 하는 것         → enrichment 초점
─────────────────────────────────────────────────────────────────
generative            새 노드가 많다                    Phase 1 (노드 enrichment) 확대
  (remember > recall)   → 구조화가 급선무                E1-E5 배치 ↑, E13 관계 발견 ↑

consolidation         기존 기억 반복 recall              Phase 2-3 (관계 강화 + 검증) 확대
  (recall > remember)   → edge 정밀화, 품질 검증          E14 정밀화 ↑, E12 layer 검증 ↑

exploratory           다양한 도메인 recall               Phase 4 (크로스도메인 발견) 확대
  (도메인 ≥ 3)          → 새 연결 발견이 급선무           E19 missing links ↑, E22 assemblage ↑

organizing            promote/merge 활동                 Phase 5 (승격 판단) 확대
  (organization > 0)    → 승격 파이프라인 가동             E23 promotion ↑

idle                  활동 없음                          최소 유지보수만
  (total = 0)           → 리소스 절약                     전체 배치 ↓
```

---

## calculate_session_energy() 구현 (A-9 확정)

```python
# storage/action_log.py

import json
import sqlite3
from datetime import datetime, timezone
from config import DB_PATH


def calculate_session_energy(session_id: str) -> dict:
    """한 세션의 에너지(활동량) 측정."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM action_log WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()
    conn.close()
    actions = [dict(r) for r in rows]

    if not actions:
        return {"mode": "idle", "total": 0}

    creation = sum(1 for a in actions if a["action_type"] in ("remember", "auto_link"))
    retrieval = sum(1 for a in actions if a["action_type"] in ("recall", "get_context", "inspect"))
    organization = sum(1 for a in actions if a["action_type"] in ("promote", "merge", "classify"))
    strengthening = sum(1 for a in actions if a["action_type"] in ("hebbian_update", "edge_create"))

    # 도메인 다양성
    domains = set()
    for a in actions:
        if a["action_type"] == "recall":
            try:
                p = json.loads(a.get("params") or "{}")
                if p.get("project"):
                    domains.add(p["project"])
            except Exception:
                pass

    total = creation + retrieval + organization + strengthening
    if total == 0:
        mode = "idle"
    elif creation > retrieval:
        mode = "generative"
    elif len(domains) >= 3:
        mode = "exploratory"
    elif organization > 0:
        mode = "organizing"
    else:
        mode = "consolidation"

    return {
        "mode": mode,
        "total": total,
        "creation": creation,
        "retrieval": retrieval,
        "organization": organization,
        "strengthening": strengthening,
        "exploration_domains": len(domains),
    }


def get_recent_energy(days: int = 7) -> dict:
    """최근 N일간의 집계 에너지. 세션 단위가 아닌 기간 집계."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM action_log WHERE created_at >= datetime('now', ?)",
        (f"-{days} days",),
    ).fetchall()
    conn.close()
    actions = [dict(r) for r in rows]

    if not actions:
        return {"mode": "idle", "total": 0, "days": days}

    creation = sum(1 for a in actions if a["action_type"] in ("remember", "auto_link"))
    retrieval = sum(1 for a in actions if a["action_type"] in ("recall", "get_context", "inspect"))
    organization = sum(1 for a in actions if a["action_type"] in ("promote", "merge", "classify"))

    domains = set()
    for a in actions:
        if a["action_type"] == "recall":
            try:
                p = json.loads(a.get("params") or "{}")
                if p.get("project"):
                    domains.add(p["project"])
            except Exception:
                pass

    total = creation + retrieval + organization
    if total == 0:
        mode = "idle"
    elif creation > retrieval:
        mode = "generative"
    elif len(domains) >= 3:
        mode = "exploratory"
    elif organization > 0:
        mode = "organizing"
    else:
        mode = "consolidation"

    return {
        "mode": mode,
        "total": total,
        "creation": creation,
        "retrieval": retrieval,
        "organization": organization,
        "exploration_domains": len(domains),
        "days": days,
    }
```

---

## decide_enrichment_focus() — 에너지 → 배치 설정 변환

```python
# scripts/enrichment_policy.py (신규)

from storage.action_log import get_recent_energy

# 기본값 (에너지 데이터 없을 때)
DEFAULT_POLICY = {
    "phase1_node_limit": 100,     # 새 노드 enrichment
    "phase1_e13_limit": 50,       # cross-domain relations
    "phase1_e14_limit": 6000,     # generic edge refinement
    "phase2_e21_limit": 30,       # contradiction detection
    "phase2_e22_limit": 40,       # assemblage detection
    "phase3_e12_limit": 50,       # layer verification
    "phase3_e6_limit": 15,        # secondary types
    "phase4_e19_limit": 30,       # missing links
    "phase5_enabled": True,       # promotion
}


def decide_enrichment_focus(days: int = 7) -> dict:
    """최근 에너지 패턴에 따라 enrichment 배치 설정 결정.

    Returns:
        dict with phase-specific limits and priorities
    """
    energy = get_recent_energy(days=days)
    mode = energy["mode"]
    total = energy["total"]

    policy = dict(DEFAULT_POLICY)

    if mode == "idle":
        # 활동 없음 → 최소 유지보수
        policy.update({
            "phase1_node_limit": 20,
            "phase1_e13_limit": 10,
            "phase1_e14_limit": 500,
            "phase2_e21_limit": 10,
            "phase2_e22_limit": 10,
            "phase3_e12_limit": 10,
            "phase3_e6_limit": 5,
            "phase4_e19_limit": 10,
            "phase5_enabled": False,
        })
        policy["reason"] = "idle: 최소 유지보수"

    elif mode == "generative":
        # 새 노드 많음 → Phase 1 확대, Phase 4-5 축소
        scale = min(energy["creation"] / 10, 3.0)  # 최대 3배
        policy.update({
            "phase1_node_limit": int(100 * scale),
            "phase1_e13_limit": int(50 * scale),
            "phase1_e14_limit": 6000,
            "phase2_e21_limit": 20,
            "phase2_e22_limit": 20,
            "phase3_e12_limit": 30,
            "phase3_e6_limit": 10,
            "phase4_e19_limit": 15,
            "phase5_enabled": False,  # 생성 모드에서는 승격 판단 유보
        })
        policy["reason"] = f"generative: 새 노드 {energy['creation']}개, scale={scale:.1f}x"

    elif mode == "consolidation":
        # 기존 기억 강화 → Phase 2-3 확대
        policy.update({
            "phase1_node_limit": 50,
            "phase1_e13_limit": 30,
            "phase1_e14_limit": 6000,
            "phase2_e21_limit": 50,      # contradiction 확대
            "phase2_e22_limit": 60,      # assemblage 확대
            "phase3_e12_limit": 80,      # layer 검증 확대
            "phase3_e6_limit": 25,       # secondary types 확대
            "phase4_e19_limit": 20,
            "phase5_enabled": True,
        })
        policy["reason"] = "consolidation: 관계 정밀화 + 품질 검증 우선"

    elif mode == "exploratory":
        # 다양한 도메인 → Phase 4 (크로스도메인) 확대
        policy.update({
            "phase1_node_limit": 50,
            "phase1_e13_limit": 80,      # cross-domain relations 확대
            "phase1_e14_limit": 3000,
            "phase2_e21_limit": 20,
            "phase2_e22_limit": 60,      # assemblage 확대 (도메인 간 결합)
            "phase3_e12_limit": 30,
            "phase3_e6_limit": 10,
            "phase4_e19_limit": 60,      # missing links 확대
            "phase5_enabled": True,
        })
        policy["reason"] = f"exploratory: {energy['exploration_domains']} 도메인 탐색, 크로스도메인 발견 우선"

    elif mode == "organizing":
        # 구조화 활동 → Phase 5 (승격) 확대
        policy.update({
            "phase1_node_limit": 30,
            "phase1_e13_limit": 30,
            "phase1_e14_limit": 3000,
            "phase2_e21_limit": 30,
            "phase2_e22_limit": 30,
            "phase3_e12_limit": 60,      # layer 검증 확대 (승격 전 확인)
            "phase3_e6_limit": 20,
            "phase4_e19_limit": 20,
            "phase5_enabled": True,      # 승격 파이프라인 활성
        })
        policy["reason"] = f"organizing: promote/merge {energy['organization']}회, 승격 판단 우선"

    policy["energy"] = energy
    return policy
```

---

## daily_enrich.py 삽입 지점

### main() 시작 부분 — 정책 결정

```python
# scripts/daily_enrich.py — main() 수정

def main():
    ap = argparse.ArgumentParser(description="mcp-memory enrichment pipeline")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--phase", type=int, help="Run specific phase only (1-5)")
    ap.add_argument("--budget-large", type=int, default=config.TOKEN_BUDGETS["large"])
    ap.add_argument("--budget-small", type=int, default=config.TOKEN_BUDGETS["small"])
    ap.add_argument("--no-energy", action="store_true",
                    help="Ignore energy policy, use defaults")       # <-- 추가
    args = ap.parse_args()

    # ... budget, conn, ne, re, ga 초기화 ...

    # 에너지 기반 정책 결정 (action_log 없으면 default)     # <-- 추가
    if args.no_energy:
        policy = DEFAULT_POLICY
        policy["reason"] = "manual: --no-energy flag"
    else:
        try:
            from scripts.enrichment_policy import decide_enrichment_focus
            policy = decide_enrichment_focus(days=7)
        except Exception:
            policy = DEFAULT_POLICY
            policy["reason"] = "fallback: action_log unavailable"

    print(f"Energy policy: {policy.get('reason', 'default')}")

    # ... phases 실행 (policy 전달) ...
```

### Phase 1 — policy 기반 limit 적용

```python
# scripts/daily_enrich.py — phase1() 수정

def phase1(conn, ne, re, budget, policy=None):               # <-- policy 파라미터 추가
    """Phase 1: E1-E5,E7-E11 + E13-E14,E16-E17."""
    p = policy or DEFAULT_POLICY
    stats = {"nodes": 0, "edges": 0, "errors": 0}

    # 1a. new nodes — policy 기반 limit
    rows = conn.execute(
        "SELECT id FROM nodes WHERE enriched_at IS NULL AND status='active' "
        "ORDER BY created_at DESC LIMIT ?",                  # <-- LIMIT 추가
        (p["phase1_node_limit"],),                           # <-- policy에서
    ).fetchall()
    # ... 이하 동일 ...

    # 1c. E13 cross-domain relations
    if not budget.budget_exhausted("small"):
        try:
            re.run_e13(limit=p["phase1_e13_limit"])          # <-- policy에서
            # ...

    # 1d. E14 refine generic edges
    if not budget.budget_exhausted("small"):
        try:
            re.run_e14(limit=p["phase1_e14_limit"])          # <-- policy에서
            # ...
```

### Phase 2 — policy 기반

```python
def phase2(conn, re, ga, budget, policy=None):
    p = policy or DEFAULT_POLICY

    # 2a. E21 contradiction
    if not budget.budget_exhausted("small"):
        try:
            ga.run_e21_all(limit=p["phase2_e21_limit"])      # <-- policy에서

    # 2b. E22 assemblage
    if not budget.budget_exhausted("small"):
        try:
            ga.run_e22_all(limit=p["phase2_e22_limit"])      # <-- policy에서
```

### Phase 3-5 동일 패턴

```python
def phase3(conn, ne, budget, policy=None):
    p = policy or DEFAULT_POLICY
    # E12: limit=p["phase3_e12_limit"]
    # E6:  limit=p["phase3_e6_limit"]

def phase4(conn, ga, budget, policy=None):
    p = policy or DEFAULT_POLICY
    # E19: limit=p["phase4_e19_limit"]

def phase5(conn, ga, budget, policy=None):
    p = policy or DEFAULT_POLICY
    if not p.get("phase5_enabled", True):
        print("  Phase 5 disabled by energy policy")
        return {}
    # ...
```

### phases 리스트에 policy 전달

```python
    phases = [
        (1, "Phase 1: bulk",      lambda: phase1(conn, ne, re, budget, policy)),
        (2, "Phase 2: reasoning", lambda: phase2(conn, re, ga, budget, policy)),
        (3, "Phase 3: verify",    lambda: phase3(conn, ne, budget, policy)),
        (4, "Phase 4: deep",      lambda: phase4(conn, ga, budget, policy)),
        (5, "Phase 5: judge",     lambda: phase5(conn, ga, budget, policy)),
    ]
```

---

## 보고서에 에너지 정보 추가

```python
# daily_enrich.py — generate_report() 확장

def generate_report(budget, phase_stats, conn, policy=None):
    # ... 기존 코드 ...

    # 에너지 정보 추가
    if policy:
        lines.append("")
        lines.append("## Energy Policy")
        lines.append(f"- Mode: {policy.get('energy', {}).get('mode', 'unknown')}")
        lines.append(f"- Reason: {policy.get('reason', '')}")
        energy = policy.get("energy", {})
        if energy:
            lines.append(f"- Creation: {energy.get('creation', 0)}")
            lines.append(f"- Retrieval: {energy.get('retrieval', 0)}")
            lines.append(f"- Organization: {energy.get('organization', 0)}")
            lines.append(f"- Exploration domains: {energy.get('exploration_domains', 0)}")

    # ... 기존 코드 ...
```

---

## session_context.py 에너지 출력

```python
# scripts/session_context.py — get_context_cli() 확장

def get_context_cli(project=""):
    # ... 기존 출력 (L2+ nodes, Signals, Observations 등) ...

    # 에너지 패턴 출력
    try:
        from storage.action_log import get_recent_energy
        energy = get_recent_energy(days=7)
        if energy["total"] > 0:
            print(f"\n=== 세션 에너지 (최근 7일) ===")
            print(f"  모드: {energy['mode']}")
            print(f"  생성: {energy['creation']}  인출: {energy['retrieval']}  "
                  f"구조화: {energy['organization']}  탐색 도메인: {energy['exploration_domains']}")
            if energy["mode"] == "consolidation":
                print(f"  --> 새 경험 주입 권장")
            elif energy["mode"] == "generative":
                print(f"  --> 구조화/승격 시간 권장")
    except Exception:
        pass  # action_log 미구현 시 무시
```

---

## 데이터 흐름 요약

```
Paul의 세션 활동
  └── remember(), recall(), promote_node()
        └── action_log에 기록 (A-9)
              └── get_recent_energy(days=7) 집계
                    └── decide_enrichment_focus()
                          └── policy dict 반환
                                └── daily_enrich.py main()
                                      ├── Phase 1: policy["phase1_*"]
                                      ├── Phase 2: policy["phase2_*"]
                                      ├── Phase 3: policy["phase3_*"]
                                      ├── Phase 4: policy["phase4_*"]
                                      └── Phase 5: policy["phase5_enabled"]
```

**핵심**: 에너지 정책은 **배치 크기 조절**이다. Phase 자체를 건너뛰지 않는다 (idle 제외).
이것은 Prigogine의 산일 구조에서 **에너지 유입량에 따라 자기조직화 강도가 변하는 것**과 대응한다.

---

## 구현 순서

```
1. action_log 테이블 생성 (A-12 스키마)
2. remember/recall/promote에 action_log.record() 삽입 (A-9 삽입 지점)
3. calculate_session_energy() + get_recent_energy() 구현
4. decide_enrichment_focus() 구현 (enrichment_policy.py)
5. daily_enrich.py에 policy 파라미터 추가 (Phase 1-5)
6. session_context.py에 에너지 출력 추가
7. generate_report()에 에너지 정보 추가
```

**의존성**: 1→2→3→4→5 순차. 6,7은 독립 가능.

**action_log 없이도 동작**: `--no-energy` 플래그 또는 action_log 테이블 미존재 시 DEFAULT_POLICY로 폴백. 기존 daily_enrich.py와 동일 동작 보장.
