"""checks/promotion_pipeline.py — 승격 파이프라인 검증."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from checks import CheckResult


def run() -> list[CheckResult]:
    from config import VALID_PROMOTIONS, PROMOTE_LAYER
    from storage.sqlite_store import _db

    results = []

    # 1. Signal 노드 존재 여부
    with _db() as conn:
        signal_count = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE type='Signal' AND status='active'"
        ).fetchone()[0]
    results.append(CheckResult(
        name="signal_nodes_exist",
        category="promotion",
        status="PASS" if signal_count > 0 else "WARN",
        details={"signal_count": signal_count},
    ))

    # 2. promote_node() import 성공
    try:
        from tools.promote_node import promote_node
        results.append(CheckResult(
            name="promote_node_import",
            category="promotion",
            status="PASS",
        ))
    except Exception as e:
        results.append(CheckResult(
            name="promote_node_import",
            category="promotion",
            status="FAIL",
            details={"error": str(e)},
        ))

    # 3. VALID_PROMOTIONS 경로 gate 로직 검증 (시뮬레이션, deprecated 제외)
    DEPRECATED = {"Evidence", "Heuristic", "Concept"}
    failed_paths = []
    for src_type, tgt_types in VALID_PROMOTIONS.items():
        src_layer = PROMOTE_LAYER.get(src_type)
        for tgt_type in tgt_types:
            if tgt_type in DEPRECATED:
                continue  # deprecated 타입은 건너뜀
            tgt_layer = PROMOTE_LAYER.get(tgt_type)
            if src_layer is None or tgt_layer is None:
                failed_paths.append(f"{src_type}→{tgt_type}: layer None")
            elif tgt_layer < src_layer:
                # 동일 레이어 승격(lateral) 허용, 하위 레이어로 승격만 금지
                failed_paths.append(f"{src_type}→{tgt_type}: tgt layer({tgt_layer}) < src({src_layer})")
    results.append(CheckResult(
        name="valid_promotions_layer_check",
        category="promotion",
        status="PASS" if not failed_paths else "FAIL",
        details={"failed_paths": failed_paths},
    ))

    # 4. promotion_candidate=1 노드 수
    with _db() as conn:
        candidate_count = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE promotion_candidate=1 AND status='active'"
        ).fetchone()[0]
    results.append(CheckResult(
        name="promotion_candidates",
        category="promotion",
        status="PASS",
        details={"count": candidate_count},
    ))

    # 5. L4/L5 접근 제어 (_check_layer_permissions 직접 호출로 검증)
    from utils.access_control import _check_layer_permissions
    l4_write_system = _check_layer_permissions(4, "write", "system")
    l5_write_system = _check_layer_permissions(5, "write", "system")
    # system은 L4/L5 write 불가여야 정상
    results.append(CheckResult(
        name="l4_l5_access_control",
        category="promotion",
        status="PASS" if not l4_write_system and not l5_write_system else "WARN",
        details={
            "l4_write_by_system": l4_write_system,
            "l5_write_by_system": l5_write_system,
        },
    ))

    return results
