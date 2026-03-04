"""visualize() — pyvis HTML 그래프 생성."""

from pathlib import Path

from config import DATA_DIR
from storage import sqlite_store
from graph.traversal import build_graph, traverse

# 타입별 색상
TYPE_COLORS = {
    "Decision": "#4CAF50",
    "Failure": "#F44336",
    "Pattern": "#2196F3",
    "Identity": "#9C27B0",
    "Preference": "#FF9800",
    "Goal": "#00BCD4",
    "Insight": "#FFEB3B",
    "Question": "#FF5722",
    "Principle": "#3F51B5",
    "AntiPattern": "#E91E63",
    "Project": "#009688",
    "Tool": "#607D8B",
    "Conversation": "#795548",
    "Unclassified": "#9E9E9E",
}

DEFAULT_COLOR = "#78909C"


def visualize(center: str = "", depth: int = 2, max_nodes: int = 100) -> dict:
    """그래프 시각화 HTML 생성.

    Args:
        center: 중심 노드 검색어 (빈 문자열이면 전체)
        depth: 탐색 깊이
        max_nodes: 최대 노드 수
    """
    try:
        from pyvis.network import Network
    except ImportError:
        return {"error": "pyvis not installed. Run: pip install pyvis"}

    all_edges = sqlite_store.get_all_edges()
    graph = build_graph(all_edges)

    # 중심 노드 결정
    if center:
        from storage.hybrid import hybrid_search
        results = hybrid_search(center, top_k=3)
        seed_ids = [r["id"] for r in results]
        visible_ids = traverse(graph, seed_ids, depth=depth)
        visible_ids.update(seed_ids)
    else:
        # 전체 (최근 노드)
        recent = sqlite_store.get_recent_nodes(limit=max_nodes)
        visible_ids = {n["id"] for n in recent}

    if not visible_ids:
        return {"message": "No nodes to visualize.", "file": ""}

    # pyvis 그래프 생성
    net = Network(height="700px", width="100%", directed=True, bgcolor="#1a1a2e", font_color="white")
    net.barnes_hut(gravity=-5000, spring_length=150)

    # 노드 추가
    added_nodes = set()
    for nid in list(visible_ids)[:max_nodes]:
        node = sqlite_store.get_node(nid)
        if not node:
            continue
        color = TYPE_COLORS.get(node["type"], DEFAULT_COLOR)
        label = f"#{nid}\n{node['content'][:40]}"
        title = f"[{node['type']}] {node['content'][:200]}\ntags: {node['tags']}\nproject: {node['project']}"
        net.add_node(nid, label=label, title=title, color=color, size=20)
        added_nodes.add(nid)

    # 에지 추가
    for e in all_edges:
        if e["source_id"] in added_nodes and e["target_id"] in added_nodes:
            net.add_edge(
                e["source_id"],
                e["target_id"],
                title=e["relation"],
                label=e["relation"],
                color="#555555",
                width=max(1, e.get("strength", 1.0) * 3),
            )

    # HTML 파일 저장
    output_dir = DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "graph.html"
    net.save_graph(str(output_path))

    return {
        "file": str(output_path),
        "nodes": len(added_nodes),
        "edges": len([e for e in all_edges if e["source_id"] in added_nodes and e["target_id"] in added_nodes]),
        "message": f"Graph saved to {output_path} ({len(added_nodes)} nodes)",
    }
