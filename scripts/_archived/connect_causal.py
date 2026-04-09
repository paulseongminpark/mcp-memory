#!/usr/bin/env python3
"""WS-3.2: 끊어진 인과 체인 보강.

타입별 causal relation을 vector search + 타입 필터로 연결.

Usage:
  python scripts/connect_causal.py --dry-run
  python scripts/connect_causal.py
"""
import argparse
import os
import sys

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from storage import sqlite_store, vector_store

# 타입별 causal 규칙: (source_type, missing_relation, target_types, new_relation)
CAUSAL_RULES = [
    # Decision without led_to → Pattern/Insight/Failure
    ("Decision", "led_to", ["Pattern", "Insight"], "led_to", 0.45),
    ("Decision", "resulted_in", ["Failure"], "resulted_in", 0.45),
    # Failure without resolved_by → Decision/Insight
    ("Failure", "resolved_by", ["Decision", "Insight"], "resolved_by", 0.45),
    # Signal without realized_as → Pattern/Insight
    ("Signal", "realized_as", ["Pattern", "Insight"], "realized_as", 0.50),
    # Question without resolved_by → Insight/Decision
    ("Question", "resolved_by", ["Insight", "Decision"], "resolved_by", 0.45),
]


def get_broken_nodes(src_type: str, missing_rel: str) -> list[dict]:
    """causal edge가 없는 노드 추출."""
    with sqlite_store._db() as conn:
        rows = conn.execute(f"""
            SELECT n.id, n.type, n.content, n.project, n.layer
            FROM nodes n
            WHERE n.type = ? AND n.status = 'active'
            AND NOT EXISTS (
                SELECT 1 FROM edges e WHERE e.status = 'active'
                AND e.source_id = n.id AND e.relation = ?
            )
        """, (src_type, missing_rel)).fetchall()
    return [
        {"id": r[0], "type": r[1], "content": r[2], "project": r[3], "layer": r[4]}
        for r in rows
    ]


def find_causal_target(node: dict, target_types: list[str], min_cosine: float) -> tuple[int, float] | None:
    """vector search로 causal target 찾기. 같은 project 우선."""
    for tgt_type in target_types:
        try:
            where = {"type": tgt_type}
            results = vector_store.search(
                node["content"][:500], top_k=5, where=where
            )
        except Exception:
            continue

        for nid, distance, _ in results:
            if nid == node["id"]:
                continue
            cosine = 1.0 - distance
            if cosine < min_cosine:
                continue
            # 같은 project 우선
            tgt = sqlite_store.get_node(nid)
            if not tgt or tgt.get("status") != "active":
                continue
            if tgt.get("project") == node["project"]:
                return nid, cosine
            # cross-project는 더 높은 threshold
            if cosine >= min_cosine + 0.10:
                return nid, cosine
    return None


def connect(src_id: int, tgt_id: int, relation: str, strength: float, dry_run: bool) -> bool:
    """edge 생성. 이미 있으면 skip."""
    with sqlite_store._db() as conn:
        existing = conn.execute(
            """SELECT id FROM edges WHERE status='active'
               AND source_id=? AND target_id=? AND relation=?""",
            (src_id, tgt_id, relation)
        ).fetchone()
        if existing:
            return False

    if dry_run:
        return True

    sqlite_store.insert_edge(
        source_id=src_id,
        target_id=tgt_id,
        relation=relation,
        strength=strength,
        generation_method="semantic_auto",
    )
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    total_created = 0
    total_skipped = 0

    for src_type, missing_rel, tgt_types, new_rel, min_cos in CAUSAL_RULES:
        broken = get_broken_nodes(src_type, missing_rel)
        created = 0
        skipped = 0

        for i, node in enumerate(broken, 1):
            result = find_causal_target(node, tgt_types, min_cos)
            if result:
                tgt_id, cosine = result
                if connect(node["id"], tgt_id, new_rel, cosine, args.dry_run):
                    created += 1
                else:
                    skipped += 1

            if i % 50 == 0:
                print(f"  {src_type} → {new_rel}: {i}/{len(broken)}, +{created}")

        prefix = "DRY " if args.dry_run else ""
        print(f"{prefix}{src_type} → {new_rel}: {created}/{len(broken)} created, {skipped} skipped")
        total_created += created
        total_skipped += skipped

    print(f"\nTotal: {total_created} created, {total_skipped} skipped")


if __name__ == "__main__":
    main()
