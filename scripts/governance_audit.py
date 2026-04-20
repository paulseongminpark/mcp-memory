#!/usr/bin/env python3
"""governance_audit.py — Loop 4 Governance 기초 측정 (SQLite 범위).

Usage:
    python scripts/governance_audit.py              # 7일 기본, 리포트 작성
    python scripts/governance_audit.py --days 14    # 기간 변경
    python scripts/governance_audit.py --stdout     # 파일 쓰지 않고 stdout

출력: data/reports/governance-audit-YYYYMMDD.md
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config

POLICY_DIR = Path.home() / '.claude' / 'policy'
RULES_DIR = POLICY_DIR / 'rules'


from contextlib import contextmanager


@contextmanager
def _conn():
    # Harden R1 (S): context manager로 close 보장 (sqlite3.Connection의 __exit__는 close 안 함)
    c = sqlite3.connect(str(config.DB_PATH))
    c.row_factory = sqlite3.Row
    try:
        yield c
    finally:
        c.close()


def audit_feedback_rate(days: int) -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _conn() as c:
        rows = c.execute(
            "SELECT feedback_type, COUNT(*) AS n FROM feedback_events "
            "WHERE created_at >= ? GROUP BY feedback_type",
            (cutoff,),
        ).fetchall()
        total = c.execute(
            "SELECT COUNT(*) FROM feedback_events WHERE created_at >= ?",
            (cutoff,),
        ).fetchone()[0]
    distribution = {r['feedback_type']: r['n'] for r in rows}
    reject = distribution.get('reject', 0)
    approve = distribution.get('approve', 0)
    return {
        'days': days,
        'total': total,
        'distribution': distribution,
        'reject_rate': round(reject / total, 3) if total else 0.0,
        'approve_rate': round(approve / total, 3) if total else 0.0,
    }


def audit_retrieval_stats(days: int) -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _conn() as c:
        total = c.execute(
            "SELECT COUNT(*) FROM retrieval_logs WHERE created_at >= ?",
            (cutoff,),
        ).fetchone()[0]
        sessions = c.execute(
            "SELECT COUNT(DISTINCT session_id) FROM retrieval_logs "
            "WHERE created_at >= ? AND session_id != ''",
            (cutoff,),
        ).fetchone()[0]
        cross_n = c.execute(
            "SELECT COUNT(*) FROM retrieval_logs "
            "WHERE created_at >= ? AND cross_domain = 1",
            (cutoff,),
        ).fetchone()[0]
        feedback_linked = c.execute(
            "SELECT COUNT(*) FROM retrieval_logs "
            "WHERE created_at >= ? AND feedback_linked = 1",
            (cutoff,),
        ).fetchone()[0]
        slot_rows = c.execute(
            "SELECT slot_distribution FROM retrieval_logs "
            "WHERE created_at >= ? AND slot_distribution != '{}' LIMIT 500",
            (cutoff,),
        ).fetchall()
    slot_totals: dict[str, int] = {}
    slot_samples = 0
    for row in slot_rows:
        try:
            dist = json.loads(row['slot_distribution'])
            if not isinstance(dist, dict):
                continue
            slot_samples += 1
            for k, v in dist.items():
                if isinstance(v, (int, float)):
                    slot_totals[k] = slot_totals.get(k, 0) + int(v)
        except (ValueError, TypeError):
            continue
    slot_avg = {k: round(v / slot_samples, 2) for k, v in slot_totals.items()} if slot_samples else {}
    return {
        'days': days,
        'total_retrievals': total,
        'unique_sessions': sessions,
        'cross_domain_rate': round(cross_n / total, 3) if total else 0.0,
        'feedback_linked_rate': round(feedback_linked / total, 3) if total else 0.0,
        'slot_samples': slot_samples,
        'slot_avg': slot_avg,
    }


def audit_stale_policy(days: int) -> list[dict]:
    if not RULES_DIR.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stale: list[dict] = []
    with _conn() as c:
        for rule_file in RULES_DIR.glob('*.json'):
            try:
                rule = json.loads(rule_file.read_text(encoding='utf-8'))
            except (ValueError, OSError):
                continue
            compiled_raw = rule.get('compiled_at', '')
            if not compiled_raw:
                stale.append({'name': rule.get('name', rule_file.stem), 'reason': 'no_compiled_at'})
                continue
            try:
                if compiled_raw.endswith('Z'):
                    compiled_at = datetime.fromisoformat(compiled_raw.replace('Z', '+00:00'))
                elif '+' in compiled_raw or compiled_raw.count('-') > 2:
                    compiled_at = datetime.fromisoformat(compiled_raw)
                else:
                    compiled_at = datetime.fromisoformat(compiled_raw).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if compiled_at > cutoff:
                continue
            trait_id = (rule.get('metadata') or {}).get('source_trait_id')
            if not trait_id:
                stale.append({'name': rule['name'], 'reason': 'no_trait_link'})
                continue
            row = c.execute(
                "SELECT status, approval FROM self_model_traits WHERE id = ?",
                (trait_id,),
            ).fetchone()
            if not row:
                stale.append({'name': rule['name'], 'reason': 'trait_missing'})
            elif row['status'] in ('provisional', 'archived') or row['approval'] in ('pending', 'rejected', 'expired'):
                stale.append({
                    'name': rule['name'],
                    'reason': f"trait status={row['status']} approval={row['approval']}",
                })
    return stale


def audit_trait_conflicts() -> dict:
    with _conn() as c:
        total = c.execute(
            "SELECT COUNT(*) FROM self_trait_conflicts WHERE resolved = 0"
        ).fetchone()[0]
        by_source = c.execute(
            "SELECT conflicting_source_type, COUNT(*) AS n FROM self_trait_conflicts "
            "WHERE resolved = 0 GROUP BY conflicting_source_type"
        ).fetchall()
    return {
        'unresolved_total': total,
        'by_source': {r['conflicting_source_type'] or 'null': r['n'] for r in by_source},
    }


def render_markdown(days: int, fb: dict, rt: dict, stale: list[dict], conflicts: dict) -> str:
    today = datetime.now().strftime('%Y-%m-%d')
    md = [
        f"# Governance Audit — {today}",
        "",
        f"> 측정 기간: 최근 **{days}일**. Loop 4 기초 (SQLite 범위, R3 산출물).",
        "",
        "## 1. Feedback Rate",
        "",
        f"- 전체 이벤트: **{fb['total']}**",
        f"- reject_rate: `{fb['reject_rate']}` / approve_rate: `{fb['approve_rate']}`",
        f"- 분포: `{fb['distribution']}`",
        "",
        "## 2. Retrieval Stats",
        "",
        f"- 전체 retrieval: **{rt['total_retrievals']}** (고유 세션 {rt['unique_sessions']})",
        f"- cross_domain_rate: `{rt['cross_domain_rate']}`",
        f"- feedback_linked_rate: `{rt['feedback_linked_rate']}`",
        f"- 슬롯 평균 (샘플 {rt['slot_samples']}개): `{rt['slot_avg']}`",
        "",
        "## 3. Stale Policy Rules",
        "",
        f"- stale 후보: **{len(stale)}개** (기준: compiled_at > {days}일 전 + trait unverified/missing)",
    ]
    if stale:
        md.append("")
        md.append("| rule name | reason |")
        md.append("|-----------|--------|")
        for s in stale[:30]:
            md.append(f"| `{s['name']}` | {s['reason']} |")
        if len(stale) > 30:
            md.append(f"| … | 외 {len(stale) - 30}건 |")
    md.extend([
        "",
        "## 4. Trait Conflicts (Unresolved)",
        "",
        f"- 미해결 총계: **{conflicts['unresolved_total']}**",
        f"- 소스별: `{conflicts['by_source']}`",
        "",
        "## 5. 권장 조치",
        "",
    ])
    if fb['reject_rate'] > 0.2:
        md.append("- ⚠️ reject_rate 20% 초과 — policy/claim 품질 점검 필요")
    if rt['cross_domain_rate'] < 0.1 and rt['total_retrievals'] > 10:
        md.append("- ⚠️ cross_domain_rate 낮음 — 프로젝트 간 전이 불충분 여부 검토")
    if len(stale) > 20:
        md.append(f"- ⚠️ stale policy {len(stale)}건 — trait 재검증 또는 archive 결정 필요")
    if conflicts['unresolved_total'] > 5:
        md.append(f"- ⚠️ 미해결 trait conflicts {conflicts['unresolved_total']}건 — Paul 수동 확인 대기")
    md.append("")
    md.append(f"---\n_생성: `scripts/governance_audit.py` (R3 기초). 자동 반영은 Phase 4 이월._")
    return "\n".join(md)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=7)
    ap.add_argument('--stdout', action='store_true')
    args = ap.parse_args()

    fb = audit_feedback_rate(args.days)
    rt = audit_retrieval_stats(args.days)
    stale = audit_stale_policy(args.days)
    conflicts = audit_trait_conflicts()

    md = render_markdown(args.days, fb, rt, stale, conflicts)

    if args.stdout:
        print(md)
    else:
        out_dir = ROOT / 'data' / 'reports'
        out_dir.mkdir(parents=True, exist_ok=True)
        # Harden R1 (R): 동일 날짜 재실행 시 overwrite 방지 — HHMMSS suffix
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        out_file = out_dir / f"governance-audit-{stamp}.md"
        out_file.write_text(md, encoding='utf-8')
        # 최신 alias
        latest = out_dir / "governance-audit-latest.md"
        try:
            latest.write_text(md, encoding='utf-8')
        except OSError:
            pass
        print(f"Wrote: {out_file}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
