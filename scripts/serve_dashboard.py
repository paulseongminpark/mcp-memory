#!/usr/bin/env python3
"""실시간 대시보드 서버 — 매 요청마다 DB에서 신선한 데이터로 생성.

Usage:
    python3 scripts/serve_dashboard.py        # http://localhost:7676
    python3 scripts/serve_dashboard.py --port 8080
"""

import os
import sys
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from scripts.dashboard import generate_dashboard, _build_html
from config import DB_PATH
from scripts.health_metrics import get_active_orphan_count


def _get_fresh_html() -> str:
    """DB에서 직접 읽어 HTML 생성 (파일 저장 없이)."""
    import sqlite3, json
    from pathlib import Path

    if not DB_PATH.exists():
        return "<h1>DB not found</h1>"

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    total_nodes = conn.execute("SELECT COUNT(*) FROM nodes WHERE status='active'").fetchone()[0]
    total_edges = conn.execute("SELECT COUNT(*) FROM edges WHERE status='active'").fetchone()[0]

    type_dist = conn.execute(
        "SELECT type, COUNT(*) c FROM nodes WHERE status='active' GROUP BY type ORDER BY c DESC"
    ).fetchall()
    type_data = {r["type"]: r["c"] for r in type_dist}

    proj_dist = conn.execute(
        "SELECT COALESCE(NULLIF(project,''), 'none') p, COUNT(*) c FROM nodes WHERE status='active' GROUP BY p ORDER BY c DESC"
    ).fetchall()
    proj_data = {r["p"]: r["c"] for r in proj_dist}

    rel_dist = conn.execute(
        "SELECT relation, COUNT(*) c FROM edges WHERE status='active' GROUP BY relation ORDER BY c DESC"
    ).fetchall()
    rel_data = {r["relation"]: r["c"] for r in rel_dist}

    recent = conn.execute("""
        SELECT id, type, content, project, tags, created_at
        FROM nodes WHERE status='active' AND type != 'Conversation'
        ORDER BY created_at DESC LIMIT 20
    """).fetchall()
    recent_list = [dict(r) for r in recent]

    edges = conn.execute("""
        SELECT e.source_id, e.target_id, e.relation, e.strength,
               s.type as s_type, t.type as t_type
        FROM edges e
        JOIN nodes s ON s.id = e.source_id
        JOIN nodes t ON t.id = e.target_id
        WHERE e.status='active'
          AND s.status='active'
          AND t.status='active'
    """).fetchall()
    edge_list = [dict(r) for r in edges]

    orphan_count = get_active_orphan_count(conn)

    node_ids_in_graph = set()
    for e in edge_list:
        node_ids_in_graph.add(e["source_id"])
        node_ids_in_graph.add(e["target_id"])

    graph_nodes = []
    for nid in node_ids_in_graph:
        n = conn.execute("SELECT * FROM nodes WHERE id = ?", (nid,)).fetchone()
        if n and n["status"] == "active":
            graph_nodes.append({"id": n["id"], "type": n["type"], "label": n["content"][:50], "project": n["project"] or ""})

    extra = conn.execute("""
        SELECT * FROM nodes WHERE status='active' AND type != 'Conversation'
        ORDER BY created_at DESC LIMIT 15
    """).fetchall()
    for n in extra:
        if n["id"] not in node_ids_in_graph:
            graph_nodes.append({"id": n["id"], "type": n["type"], "label": n["content"][:50], "project": n["project"] or ""})
            node_ids_in_graph.add(n["id"])

    conn.close()

    graph_edges = [{"source": e["source_id"], "target": e["target_id"], "relation": e["relation"], "strength": e["strength"]} for e in edge_list]

    return _build_html(
        total_nodes=total_nodes,
        total_edges=total_edges,
        orphan_count=orphan_count,
        type_data=type_data,
        proj_data=proj_data,
        rel_data=rel_data,
        recent_list=recent_list,
        graph_nodes=graph_nodes,
        graph_edges=graph_edges,
    )


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/dashboard":
            html = _get_fresh_html()
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # 로그 억제


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7676)
    args = parser.parse_args()

    server = HTTPServer(("localhost", args.port), DashboardHandler)
    print(f"Dashboard: http://localhost:{args.port}")
    print(f"DB: {DB_PATH}")
    print(f"브라우저 새로고침으로 갱신 | Ctrl+C로 종료")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n종료")
