#!/usr/bin/env python3
"""메모리 시스템 대시보드 HTML 생성.

실행: python3 scripts/dashboard.py
결과: data/dashboard.html → 브라우저에서 열기
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH, DATA_DIR
from scripts.health_metrics import get_active_orphan_count


def generate_dashboard() -> str:
    if not DB_PATH.exists():
        return "DB not found"

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # 데이터 수집
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

    # 최근 노드 (비-Conversation)
    recent = conn.execute("""
        SELECT id, type, content, project, tags, created_at
        FROM nodes WHERE status='active' AND type != 'Conversation'
        ORDER BY created_at DESC LIMIT 20
    """).fetchall()
    recent_list = [dict(r) for r in recent]

    # 에지 목록 (그래프용)
    edges = conn.execute("""
        SELECT e.source_id, e.target_id, e.relation, e.strength,
               s.type as s_type, s.content as s_content,
               t.type as t_type, t.content as t_content
        FROM edges e
        JOIN nodes s ON s.id = e.source_id
        JOIN nodes t ON t.id = e.target_id
        WHERE e.status='active'
          AND s.status='active'
          AND t.status='active'
    """).fetchall()
    edge_list = [dict(r) for r in edges]

    # 고립 노드
    orphan_count = get_active_orphan_count(conn)

    conn.close()

    # 그래프 노드/에지 JSON (비-Conversation만)
    graph_nodes = []
    node_ids_in_graph = set()
    for e in edge_list:
        node_ids_in_graph.add(e["source_id"])
        node_ids_in_graph.add(e["target_id"])

    conn2 = sqlite3.connect(str(DB_PATH))
    conn2.row_factory = sqlite3.Row
    for nid in node_ids_in_graph:
        n = conn2.execute("SELECT * FROM nodes WHERE id = ?", (nid,)).fetchone()
        if n and n["status"] == "active":
            graph_nodes.append({"id": n["id"], "type": n["type"], "label": n["content"][:50], "project": n["project"] or ""})

    # 연결 없는 주요 노드도 추가 (비-Conversation, 최근 15개)
    extra = conn2.execute("""
        SELECT * FROM nodes WHERE status='active' AND type != 'Conversation'
        ORDER BY created_at DESC LIMIT 15
    """).fetchall()
    for n in extra:
        if n["id"] not in node_ids_in_graph:
            graph_nodes.append({"id": n["id"], "type": n["type"], "label": n["content"][:50], "project": n["project"] or ""})
            node_ids_in_graph.add(n["id"])
    conn2.close()

    graph_edges = [{"source": e["source_id"], "target": e["target_id"], "relation": e["relation"], "strength": e["strength"]} for e in edge_list]

    # HTML 생성
    html = _build_html(
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

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    return str(out)


TYPE_COLORS = {
    "Decision": "#4CAF50", "Failure": "#F44336", "Pattern": "#2196F3",
    "Identity": "#9C27B0", "Preference": "#FF9800", "Goal": "#00BCD4",
    "Insight": "#FFEB3B", "Question": "#FF5722", "Principle": "#3F51B5",
    "AntiPattern": "#E91E63", "Project": "#009688", "Tool": "#607D8B",
    "Conversation": "#795548", "Unclassified": "#9E9E9E",
    "Metaphor": "#AB47BC", "Connection": "#26A69A", "Evolution": "#5C6BC0",
    "Breakthrough": "#FFA726", "SystemVersion": "#78909C", "Experiment": "#EC407A",
    "Framework": "#42A5F5", "Workflow": "#66BB6A", "Tension": "#EF5350",
    "Narrative": "#7E57C2", "Skill": "#29B6F6", "Agent": "#26C6DA",
}

def _build_html(**d) -> str:
    type_labels = json.dumps(list(d["type_data"].keys()))
    type_values = json.dumps(list(d["type_data"].values()))
    type_colors = json.dumps([TYPE_COLORS.get(t, "#78909C") for t in d["type_data"]])
    proj_labels = json.dumps(list(d["proj_data"].keys()))
    proj_values = json.dumps(list(d["proj_data"].values()))
    graph_nodes_json = json.dumps(d["graph_nodes"], ensure_ascii=False)
    graph_edges_json = json.dumps(d["graph_edges"], ensure_ascii=False)
    type_colors_json = json.dumps(TYPE_COLORS)

    recent_rows = ""
    for r in d["recent_list"]:
        color = TYPE_COLORS.get(r["type"], "#78909C")
        content = r["content"][:80].replace("<", "&lt;")
        recent_rows += f"""<tr>
            <td>#{r['id']}</td>
            <td><span class="badge" style="background:{color}">{r['type']}</span></td>
            <td>{content}</td>
            <td>{r['project'] or '-'}</td>
            <td>{r['tags'][:30] if r['tags'] else '-'}</td>
            <td>{r['created_at'][:16]}</td>
        </tr>"""

    rel_rows = ""
    for rel, cnt in d["rel_data"].items():
        rel_rows += f"<tr><td>{rel}</td><td>{cnt}</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Memory System Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, 'Pretendard', sans-serif; background: #0f0f1a; color: #e0e0e0; }}
.header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 24px 32px; border-bottom: 1px solid #333; }}
.header h1 {{ font-size: 20px; font-weight: 600; }}
.header .stats {{ display: flex; gap: 24px; margin-top: 12px; }}
.stat {{ background: rgba(255,255,255,0.05); padding: 12px 20px; border-radius: 8px; }}
.stat .num {{ font-size: 28px; font-weight: 700; color: #64B5F6; }}
.stat .label {{ font-size: 12px; color: #888; margin-top: 2px; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 16px 32px; }}
.card {{ background: #1a1a2e; border: 1px solid #2a2a3e; border-radius: 10px; padding: 20px; }}
.card h2 {{ font-size: 14px; color: #888; text-transform: uppercase; margin-bottom: 12px; letter-spacing: 1px; }}
.full {{ grid-column: 1 / -1; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid #222; }}
th {{ color: #888; font-weight: 500; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; color: #fff; font-weight: 600; }}
#graph {{ width: 100%; height: 650px; cursor: grab; }}
#graph:active {{ cursor: grabbing; }}
canvas {{ max-height: 300px; }}
.graph-controls {{ margin-bottom: 8px; display: flex; gap: 8px; }}
.graph-controls button {{ background: #2a2a3e; border: 1px solid #444; color: #ccc; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; }}
.graph-controls button:hover {{ background: #3a3a5e; }}
</style>
</head>
<body>
<div class="header">
    <h1>External Memory System</h1>
    <div class="stats">
        <div class="stat"><div class="num">{d['total_nodes']}</div><div class="label">Nodes</div></div>
        <div class="stat"><div class="num">{d['total_edges']}</div><div class="label">Edges</div></div>
        <div class="stat"><div class="num">{d['orphan_count']}</div><div class="label">Orphan Nodes</div></div>
        <div class="stat"><div class="num">{len(d['type_data'])}</div><div class="label">Active Types</div></div>
    </div>
</div>

<div class="grid">
    <div class="card">
        <h2>Node Type Distribution</h2>
        <canvas id="typeChart"></canvas>
    </div>
    <div class="card">
        <h2>Project Distribution</h2>
        <canvas id="projChart"></canvas>
    </div>
    <div class="card full">
        <h2>Knowledge Graph</h2>
        <div class="graph-controls">
            <button onclick="zoomReset()">리셋</button>
            <button onclick="zoomIn()">확대 +</button>
            <button onclick="zoomOut()">축소 -</button>
            <span style="color:#666;font-size:11px;margin-left:8px">스크롤 = 줌 | 빈 공간 드래그 = 이동 | 노드 드래그 = 이동</span>
        </div>
        <svg id="graph"></svg>
    </div>
    <div class="card full">
        <h2>Recent Memories (non-Conversation)</h2>
        <table>
            <thead><tr><th>ID</th><th>Type</th><th>Content</th><th>Project</th><th>Tags</th><th>Created</th></tr></thead>
            <tbody>{recent_rows}</tbody>
        </table>
    </div>
    <div class="card">
        <h2>Relationship Types</h2>
        <table>
            <thead><tr><th>Relation</th><th>Count</th></tr></thead>
            <tbody>{rel_rows if rel_rows else '<tr><td colspan="2">No edges yet</td></tr>'}</tbody>
        </table>
    </div>
</div>

<script>
// Charts
new Chart(document.getElementById('typeChart'), {{
    type: 'doughnut',
    data: {{
        labels: {type_labels},
        datasets: [{{ data: {type_values}, backgroundColor: {type_colors}, borderWidth: 0 }}]
    }},
    options: {{ plugins: {{ legend: {{ position: 'right', labels: {{ color: '#ccc', font: {{ size: 11 }} }} }} }} }}
}});

new Chart(document.getElementById('projChart'), {{
    type: 'bar',
    data: {{
        labels: {proj_labels},
        datasets: [{{ data: {proj_values}, backgroundColor: '#64B5F6', borderRadius: 4 }}]
    }},
    options: {{
        indexAxis: 'y',
        plugins: {{ legend: {{ display: false }} }},
        scales: {{ x: {{ ticks: {{ color: '#888' }} }}, y: {{ ticks: {{ color: '#ccc' }} }} }}
    }}
}});

// D3 Force Graph
const gNodes = {graph_nodes_json};
const gEdges = {graph_edges_json};
const typeColors = {type_colors_json};

const svg = d3.select("#graph");
const width = svg.node().parentElement.clientWidth;
const height = 650;
svg.attr("width", width).attr("height", height).attr("viewBox", `0 0 ${{width}} ${{height}}`);

// zoom/pan 컨테이너
const zoomG = svg.append("g").attr("class", "zoom-container");

const zoomBehavior = d3.zoom()
    .scaleExtent([0.1, 5])
    .on("zoom", (e) => zoomG.attr("transform", e.transform));
svg.call(zoomBehavior);
window.zoomReset = () => svg.transition().duration(400).call(zoomBehavior.transform, d3.zoomIdentity.translate(width/2, height/2).scale(0.8));
window.zoomIn  = () => svg.transition().duration(300).call(zoomBehavior.scaleBy, 1.4);
window.zoomOut = () => svg.transition().duration(300).call(zoomBehavior.scaleBy, 0.7);

if (gNodes.length > 0) {{
    const sim = d3.forceSimulation(gNodes)
        .alphaDecay(0.05)
        .force("link", d3.forceLink(gEdges).id(d => d.id).distance(100))
        .force("charge", d3.forceManyBody().strength(-250))
        .force("center", d3.forceCenter(width/2, height/2))
        .force("collision", d3.forceCollide(18));

    // 에지
    const linkG = zoomG.append("g");
    const link = linkG.selectAll("line").data(gEdges).enter().append("line")
        .attr("stroke", "#444").attr("stroke-width", d => Math.max(1, (d.strength||0.5) * 2));

    // 에지 레이블
    const linkLabel = linkG.selectAll("text").data(gEdges).enter().append("text")
        .text(d => d.relation)
        .attr("fill", "#555").attr("font-size", "9px").attr("text-anchor", "middle")
        .style("pointer-events", "none");

    // 노드 그룹 (circle + label을 <g>로 묶어 드래그 통합)
    const dragHandler = d3.drag()
        .on("start", (e, d) => {{ if(!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }})
        .on("drag",  (e, d) => {{ d.fx=e.x; d.fy=e.y; }})
        .on("end",   (e, d) => {{ if(!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }});

    const nodeG = zoomG.append("g");
    const nodeGroup = nodeG.selectAll("g").data(gNodes).enter().append("g")
        .style("cursor", "pointer")
        .call(dragHandler);

    nodeGroup.append("circle")
        .attr("r", 10)
        .attr("fill", d => typeColors[d.type] || "#78909C")
        .attr("stroke", "#fff").attr("stroke-width", 1.5);

    nodeGroup.append("text")
        .text(d => `#${{d.id}} ${{d.label.substring(0,22)}}`)
        .attr("fill", "#ccc").attr("font-size", "10px")
        .attr("dx", 13).attr("dy", 4)
        .style("pointer-events", "none");

    nodeGroup.append("title")
        .text(d => `#${{d.id}} [${{d.type}}]\\n${{d.label}}\\nproject: ${{d.project||"-"}}`);

    sim.on("tick", () => {{
        link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y)
            .attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
        linkLabel.attr("x",d=>(d.source.x+d.target.x)/2).attr("y",d=>(d.source.y+d.target.y)/2);
        nodeGroup.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
    }});

    // 초기 줌 fit + 시뮬레이션 정지
    setTimeout(() => {{
        sim.stop();
        svg.call(zoomBehavior.transform, d3.zoomIdentity.translate(width*0.1, height*0.1).scale(0.85));
    }}, 600);
}} else {{
    zoomG.append("text").attr("x",20).attr("y",40).attr("fill","#666")
        .text("No graph edges yet — build_graph.py 실행 후 갱신");
}}
</script>
</body>
</html>"""


if __name__ == "__main__":
    path = generate_dashboard()
    print(f"Dashboard: {path}")
