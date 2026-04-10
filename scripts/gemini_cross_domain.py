"""Gemini-based cross-domain edge enrichment."""
import sqlite3, json, sys, time
from google import genai

client = genai.Client(
    vertexai=True,
    project="project-d8e75491-ca74-415f-802",
    location="us-central1"
)

conn = sqlite3.connect("data/memory.db", timeout=30)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=30000")
c = conn.cursor()

# Knowledge-bearing nodes with 0 cross-domain edges
c.execute("""
SELECT n.id, n.content, n.project, n.tags
FROM nodes n
WHERE n.status='active'
AND n.type IN ('Principle','Pattern','Insight','Decision','Failure','Goal','Identity','Signal')
AND n.project != ''
AND n.id NOT IN (
    SELECT e.source_id FROM edges e
    JOIN nodes n2 ON e.target_id=n2.id
    WHERE e.status='active' AND n2.project != n.project AND n2.project != ''
    UNION
    SELECT e.target_id FROM edges e
    JOIN nodes n2 ON e.source_id=n2.id
    WHERE e.status='active' AND n2.project != n.project AND n2.project != ''
)
ORDER BY n.type IN ('Principle','Pattern','Insight') DESC, n.visit_count DESC
LIMIT 200
""")
orphan_obs = c.fetchall()
print(f"Nodes to enrich: {len(orphan_obs)}")

created_edges = 0
errors = 0

for i, (node_id, content, project, tags) in enumerate(orphan_obs):
    # Get candidates from other projects
    c.execute("""
    SELECT id, content, project, type FROM nodes
    WHERE status='active' AND project != ? AND project != ''
    AND type IN ('Principle','Pattern','Insight','Decision')
    AND visit_count > 0
    ORDER BY RANDOM() LIMIT 5
    """, (project,))
    candidates = c.fetchall()
    if not candidates:
        continue

    prompt = f"""다음 노드와 후보 노드들 사이의 의미적 관련성을 판단하라.

원본 (ID:{node_id}, {project}): {content[:200]}

후보:
"""
    for cid, cc, cp, ct in candidates:
        prompt += f"- ID:{cid} ({cp}/{ct}): {cc[:150]}\n"

    prompt += """
관련 있는 쌍만 JSON 배열로 반환. [{"target_id": N, "relation": "supports|contradicts|extends|analogous_to|inspired_by", "reason": "20자 이유"}]
관련 없으면 []. JSON만."""

    try:
        resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = resp.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        edges = json.loads(text)
        for edge in edges:
            tid = edge["target_id"]
            rel = edge["relation"]
            reason = edge.get("reason", "")

            c.execute("SELECT COUNT(*) FROM edges WHERE source_id=? AND target_id=? AND status='active'", (node_id, tid))
            if c.fetchone()[0] > 0:
                continue

            c.execute("""INSERT INTO edges (source_id, target_id, relation, description, strength,
                created_at, status, generation_method)
                VALUES (?, ?, ?, ?, 0.7, datetime('now'), 'active', 'gemini-enrichment')""",
                (node_id, tid, rel, reason))
            created_edges += 1

        if (i + 1) % 10 == 0:
            conn.commit()
            print(f"  [{i+1}/{len(orphan_obs)}] edges: {created_edges}")

    except Exception as e:
        errors += 1
        print(f"  Error node {node_id}: {str(e)[:80]}")
        time.sleep(1)

conn.commit()
print(f"\nDone: {created_edges} edges created, {errors} errors")

# Stats
c.execute("""SELECT COUNT(*) FROM edges e JOIN nodes n1 ON e.source_id=n1.id JOIN nodes n2 ON e.target_id=n2.id
WHERE e.status='active' AND n1.project != n2.project AND n1.project != '' AND n2.project != '' """)
cross = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM edges WHERE status='active'")
total = c.fetchone()[0]
print(f"Cross-domain: {cross}/{total} ({cross/total*100:.1f}%)")
conn.close()
