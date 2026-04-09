import sqlite3
import collections
import json

db_path = r'C:\dev\01_projects\06_mcp-memory\data\memory.db'

def analyze_recall():
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Type diversity in recall
        cursor.execute("""
            SELECT n.type, COUNT(*) as count
            FROM recall_log r
            JOIN nodes n ON r.node_id = n.id
            GROUP BY n.type
            ORDER BY count DESC
        """)
        type_dist = {row['type']: row['count'] for row in cursor.fetchall()}
        
        # Repeated queries
        cursor.execute("""
            SELECT query, COUNT(*) as count
            FROM recall_log
            GROUP BY query
            HAVING count > 1
            ORDER BY count DESC
            LIMIT 20
        """)
        repeated_queries = {row['query']: row['count'] for row in cursor.fetchall()}
        
        # Recent session continuity
        cursor.execute("""
            SELECT action_type, created_at FROM action_log 
            WHERE action_type IN ('session_start', 'get_context', 'save_session')
            ORDER BY created_at DESC
            LIMIT 50
        """)
        session_actions = [dict(row) for row in cursor.fetchall()]
        
        return {
            'type_distribution_in_recall': type_dist,
            'repeated_queries': repeated_queries,
            'recent_session_actions': session_actions
        }

if __name__ == "__main__":
    results = analyze_recall()
    print(json.dumps(results, indent=2))
