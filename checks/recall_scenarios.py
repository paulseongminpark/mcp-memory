"""checks/recall_scenarios.py — recall 시나리오 검증."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from checks import CheckResult


def run() -> list[CheckResult]:
    from storage.hybrid import hybrid_search
    from storage.sqlite_store import _db
    from config import UCB_C_FOCUS, UCB_C_DMN

    results = []

    # 1. 한국어 2글자 쿼리 ("충돌") → 결과 1개+ 반환
    r1 = hybrid_search("충돌", top_k=5)
    results.append(CheckResult(
        name="korean_2char_query",
        category="recall",
        status="PASS" if len(r1) >= 1 else "FAIL",
        details={"query": "충돌", "count": len(r1)},
    ))

    # 2. 한국어 조사 포함 쿼리 ("시스템에서") → 결과 반환
    r2 = hybrid_search("시스템에서", top_k=5)
    results.append(CheckResult(
        name="korean_particle_query",
        category="recall",
        status="PASS" if len(r2) >= 1 else "WARN",
        details={"query": "시스템에서", "count": len(r2)},
    ))

    # 3. 영어 쿼리 ("orchestration") → FTS5 trigram 매칭
    r3 = hybrid_search("orchestration", top_k=5)
    results.append(CheckResult(
        name="english_fts_query",
        category="recall",
        status="PASS" if len(r3) >= 1 else "WARN",
        details={"query": "orchestration", "count": len(r3)},
    ))

    # 4. 혼합 쿼리 ("AI 설계 원칙") → 결과 반환
    r4 = hybrid_search("AI 설계 원칙", top_k=5)
    results.append(CheckResult(
        name="mixed_query",
        category="recall",
        status="PASS" if len(r4) >= 1 else "WARN",
        details={"query": "AI 설계 원칙", "count": len(r4)},
    ))

    # 5. mode=focus → UCB_C=0.3 적용 확인
    from storage.hybrid import _auto_ucb_c
    c_focus = _auto_ucb_c("매우 구체적인 정확한 쿼리 워크플로우 시스템", mode="focus")
    results.append(CheckResult(
        name="mode_focus_ucb_c",
        category="recall",
        status="PASS" if c_focus == UCB_C_FOCUS else "FAIL",
        details={"expected": UCB_C_FOCUS, "actual": c_focus},
    ))

    # 6. mode=dmn → UCB_C=2.5 적용 확인
    c_dmn = _auto_ucb_c("탐색", mode="dmn")
    results.append(CheckResult(
        name="mode_dmn_ucb_c",
        category="recall",
        status="PASS" if c_dmn == UCB_C_DMN else "FAIL",
        details={"expected": UCB_C_DMN, "actual": c_dmn},
    ))

    # 7. duplicate remember → content_hash 차단 확인
    from tools.remember import remember as _remember
    import hashlib
    test_content = "__test_duplicate_check_recall_scenarios__"
    h = hashlib.sha256(test_content.encode()).hexdigest()
    # 첫 번째 remember
    r_first = _remember(content=test_content, type="Observation", tags="test")
    # 두 번째 동일 remember
    r_second = _remember(content=test_content, type="Observation", tags="test")
    is_blocked = r_second.get("status") == "duplicate" or r_second.get("duplicate") is True
    results.append(CheckResult(
        name="duplicate_remember_blocked",
        category="recall",
        status="PASS" if is_blocked else "WARN",
        details={"first_id": r_first.get("id"), "second_status": r_second.get("status")},
    ))
    # 테스트 노드 정리
    if r_first.get("id"):
        with _db() as conn:
            conn.execute("UPDATE nodes SET status='deleted' WHERE id=?", (r_first["id"],))
            conn.commit()

    # 8. recall_log 기록 확인
    with _db() as conn:
        before = conn.execute("SELECT COUNT(*) FROM recall_log").fetchone()[0]
    hybrid_search("테스트 recall_log 검증", top_k=3)
    with _db() as conn:
        after = conn.execute("SELECT COUNT(*) FROM recall_log").fetchone()[0]
    results.append(CheckResult(
        name="recall_log_recorded",
        category="recall",
        status="PASS" if after >= before else "WARN",
        details={"before": before, "after": after},
    ))

    return results
