#!/usr/bin/env python3
import sqlite3, os, sys
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from config import DB_PATH

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT id, content, source FROM nodes WHERE type='Conversation' ORDER BY id").fetchall()

patterns = {}
for r in rows:
    src = (r['source'] or '').replace("\\", "/")
    content = r['content'][:70].replace("\n", " ")
    if "_history/plans" in src:
        key = "plans/_history"
    elif "STATE.md" in src or "KNOWLEDGE.md" in src:
        key = "Living Docs"
    elif "_history/evidence" in src:
        key = "evidence/_history"
    elif "_history/archive" in src:
        key = "archive/_history"
    elif "docs/plans" in src:
        key = "docs/plans"
    elif ".claude" in src or ".rulesync" in src or ".codex" in src or ".agents" in src:
        key = "config files"
    elif "HOME.md" in src:
        key = "HOME.md"
    elif "/logs/" in src:
        key = "logs/"
    elif "/docs/" in src:
        key = "docs/"
    else:
        key = "other"
    patterns.setdefault(key, []).append({"id": r["id"], "content": content})

for k, v in sorted(patterns.items(), key=lambda x: -len(x[1])):
    print(f"[{k}] {len(v)}개")
    for item in v[:3]:
        print(f"  #{item['id']}: {item['content']}")

conn.close()
