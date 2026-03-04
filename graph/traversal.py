"""NetworkX graph traversal for relationship exploration."""

import random
from collections import deque

import networkx as nx

from config import GRAPH_MAX_HOPS, EXPLORATION_RATE


def build_graph(edges: list[dict]) -> nx.DiGraph:
    G = nx.DiGraph()
    for e in edges:
        G.add_edge(
            e["source_id"],
            e["target_id"],
            relation=e["relation"],
            strength=e.get("strength", 1.0),
            description=e.get("description", ""),
        )
    return G


def traverse(graph: nx.DiGraph, start_ids: list[int], depth: int = GRAPH_MAX_HOPS) -> set[int]:
    """BFS 양방향 탐색 + EXPLORATION_RATE로 약한 edge 탐험."""
    visited: set[int] = set()
    undirected = graph.to_undirected(as_view=True)

    for sid in start_ids:
        if sid not in graph:
            continue
        queue: deque[tuple[int, int]] = deque([(sid, 0)])
        visited.add(sid)
        while queue:
            node, d = queue.popleft()
            if d >= depth:
                continue
            for neighbor in undirected.neighbors(node):
                if neighbor in visited:
                    continue
                # strength 기반 필터링 + EXPLORATION_RATE
                # DiGraph에서 edge 데이터 조회 (양방향 중 존재하는 쪽)
                if graph.has_edge(node, neighbor):
                    strength = graph.edges[node, neighbor].get("strength", 0.5)
                elif graph.has_edge(neighbor, node):
                    strength = graph.edges[neighbor, node].get("strength", 0.5)
                else:
                    strength = 0.5
                # 강한 edge는 항상 탐색, 약한 edge는 EXPLORATION_RATE 확률로 탐험
                if strength >= 0.3 or random.random() < EXPLORATION_RATE:
                    visited.add(neighbor)
                    queue.append((neighbor, d + 1))
    return visited


def get_relation_path(graph: nx.DiGraph, source: int, target: int) -> list[str]:
    try:
        path = nx.shortest_path(graph.to_undirected(), source, target)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []
    relations = []
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        if graph.has_edge(a, b):
            rel = graph[a][b].get("relation", "?")
            relations.append(f"{a} --{rel}--> {b}")
        elif graph.has_edge(b, a):
            rel = graph[b][a].get("relation", "?")
            relations.append(f"{a} <--{rel}-- {b}")
        else:
            relations.append(f"{a} -- {b}")
    return relations
