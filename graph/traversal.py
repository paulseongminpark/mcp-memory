"""NetworkX graph traversal for relationship exploration."""

import networkx as nx

from config import GRAPH_MAX_HOPS


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
    visited = set()
    for sid in start_ids:
        if sid not in graph:
            continue
        # BFS 양방향
        undirected = graph.to_undirected()
        for node in nx.single_source_shortest_path_length(undirected, sid, cutoff=depth):
            visited.add(node)
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
