import sqlite3
import json
import collections
import statistics
from datetime import datetime, timedelta

db_path = r'C:\dev\01_projects\06_mcp-memory\data\memory.db'

def get_connection():
    return sqlite3.connect(db_path)

def audit_nodes():
    results = {}
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Type distribution
        cursor.execute("SELECT type, COUNT(*) as count FROM nodes WHERE status='active' GROUP BY type ORDER BY count DESC")
        results['type_distribution'] = {row['type']: row['count'] for row in cursor.fetchall()}

        # Quality score distribution
        cursor.execute("SELECT quality_score FROM nodes WHERE status='active' AND quality_score IS NOT NULL")
        scores = [row['quality_score'] for row in cursor.fetchall()]
        if scores:
            results['quality_score_stats'] = {
                'min': min(scores),
                'max': max(scores),
                'avg': sum(scores) / len(scores),
                'median': statistics.median(scores)
            }
        
        # Content length distribution
        cursor.execute("SELECT length(content) as len FROM nodes WHERE status='active'")
        lengths = [row['len'] for row in cursor.fetchall()]
        if lengths:
            results['content_length_stats'] = {
                'min': min(lengths),
                'max': max(lengths),
                'avg': sum(lengths) / len(lengths),
                'median': statistics.median(lengths)
            }

        # Random sample for manual check (we'll just output them for later review)
        cursor.execute("SELECT id, type, content FROM nodes WHERE status='active' ORDER BY RANDOM() LIMIT 50")
        results['random_sample'] = [dict(row) for row in cursor.fetchall()]

    return results

def audit_graph():
    results = {}
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM nodes WHERE status='active'")
        node_count = cursor.fetchone()[0]
        results['node_count'] = node_count

        cursor.execute("SELECT COUNT(*) FROM edges WHERE status='active'")
        edge_count = cursor.fetchone()[0]
        results['edge_count'] = edge_count

        results['edge_density'] = edge_count / node_count if node_count > 0 else 0

        # Orphan ratio
        cursor.execute("""
            SELECT COUNT(*) FROM nodes n
            WHERE n.status='active' 
            AND n.id NOT IN (SELECT source_id FROM edges WHERE status='active')
            AND n.id NOT IN (SELECT target_id FROM edges WHERE status='active')
        """)
        orphan_count = cursor.fetchone()[0]
        results['orphan_count'] = orphan_count
        results['orphan_ratio'] = orphan_count / node_count if node_count > 0 else 0

        # Hub nodes
        cursor.execute("""
            SELECT node_id, count(*) as degree FROM (
                SELECT source_id as node_id FROM edges WHERE status='active'
                UNION ALL
                SELECT target_id as node_id FROM edges WHERE status='active'
            ) GROUP BY node_id HAVING degree >= 10 ORDER BY degree DESC
        """)
        results['hub_nodes'] = [dict(row) for row in cursor.fetchall()]

        # Relation type diversity
        cursor.execute("SELECT relation, COUNT(*) as count FROM edges WHERE status='active' GROUP BY relation ORDER BY count DESC LIMIT 10")
        results['relation_distribution'] = {row['relation']: row['count'] for row in cursor.fetchall()}

    return results

def audit_promotion():
    results = {}
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # layer counts
        cursor.execute("SELECT layer, COUNT(*) as count FROM nodes WHERE status='active' GROUP BY layer")
        results['layer_counts'] = {row['layer']: row['count'] for row in cursor.fetchall()}

        # Promotion edges (source layer < target layer)
        cursor.execute("""
            SELECT n1.layer as s_layer, n2.layer as t_layer, COUNT(*) as count
            FROM edges e
            JOIN nodes n1 ON e.source_id = n1.id
            JOIN nodes n2 ON e.target_id = n2.id
            WHERE e.status='active' AND n1.layer IS NOT NULL AND n2.layer IS NOT NULL
            AND n1.layer < n2.layer
            GROUP BY n1.layer, n2.layer
        """)
        results['promotion_edges'] = [dict(row) for row in cursor.fetchall()]

    return results

def audit_temporal():
    results = {}
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Node creation trend
        now = datetime.now()
        seven_days_ago = (now - timedelta(days=7)).isoformat()
        thirty_days_ago = (now - timedelta(days=30)).isoformat()

        cursor.execute("SELECT COUNT(*) FROM nodes WHERE created_at >= ?", (seven_days_ago,))
        results['new_nodes_7d'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM nodes WHERE created_at >= ?", (thirty_days_ago,))
        results['new_nodes_30d'] = cursor.fetchone()[0]

        # Stale nodes (6 months+ ago, visit_count=0)
        six_months_ago = (now - timedelta(days=180)).isoformat()
        cursor.execute("SELECT COUNT(*) FROM nodes WHERE created_at < ? AND visit_count = 0", (six_months_ago,))
        results['stale_nodes'] = cursor.fetchone()[0]

    return results

def audit_interaction():
    results = {}
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Recall log
        cursor.execute("SELECT score FROM recall_log")
        scores = [row['score'] for row in cursor.fetchall()]
        if scores:
            results['recall_score_stats'] = {
                'avg': sum(scores) / len(scores),
                'median': statistics.median(scores)
            }

        # Action log
        cursor.execute("SELECT action_type, COUNT(*) as count FROM action_log GROUP BY action_type ORDER BY count DESC")
        results['action_distribution'] = {row['action_type']: row['count'] for row in cursor.fetchall()}

        # Source distribution
        cursor.execute("SELECT source, COUNT(*) as count FROM nodes GROUP BY source ORDER BY count DESC")
        results['source_distribution'] = {row['source']: row['count'] for row in cursor.fetchall()}

        # Correction nodes
        cursor.execute("SELECT COUNT(*) FROM nodes WHERE type='Correction'")
        results['correction_nodes_count'] = cursor.fetchone()[0]

        # Flag node calls
        cursor.execute("SELECT COUNT(*) FROM action_log WHERE action_type='flag_node'")
        results['flag_node_calls'] = cursor.fetchone()[0]

    return results

if __name__ == "__main__":
    audit_data = {
        'nodes': audit_nodes(),
        'graph': audit_graph(),
        'promotion': audit_promotion(),
        'temporal': audit_temporal(),
        'interaction': audit_interaction()
    }
    print(json.dumps(audit_data, indent=2))
