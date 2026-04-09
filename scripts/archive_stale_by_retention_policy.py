#!/usr/bin/env python3
"""잔여 stale 노드에 대해 plane별 retention policy를 적용한다."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

KEEP_RULES = (
    {
        "label": "hot_capture_keep",
        "rule": "source IN ('checkpoint', 'claude')",
        "reason": "checkpoint/claude는 오래돼도 운영 지식이 많아 자동 archive 금지",
    },
    {
        "label": "canonical_docs_keep",
        "rule": (
            "source LIKE 'obsidian:01_projects\\06_mcp-memory\\docs\\%' ESCAPE '\\' "
            "OR source LIKE 'obsidian:HOME.md%' ESCAPE '\\' "
            "OR source LIKE 'obsidian:01_projects\\01_orchestration\\REFERENCE.md%' ESCAPE '\\'"
        ),
        "reason": "설계/워크플로우/레퍼런스 문서는 stale여도 SoT 성격이라 active 유지",
    },
)

ARCHIVE_RULES = (
    {
        "label": "page12_command_cookbook",
        "rule": (
            "source = 'obsidian:01_projects\\04_monet-lab\\docs\\plans\\2026-02-22-page-12-implementation.md#8013135c7cf3f600' "
            "AND type = 'Tool'"
        ),
        "reason": "명령/조작 cookbook은 30일 이상 미접근 시 active ontology 가치가 낮음",
    },
    {
        "label": "dated_digest_impl",
        "rule": (
            "source = 'obsidian:01_projects\\03_tech-review\\blog\\docs\\plans\\2026-02-18-daily-digest-impl.md#dc443a29d25fa44f'"
        ),
        "reason": "dated external digest content는 personal durable memory보다 temporal report에 가까움",
    },
)


def _base_where(days: int) -> str:
    keep_clause = " OR ".join(f"({item['rule']})" for item in KEEP_RULES)
    return f"""
        status='active'
        AND COALESCE(visit_count, 0)=0
        AND datetime(created_at) < datetime('now', '-{days} day')
        AND COALESCE(node_role, '') != 'knowledge_core'
        AND COALESCE(epistemic_status, '') != 'validated'
        AND NOT ({keep_clause})
    """


def _collect_rows(conn: sqlite3.Connection, days: int) -> list[dict]:
    base = _base_where(days)
    out: list[dict] = []
    for item in ARCHIVE_RULES:
        rows = conn.execute(
            f"""
            SELECT id, source, type, project, created_at, content
            FROM nodes
            WHERE {base} AND ({item['rule']})
            ORDER BY id
            """
        ).fetchall()
        for row in rows:
            out.append(
                {
                    "id": row["id"],
                    "source": row["source"],
                    "type": row["type"],
                    "project": row["project"],
                    "created_at": row["created_at"],
                    "content": (row["content"] or "")[:180],
                    "rule_label": item["label"],
                    "rule_reason": item["reason"],
                }
            )
    out.sort(key=lambda row: (row["rule_label"], row["id"]))
    return out


def collect_candidates(conn: sqlite3.Connection, days: int, sample_limit: int = 40) -> dict:
    rows = _collect_rows(conn, days)
    by_rule: dict[str, int] = {}
    for row in rows:
        by_rule[row["rule_label"]] = by_rule.get(row["rule_label"], 0) + 1
    return {
        "candidate_count": len(rows),
        "by_rule": by_rule,
        "keep_rules": [{"label": item["label"], "reason": item["reason"]} for item in KEEP_RULES],
        "archive_rules": [{"label": item["label"], "reason": item["reason"]} for item in ARCHIVE_RULES],
        "samples": rows[:sample_limit],
    }


def apply_archive(conn: sqlite3.Connection, days: int) -> dict:
    rows = _collect_rows(conn, days)
    ids = [row["id"] for row in rows]
    now = datetime.now(timezone.utc).isoformat()
    if not ids:
        return {"archived_count": 0, "updated_at": now}

    conn.executemany(
        "UPDATE nodes SET status='archived', updated_at=? WHERE id=?",
        [(now, node_id) for node_id in ids],
    )
    conn.commit()
    return {
        "archived_count": len(ids),
        "updated_at": now,
        "sample_ids": ids[:40],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="archive stale nodes by retention policy")
    parser.add_argument("--db", type=Path, default=config.DB_PATH, help="memory.db path")
    parser.add_argument("--days", type=int, default=30, help="minimum age in days")
    parser.add_argument("--apply", action="store_true", help="실제 archive 수행")
    parser.add_argument("--report", type=Path, help="JSON report output path")
    parser.add_argument("--sample-limit", type=int, default=40, help="sample row count")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    try:
        payload: dict[str, object] = {
            "db": str(args.db),
            "days": args.days,
            "apply": args.apply,
            "candidates": collect_candidates(conn, args.days, sample_limit=args.sample_limit),
        }
        if args.apply:
            payload["applied"] = apply_archive(conn, args.days)

        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        print(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
