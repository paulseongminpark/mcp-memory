"""checks/enrichment_coverage.py — enrichment 커버리지 검증."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from checks import CheckResult
from config import VERIFY_THRESHOLDS


def run() -> list[CheckResult]:
    from storage.sqlite_store import _db

    results = []
    with _db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE status='active'"
        ).fetchone()[0]
        if total == 0:
            return [CheckResult(name="enrichment_coverage", category="enrichment",
                                status="WARN", details={"msg": "no active nodes"})]

        # enrichment_status 분포
        # enrichment_status = '{}' → 미처리 (pending)
        # enrichment_status = '{"E1": ..., ...}' → 처리됨 (enriched)
        # enrichment_status = 'enriched' → 새 형식으로 처리됨
        # enrichment_status = 'failed' → 실패
        pending_count = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE status='active' AND (enrichment_status='{}' OR enrichment_status IS NULL OR enrichment_status='pending')"
        ).fetchone()[0]
        failed_count = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE status='active' AND enrichment_status='failed'"
        ).fetchone()[0]
        # summary가 있으면 enriched로 간주 (enrichment_status 형식 무관)
        enriched_count = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE status='active' AND summary IS NOT NULL AND summary != ''"
        ).fetchone()[0]
        coverage = enriched_count / total

        results.append(CheckResult(
            name="enrichment_coverage",
            category="enrichment",
            score=coverage,
            threshold=VERIFY_THRESHOLDS["enrichment_coverage"],
            details={
                "enriched": enriched_count,
                "pending": pending_count,
                "failed": failed_count,
                "total": total,
            },
        ))

        # summary NULL 비율
        null_summary = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE status='active' AND (summary IS NULL OR summary='')"
        ).fetchone()[0]
        results.append(CheckResult(
            name="summary_null_pct",
            category="enrichment",
            score=null_summary / total,
            threshold=0.5,
            higher_is_better=False,
            details={"null_summary": null_summary, "total": total},
        ))

        # key_concepts NULL 비율
        null_kc = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE status='active' AND (key_concepts IS NULL OR key_concepts='')"
        ).fetchone()[0]
        results.append(CheckResult(
            name="key_concepts_null_pct",
            category="enrichment",
            score=null_kc / total,
            threshold=0.5,
            higher_is_better=False,
            details={"null_key_concepts": null_kc, "total": total},
        ))

        # domains NULL 비율
        null_domains = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE status='active' AND (domains IS NULL OR domains='')"
        ).fetchone()[0]
        results.append(CheckResult(
            name="domains_null_pct",
            category="enrichment",
            score=null_domains / total,
            threshold=0.5,
            higher_is_better=False,
            details={"null_domains": null_domains, "total": total},
        ))

        # quality_score > 0 비율
        qs_positive = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE status='active' AND quality_score > 0"
        ).fetchone()[0]
        results.append(CheckResult(
            name="quality_score_positive_pct",
            category="enrichment",
            score=qs_positive / total,
            threshold=0.3,
            details={"qs_positive": qs_positive, "total": total},
        ))

    return results
