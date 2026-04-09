import sqlite3
import json

db_path = r'C:\dev\01_projects\06_mcp-memory\data\memory.db'

def query_schema():
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        schemas = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table});")
            schemas[table] = cursor.fetchall()
    return schemas

if __name__ == "__main__":
    schemas = query_schema()
    print(json.dumps(schemas, indent=2))
