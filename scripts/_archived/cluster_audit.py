import sqlite3
import collections

db_path = r'C:\dev\01_projects\06_mcp-memory\data\memory.db'

def get_connected_components():
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM nodes WHERE status='active'")
        nodes = [row['id'] for row in cursor.fetchall()]
        
        cursor.execute("SELECT source_id, target_id FROM edges WHERE status='active'")
        adj = collections.defaultdict(list)
        for row in cursor.fetchall():
            adj[row['source_id']].append(row['target_id'])
            adj[row['target_id']].append(row['source_id'])
            
        visited = set()
        components = []
        for node in nodes:
            if node not in visited:
                component = []
                stack = [node]
                while stack:
                    curr = stack.pop()
                    if curr not in visited:
                        visited.add(curr)
                        component.append(curr)
                        stack.extend(adj[curr])
                components.append(component)
        
        comp_sizes = [len(c) for c in components]
        return {
            'count': len(components),
            'sizes': sorted(comp_sizes, reverse=True)[:10],
            'total_nodes': sum(comp_sizes),
            'max_component_ratio': max(comp_sizes) / len(nodes) if nodes else 0
        }

if __name__ == "__main__":
    results = get_connected_components()
    import json
    print(json.dumps(results, indent=2))
